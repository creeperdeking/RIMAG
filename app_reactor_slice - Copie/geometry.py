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


def _is_uranium_atom(name: str) -> bool:
    return name == "U" or (len(name) > 1 and name[0] == "U" and name[1].isdigit())


def _contains_uranium(spec) -> bool:
    return any(_is_uranium_atom(part.atom.name) for part in spec.composition)


def _library_parts(name: str, specs: dict, mixed: dict):
    """The material spec, or a mixture, including a trailing copy such as ' 2'."""
    if name in specs:
        return specs[name], None
    base, separator, suffix = name.rpartition(" ")
    if separator and suffix.isdigit() and base in specs:
        return specs[base], None
    mix = mixed.get(name)
    if mix is None and separator and suffix.isdigit():
        mix = mixed.get(base)
    return None, mix


def uranium_bearing_density(name: str, specs: dict, mixed: dict) -> float | None:
    """Density in g/cm³ of the uranium-bearing material, as stored in the library.

    A pure compound uses that material's density. A mixture uses the library
    densities of its uranium-bearing constituents and leaves the rest out.
    """
    spec, mix = _library_parts(name.strip(), specs, mixed)
    if spec is not None:
        if not _contains_uranium(spec) or spec.density <= 0:
            return None
        return float(spec.density)
    if mix is None:
        return None
    uranium_weight = 0.0
    volume = 0.0
    for component, proportion in zip(mix.materials, mix.proportions):
        component_spec = specs.get(component)
        if component_spec is None or component_spec.density <= 0 or proportion <= 0:
            return None
        volume += proportion / component_spec.density
        if _contains_uranium(component_spec):
            uranium_weight += proportion
    if uranium_weight <= 0 or volume <= 0:
        return None
    return uranium_weight / volume


def uranium_inventory_kg(
    rows: list[dict],
    fuel_area_m2: float,
    columns: int,
    stack_m: float,
    layer_cm: float,
    specs: dict,
    mixed: dict,
) -> tuple[float, list[tuple[str, float, float]], list[str]]:
    """Mass of uranium-bearing fuel, per material, and names missing from the library.

    Each counted row fills the fuel area through its own thickness, on every
    slice of the stack. ``layer_cm`` is the shared slice pitch. Density is the
    library density of that uranium-bearing material.
    """
    if layer_cm <= 0:
        return 0.0, [], []
    mass_kg = 0.0
    counted: list[tuple[str, float, float]] = []
    skipped: list[str] = []
    for row in rows:
        name = str(row.get("name", "")).strip()
        density = uranium_bearing_density(name, specs, mixed)
        if density is None:
            if "uranium" in name.lower():
                skipped.append(name or "uranium")
            continue
        cm = float(row.get("cm", 0.0))
        volume_m3 = fuel_area_m2 * columns * stack_m * (cm / layer_cm)
        row_kg = volume_m3 * density * 1000.0
        mass_kg += row_kg
        counted.append((name, row_kg, density))
    return mass_kg, counted, skipped


def triso_cylinder_fractions(
    diameter_mm: float,
    wall_margin_mm: float,
    spacing_mm: float,
    packing_pct: float,
    hm_particle_pct: float,
) -> tuple[float, float]:
    """Particle share of a cylinder, and heavy-metal share of the fuel layer.

    Cylinders span the fuel layer, so the layer is one diameter thick. Particles
    stay ``wall_margin_mm`` inside the wall and are packed at ``packing_pct`` in
    that inner circle. Cylinders are separated by ``spacing_mm``, so one cylinder
    and its gap occupy a cell ``diameter`` by ``diameter + spacing``. The heavy
    metal is the particle volume in that cell times the HM fraction per particle.
    """
    diameter = float(diameter_mm)
    radius = diameter / 2.0
    pitch = diameter + float(spacing_mm)
    if diameter <= 0 or radius <= 0 or pitch <= 0:
        return 0.0, 0.0
    usable = max(radius - float(wall_margin_mm), 0.0)
    packing = min(max(packing_pct / 100.0, 0.0), 1.0)
    hm = min(max(hm_particle_pct / 100.0, 0.0), 1.0)
    particle_in_cylinder = packing * (usable / radius) ** 2
    cell_area = diameter * pitch
    hm_fraction = packing * hm * math.pi * usable * usable / cell_area
    return particle_in_cylinder, min(max(hm_fraction, 0.0), 1.0)


