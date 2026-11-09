"""Zone geometry for a hollow disk split into fuel, reflector, shield, and TPV.

The disk is an annulus. Its inner diameter is ``a + reflector + absorber + b``.
``a`` is the shield moderator thickness. The shield absorber sits between the
moderator and the TPV.

- Fuel is centred at the top.
- On each side the order is fuel, reflector, shield moderator, shield absorber, TPV.
- Each layer's angle is set by its thickness: the straight line between its
  inner corners equals that thickness, 2 * R_i * sin(phi / 2) = thickness.
- Fuel and TPV share the remaining angle in the requested ratio.
- In the hole, every point of the inner disk within one absorber thickness of
  the TPV arc is absorber, so each TPV cell has that thickness in front of it.
  The boundary is a concentric arc plus a circular cap at each TPV corner.
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
    absorber: float
    gap_angle: float
    """Angle of ONE shield moderator sector, in radians."""
    reflector_angle: float
    """Angle of ONE reflector sector, in radians."""
    absorber_angle: float
    """Angle of ONE shield absorber sector, in radians."""
    fuel_angle: float
    opposite_angle: float
    fuel_area: float
    opposite_area: float
    gap_area: float
    """Combined area of both shield moderator sectors."""
    reflector_area: float
    """Combined area of both reflector sectors."""
    absorber_area: float
    """Combined area of both shield absorber sectors."""
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


def _inner_diameter(a: float, b: float, reflector: float, absorber: float, extra: float) -> float:
    return a + reflector + absorber + b + extra


def _layer_angles(a: float, reflector: float, absorber: float, diameter: float) -> tuple[float, float, float]:
    """Moderator, reflector, and absorber sector angles at ``diameter``."""
    return (
        chord_angle(a, diameter),
        chord_angle(reflector, diameter),
        chord_angle(absorber, diameter),
    )


def max_percent_fuel(a: float, b: float, reflector: float = 0.0, absorber: float = 0.0) -> float:
    """Largest percent_fuel that still leaves room for the TPV (with zero size)."""
    diameter = _inner_diameter(a, b, reflector, absorber, 0.0)
    moderator, reflected, absorbed = _layer_angles(a, reflector, absorber, diameter)
    return 100.0 * (1 - (moderator + reflected + absorbed) / math.pi)


def fuel_to_tpv_ratio(
    a: float,
    b: float,
    percent_fuel: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
) -> float:
    """Fuel area divided by TPV area. Infinite when the TPV has vanished."""
    diameter = _inner_diameter(a, b, reflector, absorber, 0.0)
    moderator, reflected, absorbed = _layer_angles(a, reflector, absorber, diameter)
    blocked = moderator + reflected + absorbed
    fuel_angle = 2 * math.pi * percent_fuel / 100.0
    opposite_angle = 2 * math.pi - fuel_angle - 2 * blocked
    if opposite_angle <= 1e-12:
        return math.inf
    return fuel_angle / opposite_angle


def percent_fuel_for_ratio(
    a: float,
    b: float,
    ratio: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
    extra: float = 0.0,
) -> float:
    """percent_fuel that makes the fuel area / TPV area equal ``ratio``."""
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    diameter = _inner_diameter(a, b, reflector, absorber, extra)
    moderator, reflected, absorbed = _layer_angles(a, reflector, absorber, diameter)
    free = max(0.0, 2 * math.pi - 2 * (moderator + reflected + absorbed))
    fuel_angle = ratio / (1.0 + ratio) * free
    return 100.0 * fuel_angle / (2 * math.pi)


def compute_layout(
    a: float,
    b: float,
    w: float,
    percent_fuel: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
    extra: float = 0.0,
) -> ZoneLayout:
    if a <= 0:
        raise ValueError("a must be positive")
    if b < 0:
        raise ValueError("b must be non-negative")
    if reflector < 0:
        raise ValueError("reflector must be non-negative")
    if absorber < 0:
        raise ValueError("absorber must be non-negative")
    if extra < 0:
        raise ValueError("extra must be non-negative")
    if w <= 0:
        raise ValueError("w must be positive")
    if not 0 <= percent_fuel <= 100:
        raise ValueError("percent_fuel must be between 0 and 100")

    diameter = _inner_diameter(a, b, reflector, absorber, extra)
    r_inner = diameter / 2
    r_outer = r_inner + w
    ring = r_outer**2 - r_inner**2
    total_area = math.pi * ring

    gap_angle, reflector_angle, absorber_angle = _layer_angles(a, reflector, absorber, diameter)
    p_max = 100.0 * (1 - (gap_angle + reflector_angle + absorber_angle) / math.pi)
    feasible = percent_fuel <= p_max + 1e-12

    fuel_angle = 2 * math.pi * percent_fuel / 100
    opposite_angle = max(0.0, 2 * math.pi - fuel_angle - 2 * (gap_angle + reflector_angle + absorber_angle))

    fuel_area = fuel_angle / 2 * ring
    gap_area = gap_angle * ring
    reflector_area = reflector_angle * ring
    absorber_area = absorber_angle * ring
    opposite_area = opposite_angle / 2 * ring

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
        fuel_area=fuel_area,
        opposite_area=opposite_area,
        gap_area=gap_area,
        reflector_area=reflector_area,
        absorber_area=absorber_area,
        max_percent_fuel=p_max,
        feasible=feasible,
    )


@dataclass(frozen=True)
class CenterCuts:
    """Horizontal chord positions in the local frame, fuel at +y."""

    moderator_y: float
    reflector_y: float | None


def center_cuts(layout: ZoneLayout) -> CenterCuts:
    """Moderator and reflector edges of the hole fills.

    The moderator edge is the line further toward the TPV of the moderator/absorber
    junction and the fuel-clearance line. The absorber in the hole is not a chord;
    ``absorber_front`` is its outline.
    """
    ri = layout.r_inner
    y_fuel = ri * math.cos(layout.fuel_angle / 2)
    junction = min(math.pi, layout.opposite_angle / 2 + layout.absorber_angle)
    y_moderator = min(
        y_fuel - (layout.a + layout.reflector),
        -ri * math.cos(junction),
    )
    reflector_y = None
    if layout.reflector > 1e-9:
        reflector_y = ri * math.cos(layout.fuel_angle / 2 + layout.reflector_angle)
    return CenterCuts(y_moderator, reflector_y)


def _arc_points(cx: float, cy: float, radius: float, a0: float, a1: float, n: int) -> list[tuple[float, float]]:
    """Points along the arc from angle ``a0`` to ``a1`` (radians), inclusive."""
    if n < 2:
        n = 2
    return [
        (cx + radius * math.cos(a0 + (a1 - a0) * i / (n - 1)),
         cy + radius * math.sin(a0 + (a1 - a0) * i / (n - 1)))
        for i in range(n)
    ]


def _append_arc(points: list[tuple[float, float]], arc: list[tuple[float, float]]) -> None:
    if points and arc and math.hypot(points[-1][0] - arc[0][0], points[-1][1] - arc[0][1]) < 1e-9:
        points.extend(arc[1:])
    else:
        points.extend(arc)


def _cap_sweep(center: tuple[float, float], radius: float, start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    """Signed sweep, from ``start`` to ``end`` around ``center``, that stays inside the reactor disk."""
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    ccw = (a1 - a0) % (2 * math.pi)
    sweeps = (ccw, ccw - 2 * math.pi)

    def midpoint(sweep: float) -> tuple[float, float]:
        mid = a0 + sweep / 2
        return (center[0] + radius * math.cos(mid), center[1] + radius * math.sin(mid))

    inside = [sweep for sweep in sweeps if math.hypot(*midpoint(sweep)) <= math.hypot(*center) + 1e-8]
    sweep = min(inside or sweeps, key=lambda sweep: math.hypot(*midpoint(sweep)))
    return a0, a0 + sweep


def absorber_front(layout: ZoneLayout) -> list[tuple[float, float]] | None:
    """Hole absorber in front of the TPV, or None when there is no absorber.

    The polygon is every point of the inner disk within ``layout.absorber`` of
    the TPV inner arc. Across the TPV the far edge is the concentric arc of
    radius ``R - absorber``. Each end is a circular cap of that same radius
    centered on the TPV corner, meeting the inner circle where the absorber
    rim sector meets the moderator. A ray that stays in the disk therefore
    travels at least one absorber thickness through this region.
    """
    thickness = layout.absorber
    radius = layout.r_inner
    if thickness <= 1e-12 or radius <= 1e-12 or thickness >= 2 * radius - 1e-9:
        return None
    alpha = layout.opposite_angle / 2
    phi = layout.absorber_angle
    right = -math.pi / 2 + alpha
    left = -math.pi / 2 - alpha
    samples = 96

    def at(angle: float, rad: float) -> tuple[float, float]:
        return (rad * math.cos(angle), rad * math.sin(angle))

    outer = _arc_points(0.0, 0.0, radius, left - phi, right + phi, samples)
    points: list[tuple[float, float]] = []
    _append_arc(points, outer)

    if thickness < radius - 1e-9:
        inner_r = radius - thickness
        right_end = at(right, radius)
        inner_right = at(right, inner_r)
        a0, a1 = _cap_sweep(right_end, thickness, at(right + phi, radius), inner_right)
        _append_arc(points, _arc_points(right_end[0], right_end[1], thickness, a0, a1, samples // 2))
        _append_arc(points, _arc_points(0.0, 0.0, inner_r, right, left, samples))
        left_end = at(left, radius)
        inner_left = at(left, inner_r)
        a0, a1 = _cap_sweep(left_end, thickness, inner_left, at(left - phi, radius))
        _append_arc(points, _arc_points(left_end[0], left_end[1], thickness, a0, a1, samples // 2))
    else:
        # The offset has passed the centre. The two corner caps meet across the hole.
        right_end = at(right, radius)
        left_end = at(left, radius)
        if math.hypot(right_end[0] - left_end[0], right_end[1] - left_end[1]) < 1e-8:
            a0, a1 = _cap_sweep(right_end, thickness, at(right + phi, radius), at(left - phi, radius))
            _append_arc(points, _arc_points(right_end[0], right_end[1], thickness, a0, a1, samples))
            return points
        meet = _cap_meeting(right_end, left_end, thickness)
        a0, a1 = _cap_sweep(right_end, thickness, at(right + phi, radius), meet)
        _append_arc(points, _arc_points(right_end[0], right_end[1], thickness, a0, a1, samples // 2))
        a0, a1 = _cap_sweep(left_end, thickness, meet, at(left - phi, radius))
        _append_arc(points, _arc_points(left_end[0], left_end[1], thickness, a0, a1, samples // 2))
    return points


def _cap_meeting(right: tuple[float, float], left: tuple[float, float], thickness: float) -> tuple[float, float]:
    """Fuel-side intersection of the two corner caps."""
    mid_x = (right[0] + left[0]) / 2
    mid_y = (right[1] + left[1]) / 2
    span = math.hypot(right[0] - left[0], right[1] - left[1])
    reach = math.sqrt(max(thickness * thickness - (span / 2) ** 2, 0.0))
    # Toward the fuel (+y) from the chord between the TPV corners.
    return (mid_x - reach * (right[1] - left[1]) / span, mid_y + reach * (right[0] - left[0]) / span)


def central_absorber_thickness(layout: ZoneLayout) -> float:
    """Absorber thickness along the centreline, in front of the middle TPV cell."""
    if layout.absorber <= 1e-12:
        return 0.0
    return min(layout.absorber, 2 * layout.r_inner)


def compute_layout_for_ratio(
    a: float,
    b: float,
    w: float,
    ratio: float,
    reflector: float = 0.0,
    absorber: float = 0.0,
) -> ZoneLayout:
    """Layout at ``ratio``. The curved absorber keeps its thickness without growing the disk."""
    percent = percent_fuel_for_ratio(a, b, ratio, reflector, absorber, 0.0)
    return compute_layout(a, b, w, percent, reflector, absorber, 0.0)