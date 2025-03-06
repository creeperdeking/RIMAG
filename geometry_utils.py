from pydantic import BaseModel
import openmc
from typing import List


class Assembly(BaseModel):
    thickness: float
    material: str


class AssemblySections(BaseModel):
    parts: List[Assembly]


class MaterialChoice(BaseModel):
    moderator: str
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
