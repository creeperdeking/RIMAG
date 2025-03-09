import math
from typing import List
import scipy.constants as cst

from pydantic import BaseModel


class DrumDesc(BaseModel):
    drum_core_distance: float
    drum_core_margin_outer: float
    drum_core_margin_inner: float


class DrumLayer(BaseModel):

    radius: float
    """
    The radius of the drum
    """

    number: int
    """
    The number of the drum
    """


class CoreDesc(BaseModel):
    core_radius: float
    core_height: float
    reflector_thickness: float
    neutron_shield_thickness: float
    outer_core_radius: float
    outer_core_height: float
    reflector_radius: float
    reflector_height: float


def compute_core_desc(
    core_radius: float,
    core_height: float,
    reflector_thickness: float,
    neutron_shield_thickness: float,
):
    return CoreDesc(
        core_radius=core_radius,
        core_height=core_height,
        reflector_thickness=reflector_thickness,
        neutron_shield_thickness=neutron_shield_thickness,
        outer_core_radius=core_radius + reflector_thickness + neutron_shield_thickness,
        outer_core_height=core_height
        + reflector_thickness * 2
        + neutron_shield_thickness * 2,
        reflector_radius=core_radius + reflector_thickness,
        reflector_height=core_height + reflector_thickness * 2,
    )


def calculate_drum_arc_length(
    drum: DrumLayer, drum_distance_from_core: float, core_radius: float
):
    return (
        2
        * drum.radius
        * math.acos(
            (drum_distance_from_core**2 + drum.radius**2 - core_radius**2)
            / (2 * drum_distance_from_core * drum.radius)
        )
    )


def calculate_drum_surface_in_core(
    drum: DrumLayer, core_desc: CoreDesc, drum_desc: DrumDesc
):
    return (
        calculate_drum_arc_length(
            drum,
            drum_desc.drum_core_distance,
            core_desc.core_radius,
        )
        * core_desc.core_height
    )


def calculate_drums_surface_in_core(
    drums: List[DrumLayer],
    drum_desc: DrumDesc,
    core_desc: CoreDesc,
) -> float:
    drum_surface_in_core = 0
    for drum in drums:
        drum_surface_in_core += calculate_drum_surface_in_core(
            drum, core_desc, drum_desc
        )
    return drum_surface_in_core


def make_drums(
    drum_desc: DrumDesc,
    core_radius: float,
    distance_between_drums: float,
    half_drum: bool = False,
) -> List[DrumLayer]:
    outer_drum_radius = (
        drum_desc.drum_core_distance + core_radius - drum_desc.drum_core_margin_outer
    )
    if half_drum:
        outer_drum_radius = (
            drum_desc.drum_core_distance - drum_desc.drum_core_margin_outer
        )
    drum_radiuses = [outer_drum_radius]

    while (
        core_radius
        + drum_radiuses[-1]
        - drum_desc.drum_core_distance
        - distance_between_drums
    ) >= drum_desc.drum_core_margin_inner:
        drum_radiuses.append(drum_radiuses[-1] - distance_between_drums)
    return [
        DrumLayer(
            radius=drum_radius,
            number=i,
        )
        for i, drum_radius in enumerate(drum_radiuses)
    ]


def radiative_heat_flux_between_plates(
    T1: float, T2: float, epsilon1: float, epsilon2: float
):
    return cst.Stefan_Boltzmann * (T1**4 - T2**4) / (1 / epsilon1 + 1 / epsilon2 - 1)
