from typing import List

from common_lib.assemblies import CoreDesc
from common_lib.geometry_utils import circle_intersection_area
from common_lib.rotary_assembly import RotaryAssemblyDesc
from pydantic import BaseModel


class DiskAssemblyLayer(BaseModel):

    height: float
    """
    The height of the layer
    """

    number: int
    """
    The number of the layer
    """


def calculate_disk_radius(core_desc: CoreDesc, disc_desc: RotaryAssemblyDesc):
    return disc_desc.assembly_core_distance + core_desc.core_radius


def calculate_disk_surface_in_core(
    disk: DiskAssemblyLayer, core_desc: CoreDesc, disc_desc: RotaryAssemblyDesc
):
    disk_radius = calculate_disk_radius(core_desc, disc_desc)
    return circle_intersection_area(
        core_desc.core_radius,
        disk_radius,
        disc_desc.assembly_core_distance,
    )


def calculate_disks_surface_in_core(
    disks: List[DiskAssemblyLayer],
    disc_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
) -> float:
    disk_surface_in_core = 0
    for disk in disks:
        disk_surface_in_core += calculate_disk_surface_in_core(
            disk, core_desc, disc_desc
        )
    return disk_surface_in_core


class DisksGeometrySettings:
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def make_disks(
    geometry_settings: DisksGeometrySettings,
    distance_between_disks: float,
) -> List[DiskAssemblyLayer]:
    current_disk_height = (
        -geometry_settings.core_desc.core_radius
        + geometry_settings.rotary_assembly_desc.assembly_core_distance
    )
    disks = []

    while (
        current_disk_height + distance_between_disks
        < geometry_settings.core_desc.core_radius
        - geometry_settings.rotary_assembly_desc.assembly_core_distance
    ):
        disks.append(DiskAssemblyLayer(height=current_disk_height, number=len(disks)))
        current_disk_height += distance_between_disks

    return disks
