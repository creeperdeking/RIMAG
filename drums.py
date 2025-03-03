import math
from typing import List

from pydantic import BaseModel


class DrumLayer(BaseModel):
    distance_from_core: float
    radius: float


class CoreDesc(BaseModel):
    core_diameter: float
    core_height: float
    reflector_thickness: float


def calculate_drum_arc_length(drum: DrumLayer, core_radius: float):
    return (
        2
        * drum.radius
        * math.acos(
            (drum.distance_from_core**2 + drum.radius**2 - core_radius**2)
            / (2 * drum.distance_from_core * drum.radius)
        )
    )


def calculate_drum_surface_in_core(drum: DrumLayer, core: CoreDesc):
    return calculate_drum_arc_length(drum, core.core_radius) * core.core_height


def make_drum_layers(
    outer_drum: DrumLayer,
    core_radius: float,
    distance_between_drums: float,
    last_drum_core_margin: float,
) -> List[DrumLayer]:
    drum_radiuses = [outer_drum.distance_from_core]
    while (
        drum_radiuses[-1] - (outer_drum.radius - core_radius)
        > distance_between_drums + last_drum_core_margin
    ):
        drum_radiuses.append(drum_radiuses[-1] - distance_between_drums)
    return [
        DrumLayer(distance_from_core=distance_from_core, radius=distance_from_core)
        for distance_from_core in drum_radiuses
    ]


def calculate_drum_layers_surface_in_core(
    drums: List[DrumLayer], core: CoreDesc
) -> float:
    drum_surface_in_core = 0
    for drum in drums:
        drum_surface_in_core += calculate_drum_surface_in_core(drum, core)
    return drum_surface_in_core
