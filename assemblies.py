from typing import List

import openmc

from geometry_utils import (
    AssemblySectionDesc,
    MaterialChoice,
    create_hollow_cylinder,
)
from materials import materials_dict
from drums import CoreDesc, DrumLayer, DrumDesc


def calculate_assembly_thickness(assembly_section: AssemblySectionDesc) -> float:
    return (
        assembly_section.fuel_thickness
        + assembly_section.fuel_cladding_gap * 2
        + assembly_section.cladding_thickness * 2
        + assembly_section.cladding_drum_gap * 2
        + assembly_section.drum_thickness
    )


def get_assemblies_boundaries(
    assembly_section: AssemblySectionDesc,
    drums: List[DrumLayer],
    core_desc: CoreDesc,
    drums_desc: DrumDesc,
):
    distance_from_core = drums_desc.drum_core_distance
    assembly_thickness = calculate_assembly_thickness(assembly_section)
    drum_height = drums_desc.height
    fist_assembly_radius = drums[0].radius
    last_assembly_radius = (
        drums[-1].radius - assembly_section.drum_thickness - assembly_thickness
    )

    assemblies_boundary = create_hollow_cylinder(
        fist_assembly_radius,
        last_assembly_radius,
        drum_height,
        distance_from_origin=distance_from_core,
    ) & -openmc.ZCylinder(
        r=(
            core_desc.core_diameter
            + core_desc.reflector_thickness
            + core_desc.neutron_shield_thickness
        )
        / 2
    )

    return assemblies_boundary


