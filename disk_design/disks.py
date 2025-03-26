from typing import List

from common_lib.assemblies import CoreDesc
from common_lib.rotary_assembly import RotaryAssemblyDesc
from pydantic import BaseModel
from common_lib.geometry_utils import circle_intersection_area


class DiskAssemblyLayer(BaseModel):
    radius: float
    height: float
    number: int


def calculate_disk_surface_in_core(
    disk: DiskAssemblyLayer, core_desc: CoreDesc, disc_desc: RotaryAssemblyDesc
):
    return circle_intersection_area(
        core_desc.core_radius,
        disk.radius,
        disc_desc.assembly_core_distance,
    )


def calculate_disks_surface_in_core(
    disks: List[DiskAssemblyLayer],
    disc_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
):
    return sum(
        calculate_disk_surface_in_core(disk, core_desc, disc_desc) for disk in disks
    )


class DisksGeometrySettings:
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


# todo
def make_disks(
    geometry_settings: DisksGeometrySettings,
    distance_between_disks: float,
) -> List[DiskAssemblyLayer]:
    disks_radius = (
        geometry_settings.rotary_assembly_desc.assembly_core_distance
        + geometry_settings.core_desc.core_radius
    )
    current_disk_height = (
        -geometry_settings.core_desc.core_height / 2
        + geometry_settings.rotary_assembly_desc.assembly_core_margin
    )
    disks = []

    while (
        current_disk_height + distance_between_disks
        < geometry_settings.core_desc.core_height / 2
        - geometry_settings.rotary_assembly_desc.assembly_core_margin
    ):
        disks.append(
            DiskAssemblyLayer(
                radius=disks_radius,
                height=current_disk_height,
                number=len(disks),
            )
        )
        current_disk_height += distance_between_disks

    return disks
