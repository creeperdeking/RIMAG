from typing import List, Dict, Optional
import copy
import openmc

from common_lib.geometry import GeometrySettings

from common_lib.geometry_utils import (
    Assembly,
    AssemblySections,
    create_hollow_cylinder,
    create_cylinder,
    calculate_assembly_thickness,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc, RotaryAssemblyLayer
from common_lib.core import CoreDesc


class BoundariesGeometrySettings:
    emitter_assembly: AssemblySections
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def get_assemblies_boundaries(
    geometry_settings: BoundariesGeometrySettings,
    drums: List[RotaryAssemblyLayer],
    assembly_thickness: float,
) -> openmc.Cell:

    assemblies_boundary = create_hollow_cylinder(
        drums[0].radius,
        drums[-1].radius - assembly_thickness,
        geometry_settings.core_desc.core_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    ) & -openmc.ZCylinder(
        r=geometry_settings.core_desc.outer_core_radius,
        boundary_type="vacuum",
    )

    if geometry_settings.double_assembly:
        assemblies_boundary = assemblies_boundary | create_hollow_cylinder(
            drums[0].radius,
            drums[-1].radius - assembly_thickness,
            geometry_settings.core_desc.core_height,
            distance_from_origin=-geometry_settings.rotary_assembly_desc.assembly_core_distance,
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
        current_radius -= assembly_part.thickness
        if assembly_part.is_emitter:
            continue
        cell = openmc.Cell(name=f"{assembly_part.material} {str(i)} - {drum.number}")
        cell.fill = materials_dict[assembly_part.material]
        cell.region = shape
        assembly_cells.append(cell)

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
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    drum_desc: RotaryAssemblyDesc,
    boundary_shape,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:
    cells = []
    for drum in drums:
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
    return cells


def make_assemblies_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    double_assembly: bool,
    boundary_shape,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:
    cells = [
        *make_assemblies_cells_base(
            assembly_section,
            core_desc,
            drums,
            rotary_assembly_desc,
            boundary_shape,
            materials_dict,
        )
    ]
    if double_assembly:
        other_rotary_assembly_desc = rotary_assembly_desc
        other_rotary_assembly_desc.assembly_core_distance = (
            -other_rotary_assembly_desc.assembly_core_distance
        )
        cells.extend(
            *make_assemblies_cells_base(
                assembly_section,
                core_desc,
                drums,
                other_rotary_assembly_desc,
                boundary_shape,
                materials_dict,
            )
        )
    return cells


def define_emitter_boundary(
    assembly_section: AssemblySections,
    drums: List[RotaryAssemblyLayer],
    core_desc: CoreDesc,
    drum_desc: RotaryAssemblyDesc,
) -> openmc.Intersection:
    outer_core_assembly_section = create_outer_core_assembly_section(assembly_section)
    boundary_shape = None
    for drum in drums:
        curent_radius = drum.radius
        for assembly_part in outer_core_assembly_section.parts:
            if assembly_part.is_emitter:
                additional_boundary_shape = create_hollow_cylinder(
                    curent_radius,
                    curent_radius - assembly_part.thickness,
                    core_desc.core_height,
                    distance_from_origin=drum_desc.assembly_core_distance,
                )
                boundary_shape = (
                    additional_boundary_shape
                    if boundary_shape is None
                    else boundary_shape | additional_boundary_shape
                )
            curent_radius -= assembly_part.thickness

    return boundary_shape


def make_outer_core_layers(
    outer_core_layers: AssemblySections,
    core_desc: CoreDesc,
    emitter_boundary: openmc.Cell,
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
        cell.region = cylinder & ~emitter_boundary
        cell.fill = materials_dict[layer.material]
        cells.append(cell)
        previous_layer_radius = current_layer_radius
    return cells


def create_outer_core_assembly_section(
    assembly_section_core: AssemblySections,
) -> AssemblySections:
    parts = []
    current_part_thickness = 0
    for part in assembly_section_core.parts:
        if part.is_emitter:
            if current_part_thickness > 0:
                parts.append(Assembly(material=None, thickness=current_part_thickness))
            parts.append(part)
            current_part_thickness = 0
        else:
            current_part_thickness += part.thickness
    if current_part_thickness > 0:
        parts.append(Assembly(material=None, thickness=current_part_thickness))

    return AssemblySections(parts=parts)
