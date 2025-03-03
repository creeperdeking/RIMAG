from typing import List

import openmc

from geometry import (
    AssemblySectionDesc,
    DrumLayer,
    MaterialChoice,
    create_hollow_cylinder,
)
from materials import materials_dict
from drums import CoreDesc


def calculate_assembly_thickness(assembly_section: AssemblySectionDesc) -> float:
    return (
        assembly_section.fuel_thickness
        + assembly_section.fuel_cladding_gap * 2
        + assembly_section.cladding_thickness * 2
        + assembly_section.cladding_drum_gap * 2
        + assembly_section.drum_thickness
    )


def get_assemblies_boundaries(
    assembly_section: AssemblySectionDesc, drums: List[DrumLayer], core_diameter: float
):
    distance_from_core = drums[0].distance_from_core
    assembly_thickness = calculate_assembly_thickness(assembly_section)
    drum_height = drums[0].height
    fist_assembly_radius = drums[0].radius + assembly_section.drum_thickness / 2
    last_assembly_radius = (
        drums[-1].radius - assembly_section.drum_thickness / 2 - assembly_thickness
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
) -> List[openmc.Cell]:
    core_shape = -openmc.ZCylinder(r=core_diameter / 2)
    current_radius = drum.radius
    drum_shape = (
        create_hollow_cylinder(
            drum.radius + assembly_section.drum_thickness / 2,
            drum.radius - assembly_section.drum_thickness / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.drum_thickness / 2
    cladding_drum_gap1 = (
        create_hollow_cylinder(
            current_radius + assembly_section.cladding_drum_gap / 2,
            current_radius - assembly_section.cladding_drum_gap / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_drum_gap / 2
    cladding_shape1 = (
        create_hollow_cylinder(
            current_radius + assembly_section.cladding_thickness / 2,
            current_radius - assembly_section.cladding_thickness / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_thickness / 2
    fuel_cladding_gap1 = (
        create_hollow_cylinder(
            current_radius + assembly_section.fuel_cladding_gap / 2,
            current_radius - assembly_section.fuel_cladding_gap / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_cladding_gap / 2
    fuel_shape = (
        create_hollow_cylinder(
            current_radius + assembly_section.fuel_thickness / 2,
            current_radius - assembly_section.fuel_thickness / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_thickness / 2
    fuel_cladding_gap2 = (
        create_hollow_cylinder(
            current_radius + assembly_section.fuel_cladding_gap / 2,
            current_radius - assembly_section.fuel_cladding_gap / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.fuel_cladding_gap / 2
    cladding_shape2 = (
        create_hollow_cylinder(
            current_radius + assembly_section.cladding_thickness / 2,
            current_radius - assembly_section.cladding_thickness / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )
    current_radius -= assembly_section.cladding_thickness / 2
    cladding_drum_gap2 = (
        create_hollow_cylinder(
            current_radius + assembly_section.cladding_drum_gap / 2,
            current_radius - assembly_section.cladding_drum_gap / 2,
            drum.height,
            distance_from_origin=drum.distance_from_core,
        )
        & core_shape
    )

    fuel = openmc.Cell(name="fuel_drum" + str(drum.number))
    fuel.fill = materials_dict[material_choice.fuel]
    fuel.region = fuel_shape

    gap = openmc.Cell(name="gap" + str(drum.number))
    gap.fill = materials_dict[material_choice.gap]
    gap.region = (
        fuel_cladding_gap1
        | fuel_cladding_gap2
        | cladding_drum_gap1
        | cladding_drum_gap2
    )

    cladding = openmc.Cell(name="cladding_drum" + str(drum.number))
    cladding.fill = materials_dict[material_choice.cladding]
    cladding.region = cladding_shape1 | cladding_shape2

    drum_shape = openmc.Cell(name="drum" + str(drum.number))
    drum_shape.fill = materials_dict[material_choice.drum]
    drum_shape.region = drum_shape

    return [fuel, gap, cladding, drum_shape]


def make_assemblies_cells(
    assembly_section: AssemblySectionDesc,
    core: CoreDesc,
    material_choice: MaterialChoice,
    drums: List[DrumLayer],
) -> List[openmc.Cell]:
    cells = []
    for drum in drums:
        cells.extend(
            create_assembly_cells(
                assembly_section, core.core_diameter, drum, material_choice
            )
        )
    return cells
