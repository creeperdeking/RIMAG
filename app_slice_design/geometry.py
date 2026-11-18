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


def _slab(z0: float, z1: float, conical_pitch_deg: float = 0.0) -> openmc.Region:
    """Region between two axial bounds (planes or cones) in material z."""
    return +_layer_surface(z0, conical_pitch_deg) & -_layer_surface(z1, conical_pitch_deg)


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
    if resolved == "Void":
        return material_choice.void
    if zone_id == "fuel":
        if resolved == "Uranium Dioxide":
            return material_choice.fuel
        return material_choice.fuel_cladding
    if zone_id == "tpv":
        if resolved == "InGaAs":
            return material_choice.photovoltaic
        return material_choice.coolant
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
) -> None:
    if fill_name not in materials_dict:
        raise ValueError(f"Material '{fill_name}' not in materials_dict")
    cell = openmc.Cell(name=name, region=region, fill=materials_dict[fill_name])
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
) -> None:
    if not spans:
        return
    sector = _union_regions([_angular_sector(a0, a1) for a0, a1 in spans])
    if sector is None:
        return
    ring = _annulus(r_in_cm, r_out_cm) & sector
    rows = stack_with_disk(zone_rows, disk_rows)
    z = z_bot
    zone_count = len(zone_rows)
    for index, row in enumerate(rows):
        if row.cm <= 0:
            continue
        layer_zone = zone_id if index < zone_count else "disk"
        slab = _slab(z, z + row.cm, conical_pitch_deg)
        fill_name = _fill_name_for_zone(layer_zone, row.name, material_choice)
        _add_cell(
            cells,
            tracked,
            materials_dict,
            fill_name,
            ring & slab,
            name=f"{zone_id}_{index}_{fill_name}",
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
) -> None:
    """Approximate hole fills with chord planes (fuel at +y)."""
    cuts = center_cuts(layout)
    r_in_cm = layout.r_inner * 100.0
    z_bot = -pitch_cm / 2.0
    z_top = pitch_cm / 2.0
    inside = -openmc.ZCylinder(r=r_in_cm) & _slab(z_bot, z_top, conical_pitch_deg)

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
        )

    _build_hole_cells(
        layout,
        pitch_cm,
        materials_dict,
        material_choice,
        tracked,
        cells,
        conical_pitch_deg,
    )

    # Outer void padding inside the disk universe footprint (for transforms).
    pad = 2.0
    outside = (
        -openmc.ZCylinder(r=r_out_cm + pad)
        & +openmc.ZCylinder(r=r_out_cm)
        & _slab(z_bot, z_bot + pitch_cm, conical_pitch_deg)
    )
    _add_cell(
        cells,
        tracked,
        materials_dict,
        material_choice.void,
        outside,
        "disk_outer_void",
    )

    return openmc.Universe(cells=cells), dict(tracked), cells


def _slice_count(stack_m: float, period_cm: float) -> int:
    """How many identical pitch-tall slice universes fit in the stack height."""
    if period_cm <= 0:
        raise ValueError("period_cm must be positive")
    return max(1, int(round((stack_m * 100.0) / period_cm)))


def _build_column_stack_universe(
    slice_universe: openmc.Universe,
    pitch_cm: float,
    n_slices: int,
    r_out_cm: float,
    conical_pitch_deg: float,
) -> openmc.Universe:
    """Repeat the same slice universe upward; every vertical layer is identical."""
    z_scale = _z_scaling(conical_pitch_deg)
    half_mat = n_slices * pitch_cm / 2.0
    col_cyl = -openmc.ZCylinder(r=r_out_cm + 1.0)
    surfaces = [
        _layer_surface(-half_mat + k * pitch_cm, conical_pitch_deg)
        for k in range(n_slices + 1)
    ]
    stack_cells: List[openmc.Cell] = []
    for k in range(n_slices):
        z_center_mat = -half_mat + pitch_cm / 2.0 + k * pitch_cm
        region = col_cyl & +surfaces[k] & -surfaces[k + 1]
        cell = openmc.Cell(
            name=f"slice_{k}",
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
    half_stack = stack_height_cm / 2.0

    # 1) One pitch-tall slice universe (shared by every vertical layer).
    slice_universe, tracked, _ = _one_disk_universe(
        layout,
        setup.layers,
        pitch_cm,
        materials_dict,
        material_choice,
        conical_pitch_deg,
    )

    r_out_cm = layout.r_outer * 100.0
    # 2) One column = n_slices fills of that same slice universe.
    column_universe = _build_column_stack_universe(
        slice_universe,
        pitch_cm,
        n_slices,
        r_out_cm,
        conical_pitch_deg,
    )

    poses = column_poses(columns, layout.r_outer)
    extent = 0.0
    for x_m, y_m, _rot in poses:
        extent = max(extent, math.hypot(x_m, y_m) * 100.0 + r_out_cm)
    extent += 10.0

    # Periodic over the full stack height (flat ZPlanes, as in the paper).
    # Layer tilts live on the cones inside slice_universe / column stack.
    z_low = openmc.ZPlane(z0=-half_stack, boundary_type="periodic")
    z_high = openmc.ZPlane(z0=half_stack, boundary_type="periodic")
    z_low.periodic_surface = z_high

    # 3) Root instantiates the same column_universe once per reactor cylinder.
    column_cells: List[openmc.Cell] = []
    for index, (x_m, y_m, rot_deg) in enumerate(poses):
        cx, cy = x_m * 100.0, y_m * 100.0
        col_cyl = -openmc.ZCylinder(x0=cx, y0=cy, r=r_out_cm + 1.0)
        region = col_cyl & +z_low & -z_high
        cell = openmc.Cell(
            name=f"column_{index}",
            region=region,
            fill=column_universe,
        )
        cell.translation = (cx, cy, 0.0)
        if abs(rot_deg) > 1e-9:
            cell.rotation = (0.0, 0.0, rot_deg)
        column_cells.append(cell)

    world = -openmc.ZCylinder(r=extent, boundary_type="vacuum") & +z_low & -z_high
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

    for name in material_choice.model_dump().values():
        tracked.setdefault(name, [])

    print(
        f"App-slice stack: {n_slices}× shared slice_universe "
        f"(material pitch {pitch_cm:.3f} cm, conical_pitch {conical_pitch_deg}°, "
        f"vertical period {period_cm:.3f} cm) inside one column_universe; "
        f"{columns}× column_universe instance(s); "
        f"stack height {stack_height_cm:.3f} cm"
    )

    # Bounding box grows with cone flare at the outer radius.
    flare = _cone_extra_height(extent, conical_pitch_deg)
    ll = (-extent, -extent, -half_stack - flare)
    ur = (extent, extent, half_stack + flare)
    return MakeAppSliceGeometryResult(
        geometry=geometry,
        universe=root,
        tracked_cells=tracked,
        bounding_box=(ll, ur),
        render_radius=extent,
        render_height=(stack_height_cm + 2.0 * flare) * 1.05,
        render_origin=(0.0, 0.0, 0.0),
        layout=layout,
        pitch_cm=pitch_cm,
        fuel_thickness_cm=fuel_thickness_cm,
        photovoltaic_thickness_cm=photovoltaic_thickness_cm,
        vertical_core_height_cm=period_cm,
        rotary_axle_radius_cm=layout.r_inner * 100.0,
    )
