import math

import openmc

SPACING_CONSTANT = 0.000001


def create_cylinder(
    radius: float,
    thickness: float,
    distance_from_origin: float = 0,
    height: float = 0,
    boundary_type: str = "transmission",
):
    return (
        -openmc.ZCylinder(
            r=radius, x0=distance_from_origin, y0=0, boundary_type=boundary_type
        )
        & -openmc.ZPlane(z0=thickness / 2 + height, boundary_type=boundary_type)
        & +openmc.ZPlane(z0=-thickness / 2 + height, boundary_type=boundary_type)
    )


def create_hollow_cylinder(
    outer_radius: float,
    inner_radius,
    thickness: float,
    distance_from_origin: float = 0,
    height: float = 0,
):
    return (
        -openmc.ZCylinder(r=outer_radius, x0=distance_from_origin, y0=0)
        & +openmc.ZCylinder(r=inner_radius, x0=distance_from_origin, y0=0)
        & -openmc.ZPlane(z0=thickness / 2 + height)
        & +openmc.ZPlane(z0=-thickness / 2 + height)
    )


def circle_intersection_area(r1, r2, d):
    """
    Calculates the area of intersection between two circles.

    Parameters:
        r1 (float): Radius of the first circle (centered at the origin).
        r2 (float): Radius of the second circle (centered at (d, 0)).
        d (float): Distance between the centers of the circles.

    Returns:
        float: The area of the overlapping region between the two circles.
    """
    # Input validation
    if r1 < 0 or r2 < 0:
        raise ValueError("Radius cannot be negative")
    if d < 0:
        raise ValueError("Distance cannot be negative")

    # Special case: if either radius is zero, there's no overlap
    if r1 == 0 or r2 == 0:
        return 0

    # Case 1: No intersection
    if d >= r1 + r2:
        return 0.0

    # Case 2: One circle is completely inside the other
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2

    # Case 3: Partial overlap
    # Compute the angles for the segments in each circle using the cosine law.
    angle1 = math.acos((d**2 + r1**2 - r2**2) / (2 * d * r1))
    angle2 = math.acos((d**2 + r2**2 - r1**2) / (2 * d * r2))

    # Compute the area components from each circle.
    area1 = r1**2 * angle1
    area2 = r2**2 * angle2

    # Compute the area of the triangle (using Heron-like expression)
    area_triangle = 0.5 * math.sqrt(
        (-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2)
    )

    # Total intersection area
    intersection_area = area1 + area2 - area_triangle
    return intersection_area
