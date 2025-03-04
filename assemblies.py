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
    core_diameter: float,
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
    ) & -openmc.ZCylinder(r=core_diameter / 2)

    return assemblies_boundary


def create_assembly_cells(
    assembly_section: AssemblySectionDesc,
    core_diameter: float,
    drum: DrumLayer,
    material_choice: MaterialChoice,
    drum_desc: DrumDesc,
) -> List[openmc.Cell]:
    core_shape = -openmc.ZCylinder(r=core_diameter / 2)
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


def create_last_drum_cell(
    core_diameter: float,
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
    ) & -openmc.ZCylinder(r=core_diameter / 2)

    last_drum_cell = openmc.Cell(name="last_drum")
    last_drum_cell.fill = materials_dict[material_choice.drum]
    last_drum_cell.region = last_drum_shape

    return last_drum_cell


def make_assemblies_cells(
    assembly_section: AssemblySectionDesc,
    core: CoreDesc,
    material_choice: MaterialChoice,
    drums: List[DrumLayer],
    drum_desc: DrumDesc,
) -> List[openmc.Cell]:
    cells = []
    for drum in drums:
        cells.extend(
            create_assembly_cells(
                assembly_section,
                core.core_diameter,
                drum,
                material_choice,
                drum_desc,
            )
        )
    cells.append(
        create_last_drum_cell(
            core.core_diameter,
            assembly_section,
            drums[-1],
            drum_desc,
            material_choice,
        )
    )
    return cells
