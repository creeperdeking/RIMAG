from typing import Dict, List, Optional

import openmc
from common_lib.assemblies import (
    create_outer_core_assembly_section,
    AssemblySections,
    CoreDesc,
)
from common_lib.geometry_utils import (
    create_hollow_cylinder,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc
from drum_design.drums import calculate_drums_surface_in_core, DrumAssemblyLayer


def calculate_drums_fuel_volume(
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    assembly_section: AssemblySections,
    drums: List[DrumAssemblyLayer],
    half_assembly: bool = False,
) -> float:
    fuel_radius_offset = 0
    fuel_thickness = 0
    for assembly_part in assembly_section.parts:
        if not assembly_part.is_emitter and assembly_part.is_fuel:
            fuel_thickness = assembly_part.thickness
            break

        fuel_radius_offset += assembly_part.thickness

    fuel_drums = []

    for drum in drums:
        fuel_radius = drum.radius - fuel_radius_offset
        fuel_drums.append(DrumAssemblyLayer(radius=fuel_radius, number=drum.number))

    print(calculate_drums_surface_in_core(fuel_drums, drum_desc, core_desc))

    fuel_volume = (
        calculate_drums_surface_in_core(fuel_drums, drum_desc, core_desc)
        * fuel_thickness
    ) * (2 if half_assembly else 1)

    return fuel_volume


def make_drum_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[DrumAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    materials_dict: Dict[str, openmc.Material],
    boundary_shape: Optional[openmc.Intersection] = None,
) -> Dict[str, openmc.Cell]:
    shapes = {}
    for drum in drums:
        current_radius = drum.radius
        for assembly_part in assembly_section.parts:
            if not assembly_part.is_emitter and assembly_part.material is not None:
                shape = create_hollow_cylinder(
                    current_radius,
                    current_radius - assembly_part.thickness,
                    core_desc.core_height,
                    distance_from_origin=rotary_assembly_desc.assembly_core_distance,
                )
                if boundary_shape is not None:
                    shape = shape & boundary_shape
                if assembly_part.material in shapes:
                    shapes[assembly_part.material] = (
                        shapes[assembly_part.material] | shape
                    )
                else:
                    shapes[assembly_part.material] = shape
            current_radius -= assembly_part.thickness
    cells = {}
    for material, shape in shapes.items():
        cell = openmc.Cell(name=f"{material}")
        cell.region = shape
        cell.fill = materials_dict[material]
        cells[material] = cell
    return cells


def define_drum_emitter_boundary(
    assembly_section: AssemblySections,
    drums: List[DrumAssemblyLayer],
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
