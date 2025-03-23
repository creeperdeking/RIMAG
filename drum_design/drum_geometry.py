import math
from typing import Dict

import openmc

from assemblies import (
    get_assemblies_boundaries,
    make_assemblies_cells,
    make_outer_core_layers,
    define_emitter_boundary,
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

    core_fill_region = core_boundary & ~get_assemblies_boundaries(
        geometry_settings, drums, assembly_thickness
    )

    ### Making Cells
    core_fill_cell = openmc.Cell(name="core_fill")
    core_fill_cell.region = core_fill_region
    core_fill_cell.fill = materials_dict[geometry_settings.material_choice.reflector]

    outer_core_layers_cells = make_outer_core_layers(
        geometry_settings.outer_core_layers,
        geometry_settings.core_desc,
        emitter_boundary,
        materials_dict,
    )

    core_assembly_cells = make_assemblies_cells(
        assembly_section=geometry_settings.assembly_section_core,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        double_assembly=geometry_settings.double_assembly,
        boundary_shape=core_boundary,
        materials_dict=materials_dict,
    )

    ### Define outer drum zone for solar cells tallies
    photovoltaic_slice = (
        -openmc.ZCylinder(
            r=geometry_settings.core_desc.core_radius,
            x0=geometry_settings.rotary_assembly_desc.assembly_core_distance * 2,
        )
        & -openmc.ZPlane(
            z0=geometry_settings.core_desc.core_height / 2,
        )
        & +openmc.ZPlane(
            z0=-geometry_settings.core_desc.core_height / 2,
        )
    ) & ~emitter_boundary

    photovoltaic_slice_volume = (
        math.pi
        * (geometry_settings.core_desc.core_radius**2)
        * geometry_settings.core_desc.core_height
    )

    photovoltaic_cell = openmc.Cell(name="photovoltaic")
    photovoltaic_cell.region = photovoltaic_slice
    photovoltaic_cell.fill = materials_dict[
        geometry_settings.material_choice.photovoltaic
    ]

    outer_drum_zone = (
        (
            -openmc.ZCylinder(
                r=drums[0].radius
                + geometry_settings.rotary_assembly_desc.assembly_core_distance,
                # x0=geometry_settings.drum_desc.drum_core_distance,
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
        & ~photovoltaic_slice
        & ~emitter_boundary
    )

    outer_drum_zone_cell = openmc.Cell(name="outer_drum_zone")
    outer_drum_zone_cell.region = outer_drum_zone
    outer_drum_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    universe = openmc.Universe(
        cells=[
            *core_assembly_cells,
            *outer_core_layers_cells,
            core_fill_cell,
            outer_drum_zone_cell,
            photovoltaic_cell,
        ]
    )

    return (
        openmc.Geometry(universe),
        universe,
        drums,
        photovoltaic_cell,
        photovoltaic_slice_volume,
    )
