import math
from typing import List

from common_lib.assemblies import CoreDesc
from common_lib.rotary_assembly import RotaryAssemblyDesc
from pydantic import BaseModel


class DrumAssemblyLayer(BaseModel):

    radius: float
    """
    The radius of the layer
    """

    number: int
    """
    The number of the layer
    """


def calculate_drum_arc_length(
    drum: DrumAssemblyLayer, drum_distance_from_core: float, core_radius: float
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
    drum: DrumAssemblyLayer, core_desc: CoreDesc, drum_desc: RotaryAssemblyDesc
):
    return (
        calculate_drum_arc_length(
            drum,
            drum_desc.assembly_core_distance,
            core_desc.core_radius,
        )
        * core_desc.core_height
    )


def calculate_drums_surface_in_core(
    drums: List[DrumAssemblyLayer],
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
) -> float:
    return sum(
        calculate_drum_surface_in_core(drum, core_desc, drum_desc) for drum in drums
    )


class DrumsGeometrySettings:
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def make_drums(
    geometry_settings: DrumsGeometrySettings,
    distance_between_drums: float,
) -> List[DrumAssemblyLayer]:
    core_boundary_drum_radius = (
        geometry_settings.rotary_assembly_desc.assembly_core_distance
        - geometry_settings.core_desc.core_radius
    )
    outer_drum_radius = (
        geometry_settings.rotary_assembly_desc.assembly_core_distance
        + geometry_settings.core_desc.core_radius
        - geometry_settings.rotary_assembly_desc.assembly_core_margin
    )
    if geometry_settings.double_assembly:
        outer_drum_radius = (
            geometry_settings.rotary_assembly_desc.assembly_core_distance
            - geometry_settings.rotary_assembly_desc.assembly_core_margin
        )
    drum_radiuses = [outer_drum_radius]

    assembly_core_distance = outer_drum_radius - core_boundary_drum_radius

    while (
        assembly_core_distance - distance_between_drums
    ) > geometry_settings.rotary_assembly_desc.assembly_core_margin:
        drum_radiuses.append(drum_radiuses[-1] - distance_between_drums)
        assembly_core_distance -= distance_between_drums

    return [
        DrumAssemblyLayer(
            radius=drum_radius,
            number=i,
        )
        for i, drum_radius in enumerate(drum_radiuses)
    ]
