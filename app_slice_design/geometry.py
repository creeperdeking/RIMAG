"""OpenMC CSG for one hollow-disk slice matching the web calculator layout."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import openmc
from pydantic import BaseModel

from app_slice_design.layout import (
    ZoneLayout,
    center_cuts,
    column_poses,
    compute_layout_for_ratio,
)
from app_slice_design.materials_map import (
    fuel_and_tpv_thickness_cm,
    resolve_material_name,
    same_material_names,
    shared_stack_thickness_cm,
    stack_with_disk,
)
from app_slice_design.setup import AppSliceRunConfig, LayerRow
from common_lib.materials import MaterialChoice


class MakeAppSliceGeometryResult(BaseModel, arbitrary_types_allowed=True):
    geometry: openmc.Geometry
    universe: openmc.Universe
    tracked_cells: Dict[str, List[openmc.Cell]]
    bounding_box: Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    render_radius: float
    render_height: float
    render_origin: Tuple[float, float, float]
    layout: ZoneLayout
    pitch_cm: float
    fuel_thickness_cm: float
    photovoltaic_thickness_cm: float
    vertical_core_height_cm: float
    rotary_axle_radius_cm: float


def _angular_sector(phi0: float, phi1: float) -> openmc.Region:
    """CCW sector from phi0 to phi1 (radians from +x)."""
    span = (phi1 - phi0) % (2.0 * math.pi)
    if span < 1e-12:
        # Degenerate: empty-ish region; keep a tiny wedge.
        span = 1e-6
        phi1 = phi0 + span
    p0 = openmc.Plane(a=-math.sin(phi0), b=math.cos(phi0), c=0.0, d=0.0)
    p1 = openmc.Plane(a=-math.sin(phi1), b=math.cos(phi1), c=0.0, d=0.0)
    if span <= math.pi + 1e-12:
        return +p0 & -p1
    return +p0 | -p1


def _annulus(r_in_cm: float, r_out_cm: float) -> openmc.Region:
    outer = -openmc.ZCylinder(r=r_out_cm)
    if r_in_cm <= 1e-12:
        return outer
    return outer & +openmc.ZCylinder(r=r_in_cm)


def _sector_area_cm2(
    spans: List[Tuple[float, float]],
    r_in_cm: float,
    r_out_cm: float,
) -> float:
    """Horizontal area of annular sectors. Spans are CCW radians, not wrapping."""
    radial = 0.5 * (r_out_cm * r_out_cm - r_in_cm * r_in_cm)
    return sum(radial * (phi1 - phi0) for phi0, phi1 in spans)


def _z_scaling(conical_pitch_deg: float) -> float:
    """Map material-stack thickness to vertical period (paper get_z_scaling)."""
    if abs(conical_pitch_deg) < 1e-12:
        return 1.0
    return 1.0 / math.sin(math.radians(90.0 - conical_pitch_deg))


def _cone_extra_height(radius_cm: float, conical_pitch_deg: float) -> float:
    """Extra |z| from axis to radius along the cone generators."""
    if abs(conical_pitch_deg) < 1e-12 or radius_cm <= 0:
        return 0.0
    return radius_cm / math.tan(math.radians(90.0 - conical_pitch_deg))


def _layer_surface(
    z0: float,
    conical_pitch_deg: float,
    boundary_type: str = "transmission",
) -> openmc.Plane | openmc.model.ZConeOneSided:
    """
    Axial bound for one material coordinate z0.

    Pitch 0 → flat ZPlane. Otherwise a one-sided cone whose axis is the disk
    centerline (x=y=0), so layers tilt toward the cylinder axis.
    """
    if abs(conical_pitch_deg) < 1e-12:
        return openmc.ZPlane(z0=z0, boundary_type=boundary_type)
    r2 = 1.0 / math.tan(math.radians(conical_pitch_deg)) ** 2
    return openmc.model.ZConeOneSided(
        z0=z0 * _z_scaling(conical_pitch_deg),
        x0=0.0,
        y0=0.0,
        r2=r2,
        boundary_type=boundary_type,
        up=False,
    )


def _axial_region(
    z0: float,
    z1: float,
    conical_pitch_deg: float = 0.0,
    *,
    open_bottom: bool = False,
    open_top: bool = False,
) -> Optional[openmc.Region]:
    """Region between two material-z bounds.

    Open ends are used when the root cell already clips that side with a
    periodic cone, so the fill does not carry a second coincident surface.
    """
    parts: List[openmc.Region] = []
    if not open_bottom:
        parts.append(+_layer_surface(z0, conical_pitch_deg))
    if not open_top:
        parts.append(-_layer_surface(z1, conical_pitch_deg))
    if not parts:
        return None
    region = parts[0]
    for part in parts[1:]:
        region = region & part
    return region


def _zone_phi_spans(layout: ZoneLayout) -> Dict[str, List[Tuple[float, float]]]:
    """Fuel is centered on +y. Returns list of (phi0, phi1) CCW spans per zone."""
    fuel_half = layout.fuel_angle / 2.0
    opp_half = layout.opposite_angle / 2.0
    # Local angles measured from +y, then convert to +x CCW.
    # +y is pi/2 in standard math angles.
    def from_y(delta: float) -> float:
        return math.pi / 2.0 + delta

    fuel = (from_y(-fuel_half), from_y(+fuel_half))

    # Going clockwise from fuel's right edge: reflector, shield mod, absorber, then TPV...
    # and mirrored on the left. Build both sides.
    right = fuel_half
    left = -fuel_half

    def take_right(width: float) -> Tuple[float, float]:
        nonlocal right
        a0, a1 = right, right + width
        right = a1
        return from_y(a0), from_y(a1)

    def take_left(width: float) -> Tuple[float, float]:
        nonlocal left
        a1, a0 = left, left - width
        left = a0
        return from_y(a0), from_y(a1)

    spans: Dict[str, List[Tuple[float, float]]] = {
        "fuel": [fuel],
        "reflector": [],
        "shield_moderator": [],
        "shield_absorber": [],
        "tpv": [],
    }

    if layout.reflector_angle > 1e-12:
        spans["reflector"].append(take_right(layout.reflector_angle))
        spans["reflector"].append(take_left(layout.reflector_angle))
    if layout.gap_angle > 1e-12:
        spans["shield_moderator"].append(take_right(layout.gap_angle))
        spans["shield_moderator"].append(take_left(layout.gap_angle))
    if layout.absorber_angle > 1e-12:
        spans["shield_absorber"].append(take_right(layout.absorber_angle))
        spans["shield_absorber"].append(take_left(layout.absorber_angle))

    # TPV is centered on -y.
    spans["tpv"] = [
        (
            math.pi / 2.0 + math.pi - opp_half,
            math.pi / 2.0 + math.pi + opp_half,
        )
    ]
    return spans


def _union_regions(regions: List[openmc.Region]) -> Optional[openmc.Region]:
    if not regions:
        return None
    out = regions[0]
    for region in regions[1:]:
        out = out | region
    return out


def _fill_name_for_zone(
    zone_id: str,
    layer_name: str,
    material_choice: MaterialChoice,
) -> str:
    """Map a calculator layer onto the post-make_materials MaterialChoice name."""
    resolved = resolve_material_name(layer_name)
    # TPV gaps are the coolant role (often Void 2 after material de-duplication).
    # Check that before the generic Void → void mapping used by disk voids.
    if zone_id == "tpv":
        if resolved == "InGaAs":
            return material_choice.photovoltaic
        return material_choice.coolant
    if resolved == "Void":
        return material_choice.void
    if zone_id == "fuel":
        if resolved == "Uranium Dioxide":
            return material_choice.fuel
        return material_choice.fuel_cladding
    if zone_id == "reflector":
        return material_choice.neutron_reflector
    if zone_id == "shield_moderator":
        return material_choice.neutron_shield_moderator
    if zone_id == "shield_absorber":
        return material_choice.neutron_absorber
    if zone_id == "disk":
        return material_choice.emitter
    return resolved


def _add_cell(
    cells: List[openmc.Cell],
    tracked: Dict[str, List[openmc.Cell]],
    materials_dict: Dict[str, openmc.Material],
    fill_name: str,
    region: openmc.Region,
    name: str,
    volume: Optional[float] = None,
) -> None:
    if fill_name not in materials_dict:
        raise ValueError(f"Material '{fill_name}' not in materials_dict")
    cell = openmc.Cell(name=name, region=region, fill=materials_dict[fill_name])
    if volume is not None:
        # One column. make_app_slice_geometry multiplies by the column count,
        # because the same cell is instantiated once per cylinder.
        cell.volume = volume
    cells.append(cell)
    tracked[fill_name].append(cell)


def _build_zone_stack_cells(
    zone_id: str,
    spans: List[Tuple[float, float]],
    zone_rows: List[LayerRow],
    disk_rows: List[LayerRow],
    r_in_cm: float,
    r_out_cm: float,
    z_bot: float,
    materials_dict: Dict[str, openmc.Material],
    material_choice: MaterialChoice,
    tracked: Dict[str, List[openmc.Cell]],
    cells: List[openmc.Cell],
    conical_pitch_deg: float,
    open_period: bool,
) -> None:
    if not spans:
        return
    sector = _union_regions([_angular_sector(a0, a1) for a0, a1 in spans])
    if sector is None:
        return
    ring = _annulus(r_in_cm, r_out_cm) & sector
    # Parallel cone sheets are a constant vertical gap apart: t / cos(pitch).
    # That makes the sheet volume exact, so the sampler never has to hit a
    # 0.05 cm gap inside the tilted-shell box.
    sheet_area = _sector_area_cm2(spans, r_in_cm, r_out_cm)
    z_scale = _z_scaling(conical_pitch_deg)
    rows = stack_with_disk(zone_rows, disk_rows)
    active = [(index, row) for index, row in enumerate(rows) if row.cm > 0]
    z = z_bot
    zone_count = len(zone_rows)
    for place, (index, row) in enumerate(active):
        layer_zone = zone_id if index < zone_count else "disk"
        slab = _axial_region(
            z,
            z + row.cm,
            conical_pitch_deg,
            open_bottom=open_period and place == 0,
            open_top=open_period and place == len(active) - 1,
        )
        region = ring if slab is None else ring & slab
        fill_name = _fill_name_for_zone(layer_zone, row.name, material_choice)
        _add_cell(
            cells,
            tracked,
            materials_dict,
            fill_name,
            region,
            name=f"{zone_id}_{index}_{fill_name}",
            volume=sheet_area * row.cm * z_scale,
        )
        z += row.cm


def _build_hole_cells(
    layout: ZoneLayout,
    pitch_cm: float,
    materials_dict: Dict[str, openmc.Material],
    material_choice: MaterialChoice,
    tracked: Dict[str, List[openmc.Cell]],
    cells: List[openmc.Cell],
    conical_pitch_deg: float,
    open_period: bool,
) -> None:
    """Approximate hole fills with chord planes (fuel at +y)."""
    cuts = center_cuts(layout)
    r_in_cm = layout.r_inner * 100.0
    z_bot = -pitch_cm / 2.0
    z_top = pitch_cm / 2.0
    # When the root cell already clips with periodic cones, leave the hole
    # axially open — a coincident transmission slab would merge into the
    # periodic surfaces and lose particles after the boundary jump.
    hole = -openmc.ZCylinder(r=r_in_cm)
    slab_region = _axial_region(
        z_bot,
        z_top,
        conical_pitch_deg,
        open_bottom=open_period,
        open_top=open_period,
    )
    inside = hole if slab_region is None else hole & slab_region

    opp_half = layout.opposite_angle / 2.0
    tpv_phi0 = math.pi / 2.0 + math.pi - opp_half
    tpv_phi1 = math.pi / 2.0 + math.pi + opp_half
    absorber_cm = layout.absorber * 100.0

    used = inside
    if absorber_cm > 1e-9 and layout.absorber_angle + layout.opposite_angle > 1e-12:
        abs_phi0 = tpv_phi0 - layout.absorber_angle
        abs_phi1 = tpv_phi1 + layout.absorber_angle
        abs_ring = _annulus(max(0.0, r_in_cm - absorber_cm), r_in_cm) & _angular_sector(
            abs_phi0, abs_phi1
        )
        region = inside & abs_ring
        _add_cell(
            cells,
            tracked,
            materials_dict,
            material_choice.neutron_absorber,
            region,
            "hole_absorber",
        )
        used = used & ~region

    mod_plane = openmc.YPlane(y0=cuts.moderator_y * 100.0)
    mod_region = used & +mod_plane
    _add_cell(
        cells,
        tracked,
        materials_dict,
        material_choice.moderator,
        mod_region,
        "hole_moderator",
    )
    used = used & ~mod_region

    if cuts.reflector_y is not None and layout.reflector > 1e-9:
        refl_plane = openmc.YPlane(y0=cuts.reflector_y * 100.0)
        # Between fuel chord and moderator cut, on the fuel side of the reflector chord.
        fuel_y = r_in_cm * math.cos(layout.fuel_angle / 2.0)
        fuel_plane = openmc.YPlane(y0=fuel_y)
        refl_region = used & +refl_plane & -fuel_plane
        _add_cell(
            cells,
            tracked,
            materials_dict,
            material_choice.neutron_reflector,
            refl_region,
            "hole_reflector",
        )
        used = used & ~refl_region

    _add_cell(
        cells,
        tracked,
        materials_dict,
        material_choice.void,
        used,
        "hole_void",
    )


def _one_disk_universe(
    layout: ZoneLayout,
    setup_layers: Dict[str, List[LayerRow]],
    pitch_cm: float,
    materials_dict: Dict[str, openmc.Material],
    material_choice: MaterialChoice,
    conical_pitch_deg: float,
    open_period: bool = False,
) -> Tuple[openmc.Universe, Dict[str, List[openmc.Cell]], List[openmc.Cell]]:
    tracked: Dict[str, List[openmc.Cell]] = defaultdict(list)
    cells: List[openmc.Cell] = []
    r_in_cm = layout.r_inner * 100.0
    r_out_cm = layout.r_outer * 100.0
    z_bot = -pitch_cm / 2.0
    spans = _zone_phi_spans(layout)
    disk_rows = setup_layers.get("disk", [])

    zone_keys = (
        ("fuel", "fuel"),
        ("reflector", "reflector"),
        ("shield_moderator", "shield_moderator"),
        ("shield_absorber", "shield_absorber"),
        ("tpv", "tpv"),
    )
    for zone_id, layer_key in zone_keys:
        _build_zone_stack_cells(
            zone_id,
            spans.get(zone_id, []),
            setup_layers.get(layer_key, []),
            disk_rows,
            r_in_cm,
            r_out_cm,
            z_bot,
            materials_dict,
            material_choice,
            tracked,
            cells,
            conical_pitch_deg,
            open_period,
        )

    _build_hole_cells(
        layout,
        pitch_cm,
        materials_dict,
        material_choice,
        tracked,
        cells,
        conical_pitch_deg,
        open_period,
    )

    # No radial pad outside r_out: multi-column layouts place centers 2*r_out
    # apart, and any outer shell would overlap the neighbor column cell.

    return openmc.Universe(cells=cells), dict(tracked), cells


def _slice_count(stack_m: float, period_cm: float) -> int:
    """How many identical pitch-tall slices fit in the engineering stack height."""
    if period_cm <= 0:
        raise ValueError("period_cm must be positive")
    return max(1, int(round((stack_m * 100.0) / period_cm)))


def _fuel_mid_local_cm(layout: ZoneLayout) -> Tuple[float, float, float]:
    """Mid-annulus point of the fuel sector in slice-local cm (fuel on +y)."""
    r_mid = 0.5 * (layout.r_inner + layout.r_outer) * 100.0
    return (0.0, r_mid, 0.0)


def _rotate_xy(x: float, y: float, rot_deg: float) -> Tuple[float, float]:
    """Rotate (x, y) by rot_deg about +z (same convention as OpenMC cell.rotation)."""
    if abs(rot_deg) < 1e-12:
        return x, y
    phi = math.radians(rot_deg)
    c, s = math.cos(phi), math.sin(phi)
    return c * x - s * y, s * x + c * y


def _fuel_mid_world_cm(
    layout: ZoneLayout,
    x_m: float,
    y_m: float,
    rot_deg: float,
) -> Tuple[float, float, float]:
    """World-cm coordinates of the fuel mid-point for one column pose."""
    lx, ly, lz = _fuel_mid_local_cm(layout)
    rx, ry = _rotate_xy(lx, ly, rot_deg)
    return (rx + x_m * 100.0, ry + y_m * 100.0, lz)


def _transport_layer_count(
    period_cm: float,
    r_out_cm: float,
    conical_pitch_deg: float,
) -> Tuple[int, int]:
    """
    How many pitch-tall shells to tile for one periodic transport unit cell.

    Matches the paper: the Monte Carlo domain is only one vertical period tall.
    Extra shells exist so conical layer surfaces still cover that unit cell
    (including flare at the outer radius). stack_m is NOT the transport height.
    Returns (n_layers, start_index) where start_index is the unshifted center shell.
    """
    if abs(conical_pitch_deg) < 1e-12 or period_cm <= 0:
        return 1, 0
    flare = _cone_extra_height(r_out_cm, conical_pitch_deg)
    lower_z = -period_cm / 2.0 - flare
    upper_z = period_cm / 2.0 + flare
    n_above = math.ceil(0.5 - lower_z / period_cm)
    n_below = math.ceil(0.5 + upper_z / period_cm)
    n_layers = max(1, int(n_above + n_below + 1))
    # Same insurance as common_lib.geometry.make_module_stack_surfaces.
    n_layers *= 2
    return n_layers, int(n_below)


def _build_column_stack_universe(
    slice_universe: openmc.Universe,
    pitch_cm: float,
    n_layers: int,
    start_index: int,
    r_out_cm: float,
    conical_pitch_deg: float,
) -> openmc.Universe:
    """
    Tile the shared slice universe for one periodic period.

    Parent cells are named boundary_layer_* so stochastic volume checks skip them
    (same convention as the paper geometry).
    """
    z_scale = _z_scaling(conical_pitch_deg)
    # Exact outer radius: centers are 2*R apart, so +padding would overlap neighbors.
    col_cyl = -openmc.ZCylinder(r=r_out_cm)
    # Material-z bounds: center shell spans [-pitch/2, +pitch/2].
    surfaces = [
        _layer_surface(
            -pitch_cm / 2.0 + (k - start_index) * pitch_cm,
            conical_pitch_deg,
        )
        for k in range(n_layers + 1)
    ]
    stack_cells: List[openmc.Cell] = []
    for k in range(n_layers):
        z_center_mat = (k - start_index) * pitch_cm
        region = col_cyl & +surfaces[k] & -surfaces[k + 1]
        cell = openmc.Cell(
            name=f"boundary_layer_{k}",
            region=region,
            fill=slice_universe,
        )
        # Real-z shift matches paper: material pitch × z_scaling.
        cell.translation = (0.0, 0.0, z_center_mat * z_scale)
        stack_cells.append(cell)
    return openmc.Universe(cells=stack_cells)


def make_app_slice_geometry(
    config: AppSliceRunConfig,
    materials_dict: Dict[str, openmc.Material],
    material_choice: MaterialChoice,
) -> MakeAppSliceGeometryResult:
    setup = config.setup
    merge_reflector = same_material_names(
        setup.layers.get("reflector", []),
        setup.layers.get("shield_moderator", []),
    )
    shield_a = setup.a + setup.refl if merge_reflector else setup.a
    reflector = 0.0 if merge_reflector else setup.refl
    layout = compute_layout_for_ratio(
        shield_a,
        (setup.a * setup.b_pct) / 100.0,
        setup.w,
        setup.ratio_pct / 100.0,
        reflector,
        setup.absorber,
    )
    if not layout.feasible:
        raise ValueError(
            f"Layout is not feasible (fuel {layout.percent_fuel:.2f}% > max {layout.max_percent_fuel:.2f}%)"
        )

    pitch_cm = shared_stack_thickness_cm(setup)
    fuel_thickness_cm, photovoltaic_thickness_cm = fuel_and_tpv_thickness_cm(setup)
    columns = max(1, min(3, int(round(setup.columns))))
    conical_pitch_deg = float(config.simulation.conical_pitch)
    z_scale = _z_scaling(conical_pitch_deg)
    # Vertical period of one slice (paper core_vertical_height).
    period_cm = pitch_cm * z_scale
    n_slices = _slice_count(setup.stack_m, period_cm)
    stack_height_cm = n_slices * period_cm
    half_period = period_cm / 2.0

    r_in_cm = layout.r_inner * 100.0
    r_out_cm = layout.r_outer * 100.0
    r_mid_cm = 0.5 * (r_in_cm + r_out_cm)
    use_periodic_cones = abs(conical_pitch_deg) >= 1e-12
    # Shift so the slice midplane at the fuel radius passes through world z = 0.
    tan_pitch = math.tan(math.radians(conical_pitch_deg)) if use_periodic_cones else 0.0
    z_shift = r_mid_cm * tan_pitch

    # Open the fill's outer sheets against the root periodic cones (no second
    # coincident surface). The hole stays axially bounded so it cannot reach
    # the cone apex on the axis.
    slice_universe, tracked, _ = _one_disk_universe(
        layout,
        setup.layers,
        pitch_cm,
        materials_dict,
        material_choice,
        conical_pitch_deg,
        open_period=use_periodic_cones,
    )
    half_bc = half_period

    if use_periodic_cones:
        # One shell. The periodic cones replace the flat-slab layer stack.
        n_layers = 1
        column_fill: openmc.Universe = slice_universe
    else:
        n_layers, start_index = _transport_layer_count(
            period_cm, r_out_cm, conical_pitch_deg
        )
        column_fill = _build_column_stack_universe(
            slice_universe,
            pitch_cm,
            n_layers,
            start_index,
            r_out_cm,
            conical_pitch_deg,
        )

    poses = column_poses(columns, layout.r_outer)
    # Put world (0,0,0) at column-0 fuel mid-annulus so the default
    # IndependentSource Point(0,0,0) starts inside fissionable fuel.
    ox, oy, _oz = _fuel_mid_world_cm(layout, *poses[0])

    shifted: List[Tuple[float, float, float]] = []
    extent = 0.0
    for x_m, y_m, rot_deg in poses:
        cx = x_m * 100.0 - ox
        cy = y_m * 100.0 - oy
        shifted.append((cx, cy, rot_deg))
        extent = max(extent, math.hypot(cx, cy) + r_out_cm)
    extent += 10.0

    # Flat pitch keeps periodic planes. A cone pitch puts one periodic z-cone
    # pair on each column, coaxial with that column. The pair is one period apart.
    z_low = None
    z_high = None
    if not use_periodic_cones:
        z_low = openmc.ZPlane(z0=-half_period, boundary_type="periodic")
        z_high = openmc.ZPlane(z0=half_period, boundary_type="periodic")
        z_low.periodic_surface = z_high

    # 3) Root instantiates the column fill once per reactor cylinder.
    # Column footprints use r_out only — centers are 2*r_out apart (rims touch).
    column_cells: List[openmc.Cell] = []
    for index, (cx, cy, rot_deg) in enumerate(shifted):
        col_cyl = -openmc.ZCylinder(x0=cx, y0=cy, r=r_out_cm)
        if use_periodic_cones:
            r2 = 1.0 / tan_pitch**2
            cone_lo = openmc.ZCone(
                x0=cx,
                y0=cy,
                z0=z_shift - half_bc,
                r2=r2,
                boundary_type="periodic",
                name=f"period_lo_{index}",
            )
            cone_hi = openmc.ZCone(
                x0=cx,
                y0=cy,
                z0=z_shift + half_bc,
                r2=r2,
                boundary_type="periodic",
                name=f"period_hi_{index}",
            )
            cone_lo.periodic_surface = cone_hi
            # Downward nappe: outside the lower-apex cone and inside the upper one.
            region = col_cyl & +cone_lo & -cone_hi
            translation_z = z_shift
        else:
            region = col_cyl & +z_low & -z_high
            translation_z = 0.0
        cell = openmc.Cell(
            name=f"column_{index}",
            region=region,
            fill=column_fill,
        )
        cell.translation = (cx, cy, translation_z)
        if abs(rot_deg) > 1e-9:
            cell.rotation = (0.0, 0.0, rot_deg)
        column_cells.append(cell)

    if use_periodic_cones:
        # The shell droops by R·tan(pitch). Vacuum planes sit just outside it.
        z_min = (z_shift - half_bc) - r_out_cm * tan_pitch
        z_max = z_shift + half_bc
        margin = 1.0
        z_vac_lo = openmc.ZPlane(z0=z_min - margin, boundary_type="vacuum")
        z_vac_hi = openmc.ZPlane(z0=z_max + margin, boundary_type="vacuum")
        world = -openmc.ZCylinder(r=extent, boundary_type="vacuum") & +z_vac_lo & -z_vac_hi
        bound_z = (z_min - margin, z_max + margin)
    else:
        world = -openmc.ZCylinder(r=extent, boundary_type="vacuum") & +z_low & -z_high
        bound_z = (-half_period, half_period)
    columns_union = column_cells[0].region
    for cell in column_cells[1:]:
        columns_union = columns_union | cell.region
    void_cell = openmc.Cell(
        name="world_void",
        region=world & ~columns_union,
        fill=materials_dict[material_choice.void],
    )
    root = openmc.Universe(cells=[*column_cells, void_cell])
    geometry = openmc.Geometry(root, merge_surfaces=True, surface_precision=5)

    # Sheet volumes above are for one column. Each column instantiates the same cells.
    seen: set[int] = set()
    for cell_list in tracked.values():
        for cell in cell_list:
            ident = id(cell)
            if cell.volume is None or ident in seen:
                continue
            cell.volume *= columns
            seen.add(ident)

    for name in material_choice.model_dump().values():
        tracked.setdefault(name, [])

    axial = "periodic z-cones" if use_periodic_cones else f"{n_layers}× boundary_layer"
    print(
        f"App-slice transport: {axial} "
        f"over one period {period_cm:.3f} cm "
        f"(material pitch {pitch_cm:.3f} cm, conical_pitch {conical_pitch_deg}°); "
        f"{columns}× column(s); engineering stack {stack_height_cm:.3f} cm "
        f"({n_slices} periods from stack_m); "
        f"origin = column-0 fuel mid (shift {-ox:.3f}, {-oy:.3f}, 0) cm"
    )

    ll = (-extent, -extent, bound_z[0])
    ur = (extent, extent, bound_z[1])
    return MakeAppSliceGeometryResult(
        geometry=geometry,
        universe=root,
        tracked_cells=tracked,
        bounding_box=(ll, ur),
        render_radius=extent,
        render_height=(bound_z[1] - bound_z[0]) * 1.05,
        render_origin=(0.0, 0.0, 0.5 * (bound_z[0] + bound_z[1])),
        layout=layout,
        pitch_cm=pitch_cm,
        fuel_thickness_cm=fuel_thickness_cm,
        photovoltaic_thickness_cm=photovoltaic_thickness_cm,
        vertical_core_height_cm=period_cm,
        rotary_axle_radius_cm=layout.r_inner * 100.0,
    )
