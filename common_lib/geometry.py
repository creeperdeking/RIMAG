from typing import Dict

import openmc
import openmc.model
from pydantic import BaseModel


from common_lib.assemblies_types import (
    AssemblySections,
    CoreDesc,
)
from common_lib.assemblies import (
    define_photovoltaic_boundary_small,
    make_outer_core_layers,
    calculate_assembly_thickness,
)
from common_lib.geometry_utils import (
    create_cylinder,
    make_surface_plane,
    SPACING_CONSTANT,
    get_outer_empty_zone_parameters,
)

from common_lib.geometry_types import GeometrySettings


def get_base_geometry(
    geometry_settings: GeometrySettings,
):
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )
    core_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )
    photovoltaic_boundary = define_photovoltaic_boundary_small(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
    )
    return assembly_thickness, core_boundary, photovoltaic_boundary


def check_assembly_thickness_equal(
    assembly1: AssemblySections,
    assembly2: AssemblySections,
):
    assembly1_thickness = calculate_assembly_thickness(assembly1)
    assembly2_thickness = calculate_assembly_thickness(assembly2)
    if assembly1_thickness != assembly2_thickness:
        raise ValueError(
            f"Assembly thickness must be the same. Assembly1 thickness: {assembly1_thickness}, Assembly2 thickness: {assembly2_thickness}"
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
    check_assembly_thickness_equal(
        geometry_settings.assembly_section_core,
        geometry_settings.photovoltaic_assembly,
    )

    outer_core_layers_thickness = calculate_assembly_thickness(
        geometry_settings.outer_core_layers_inside_shaft
    )

    shaft_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        outer_core_layers_thickness / 2,
        assembly_thickness,
        distance_from_origin=geometry_settings.core_desc.core_radius
        + outer_core_layers_thickness / 2,
    )

    outer_core_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
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
        & -make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=geometry_settings.core_desc.outer_core_height / 2 + SPACING_CONSTANT,
            boundary_type="reflective",
        )
        & +make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-geometry_settings.core_desc.outer_core_height / 2 - SPACING_CONSTANT,
            boundary_type="reflective",
        )
    )

    ### Making Cells

    outer_core_layers_inside_shaft_cells = make_outer_core_layers(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_inside_shaft,
        geometry_settings.core_desc,
        emitter_boundary,
        materials_dict,
        outer_empty_zone_boundary & shaft_boundary,
    )
    outer_core_layers_between_disks_cells = make_outer_core_layers(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_between_disks,
        geometry_settings.core_desc,
        emitter_boundary,
        materials_dict,
        outer_empty_zone_boundary & ~shaft_boundary,
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
        *outer_core_layers_inside_shaft_cells,
        *outer_core_layers_between_disks_cells,
        *photovoltaic_assembly_cells.values(),
        *emitter_assembly_cells.values(),
        outer_empty_zone_cell,
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
