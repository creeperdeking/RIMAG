import math

import openmc
from pydantic import BaseModel

from common_lib.geometry_types import GeometrySettings
from common_lib.rotary_assembly import RotaryAssemblyDesc

SPACING_CONSTANT = 0.001


class OuterEmptyZoneParameters(BaseModel):
    radius: float
    x0: float


def get_outer_empty_zone_parameters(
    geometry_settings: GeometrySettings,
) -> OuterEmptyZoneParameters:
    return OuterEmptyZoneParameters(
        radius=geometry_settings.rotary_assembly_desc.rotary_assembly_radius
        + geometry_settings.outer_core_layers_inside_shaft.parts[0].thickness / 2,
        x0=geometry_settings.rotary_assembly_desc.assembly_core_distance
        - geometry_settings.outer_core_layers_inside_shaft.parts[0].thickness / 2,
    )


def get_z_scaling(angle: float):
    complementary_angle = 90 - angle
    return 1 / math.sin(complementary_angle * math.pi / 180)


def get_z_offset(angle: float, assembly_core_distance: float):
    complementary_angle = 90 - angle
    return assembly_core_distance / math.tan(complementary_angle * math.pi / 180)


def get_height_from_length(length: float, angle: float):
    complementary_angle = 90 - angle
    return length / math.tan(complementary_angle * math.pi / 180)


def get_geometry_base_height(angle: float, geometry_settings: GeometrySettings):
    max_frustum_diameter = (
        geometry_settings.outer_core_layers_inside_shaft.parts[0].thickness
        + geometry_settings.rotary_assembly_desc.rotary_assembly_radius
    )
    return (
        get_height_from_length(max_frustum_diameter, angle)
        + geometry_settings.core_desc.core_vertical_height
    )


def get_geometry_bounding_box_one_full_layer(
    geometry_settings: GeometrySettings,
):
    outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)
    angle = geometry_settings.rotary_assembly_desc.frustum_pitch
    base_height = get_geometry_base_height(
        angle,
        geometry_settings,
    )

    vertical_core_height_with_margin = get_vertical_core_height_with_margin(
        geometry_settings
    )

    lower_z = (
        -get_height_from_length(geometry_settings.core_desc.core_radius, angle)
        - get_height_from_length(
            geometry_settings.outer_core_layers_inside_shaft.parts[0].thickness, angle
        )
        - vertical_core_height_with_margin / 2
    )

    lower_left_corner = (
        -outer_empty_zone_parameters.radius + outer_empty_zone_parameters.x0,
        -outer_empty_zone_parameters.radius,
        lower_z,
    )
    upper_right_corner = (
        outer_empty_zone_parameters.radius + outer_empty_zone_parameters.x0,
        outer_empty_zone_parameters.radius,
        lower_z + base_height,
    )

    return lower_left_corner, upper_right_corner


def get_vertical_core_height_with_margin(geometry_settings: GeometrySettings):
    core_height_with_margin = (
        geometry_settings.core_desc.core_height + SPACING_CONSTANT * 2
    )
    z_scaling = get_z_scaling(geometry_settings.rotary_assembly_desc.frustum_pitch)
    return core_height_with_margin * z_scaling


def get_geometry_bounding_box(
    geometry_settings: GeometrySettings,
):
    lower_left_corner, upper_right_corner = get_geometry_bounding_box_one_full_layer(
        geometry_settings,
    )

    vertical_core_height_with_margin = get_vertical_core_height_with_margin(
        geometry_settings
    )

    lower_left_corner = (
        lower_left_corner[0],
        lower_left_corner[1],
        -vertical_core_height_with_margin / 2,
    )
    upper_right_corner = (
        upper_right_corner[0],
        upper_right_corner[1],
        +vertical_core_height_with_margin / 2,
    )

    return lower_left_corner, upper_right_corner


def make_surface_plane(
    rotary_assembly_desc: RotaryAssemblyDesc,
    z0: float,
    boundary_type: str = "transmission",
):
    z_scaling = get_z_scaling(rotary_assembly_desc.frustum_pitch)
    z_offset = get_z_offset(
        rotary_assembly_desc.frustum_pitch, rotary_assembly_desc.assembly_core_distance
    )
    if rotary_assembly_desc.frustum_pitch == 0.0:
        return openmc.ZPlane(z0=z0, boundary_type=boundary_type)
    r2 = 1 / math.tan(rotary_assembly_desc.frustum_pitch * math.pi / 180) ** 2
    return openmc.model.ZConeOneSided(
        z0=z0 * z_scaling + z_offset,
        x0=rotary_assembly_desc.assembly_core_distance,
        r2=r2,
        boundary_type=boundary_type,
        up=False,
    )


def create_bounded_surface_plane(
    rotary_assembly_desc: RotaryAssemblyDesc,
    thickness: float,
    z0: float,
    boundary_type: str = "transmission",
):
    return -make_surface_plane(
        rotary_assembly_desc,
        z0=thickness / 2 + z0,
        boundary_type=boundary_type,
    ) & +make_surface_plane(
        rotary_assembly_desc,
        z0=-thickness / 2 + z0,
        boundary_type=boundary_type,
    )


def create_cylinder(
    rotary_assembly_desc: RotaryAssemblyDesc,
    radius: float,
    thickness: float,
    distance_from_origin: float = 0,
    z0: float = 0,
    boundary_type: str = "transmission",
):
    return -openmc.ZCylinder(
        r=radius, x0=distance_from_origin, y0=0, boundary_type=boundary_type
    ) & create_bounded_surface_plane(
        rotary_assembly_desc,
        thickness,
        z0,
        boundary_type,
    )


def create_hollow_cylinder(
    rotary_assembly_desc: RotaryAssemblyDesc,
    outer_radius: float,
    inner_radius,
    thickness: float,
    distance_from_origin: float = 0,
    height: float = 0,
):
    return (
        -openmc.ZCylinder(r=outer_radius, x0=distance_from_origin, y0=0)
        & +openmc.ZCylinder(r=inner_radius, x0=distance_from_origin, y0=0)
        & -make_surface_plane(
            rotary_assembly_desc,
            z0=thickness / 2 + height,
        )
        & +make_surface_plane(
            rotary_assembly_desc,
            z0=-thickness / 2 + height,
        )
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
