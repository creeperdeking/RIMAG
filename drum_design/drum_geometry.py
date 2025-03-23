import math
from typing import Dict

import openmc

from assemblies import (
    get_assemblies_boundaries,
    make_assemblies_cells,
    make_outer_core_layers,
    define_emitter_boundary,
    define_photovoltaic_boundary,
    make_cells,
    make_emitter_only_assembly,
)
from common_lib.geometry import GeometrySettings
from common_lib.geometry_utils import (
    calculate_assembly_thickness,
    create_cylinder,
)
from drum_design.drums import make_drums


def define_drum_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )
    photovoltaic_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.photovoltaic_assembly
    )
    if assembly_thickness - photovoltaic_assembly_thickness > 1e-6:
        raise ValueError(
            f"Assembly thickness and photovoltaic assembly thickness must be the same. Assembly thickness: {assembly_thickness}, Photovoltaic assembly thickness: {photovoltaic_assembly_thickness}"
        )

    drums = make_drums(
        geometry_settings,
        assembly_thickness,
    )

    emitter_boundary = define_emitter_boundary(
        geometry_settings.assembly_section_core,
        drums,
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
    )

    outer_core_boundary = create_cylinder(
        geometry_settings.core_desc.outer_core_radius,
        geometry_settings.core_desc.outer_core_height,
    )
    core_boundary = create_cylinder(
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )
    photovoltaic_boundary = define_photovoltaic_boundary(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc.assembly_core_distance,
        geometry_settings.double_assembly,
    )

    assemblies_boundary = get_assemblies_boundaries(
        geometry_settings, drums, assembly_thickness
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
    )

    core_assembly_cells = make_cells(
        assembly_section=geometry_settings.assembly_section_core,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=core_boundary,
    )

    photovoltaic_assembly_cells = make_cells(
        assembly_section=geometry_settings.photovoltaic_assembly,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=photovoltaic_boundary,
    )

    emitter_only_assembly = make_emitter_only_assembly(
        assembly_section=geometry_settings.assembly_section_core,
        emitter_assembly=geometry_settings.emitter_assembly,
    )
    emitter_only_assembly_thickness = calculate_assembly_thickness(
        emitter_only_assembly
    )
    if abs(emitter_only_assembly_thickness - assembly_thickness) > 1e-6:
        raise ValueError(
            f"Emitter only assembly thickness must be the same as the assembly thickness. Assembly thickness: {assembly_thickness}, Emitter only assembly thickness: {emitter_only_assembly_thickness}"
        )

    print(emitter_only_assembly)

    emitter_assembly_cells = make_cells(
        assembly_section=emitter_only_assembly,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
    )

    outer_drum_zone = (
        (
            -openmc.ZCylinder(
                r=drums[0].radius
                + geometry_settings.rotary_assembly_desc.assembly_core_distance,
                boundary_type="vacuum",
            )
            & -openmc.ZPlane(
                z0=geometry_settings.core_desc.outer_core_height / 2 + 1,
                boundary_type="vacuum",
            )
            & +openmc.ZPlane(
                z0=-geometry_settings.core_desc.outer_core_height / 2 - 1,
                boundary_type="vacuum",
            )
        )
        & ~outer_core_boundary
        & ~photovoltaic_boundary
        & ~emitter_boundary
    )

    outer_drum_zone_cell = openmc.Cell(name="outer_drum_zone")
    outer_drum_zone_cell.region = outer_drum_zone
    outer_drum_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    universe = openmc.Universe(
        cells=[
            *core_assembly_cells,
            *outer_core_layers_cells,
            *photovoltaic_assembly_cells,
            *emitter_assembly_cells,
            core_fill_cell,
            outer_drum_zone_cell,
            photovoltaic_fill_cell,
        ]
    )

    return (
        openmc.Geometry(universe),
        universe,
        drums,
    )
