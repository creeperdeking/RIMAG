from typing import List

import openmc

from geometry_utils import (
    AssemblySections,
    create_hollow_cylinder,
)
from materials import materials_dict
from drums import CoreDesc, DrumLayer, DrumDesc


def calculate_assembly_thickness(assembly_section: AssemblySections) -> float:
    return sum(part.thickness for part in assembly_section.parts)


def get_assemblies_boundaries(
    assembly_thickness: float,
    last_assembly_thickness: float,
    drums: List[DrumLayer],
    core_desc: CoreDesc,
    drums_desc: DrumDesc,
    outer_core_radius: float,
):
    distance_from_core = drums_desc.drum_core_distance
    drum_height = core_desc.core_height
    fist_assembly_radius = drums[0].radius
    last_assembly_radius = drums[-1].radius - last_assembly_thickness

    assemblies_boundary = create_hollow_cylinder(
        fist_assembly_radius,
        last_assembly_radius,
        drum_height,
        distance_from_origin=distance_from_core,
    ) & -openmc.ZCylinder(
        r=outer_core_radius,
        boundary_type="vacuum",
    )

    return assemblies_boundary


def create_assembly_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
    drum: DrumLayer,
    drum_desc: DrumDesc,
    boundary_shape,
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
                distance_from_origin=drum_desc.drum_core_distance,
            )
            & boundary_shape
        )
        cell = openmc.Cell(name=f"{assembly_part.material} {str(i)} - {drum.number}")
        cell.fill = materials_dict[assembly_part.material]
        cell.region = shape
        assembly_cells.append(cell)
        current_radius -= assembly_part.thickness

    return assembly_cells


def make_reflector_assembly_zone_shape(core_desc: CoreDesc):
    core_shape = -openmc.ZCylinder(r=core_desc.core_radius)
    reflector_outer_cylinder = -openmc.ZCylinder(
        r=core_desc.reflector_radius,
    )
    return ~core_shape & reflector_outer_cylinder


def make_neutron_shield_assembly_zone_shape(core_desc: CoreDesc):
    reflector_shape = -openmc.ZCylinder(r=core_desc.reflector_radius)
    neutron_shield_outer_cylinder = -openmc.ZCylinder(
        r=core_desc.outer_core_radius,
        boundary_type="vacuum",
    )
    return ~reflector_shape & neutron_shield_outer_cylinder


def make_assemblies_cells(
    assembly_section: AssemblySections,
    last_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[DrumLayer],
    drum_desc: DrumDesc,
    boundary_shape,
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
            )
        )
    cells.extend(
        create_assembly_cells(
            last_section,
            core_desc,
            drums[-1],
            drum_desc,
            boundary_shape,
        )
    )
    return cells
