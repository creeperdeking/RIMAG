import math
import copy
from typing import Dict, List, Optional

import openmc

from assemblies import (
    get_assemblies_boundaries,
    make_assemblies_cells,
)
from common_lib.core import CoreDesc
from common_lib.geometry import GeometrySettings
from common_lib.geometry_utils import (
    AssemblySections,
    calculate_assembly_thickness,
    create_cylinder,
    create_hollow_cylinder,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc, RotaryAssemblyLayer
from drum_design.drums import make_drums


def make_outer_core_layers(
    outer_core_layers: AssemblySections,
    core_desc: CoreDesc,
    drum_zone: openmc.Cell,
    materials_dict: Dict[str, openmc.Material],
    other_drum_zone: Optional[openmc.Cell] = None,
) -> List[openmc.Cell]:
    cells = []
    current_layer_radius = core_desc.core_radius
    previous_layer_radius = current_layer_radius
    for i, layer in enumerate(outer_core_layers.parts):
        current_layer_radius = current_layer_radius + layer.thickness
        inner_cylinder = create_cylinder(
            previous_layer_radius, previous_layer_radius * 2
        )
        cylinder = (
            create_cylinder(current_layer_radius, current_layer_radius * 2)
            & ~inner_cylinder
        )
        cell = openmc.Cell(name=f"outer_core_layer_{layer.material}_{i}")
        cell.region = cylinder & ~drum_zone
        if other_drum_zone is not None:
            cell.region = cell.region & ~other_drum_zone
        cell.fill = materials_dict[layer.material]
        cells.append(cell)
        previous_layer_radius = current_layer_radius
    return cells


def make_assemblies_outer_core(
    outer_core_layers: AssemblySections,
    assembly_section: AssemblySections,
    last_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    materials_dict: Dict[str, openmc.Material],
    mirrored_rotary_assembly_desc: Optional[RotaryAssemblyDesc] = None,
) -> List[openmc.Cell]:
    cells = []
    current_layer_radius = core_desc.core_radius
    previous_layer_radius = current_layer_radius
    for layer in outer_core_layers.parts:
        current_layer_radius = current_layer_radius + layer.thickness
        boundary_shape = create_hollow_cylinder(
            current_layer_radius, previous_layer_radius, current_layer_radius * 2
        )
        temp_assembly_section = copy.deepcopy(assembly_section)
        for j, assembly_part in enumerate(temp_assembly_section.parts):
            if assembly_part.material is None:
                temp_assembly_section.parts[j].material = layer.material
        cells.extend(
            make_assemblies_cells(
                temp_assembly_section,
                last_section,
                core_desc,
                drums,
                rotary_assembly_desc,
                boundary_shape,
                materials_dict,
                mirrored_rotary_assembly_desc,
            )
        )
        previous_layer_radius = current_layer_radius
    return cells


def define_drum_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    last_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_last
    )
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_inner
    )
    outer_core_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_outer_core
    )

    if outer_core_assembly_thickness != assembly_thickness:
        raise ValueError(
            "Outer core assembly thickness must be equal to the assembly thickness"
        )

    drums = make_drums(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.core_radius,
        assembly_thickness,
        geometry_settings.half_assembly,
    )
    mirrored_rotary_assembly_desc = None
    if geometry_settings.half_assembly:
        mirrored_rotary_assembly_desc = RotaryAssemblyDesc(
            assembly_core_distance=-geometry_settings.rotary_assembly_desc.assembly_core_distance,
            assembly_core_margin=geometry_settings.rotary_assembly_desc.assembly_core_margin,
        )

    assemblies_boundary = get_assemblies_boundaries(
        last_assembly_thickness,
        drums,
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.outer_core_radius,
    )
    assemblies_boundary_other_side = None
    if geometry_settings.half_assembly:
        assemblies_boundary_other_side = get_assemblies_boundaries(
            last_assembly_thickness,
            drums,
            geometry_settings.core_desc,
            mirrored_rotary_assembly_desc,
            geometry_settings.core_desc.outer_core_radius,
        )

    outer_core_boundary = create_cylinder(
        geometry_settings.core_desc.outer_core_radius,
        geometry_settings.core_desc.outer_core_height,
    )
    core_boundary = create_cylinder(
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )

    core_fill_region = core_boundary & ~assemblies_boundary

    ### Making Cells
    core_fill_cell = openmc.Cell(name="core_fill")
    core_fill_cell.region = core_fill_region
    core_fill_cell.fill = materials_dict[geometry_settings.material_choice.reflector]

    outer_core_layers_cells = make_outer_core_layers(
        geometry_settings.outer_core_layers,
        geometry_settings.core_desc,
        assemblies_boundary,
        materials_dict,
        assemblies_boundary_other_side,
    )

    core_shape = -openmc.ZCylinder(r=geometry_settings.core_desc.core_radius)
    assembly_cells = make_assemblies_cells(
        geometry_settings.assembly_section_inner,
        geometry_settings.assembly_section_last,
        geometry_settings.core_desc,
        drums,
        geometry_settings.rotary_assembly_desc,
        core_shape,
        materials_dict,
        mirrored_rotary_assembly_desc if geometry_settings.half_assembly else None,
    )

    assembly_outer_core_cells = make_assemblies_outer_core(
        geometry_settings.outer_core_layers,
        geometry_settings.assembly_section_outer_core,
        geometry_settings.assembly_section_last,
        geometry_settings.core_desc,
        drums,
        geometry_settings.rotary_assembly_desc,
        materials_dict,
        mirrored_rotary_assembly_desc if geometry_settings.half_assembly else None,
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
    )

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
    )

    outer_drum_zone_cell = openmc.Cell(name="outer_drum_zone")
    outer_drum_zone_cell.region = outer_drum_zone
    outer_drum_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    universe = openmc.Universe(
        cells=[
            *assembly_cells,
            *assembly_outer_core_cells,
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
