import math
from typing import List
import scipy.constants as cst

from pydantic import BaseModel


class DrumDesc(BaseModel):
    drum_core_distance: float
    drum_core_margin: float
    height: float


class DrumLayer(BaseModel):

    distance_from_core: float
    """
    The distance between the center of the drum and the center of the core
    """

    radius: float
    """
    The radius of the drum
    """

    height: float
    """
    The height of the drum
    """

    number: int
    """
    The number of the drum
    """


class CoreDesc(BaseModel):
    core_diameter: float
    core_height: float
    reflector_thickness: float
    neutron_shield_thickness: float
    gamma_shield_thickness: float


def calculate_drum_arc_length(drum: DrumLayer, core_radius: float):
    return (
        2
        * drum.radius
        * math.acos(
            (drum.distance_from_core**2 + drum.radius**2 - core_radius**2)
            / (2 * drum.distance_from_core * drum.radius)
        )
    )


def calculate_drum_surface_in_core(
    drum: DrumLayer, core_radius: float, core_height: float
):
    return calculate_drum_arc_length(drum, core_radius) * core_height


def calculate_drums_emissive_surface_in_core(
    drums: List[DrumLayer], core_radius: float, core_height: float
) -> float:
    drum_surface_in_core = 0
    for drum in drums:
        drum_surface_in_core += calculate_drum_surface_in_core(
            drum, core_radius, core_height
        )
    return drum_surface_in_core * 2


def make_drums(
    drum_desc: DrumDesc,
    core_diameter: float,
    distance_between_drums: float,
) -> List[DrumLayer]:
    core_radius = core_diameter / 2
    outer_drum_radius = (
        drum_desc.drum_core_distance + core_radius - drum_desc.drum_core_margin
    )
    drum_radiuses = [outer_drum_radius]

    while (
        core_radius + drum_radiuses[-1] - drum_desc.drum_core_distance
    ) >= drum_desc.drum_core_margin:
        drum_radiuses.append(drum_radiuses[-1] - distance_between_drums)
    return [
        DrumLayer(
            distance_from_core=drum_desc.drum_core_distance,
            radius=drum_radius,
            height=drum_desc.height,
            number=i,
        )
        for i, drum_radius in enumerate(drum_radiuses)
    ]


def radiative_heat_flux_between_plates(
    T1: float, T2: float, epsilon1: float, epsilon2: float
):
    return cst.Stefan_Boltzmann * (T1**4 - T2**4) / (1 / epsilon1 + 1 / epsilon2 - 1)


a = make_drums(
    drum_desc=DrumDesc(
        drum_core_distance=100,
        drum_core_margin=2,
        height=80,
    ),
    core_diameter=80,
    distance_between_drums=1,
)
print(len(a))
emissive_surface = calculate_drums_emissive_surface_in_core(a, 80, 80) / 10000
print(emissive_surface)

hot_temp = 2400 + 273
cold_temp = 1800 + 273

radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)
print(radiative_flux)

print(radiative_flux * emissive_surface / 1000000)
