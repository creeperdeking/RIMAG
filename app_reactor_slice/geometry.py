"""Zone geometry for a hollow disk split into fuel, reflector, shielding, and TPV.

The disk is an annulus with inner diameter (a + reflector + b) and rim width w.

- Fuel is centred at the top.
- A reflector layer sits on each side of the fuel, then shielding, then TPV.
- Each layer's angle is set by its thickness: the straight line between its
  inner corners equals that thickness, 2 * R_i * sin(phi / 2) = thickness.
- Fuel and TPV share the remaining angle in the requested ratio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneLayout:
    a: float
    b: float
    w: float
    reflector: float
    percent_fuel: float
    r_inner: float
    r_outer: float
    total_area: float
    gap_angle: float
    """Angle of ONE shielding sector, in radians."""
    reflector_angle: float
    """Angle of ONE reflector sector, in radians."""
    fuel_angle: float
    opposite_angle: float
    fuel_area: float
    opposite_area: float
    gap_area: float
    """Combined area of both shielding sectors."""
    reflector_area: float
    """Combined area of both reflector sectors."""
    max_percent_fuel: float
    feasible: bool

    @property
    def gap_total_angle(self) -> float:
        return 2 * self.gap_angle

    @property
    def min_distance(self) -> float:
        return 2 * self.r_inner * math.sin(self.gap_angle / 2)


def chord_angle(thickness: float, inner_diameter: float) -> float:
    """Sector angle whose inner-corner chord equals ``thickness``."""
    if thickness <= 0 or inner_diameter <= 0:
        return 0.0
    return 2 * math.asin(min(1.0, thickness / inner_diameter))


def max_percent_fuel(a: float, b: float, reflector: float = 0.0) -> float:
    """Largest percent_fuel that still leaves room for the TPV (with zero size)."""
    diameter = a + reflector + b
    blocked = chord_angle(a, diameter) + chord_angle(reflector, diameter)
    return 100.0 * (1 - blocked / math.pi)


def fuel_to_tpv_ratio(a: float, b: float, percent_fuel: float, reflector: float = 0.0) -> float:
    """Fuel area divided by TPV area. Infinite when the TPV has vanished."""
    diameter = a + reflector + b
    gap_angle = chord_angle(a, diameter) + chord_angle(reflector, diameter)
    fuel_angle = 2 * math.pi * percent_fuel / 100.0
    opposite_angle = 2 * math.pi - fuel_angle - 2 * gap_angle
    if opposite_angle <= 1e-12:
        return math.inf
    return fuel_angle / opposite_angle


def percent_fuel_for_ratio(a: float, b: float, ratio: float, reflector: float = 0.0) -> float:
    """percent_fuel that makes the fuel area / TPV area equal ``ratio``."""
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    diameter = a + reflector + b
    gap_angle = chord_angle(a, diameter) + chord_angle(reflector, diameter)
    free = 2 * math.pi - 2 * gap_angle
    fuel_angle = ratio / (1.0 + ratio) * free
    return 100.0 * fuel_angle / (2 * math.pi)


def compute_layout(a: float, b: float, w: float, percent_fuel: float, reflector: float = 0.0) -> ZoneLayout:
    if a <= 0:
        raise ValueError("a must be positive")
    if b < 0:
        raise ValueError("b must be non-negative")
    if reflector < 0:
        raise ValueError("reflector must be non-negative")
    if w <= 0:
        raise ValueError("w must be positive")
    if not 0 <= percent_fuel <= 100:
        raise ValueError("percent_fuel must be between 0 and 100")

    r_inner = (a + reflector + b) / 2
    r_outer = r_inner + w
    ring = r_outer**2 - r_inner**2
    total_area = math.pi * ring
    diameter = 2 * r_inner

    gap_angle = chord_angle(a, diameter)
    reflector_angle = chord_angle(reflector, diameter)
    p_max = max_percent_fuel(a, b, reflector)
    feasible = percent_fuel <= p_max + 1e-12

    fuel_angle = 2 * math.pi * percent_fuel / 100
    opposite_angle = max(0.0, 2 * math.pi - fuel_angle - 2 * gap_angle - 2 * reflector_angle)

    fuel_area = fuel_angle / 2 * ring
    gap_area = gap_angle * ring
    reflector_area = reflector_angle * ring
    opposite_area = opposite_angle / 2 * ring

    return ZoneLayout(
        a=a,
        b=b,
        w=w,
        reflector=reflector,
        percent_fuel=percent_fuel,
        r_inner=r_inner,
        r_outer=r_outer,
        total_area=total_area,
        gap_angle=gap_angle,
        reflector_angle=reflector_angle,
        fuel_angle=fuel_angle,
        opposite_angle=opposite_angle,
        fuel_area=fuel_area,
        opposite_area=opposite_area,
        gap_area=gap_area,
        reflector_area=reflector_area,
        max_percent_fuel=p_max,
        feasible=feasible,
    )