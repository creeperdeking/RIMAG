from typing import Dict, List

import openmc
from pydantic import BaseModel

from common_lib.geometry_utils import SPACING_CONSTANT

from common_lib.assemblies import (
    define_photovoltaic_boundary,
    make_outer_core_layers,
    calculate_assembly_thickness,
    AssemblySections,
    CoreDesc,
)
from common_lib.geometry_utils import (
    create_cylinder,
)
from common_lib.materials import MaterialChoice
from common_lib.rotary_assembly import RotaryAssemblyDesc


class GeometrySettings(BaseModel):
    core_desc: CoreDesc
    rotary_assembly_desc: RotaryAssemblyDesc
    material_choice: MaterialChoice
    assembly_section_core: AssemblySections
    outer_core_layers: AssemblySections
    double_assembly: bool = False
    emitter_assembly: AssemblySections
    photovoltaic_assembly: AssemblySections


def get_base_geometry(
    geometry_settings: GeometrySettings,
):
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )
    core_boundary = create_cylinder(
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )
    photovoltaic_boundary = define_photovoltaic_boundary(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc.assembly_core_distance,
        geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
    )
    return assembly_thickness, core_boundary, photovoltaic_boundary


class OuterEmptyZoneParameters(BaseModel):
    radius: float
    x0: float


def get_outer_empty_zone_parameters(
    geometry_settings: GeometrySettings,
) -> OuterEmptyZoneParameters:
    return OuterEmptyZoneParameters(
        radius=geometry_settings.rotary_assembly_desc.rotary_assembly_radius
        + geometry_settings.outer_core_layers.parts[0].thickness / 2,
        x0=geometry_settings.rotary_assembly_desc.assembly_core_distance
        + geometry_settings.outer_core_layers.parts[0].thickness / 2,
    )


def define_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_assembly_cells: Dict[str, openmc.Cell],
    core_assembly_cells: Dict[str, openmc.Cell],
    emitter_assembly_cells: Dict[str, openmc.Cell],
    emitter_boundary: openmc.Region,
    assemblies_boundary: openmc.Region,
    core_boundary: openmc.Region,
    photovoltaic_boundary: openmc.Region,
):
    assembly_thickness, core_boundary, photovoltaic_boundary = get_base_geometry(
        geometry_settings
    )
    photovoltaic_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.photovoltaic_assembly
    )
    if assembly_thickness - photovoltaic_assembly_thickness > 1e-6:
        raise ValueError(
            f"Assembly thickness and photovoltaic assembly thickness must be the same. Assembly thickness: {assembly_thickness}, Photovoltaic assembly thickness: {photovoltaic_assembly_thickness}"
        )

    outer_core_boundary = create_cylinder(
        geometry_settings.core_desc.outer_core_radius,
        geometry_settings.core_desc.outer_core_height,
    )
    outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)
    outer_empty_zone_boundary = (
        -openmc.ZCylinder(
            r=outer_empty_zone_parameters.radius,
            x0=outer_empty_zone_parameters.x0,
            boundary_type="vacuum",
        )
        & -openmc.ZPlane(
            z0=geometry_settings.core_desc.outer_core_height / 2 + SPACING_CONSTANT,
            boundary_type="periodic",
        )
        & +openmc.ZPlane(
            z0=-geometry_settings.core_desc.outer_core_height / 2 - SPACING_CONSTANT,
            boundary_type="periodic",
        )
    )

    core_fill_region = core_boundary & ~assemblies_boundary
    photovoltaic_fill_region = photovoltaic_boundary & ~assemblies_boundary

    ### Making Cells
    core_fill_cell = openmc.Cell(name="core_fill")
    core_fill_cell.region = core_fill_region
    core_fill_cell.fill = materials_dict[geometry_settings.material_choice.reflector]

    photovoltaic_fill_cell = openmc.Cell(name="photovoltaic_fill")
    photovoltaic_fill_cell.region = photovoltaic_fill_region
    photovoltaic_fill_cell.fill = materials_dict[geometry_settings.material_choice.void]

    outer_core_layers_cells = make_outer_core_layers(
        geometry_settings.outer_core_layers,
        geometry_settings.core_desc,
        emitter_boundary,
        materials_dict,
        outer_empty_zone_boundary,
    )

    outer_empty_zone = (
        outer_empty_zone_boundary
        & ~outer_core_boundary
        & ~photovoltaic_boundary
        & ~emitter_boundary
    )

    outer_empty_zone_cell = openmc.Cell(name="outer_drum_zone")
    outer_empty_zone_cell.region = outer_empty_zone
    outer_empty_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    cells = [
        *core_assembly_cells.values(),
        *outer_core_layers_cells,
        *photovoltaic_assembly_cells.values(),
        *emitter_assembly_cells.values(),
        core_fill_cell,
        outer_empty_zone_cell,
        photovoltaic_fill_cell,
    ]

    rotated_cells = []
    for cell in cells:
        region = cell.region
        region = region.rotate((0, 0, 0))
        cell.region = region
        rotated_cells.append(cell)

    universe = openmc.Universe(cells=rotated_cells)

    return (
        openmc.Geometry(universe, merge_surfaces=True, surface_precision=2),
        universe,
        {
            **core_assembly_cells,
            **photovoltaic_assembly_cells,
            **emitter_assembly_cells,
        },
    )
