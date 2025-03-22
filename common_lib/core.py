from pydantic import BaseModel
from common_lib.geometry_utils import AssemblySections, calculate_assembly_thickness


class CoreDesc(BaseModel):
    core_radius: float
    core_height: float
    outer_core_radius: float
    outer_core_height: float


def compute_core_desc(
    core_radius: float,
    core_height: float,
    outer_core_assembly: AssemblySections,
):
    outer_core_thickness = calculate_assembly_thickness(outer_core_assembly)
    return CoreDesc(
        core_radius=core_radius,
        core_height=core_height,
        outer_core_radius=core_radius + outer_core_thickness,
        outer_core_height=core_height + outer_core_thickness * 2,
    )
