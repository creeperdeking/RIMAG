from pydantic import BaseModel
import openmc
from typing import List, Optional, Literal


class Assembly(BaseModel):
    thickness: float
    material: Optional[str] = None
    is_fuel: bool = False
    is_emitter: Literal[False] = False


class EmitterPlaceholder(BaseModel):
    thickness: float
    is_emitter: Literal[True] = True


class AssemblySections(BaseModel):
    parts: List[Assembly | EmitterPlaceholder]


def create_cylinder(
    radius: float,
    height: float,
    distance_from_origin: float = 0,
    boundary_type: str = "transmission",
):
    return (
        -openmc.ZCylinder(
            r=radius, x0=distance_from_origin, y0=0, boundary_type=boundary_type
        )
        & -openmc.ZPlane(z0=height / 2, boundary_type=boundary_type)
        & +openmc.ZPlane(z0=-height / 2, boundary_type=boundary_type)
    )


def calculate_assembly_thickness(assembly_section: AssemblySections) -> float:
    return sum(part.thickness for part in assembly_section.parts)


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
