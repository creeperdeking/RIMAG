from pydantic import BaseModel
import openmc


class AssemblySectionDesc(BaseModel):
    fuel_thickness: float
    fuel_cladding_gap: float
    cladding_thickness: float
    cladding_drum_gap: float
    drum_thickness: float


class MaterialChoice(BaseModel):
    neutron_shield: str
    reflector: str
    fuel: str
    cladding: str
    drum: str


def create_cylinder(radius: float, height: float, boundary_type: str = "transmission"):
    return (
        -openmc.ZCylinder(r=radius, boundary_type=boundary_type)
        & -openmc.ZPlane(z0=height / 2, boundary_type=boundary_type)
        & +openmc.ZPlane(z0=-height / 2, boundary_type=boundary_type)
    )


def create_hollow_cylinder(
    outer_radius: float,
    inner_radius,
    height: float,
    distance_from_origin: float = 0,
):
    return (
        -openmc.ZCylinder(r=outer_radius, x0=distance_from_origin, y0=0)
        & +openmc.ZCylinder(r=inner_radius, x0=distance_from_origin, y0=0)
        & -openmc.ZPlane(z0=height / 2)
        & +openmc.ZPlane(z0=-height / 2)
    )
