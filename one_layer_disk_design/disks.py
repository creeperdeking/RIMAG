from typing import List

from common_lib.assemblies_types import CoreDesc
from common_lib.rotary_assembly import RotaryAssemblyDesc
from pydantic import BaseModel


class DiskAssemblyLayer(BaseModel):
    height: float
    number: int


class DisksGeometrySettings:
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def get_disks_radius(
    assembly_core_distance: float,
    core_radius: float,
):
    return assembly_core_distance + core_radius


def make_disks(
    assembly_thickness: float,
) -> List[DiskAssemblyLayer]:
    current_disk_height = -assembly_thickness / 2
    disks = []

    disks.append(
        DiskAssemblyLayer(
            height=current_disk_height,
            number=len(disks),
        )
    )

    return disks
