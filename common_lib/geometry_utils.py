import openmc


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
