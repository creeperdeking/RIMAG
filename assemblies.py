from typing import List, Dict, Optional
import copy
import openmc

from common_lib.geometry import GeometrySettings

from common_lib.geometry_utils import (
    AssemblySections,
    create_hollow_cylinder,
    create_cylinder,
    calculate_assembly_thickness,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc, RotaryAssemblyLayer
from common_lib.core import CoreDesc


def get_assemblies_boundaries(
    geometry_settings: GeometrySettings,
    drums: List[RotaryAssemblyLayer],
    mirrored_rotary_assembly_desc: Optional[RotaryAssemblyDesc] = None,
) -> openmc.Cell:
    last_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_last
    )
    fist_assembly_radius = drums[0].radius
    last_assembly_radius = drums[-1].radius - last_assembly_thickness

    assemblies_boundary = create_hollow_cylinder(
        fist_assembly_radius,
        last_assembly_radius,
        geometry_settings.core_desc.core_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    ) & -openmc.ZCylinder(
        r=geometry_settings.core_desc.outer_core_radius,
        boundary_type="vacuum",
    )

    if mirrored_rotary_assembly_desc is not None:
        assemblies_boundary = assemblies_boundary | create_hollow_cylinder(
            fist_assembly_radius,
            last_assembly_radius,
            geometry_settings.core_desc.core_height,
            distance_from_origin=mirrored_rotary_assembly_desc.assembly_core_distance,
        ) & -openmc.ZCylinder(
            r=geometry_settings.core_desc.outer_core_radius,
            boundary_type="vacuum",
        )
    return assemblies_boundary


def create_assembly_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
    drum: RotaryAssemblyLayer,
    drum_desc: RotaryAssemblyDesc,
    boundary_shape,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:
    current_radius = drum.radius
    drum_height = core_desc.core_height

    assembly_cells = []
    for i, assembly_part in enumerate(assembly_section.parts):
        shape = (
            create_hollow_cylinder(
                current_radius,
                current_radius - assembly_part.thickness,
                drum_height,
                distance_from_origin=drum_desc.assembly_core_distance,
            )
            & boundary_shape
        )
        cell = openmc.Cell(name=f"{assembly_part.material} {str(i)} - {drum.number}")
        cell.fill = materials_dict[assembly_part.material]
        cell.region = shape
        assembly_cells.append(cell)
        current_radius -= assembly_part.thickness

    return assembly_cells


def make_neutron_shield_assembly_zone_shape(core_desc: CoreDesc):
    reflector_shape = -openmc.ZCylinder(r=core_desc.reflector_radius)
    neutron_shield_outer_cylinder = -openmc.ZCylinder(
        r=core_desc.outer_core_radius,
        boundary_type="vacuum",
    )
    return ~reflector_shape & neutron_shield_outer_cylinder


def make_assemblies_cells_base(
    assembly_section: AssemblySections,
    last_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    drum_desc: RotaryAssemblyDesc,
    boundary_shape,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:
    cells = []
    for drum in drums[:-1]:
        cells.extend(
            create_assembly_cells(
                assembly_section,
                core_desc,
                drum,
                drum_desc,
                boundary_shape,
                materials_dict,
            )
        )
    cells.extend(
        create_assembly_cells(
            last_section,
            core_desc,
            drums[-1],
            drum_desc,
            boundary_shape,
            materials_dict,
        )
    )
    return cells


def make_core_assemblies_cells(
    assembly_section: AssemblySections,
    last_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    boundary_shape,
    materials_dict: Dict[str, openmc.Material],
    other_rotary_assembly_desc: Optional[RotaryAssemblyDesc] = None,
) -> List[openmc.Cell]:
    cells = [
        *make_assemblies_cells_base(
            assembly_section,
            last_section,
            core_desc,
            drums,
            rotary_assembly_desc,
            boundary_shape,
            materials_dict,
        )
    ]
    if other_rotary_assembly_desc is not None:
        cells.extend(
            *make_assemblies_cells_base(
                assembly_section,
                last_section,
                core_desc,
                drums,
                other_rotary_assembly_desc,
                boundary_shape,
                materials_dict,
            )
        )
    return cells


def make_assemblies_outer_core(
    geometry_settings: GeometrySettings,
    drums: List[RotaryAssemblyLayer],
    materials_dict: Dict[str, openmc.Material],
    mirrored_rotary_assembly_desc: Optional[RotaryAssemblyDesc] = None,
) -> List[openmc.Cell]:
    cells = []
    current_layer_radius = geometry_settings.core_desc.core_radius
    previous_layer_radius = current_layer_radius
    for layer in geometry_settings.outer_core_layers.parts:
        current_layer_radius = current_layer_radius + layer.thickness
        boundary_shape = create_hollow_cylinder(
            current_layer_radius, previous_layer_radius, current_layer_radius * 2
        )
        temp_assembly_section = copy.deepcopy(
            geometry_settings.assembly_section_outer_core
        )
        for j, assembly_part in enumerate(temp_assembly_section.parts):
            if assembly_part.material is None:
                temp_assembly_section.parts[j].material = layer.material
        cells.extend(
            make_core_assemblies_cells(
                temp_assembly_section,
                geometry_settings.assembly_section_last,
                geometry_settings.core_desc,
                drums,
                geometry_settings.rotary_assembly_desc,
                boundary_shape,
                materials_dict,
                mirrored_rotary_assembly_desc,
            )
        )
        previous_layer_radius = current_layer_radius
    return cells


def make_outer_core_layers(
    outer_core_layers: AssemblySections,
    core_desc: CoreDesc,
    drum_zone: openmc.Cell,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:
    cells = []
    current_layer_radius = core_desc.core_radius
    previous_layer_radius = current_layer_radius
    for i, layer in enumerate(outer_core_layers.parts):
        current_layer_radius = current_layer_radius + layer.thickness
        core_cylinder = create_cylinder(
            previous_layer_radius, previous_layer_radius * 2
        )
        cylinder = (
            create_cylinder(current_layer_radius, current_layer_radius * 2)
            & ~core_cylinder
        )
        cell = openmc.Cell(name=f"outer_core_layer_{layer.material}_{i}")
        cell.region = cylinder & ~drum_zone
        cell.fill = materials_dict[layer.material]
        cells.append(cell)
        previous_layer_radius = current_layer_radius
    return cells
