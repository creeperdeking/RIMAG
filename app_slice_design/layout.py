"""Port of app_reactor_slice/src/geometry.ts layout math (radial zones)."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from pydantic import BaseModel


class ZoneLayout(BaseModel):
    a: float
    b: float
    w: float
    reflector: float
    absorber: float
    percent_fuel: float
    r_inner: float
    r_outer: float
    total_area: float
    gap_angle: float
    reflector_angle: float
    absorber_angle: float
    fuel_angle: float
    opposite_angle: float
    fuel_area: float
    opposite_area: float
    gap_area: float
    reflector_area: float
    absorber_area: float
    max_percent_fuel: float
    feasible: bool


class CenterCuts(BaseModel):
    moderator_y: float
    reflector_y: Optional[float]


def chord_angle(thickness: float, inner_diameter: float) -> float:
    if thickness <= 0 or inner_diameter <= 0:
        return 0.0
    return 2.0 * math.asin(min(1.0, thickness / inner_diameter))


def _inner_diameter(a: float, b: float, reflector: float, absorber: float, extra: float = 0.0) -> float:
    return a + reflector + absorber + b + extra


def _layer_angles(a: float, reflector: float, absorber: float, diameter: float) -> Tuple[float, float, float]:
    return (
        chord_angle(a, diameter),
        chord_angle(reflector, diameter),
        chord_angle(absorber, diameter),
    )


def percent_fuel_for_ratio(
    a: float,
    b: float,
    ratio: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
) -> float:
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    diameter = _inner_diameter(a, b, reflector, absorber)
    moderator, reflected, absorbed = _layer_angles(a, reflector, absorber, diameter)
    free = max(0.0, 2.0 * math.pi - 2.0 * (moderator + reflected + absorbed))
    fuel_angle = (ratio / (1.0 + ratio)) * free
    return (100.0 * fuel_angle) / (2.0 * math.pi)


def compute_layout(
    a: float,
    b: float,
    w: float,
    percent_fuel: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
) -> ZoneLayout:
    if a <= 0:
        raise ValueError("a must be positive")
    if b < 0 or reflector < 0 or absorber < 0 or w <= 0:
        raise ValueError("invalid layout dimensions")
    if not (0.0 <= percent_fuel <= 100.0):
        raise ValueError("percent_fuel must be between 0 and 100")

    diameter = _inner_diameter(a, b, reflector, absorber)
    r_inner = diameter / 2.0
    r_outer = r_inner + w
    ring = r_outer**2 - r_inner**2
    total_area = math.pi * ring

    gap_angle, reflector_angle, absorber_angle = _layer_angles(a, reflector, absorber, diameter)
    max_pct = 100.0 * (1.0 - (gap_angle + reflector_angle + absorber_angle) / math.pi)
    feasible = percent_fuel <= max_pct + 1e-12

    fuel_angle = (2.0 * math.pi * percent_fuel) / 100.0
    opposite_angle = max(
        0.0,
        2.0 * math.pi - fuel_angle - 2.0 * (gap_angle + reflector_angle + absorber_angle),
    )

    return ZoneLayout(
        a=a,
        b=b,
        w=w,
        reflector=reflector,
        absorber=absorber,
        percent_fuel=percent_fuel,
        r_inner=r_inner,
        r_outer=r_outer,
        total_area=total_area,
        gap_angle=gap_angle,
        reflector_angle=reflector_angle,
        absorber_angle=absorber_angle,
        fuel_angle=fuel_angle,
        opposite_angle=opposite_angle,
        fuel_area=(fuel_angle / 2.0) * ring,
        opposite_area=(opposite_angle / 2.0) * ring,
        gap_area=gap_angle * ring,
        reflector_area=reflector_angle * ring,
        absorber_area=absorber_angle * ring,
        max_percent_fuel=max_pct,
        feasible=feasible,
    )


def compute_layout_for_ratio(
    a: float,
    b: float,
    w: float,
    ratio: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
) -> ZoneLayout:
    percent = percent_fuel_for_ratio(a, b, ratio, reflector, absorber)
    return compute_layout(a, b, w, percent, reflector, absorber)


def center_cuts(layout: ZoneLayout) -> CenterCuts:
    ri = layout.r_inner
    y_fuel = ri * math.cos(layout.fuel_angle / 2.0)
    junction = min(math.pi, layout.opposite_angle / 2.0 + layout.absorber_angle)
    moderator_y = min(y_fuel - (layout.a + layout.reflector), -ri * math.cos(junction))
    reflector_y = None
    if layout.reflector > 1e-9:
        reflector_y = ri * math.cos(layout.fuel_angle / 2.0 + layout.reflector_angle)
    return CenterCuts(moderator_y=moderator_y, reflector_y=reflector_y)


def column_poses(n: int, r_outer: float) -> List[Tuple[float, float, float]]:
    """Return (x, y, rotation_deg) for each column. Fuel faces the shared center."""
    apart = 2.0 * r_outer
    if n <= 1:
        return [(0.0, 0.0, 0.0)]
    if n == 2:
        return [(0.0, apart / 2.0, 180.0), (0.0, -apart / 2.0, 0.0)]
    radius = apart / math.sqrt(3.0)
    poses: List[Tuple[float, float, float]] = []
    for k in range(3):
        theta = -90.0 + k * 120.0
        rad = math.radians(theta)
        poses.append(
            (
                radius * math.cos(rad),
                radius * math.sin(rad),
                theta + 90.0,
            )
        )
    return poses