def triso_particle_layout(
    diameter_mm: float,
    wall_margin_mm: float,
    packing_pct: float,
    hm_particle_pct: float,
) -> list[tuple[float, float, float, float]]:
    """Particles inside one cylinder, in millimetres from its centre.

    Each entry is ``(x, y, radius, kernel_radius)``. Particles stay inside the
    wall margin, do not overlap, and their combined area is the packing
    fraction of that inner circle. The kernel is the heavy-metal share of each
    particle.
    """
    diameter = float(diameter_mm)
    radius = diameter / 2.0
    usable = max(radius - float(wall_margin_mm), 0.0)
    packing = min(max(packing_pct / 100.0, 0.0), 1.0)
    hm = min(max(hm_particle_pct / 100.0, 0.0), 1.0)
    if diameter <= 0 or usable <= 0 or packing <= 0:
        return []
    target = packing * math.pi * usable * usable
    nominal_r = min(0.45, usable * 0.28)
    chosen: tuple[int, float, float] | None = None
    for rings in range(6):
        count = 1 + 3 * rings * (rings + 1)
        particle_r = math.sqrt(target / (count * math.pi))
        if particle_r > usable:
            continue
        step = 0.0 if rings == 0 else (usable - particle_r) / rings
        if rings and step < 2.0 * particle_r - 1e-9:
            continue
        if chosen is None or abs(particle_r - nominal_r) < abs(chosen[1] - nominal_r):
            chosen = (rings, particle_r, step)
    if chosen is None:
        return []
    rings, particle_r, step = chosen
    limit = max(usable - particle_r, 0.0)
    points = [
        point
        for point in _hex_lattice(step, limit)
        if math.hypot(point[0], point[1]) <= limit + 1e-6
    ]
    kernel_r = particle_r * math.sqrt(hm)
    return [(point[0], point[1], particle_r, kernel_r) for point in points]


def _hex_lattice(step: float, limit: float) -> list[tuple[float, float]]:
    """Hexagonal lattice points whose centre is at most ``limit`` from the origin."""
    if step <= 0:
        return [(0.0, 0.0)]
    points = [(0.0, 0.0)]
    ring = 1
    while ring * step <= limit + 1e-9 and ring <= 40:
        for side in range(6):
            angle = math.pi / 3.0 * side
            corner_x = math.cos(angle) * ring * step
            corner_y = math.sin(angle) * ring * step
            next_angle = angle + math.pi / 3.0
            next_x = math.cos(next_angle) * ring * step
            next_y = math.sin(next_angle) * ring * step
            for index in range(ring):
                share = index / ring
                points.append(
                    (
                        corner_x + (next_x - corner_x) * share,
                        corner_y + (next_y - corner_y) * share,
                    )
                )
        ring += 1
    return points


def triso_fuel_layers(
    diameter_mm: float,
    wall_margin_mm: float,
    spacing_mm: float,
    packing_pct: float,
    hm_particle_pct: float,
) -> tuple[list[dict], float, float]:
    """Graphite, uranium dioxide, and graphite, plus the two fractions above.

    The three thicknesses add up to the cylinder diameter.
    """
    particle_in_cylinder, hm_fraction = triso_cylinder_fractions(
        diameter_mm, wall_margin_mm, spacing_mm, packing_pct, hm_particle_pct
    )
    total_cm = diameter_mm / 10.0
    uo2_cm = round(total_cm * hm_fraction, 4)
    graphite_cm = round((total_cm - uo2_cm) / 2.0, 4)
    cover_cm = round(total_cm - uo2_cm - graphite_cm, 4)
    layers = [
        {"name": "Graphite", "cm": graphite_cm},
        {"name": "Uranium Dioxide", "cm": uo2_cm},
        {"name": "Graphite", "cm": cover_cm},
    ]
    return layers, particle_in_cylinder, hm_fraction


def burnup_days(uranium_kg: float, burnup_mwd_per_kg: float, thermal_kw: float) -> float:
    """Days at ``thermal_kw`` until the uranium reaches ``burnup_mwd_per_kg``.

    ``thermal_kw`` is the core thermal power already shown in the zone overview.
    """
    return uranium_kg * burnup_mwd_per_kg / (thermal_kw / 1000.0)


def format_burnup_time(days: float) -> str:
    """Calendar years and months, rounded to the nearest month."""
    months_total = int(round(days / (365.25 / 12.0)))
    if months_total <= 0:
        return "less than a month"
    years, months = divmod(months_total, 12)
    parts: list[str] = []
    if years == 1:
        parts.append("1 year")
    elif years:
        parts.append(f"{years} years")
    if months == 1:
        parts.append("1 month")
    elif months:
        parts.append(f"{months} months")
    return " ".join(parts)