from drum_design.drums import (
    RotaryAssemblyLayer,
    calculate_drums_surface_in_core,
)
from common_lib.geometry_utils import AssemblySections
from common_lib.rotary_assembly import RotaryAssemblyDesc
from common_lib.core import CoreDesc
from typing import List


def calculate_drums_fuel_volume(
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    assembly_section: AssemblySections,
    drums: List[RotaryAssemblyLayer],
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
        fuel_drums.append(RotaryAssemblyLayer(radius=fuel_radius, number=drum.number))

    fuel_volume = (
        calculate_drums_surface_in_core(fuel_drums, drum_desc, core_desc)
        * fuel_thickness
    ) * (2 if half_assembly else 1)

    return fuel_volume