def create_assembly_cells(
    assembly_section: AssemblySectionDesc,
    core_desc: CoreDesc,
    drum: DrumLayer,
    material_choice: MaterialChoice,
    drum_desc: DrumDesc,
) -> List[openmc.Cell]:
    core_shape = -openmc.ZCylinder(r=core_desc.core_diameter / 2)
    current_radius = drum.radius
    drum_shape = (
        create_hollow_cylinder(
            drum.radius,
            drum.radius - assembly_section.drum_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.drum_thickness
    cladding_drum_gap1 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_drum_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_drum_gap
    cladding_shape1 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_thickness
    fuel_cladding_gap1 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.fuel_cladding_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_cladding_gap
    fuel_shape = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.fuel_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_thickness
    fuel_cladding_gap2 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.fuel_cladding_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_cladding_gap
    cladding_shape2 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_thickness
    cladding_drum_gap2 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_drum_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & core_shape
    )

    fuel = openmc.Cell(name="fuel_drum" + str(drum.number))
    fuel.fill = materials_dict[material_choice.fuel]
    fuel.region = fuel_shape

    gap = openmc.Cell(name="gap" + str(drum.number))
    gap.fill = materials_dict["Void"]
    gap.region = (
        fuel_cladding_gap1
        | fuel_cladding_gap2
        | cladding_drum_gap1
        | cladding_drum_gap2
    )

    cladding = openmc.Cell(name="cladding_drum" + str(drum.number))
    cladding.fill = materials_dict[material_choice.cladding]
    cladding.region = cladding_shape1 | cladding_shape2

    drum = openmc.Cell(name="drum" + str(drum.number))
    drum.fill = materials_dict[material_choice.drum]
    drum.region = drum_shape

    return [drum, gap, cladding, fuel]


def create_outer_core_assembly_cells(
    assembly_section: AssemblySectionDesc,
    core_desc: CoreDesc,
    drum: DrumLayer,
    material_choice: MaterialChoice,
    drum_desc: DrumDesc,
):
    core_shape = -openmc.ZCylinder(r=core_desc.core_diameter / 2)
    reflector_shape = create_hollow_cylinder(
        core_desc.core_diameter / 2 + core_desc.reflector_thickness,
        core_desc.core_diameter / 2,
        core_desc.core_height + core_desc.reflector_thickness,
    )
    neutron_shield_shape = create_hollow_cylinder(
        core_desc.core_diameter / 2
        + core_desc.reflector_thickness
        + core_desc.neutron_shield_thickness,
        core_desc.core_diameter / 2 + core_desc.reflector_thickness,
        core_desc.core_height
        + core_desc.reflector_thickness
        + core_desc.neutron_shield_thickness,
    )
    neutron_shield_outer_cylinder = -openmc.ZCylinder(
        r=core_desc.core_diameter / 2
        + core_desc.reflector_thickness
        + core_desc.neutron_shield_thickness,
        boundary_type="vacuum",
    )
    current_radius = drum.radius
    drum_shape = (
        create_hollow_cylinder(
            drum.radius,
            drum.radius - assembly_section.drum_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & neutron_shield_outer_cylinder
        & ~core_shape
    )
    current_radius -= assembly_section.drum_thickness
    cladding_drum_gap1 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_drum_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & neutron_shield_outer_cylinder
        & ~core_shape
    )
    current_radius -= assembly_section.cladding_drum_gap
    filled_in_thickness = (
        assembly_section.cladding_thickness * 2
        + assembly_section.fuel_cladding_gap * 2
        + assembly_section.fuel_thickness
    )
    filled_in_shape = (
        create_hollow_cylinder(
            current_radius,
            current_radius - filled_in_thickness,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & neutron_shield_outer_cylinder
        & ~core_shape
    )
    reflector_shape = filled_in_shape & reflector_shape
    neutron_shield_shape = filled_in_shape & neutron_shield_shape
    current_radius -= filled_in_thickness
    cladding_drum_gap2 = (
        create_hollow_cylinder(
            current_radius,
            current_radius - assembly_section.cladding_drum_gap,
            drum_desc.height,
            distance_from_origin=drum_desc.drum_core_distance,
        )
        & neutron_shield_outer_cylinder
        & ~core_shape
    )

    neutron_shield = openmc.Cell(name="neutron_shield" + str(drum.number))
    neutron_shield.fill = materials_dict[material_choice.neutron_shield]
    neutron_shield.region = neutron_shield_shape

    reflector = openmc.Cell(name="reflector" + str(drum.number))
    reflector.fill = materials_dict[material_choice.reflector]
    reflector.region = reflector_shape

    gap = openmc.Cell(name="gap_outer_core" + str(drum.number))
    gap.fill = materials_dict["Void"]
    gap.region = cladding_drum_gap1 | cladding_drum_gap2

    drum = openmc.Cell(name="drum" + str(drum.number))
    drum.fill = materials_dict[material_choice.drum]
    drum.region = drum_shape

    return [drum, gap, neutron_shield, reflector]


def create_last_drum_cell(
    core_desc: CoreDesc,
    assembly_section: AssemblySectionDesc,
    last_drum: DrumLayer,
    drum_desc: DrumDesc,
    material_choice: MaterialChoice,
) -> openmc.Cell:
    assembly_thickness = calculate_assembly_thickness(assembly_section)
    last_drum_shape = create_hollow_cylinder(
        last_drum.radius - assembly_thickness,
        last_drum.radius - assembly_thickness - assembly_section.drum_thickness,
        drum_desc.height,
        distance_from_origin=drum_desc.drum_core_distance,
    ) & -openmc.ZCylinder(r=core_desc.core_diameter / 2)

    last_drum_cell = openmc.Cell(name="last_drum")
    last_drum_cell.fill = materials_dict[material_choice.drum]
    last_drum_cell.region = last_drum_shape

    return last_drum_cell


def make_assemblies_cells(
    assembly_fn,
    assembly_section: AssemblySectionDesc,
    core_desc: CoreDesc,
    material_choice: MaterialChoice,
    drums: List[DrumLayer],
    drum_desc: DrumDesc,
) -> List[openmc.Cell]:
    cells = []
    for drum in drums:
        cells.extend(
            assembly_fn(
                assembly_section,
                core_desc,
                drum,
                material_choice,
                drum_desc,
            )
        )
    cells.append(
        create_last_drum_cell(
            core_desc,
            assembly_section,
            drums[-1],
            drum_desc,
            material_choice,
        )
    )
    return cells
