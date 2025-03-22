from pydantic import BaseModel


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
