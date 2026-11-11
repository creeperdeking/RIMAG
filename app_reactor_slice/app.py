import html
import json
import math
import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from blender_clipboard import SIDES, BlenderClipboardError, copy_columns_to_blender
from layer_editor import mount_layer_list
from configurations import (
    LAYER_IDS,
    NUMERIC_FIELDS,
    RELOAD_FRACTIONS,
    ConfigurationError,
    delete_configuration,
    list_configurations,
    load_configuration,
    save_configuration,
)
# The running server keeps this module after the first import, so a signature
# change would stay invisible until restart. Drop it before each script run.
sys.modules.pop("geometry", None)
from geometry import (
    ZoneLayout,
    absorber_front,
    burnup_days,
    center_cuts,
    compute_layout_for_ratio,
    format_burnup_time,
    triso_fuel_layers,
    triso_particle_layout,
    uranium_inventory_kg,
)

ZONE_COLORS = {
    "fuel": "#f59e0b",
    "opposite": "#3b82f6",
    "reflector": "#0f766e",
    "gap": "#94a3b8",
    "absorber": "#475569",
}
LAYER_GROUPS = (
    ("fuel", "Fuel layer", ("#f59e0b", "#d97706", "#b45309", "#fbbf24")),
    ("reflector", "Reflector layer", ("#0f766e", "#115e59", "#134e4a", "#14b8a6")),
    ("shield_moderator", "Shield moderator", ("#94a3b8", "#64748b", "#cbd5e1", "#475569")),
    ("shield_absorber", "Shield absorber", ("#475569", "#334155", "#1e293b", "#64748b")),
    ("tpv", "TPV layer", ("#3b82f6", "#2563eb", "#1d4ed8", "#60a5fa")),
)
DISK_GROUP = ("disk", "Disk layer", ("#000000", "#171717", "#404040", "#737373"))
EDITOR_GROUPS = (DISK_GROUP,) + LAYER_GROUPS
LAYER_MATCH_NOTE = (
    "The disk layer sits on top of every stack. Fuel, reflector, shield moderator, "
    "shield absorber, and TPV, each plus the disk, must have the same thickness."
)


def sector_outline(r_in: float, r_out: float, start_deg: float, end_deg: float, n: int = 240):
    """Closed outline of an annular sector, angles counter-clockwise from +x."""
    if end_deg < start_deg:
        end_deg += 360
    t = np.radians(np.linspace(start_deg, end_deg, n))
    xs = np.concatenate([r_out * np.cos(t), r_in * np.cos(t[::-1])])
    ys = np.concatenate([r_out * np.sin(t), r_in * np.sin(t[::-1])])
    return np.append(xs, xs[0]), np.append(ys, ys[0])


def polar(r: float, deg: float):
    rad = math.radians(deg)
    return r * math.cos(rad), r * math.sin(rad)


def rotate_points(xs, ys, rot_deg: float):
    th = math.radians(rot_deg)
    c, s = math.cos(th), math.sin(th)
    return c * xs - s * ys, s * xs + c * ys


def center_shield_cut(r: float, y_line: float, n: int = 200):
    """Fuel-side of the inner disk above a horizontal chord at ``y_line``.

    Fuel sits at +y. The chord is parallel to the old TPV-corner chord and is
    shifted toward the TPV. Returns the polygon and the chord endpoints, or the
    whole disk and no chord when the line falls outside the hole.
    """
    if y_line <= -r + 1e-9:
        t = np.linspace(0, 2 * np.pi, n)
        xs = r * np.cos(t)
        ys = r * np.sin(t)
        return np.append(xs, xs[0]), np.append(ys, ys[0]), None
    y_line = min(y_line, r - 1e-9)
    half_x = math.sqrt(max(r * r - y_line * y_line, 0.0))
    right = math.degrees(math.atan2(y_line, half_x))
    left = math.degrees(math.atan2(y_line, -half_x))
    if left < right:
        left += 360
    t = np.radians(np.linspace(right, left, n))
    xs = np.append(r * np.cos(t), r * np.cos(t[0]))
    ys = np.append(r * np.sin(t), r * np.sin(t[0]))
    return xs, ys, ((half_x, y_line), (-half_x, y_line))


def column_poses(n: int, r_outer: float):
    """Place columns so each fuel zone points at the shared middle and the rims touch."""
    apart = 2 * r_outer
    if n <= 1:
        return [(0.0, 0.0, 0.0)]
    if n == 2:
        # Upper disk fuel points down, lower disk fuel points up.
        return [(0.0, apart / 2, 180.0), (0.0, -apart / 2, 0.0)]
    radius = apart / math.sqrt(3)
    poses = []
    for k in range(3):
        theta = -90 + k * 120
        poses.append(
            (
                radius * math.cos(math.radians(theta)),
                radius * math.sin(math.radians(theta)),
                theta + 90,
            )
        )
    return poses


def build_figure(layout: ZoneLayout, show_dims: bool, columns: int) -> go.Figure:
    fuel_half = math.degrees(layout.fuel_angle) / 2
    opp_half = math.degrees(layout.opposite_angle) / 2
    ri, ro = layout.r_inner, layout.r_outer
    fig = go.Figure()

    def draw_disk(rot: float, cx: float, cy: float, legend: bool):
        fuel = (90 - fuel_half + rot, 90 + fuel_half + rot)
        opposite = (270 - opp_half + rot, 270 + opp_half + rot)
        refl_deg = math.degrees(layout.reflector_angle)
        shield_deg = math.degrees(layout.gap_angle)
        abs_deg = math.degrees(layout.absorber_angle)
        # Fuel, reflector, shield moderator, shield absorber, then TPV.
        refl_left = (fuel[1], fuel[1] + refl_deg)
        shield_left = (refl_left[1], refl_left[1] + shield_deg)
        abs_left = (shield_left[1], shield_left[1] + abs_deg)
        refl_right = (fuel[0] - refl_deg, fuel[0])
        shield_right = (refl_right[0] - shield_deg, refl_right[0])
        abs_right = (shield_right[0] - abs_deg, shield_right[0])

        # Moderator and reflector are flat chords. The absorber is drawn later,
        # over them, so its curved front stays intact.
        edges = center_cuts(layout)
        cuts = [("gap", "Shield moderator", edges.moderator_y)]
        if edges.reflector_y is not None:
            cuts.append(("reflector", "Reflector", edges.reflector_y))
        chords = []
        for color_key, name, y_line in cuts:
            xs, ys, chord = center_shield_cut(ri, y_line)
            xs, ys = rotate_points(xs, ys, rot)
            if chord is not None:
                chords.append(chord)
            fig.add_trace(
                go.Scatter(
                    x=xs + cx,
                    y=ys + cy,
                    fill="toself",
                    fillcolor=ZONE_COLORS[color_key],
                    mode="lines",
                    line=dict(width=0),
                    name=name,
                    legendgroup=color_key if color_key in ("gap", "absorber") else "reflector",
                    showlegend=False,
                    hoveron="fills",
                    hovertemplate=f"<b>{name}</b><extra></extra>",
                )
            )

        def add_zone(span, color, name, area, angle_rad, showlegend=True, legendgroup=None):
            if angle_rad <= 1e-9:
                return
            xs, ys = sector_outline(ri, ro, *span)
            fig.add_trace(
                go.Scatter(
                    x=xs + cx,
                    y=ys + cy,
                    fill="toself",
                    fillcolor=color,
                    mode="lines",
                    line=dict(color="white", width=2),
                    name=name,
                    legendgroup=legendgroup or name,
                    showlegend=legend and showlegend,
                    hoveron="fills",
                    hovertemplate=f"<b>{name}</b><br>area: {area:.4g} m²<extra></extra>",
                )
            )

        add_zone(fuel, ZONE_COLORS["fuel"], "Fuel", layout.fuel_area, layout.fuel_angle)
        add_zone(
            opposite,
            ZONE_COLORS["opposite"],
            "TPV",
            layout.opposite_area,
            layout.opposite_angle,
        )
        add_zone(
            refl_left,
            ZONE_COLORS["reflector"],
            "Reflector",
            layout.reflector_area / 2,
            layout.reflector_angle,
            legendgroup="reflector",
        )
        add_zone(
            refl_right,
            ZONE_COLORS["reflector"],
            "Reflector",
            layout.reflector_area / 2,
            layout.reflector_angle,
            showlegend=False,
            legendgroup="reflector",
        )
        add_zone(
            shield_left,
            ZONE_COLORS["gap"],
            "Shield moderator",
            layout.gap_area / 2,
            layout.gap_angle,
            legendgroup="gap",
        )
        add_zone(
            shield_right,
            ZONE_COLORS["gap"],
            "Shield moderator",
            layout.gap_area / 2,
            layout.gap_angle,
            showlegend=False,
            legendgroup="gap",
        )
        add_zone(
            abs_left,
            ZONE_COLORS["absorber"],
            "Shield absorber",
            layout.absorber_area / 2,
            layout.absorber_angle,
            legendgroup="absorber",
        )
        add_zone(
            abs_right,
            ZONE_COLORS["absorber"],
            "Shield absorber",
            layout.absorber_area / 2,
            layout.absorber_angle,
            showlegend=False,
            legendgroup="absorber",
        )

        t = np.linspace(0, 2 * np.pi, 361)
        for r in (ri, ro):
            fig.add_trace(
                go.Scatter(
                    x=cx + r * np.cos(t),
                    y=cy + r * np.sin(t),
                    mode="lines",
                    line=dict(color="#1e293b", width=1.5),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        for chord in chords:
            (x0, y0), (x1, y1) = chord
            (x0, x1), (y0, y1) = rotate_points(np.array([x0, x1]), np.array([y0, y1]), rot)
            fig.add_trace(
                go.Scatter(
                    x=[x0 + cx, x1 + cx],
                    y=[y0 + cy, y1 + cy],
                    mode="lines",
                    line=dict(color="#1e293b", width=1.5),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        # Absorber in the hole: every point within one absorber thickness of the
        # TPV arc. Concentric arc across the middle, circular cap at each corner.
        front = absorber_front(layout)
        if front:
            xs = np.array([p[0] for p in front] + [front[0][0]])
            ys = np.array([p[1] for p in front] + [front[0][1]])
            xs, ys = rotate_points(xs, ys, rot)
            fig.add_trace(
                go.Scatter(
                    x=xs + cx,
                    y=ys + cy,
                    fill="toself",
                    fillcolor=ZONE_COLORS["absorber"],
                    mode="lines",
                    line=dict(color="#1e293b", width=1.5),
                    name="Shield absorber",
                    legendgroup="absorber",
                    showlegend=False,
                    hoveron="fills",
                    hovertemplate="<b>Shield absorber</b><extra></extra>",
                )
            )

        # Inner-corner chords of each layer, each equal to that layer's thickness.
        if show_dims:
            dim_spans = [
                (shield_left, "shield moderator thickness", layout.a, legend),
                (shield_right, "shield moderator thickness", layout.a, False),
            ]
            if layout.absorber_angle > 1e-9:
                dim_spans.extend(
                    [
                        (abs_left, "shield absorber thickness", layout.absorber, legend),
                        (abs_right, "shield absorber thickness", layout.absorber, False),
                    ]
                )
            if layout.reflector_angle > 1e-9:
                dim_spans = [
                    (refl_left, "reflector thickness", layout.reflector, legend),
                    (refl_right, "reflector thickness", layout.reflector, False),
                    *dim_spans,
                ]
            for span, label, length, showlegend in dim_spans:
                x0, y0 = polar(ri, span[0])
                x1, y1 = polar(ri, span[1])
                fig.add_trace(
                    go.Scatter(
                        x=[x0 + cx, x1 + cx],
                        y=[y0 + cy, y1 + cy],
                        mode="lines+markers",
                        line=dict(color="#dc2626", width=2, dash="dot"),
                        marker=dict(size=7, color="#dc2626"),
                        name=label,
                        legendgroup=label,
                        showlegend=showlegend,
                        hovertemplate=f"{label}: {length:.4g} m<extra></extra>",
                    )
                )

    for i, (cx, cy, rot) in enumerate(column_poses(columns, ro)):
        draw_disk(rot, cx, cy, legend=i == 0)

    if show_dims and columns == 1:
        dim_color = "#334155"
        y_after_refl = ri - layout.reflector
        y_after_shield = y_after_refl - layout.a
        dx = -ri * 0.08
        dim_parts = []
        if layout.reflector > 1e-9:
            dim_parts.append((ri, y_after_refl, "refl"))
        dim_parts.append((y_after_refl, y_after_shield, "mod"))
        if layout.absorber > 1e-9:
            y_abs_far = min(ri, -ri + layout.absorber)
            dim_parts.append((-ri, y_abs_far, "abs"))
            y_gap = center_cuts(layout).moderator_y
            if y_gap > y_abs_far + 1e-6:
                dim_parts.append((y_abs_far, y_gap, "b"))
        else:
            dim_parts.append((y_after_shield, -ri, "b"))
        for y_from, y_to, label in dim_parts:
            if abs(y_from - y_to) < 1e-9:
                continue
            fig.add_annotation(
                x=dx, y=y_to, ax=dx, ay=y_from,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowside="end+start",
                arrowwidth=1.5, arrowcolor=dim_color, text="",
            )
            fig.add_annotation(
                x=dx - ri * 0.1,
                y=(y_from + y_to) / 2,
                text=f"<i>{label}</i>",
                showarrow=False,
                font=dict(color=dim_color, size=15),
            )

        x_dim = ro * 1.12
        fig.add_annotation(
            x=x_dim, y=-ro, ax=x_dim, ay=-ri,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowside="end+start",
            arrowwidth=1.5, arrowcolor=dim_color, text="",
        )
        fig.add_annotation(
            x=x_dim + ro * 0.07, y=-(ri + ro) / 2, text="<i>w</i>",
            showarrow=False, font=dict(color=dim_color, size=15),
        )
        for y in (-ri, -ro):
            fig.add_shape(
                type="line", x0=0, x1=x_dim, y0=y, y1=y,
                line=dict(color=dim_color, width=1, dash="dot"),
            )

    reach = ro * 1.3
    for cx, cy, _rot in column_poses(columns, ro):
        reach = max(reach, math.hypot(cx, cy) + ro * 1.2)
    fig.update_layout(
        xaxis=dict(range=[-reach, reach], visible=False),
        yaxis=dict(range=[-reach, reach], visible=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=10, b=10),
        height=640,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.02, xanchor="center", x=0.5),
        dragmode="pan",
    )
    return fig


def on_grid(value: float, low: float, high: float, step: float) -> float:
    """Clamp onto the slider range and its step size."""
    if high < low:
        high = low
    value = min(high, max(low, value))
    if step <= 0:
        return value
    steps = round((value - low) / step)
    snapped = low + steps * step
    return min(high, max(low, round(snapped, 10)))


def saved_number(name: str, default: float, low: float, high: float, step: float) -> float:
    """Last value stored in the page address, snapped onto the slider steps."""
    raw = st.query_params.get(name)
    if raw is None:
        return on_grid(default, low, high, step)
    try:
        value = float(raw)
    except ValueError:
        return on_grid(default, low, high, step)
    return on_grid(value, low, high, step)


def _slider_text(value: float, step: float, number_format: str | None) -> str:
    if number_format:
        return number_format % value
    step_text = f"{step:.10f}".rstrip("0").rstrip(".")
    decimals = len(step_text.split(".")[1]) if "." in step_text else 0
    return f"{value:.{decimals}f}"


def bounded_slider(
    key: str,
    label: str,
    low: float,
    high: float,
    default: float,
    step: float,
    number_format: str | None = None,
    compact: bool = False,
) -> float:
    """Slider whose saved value is pulled back inside the current limits."""
    current = st.session_state[key] if key in st.session_state else saved_number(key, default, low, high, step)
    st.session_state[key] = on_grid(current, low, high, step)
    if compact:
        reading = html.escape(_slider_text(st.session_state[key], step, number_format))
        st.markdown(
            f'<div class="compact-slider"><span>{html.escape(label)}</span><span>{reading}</span></div>',
            unsafe_allow_html=True,
        )
    if number_format is None:
        return st.slider(
            label,
            low,
            high,
            step=step,
            key=key,
            label_visibility="collapsed" if compact else "visible",
        )
    return st.slider(
        label,
        low,
        high,
        step=step,
        key=key,
        format=number_format,
        label_visibility="collapsed" if compact else "visible",
    )


def _starting_b_percent(a: float) -> float:
    """Restore b as a percent of a, including an older absolute b address."""
    if "b_pct" in st.query_params:
        return saved_number("b_pct", 100, 1, 100, 1)
    raw = st.query_params.get("b")
    if raw is not None and a > 0:
        try:
            return on_grid(float(raw) / a * 100, 1, 100, 1)
        except ValueError:
            pass
    return 100


def _starting_ratio_percent() -> float:
    """Restore the fuel/TPV percentage, including the older ratio address."""
    if "ratio_pct" in st.query_params:
        return saved_number("ratio_pct", 30, 10, 50, 1)
    raw = st.query_params.get("ratio")
    if raw is not None:
        try:
            return on_grid(float(raw) * 100, 10, 50, 1)
        except ValueError:
            pass
    return 30


def format_power(kw: float) -> str:
    if kw >= 1000:
        return f"{kw / 1000:.4g} MW"
    return f"{kw:.4g} kW"


def format_mass(kg: float) -> str:
    if kg >= 1000:
        return f"{kg / 1000:.4g} t"
    return f"{kg:.4g} kg"


def _fuel_mass_text(counted: list[tuple[str, float, float]]) -> str:
    """Mass of each uranium-bearing material at the density stored for it."""
    parts = [
        f"{format_mass(kg)} of {name} ({density:.4g} g/cm³)"
        for name, kg, density in counted
    ]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _reload_share(label: str) -> float:
    """Turn a reload label such as '1/4' into a fraction of the full burnup time."""
    numerator, denominator = label.split("/")
    return float(numerator) / float(denominator)


def show_fuel_burnup(
    rows: list[dict],
    *,
    fuel_area: float,
    n_columns: int,
    height_m: float,
    pitch_cm: float | None,
    specific_burnup: float,
    thermal_kw: float | None,
    specs: dict,
    mixed: dict,
    reload_label: str,
) -> None:
    """Years and months the fuel-layer uranium lasts at the overview thermal power.

    ``thermal_kw`` is the Zones overview thermal power, in kW. It is not derived again here.
    Density comes from the material library already loaded for this enrichment.
    """
    if thermal_kw is None or pitch_cm is None:
        st.metric("Burnup time", "—", border=True)
        st.caption("Shown once Zones overview has a thermal power.")
        return
    if not specs:
        st.metric("Burnup time", "—", border=True)
        st.caption("Material densities are unavailable.")
        return
    mass_kg, counted, skipped = uranium_inventory_kg(
        rows, fuel_area, n_columns, height_m, pitch_cm, specs, mixed
    )
    extra = ""
    if skipped:
        names = ", ".join(f"'{name}'" for name in skipped)
        verb = "is" if len(skipped) == 1 else "are"
        extra = f" {names} {verb} left out of the fuel mass."
    if mass_kg <= 0:
        st.metric("Burnup time", "—", border=True)
        st.caption("This layer has no uranium-bearing material." + extra)
        return
    if thermal_kw <= 0:
        st.metric("Burnup time", "—", border=True)
        st.caption("Thermal power is zero." + extra)
        return
    # Same integer burnup the Fuel setup tab displays. The shown time is that
    # full life multiplied by the reload fraction.
    specific = round(specific_burnup)
    days = burnup_days(mass_kg, specific, thermal_kw) * _reload_share(reload_label)
    st.metric("Burnup time", format_burnup_time(days), border=True)
    st.caption(
        f"{_fuel_mass_text(counted)} at {format_power(thermal_kw)} thermal, "
        f"{specific:,.0f} MWd/kgHM, reload {reload_label}."
        + extra
    )


def default_groups() -> dict[str, list[dict]]:
    return {
        group_id: [{"name": title, "cm": 1.0}]
        for group_id, title, _colors in EDITOR_GROUPS
    }


def _is_placeholder_stack(rows: list[dict], title: str) -> bool:
    """The one-centimeter titled row used when a stack is missing from the address."""
    return (
        len(rows) == 1
        and rows[0].get("name") == title
        and abs(float(rows[0].get("cm", 0)) - 1.0) < 1e-6
    )


def _layers_from_saved_configuration() -> dict[str, list[dict]] | None:
    """Layers of the configuration named in the address, or the only saved one."""
    cfg = st.query_params.get("cfg")
    if not cfg:
        names = list_configurations()
        cfg = names[0] if len(names) == 1 else None
    if not cfg:
        return None
    try:
        layers = load_configuration(cfg)["layers"]
    except ConfigurationError:
        return None
    st.session_state.loaded_cfg = cfg
    return layers


def initial_groups() -> dict[str, list[dict]]:
    raw = st.query_params.get("layers")
    groups = None
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            groups = {}
            address_has_disk = False
            for group_id, title, _colors in EDITOR_GROUPS:
                rows = data.get(group_id) or []
                try:
                    parsed = [{"name": str(item["n"]), "cm": float(item["cm"])} for item in rows]
                except (KeyError, TypeError, ValueError):
                    parsed = []
                if parsed and all(row["cm"] > 0 for row in parsed):
                    groups[group_id] = parsed
                    if group_id == "disk":
                        address_has_disk = True
                else:
                    groups[group_id] = [{"name": title, "cm": 1.0}]
    if groups is None:
        groups = default_groups()
        address_has_disk = False
    # A reload keeps the old address. Stacks that are still the titled 1 cm
    # placeholder are replaced from the save so they match the file.
    saved = _layers_from_saved_configuration()
    if saved:
        for group_id, title, _colors in EDITOR_GROUPS:
            if _is_placeholder_stack(groups[group_id], title) and saved.get(group_id):
                groups[group_id] = [dict(row) for row in saved[group_id]]
    if not address_has_disk:
        _drop_repeated_disk(groups)
    return groups


def _drop_repeated_disk(groups: dict[str, list[dict]]) -> None:
    """Remove a copied void / disk / void tail once the disk has its own list."""
    disk = groups.get("disk") or []
    if not disk:
        return
    for group_id, _title, _colors in LAYER_GROUPS:
        rows = groups.get(group_id) or []
        if len(rows) > len(disk) and _same_layers(rows[-len(disk) :], disk):
            groups[group_id] = rows[: -len(disk)]


def _same_layers(left: list[dict], right: list[dict]) -> bool:
    if len(left) != len(right):
        return False
    for one, other in zip(left, right):
        if one.get("name") != other.get("name"):
            return False
        if abs(float(one.get("cm", 0)) - float(other.get("cm", 0))) > 1e-4:
            return False
    return True


def bump_layer_widgets() -> None:
    """Drop the current layer widgets so the next run builds them from groups."""
    st.session_state.layer_epoch = int(st.session_state.get("layer_epoch", 0)) + 1
    for key in list(st.session_state):
        if key.startswith(("lname_", "lcm_")):
            del st.session_state[key]


def sync_groups_from_widgets() -> None:
    if "groups" not in st.session_state:
        st.session_state.groups = initial_groups()
        return
    groups = st.session_state.groups
    for group_id, title, _colors in EDITOR_GROUPS:
        if not groups.get(group_id):
            groups[group_id] = [{"name": title, "cm": 1.0}]
    st.session_state.groups = groups


def add_layer(group_id: str) -> None:
    st.session_state.groups[group_id].append({"name": "Material", "cm": 0.1})


def group_thicknesses(groups: dict[str, list[dict]]) -> list[tuple[str, float]]:
    """Total cm of each zone stack plus the shared disk, from fuel through TPV."""
    disk_cm = sum(layer["cm"] for layer in groups.get("disk") or [])
    return [
        (title, sum(layer["cm"] for layer in groups[group_id]) + disk_cm)
        for group_id, title, _colors in LAYER_GROUPS
    ]


def shared_thickness(totals: list[tuple[str, float]]) -> float | None:
    """The common thickness when every layer matches to the nearest 0.01 cm."""
    if len({round(cm, 2) for _title, cm in totals}) != 1:
        return None
    return totals[0][1]


def thickness_warning(totals: list[tuple[str, float]]) -> str:
    parts = [f"{title} is {cm:.2f} cm" for title, cm in totals]
    return ", ".join(parts[:-1]) + ", and " + parts[-1] + "."


def _project_root():
    return Path(__file__).resolve().parents[1]


def material_library(enrichment_pct: float):
    """Compositions, densities, and colors from common_lib.materials."""
    import sys

    root = str(_project_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from common_lib.materials import material_definitions
    except ModuleNotFoundError:
        return {}, {}
    return material_definitions(enrichment_pct)


def _library_entry(name: str, specs: dict, mixed: dict):
    if name in specs:
        return specs[name], None
    base, separator, suffix = name.rpartition(" ")
    if separator and suffix.isdigit() and base in specs:
        return specs[base], None
    mix = mixed.get(name)
    if mix is None and separator and suffix.isdigit():
        mix = mixed.get(base)
    return None, mix


def _composition_text(spec) -> str:
    parts = []
    for part in spec.composition:
        proportion = part.proportion
        amount = "" if proportion in (None, 1) else f" {proportion:.4g}"
        enrichment = ""
        if part.enrichment is not None:
            enrichment = f" ({part.enrichment:.4g}% enriched)"
        parts.append(f"{part.atom.name}{amount}{enrichment}")
    return ", ".join(parts)


def material_fact(name: str, specs: dict, mixed: dict) -> dict | None:
    """Color, composition, and density for one library material. Disk is not in the library."""
    spec, mix = _library_entry(name, specs, mixed)
    if spec is not None:
        return {
            "color": spec.color or "orange",
            "composition": _composition_text(spec),
            "density": spec.density,
        }
    if mix is None:
        return {"color": "black", "composition": "", "density": None} if name == "Disk" else None
    weights = [w for w in mix.proportions if w > 0]
    if not weights:
        return None
    volume = 0.0
    described = []
    color = "orange"
    for component, proportion in zip(mix.materials, mix.proportions):
        component_spec = specs.get(component)
        if component_spec is None or proportion <= 0:
            return None
        if component == mix.materials[0] and component_spec.color:
            color = component_spec.color
        volume += proportion / component_spec.density
        described.append(f"{proportion:.4g} {component}")
    total = sum(mix.proportions)
    return {
        "color": color,
        "composition": " + ".join(described),
        "density": total / volume if volume else None,
    }


def material_lines(rows: list[dict], specs: dict, mixed: dict) -> list[str]:
    lines = []
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        fact = material_fact(name, specs, mixed)
        if fact is None or not fact["composition"]:
            continue
        density = fact["density"]
        density_text = f" · {density:.4g} g/cm³" if density is not None else ""
        lines.append(f"{name}: {fact['composition']}{density_text}")
    return lines


def build_layer_figure(
    groups: dict[str, list[dict]],
    layer_cm: float | None,
    specs: dict,
    mixed: dict,
) -> go.Figure:
    fig = go.Figure()
    seen_names: set[str] = set()
    for group_id, title, colors in LAYER_GROUPS:
        stacked = list(groups[group_id]) + list(groups.get("disk") or [])
        for i, layer in enumerate(stacked):
            name = layer["name"]
            fact = material_fact(name, specs, mixed)
            color = fact["color"] if fact else colors[i % len(colors)]
            detail = ""
            if fact and fact["composition"]:
                detail = f"<br>{fact['composition']}"
                if fact["density"] is not None:
                    detail += f"<br>{fact['density']:.4g} g/cm³"
            fig.add_trace(
                go.Bar(
                    x=[title],
                    y=[layer["cm"]],
                    name=name,
                    legendgroup=name,
                    showlegend=name not in seen_names,
                    marker_color=color,
                    hovertemplate=f"<b>{name}</b>{detail}<br>{layer['cm']:.3f} cm<extra></extra>",
                )
            )
            seen_names.add(name)
    title = f"Layer thickness {layer_cm:.2f} cm" if layer_cm is not None else "Layers do not match"
    fig.update_layout(
        barmode="stack",
        height=520,
        margin=dict(l=10, r=150, t=36, b=10),
        title=title,
        yaxis=dict(title="cm", rangemode="tozero"),
        xaxis=dict(title=""),
        legend=dict(orientation="v", yanchor="top", y=1, x=1.02, xanchor="left"),
        plot_bgcolor="white",
    )
    return fig


def build_compact_section(
    diameter_mm: float,
    wall_margin_mm: float,
    spacing_mm: float,
    packing_pct: float,
    hm_particle_pct: float,
    specs: dict,
    mixed: dict,
) -> go.Figure:
    """Two fuel compacts in cross section, to scale in millimetres."""
    graphite = material_fact("Graphite", specs, mixed)
    uranium = material_fact("Uranium Dioxide", specs, mixed)
    graphite_color = graphite["color"] if graphite else "black"
    uranium_color = uranium["color"] if uranium else "green"
    diameter = float(diameter_mm)
    spacing = max(float(spacing_mm), 0.0)
    margin = max(float(wall_margin_mm), 0.0)
    pitch = diameter + spacing
    radius = diameter / 2.0
    usable = max(radius - margin, 0.0)
    particles = triso_particle_layout(diameter, margin, packing_pct, hm_particle_pct)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Graphite",
            marker=dict(size=12, color=graphite_color),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Uranium dioxide",
            marker=dict(size=12, color=uranium_color),
            hoverinfo="skip",
        )
    )
    width = diameter + pitch
    centers = (radius, radius + pitch)
    for center in centers:
        fig.add_shape(
            type="circle",
            x0=center - radius,
            y0=0,
            x1=center + radius,
            y1=diameter,
            fillcolor=graphite_color,
            line=dict(color="#d4d4d4", width=1),
            layer="below",
        )
        for x_pos, y_pos, particle_r, kernel_r in particles:
            fig.add_shape(
                type="circle",
                x0=center + x_pos - particle_r,
                y0=radius + y_pos - particle_r,
                x1=center + x_pos + particle_r,
                y1=radius + y_pos + particle_r,
                fillcolor="#52525b",
                line=dict(color="#52525b", width=0),
                layer="below",
            )
            if kernel_r > 0:
                fig.add_shape(
                    type="circle",
                    x0=center + x_pos - kernel_r,
                    y0=radius + y_pos - kernel_r,
                    x1=center + x_pos + kernel_r,
                    y1=radius + y_pos + kernel_r,
                    fillcolor=uranium_color,
                    line=dict(color=uranium_color, width=0),
                    layer="below",
                )
        if usable > 0:
            fig.add_shape(
                type="circle",
                x0=center - usable,
                y0=radius - usable,
                x1=center + usable,
                y1=radius + usable,
                fillcolor="rgba(0,0,0,0)",
                line=dict(color="#fbbf24", width=1.5, dash="dash"),
                layer="below",
            )
    hover_x = list(centers)
    hover_y = [radius, radius]
    hover_text = [
        f"Cylinder {diameter:.1f} mm<br>Wall margin {margin:.1f} mm",
        f"Cylinder {diameter:.1f} mm<br>Wall margin {margin:.1f} mm",
    ]
    if spacing > 0:
        hover_x.append(radius + diameter / 2 + spacing / 2)
        hover_y.append(radius)
        hover_text.append(f"Compact spacing {spacing:.1f} mm")
    if particles:
        sample = particles[0]
        hover_text.append(
            f"Packing {packing_pct:.0f}%<br>HM {hm_particle_pct:.0f}% of each particle"
        )
        hover_x.append(centers[0] + sample[0])
        hover_y.append(radius + sample[1])
    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            marker=dict(size=14, color="rgba(0,0,0,0)"),
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )
    pad = max(diameter * 0.08, 0.4)
    fig.update_layout(
        height=320,
        margin=dict(l=8, r=8, t=36, b=28),
        title="Compact cross section",
        legend=dict(orientation="h", yanchor="top", y=-0.22),
        plot_bgcolor="white",
        xaxis=dict(
            range=[-pad, width + pad],
            zeroline=False,
            showgrid=False,
            constrain="domain",
            ticksuffix=" mm",
        ),
        yaxis=dict(
            range=[-pad, diameter + pad],
            zeroline=False,
            showgrid=False,
            scaleanchor="x",
            scaleratio=1,
            constrain="domain",
            ticksuffix=" mm",
        ),
    )
    return fig


def build_fuel_preview(rows: list[dict], specs: dict, mixed: dict) -> go.Figure:
    """Stacked graphite, uranium dioxide, and graphite for the fuel setup tab."""
    fig = go.Figure()
    seen: set[str] = set()
    for layer in rows:
        name = str(layer["name"])
        fact = material_fact(name, specs, mixed)
        color = fact["color"] if fact else LAYER_MATERIAL_COLORS.get(name, "#94a3b8")
        cm = float(layer["cm"])
        fig.add_trace(
            go.Bar(
                x=["Fuel layer"],
                y=[cm],
                name=name,
                legendgroup=name,
                showlegend=name not in seen,
                marker_color=color,
                hovertemplate=f"<b>{name}</b><br>{cm:.3f} cm<extra></extra>",
            )
        )
        seen.add(name)
    fig.update_layout(
        barmode="stack",
        height=300,
        margin=dict(l=10, r=10, t=36, b=10),
        title="Fuel layer",
        yaxis=dict(title="cm", rangemode="tozero"),
        xaxis=dict(title=""),
        legend=dict(orientation="h", yanchor="top", y=-0.2),
        plot_bgcolor="white",
    )
    return fig


def apply_triso_fuel(
    diameter_mm: float,
    wall_margin_mm: float,
    spacing_mm: float,
    packing_pct: float,
    hm_particle_pct: float,
) -> tuple[list[dict], float, float]:
    """Replace the fuel stack with the cylinder-smeared TRISO sandwich."""
    layers, particle_in_cylinder, hm_fraction = triso_fuel_layers(
        diameter_mm, wall_margin_mm, spacing_mm, packing_pct, hm_particle_pct
    )
    rows = st.session_state.groups.get("fuel") or []
    if not _same_layers(rows, layers):
        st.session_state.groups["fuel"] = layers
        bump_layer_widgets()
    return layers, particle_in_cylinder, hm_fraction


def snapshot_configuration() -> dict:
    """Sidebar values and layer stacks."""
    layers = {}
    groups = st.session_state.get("groups") or {}
    for group_id in LAYER_IDS:
        rows = groups.get(group_id) or []
        layers[group_id] = [
            {"name": row.get("name"), "cm": row.get("cm")}
            for row in rows
        ]
    data = {key: st.session_state.get(key) for key in NUMERIC_FIELDS}
    data["reload_fraction"] = st.session_state.get("reload_fraction", "1/4")
    data["dims"] = bool(st.session_state.get("dims", True))
    data["layers"] = layers
    return data


def apply_configuration(data: dict) -> None:
    """Install a loaded configuration before the sidebar widgets are created."""
    for key in NUMERIC_FIELDS:
        st.session_state[key] = data[key]
    st.session_state.reload_fraction = data["reload_fraction"]
    st.session_state.dims = data["dims"]
    st.session_state.groups = data["layers"]
    bump_layer_widgets()


def on_save_configuration() -> None:
    try:
        path = save_configuration(st.session_state.get("save_name", ""), snapshot_configuration())
    except ConfigurationError as error:
        st.session_state.config_notice = ("error", str(error))
        return
    st.session_state.load_choice = path.stem
    st.session_state.config_notice = ("success", f"Saved {path.stem}.")


@st.dialog("Delete configuration")
def confirm_delete_configuration(name: str) -> None:
    st.write(f"Delete {name} from the save folder?")
    confirm, cancel = st.columns(2)
    if confirm.button("Delete", key="confirm_delete_config", type="primary"):
        try:
            deleted = delete_configuration(name)
        except ConfigurationError as error:
            st.error(str(error))
            return
        st.session_state.config_notice = ("success", f"Deleted {deleted}.")
        st.rerun()
    if cancel.button("Cancel", key="cancel_delete_config"):
        st.rerun()


def on_load_configuration() -> None:
    choice = st.session_state.get("load_choice")
    if not choice:
        st.session_state.config_notice = ("error", "Choose a saved configuration.")
        return
    try:
        data = load_configuration(choice)
    except ConfigurationError as error:
        st.session_state.config_notice = ("error", str(error))
        return
    apply_configuration(data)
    st.session_state.loaded_cfg = choice
    st.session_state.config_notice = ("success", f"Loaded {choice}.")


def saved_flag(name: str, default: bool) -> bool:
    raw = st.query_params.get(name)
    if raw is None:
        return default
    return raw == "1"


st.set_page_config(page_title="Hollow disk zones", layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.4rem; padding-bottom: 0.4rem; }
    .results-compact div {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 0.6rem;
        padding: 0.18rem 0;
        border-bottom: 1px solid rgba(49, 51, 63, 0.12);
        font-size: 0.92rem;
    }
    .results-compact b { white-space: nowrap; }
    .results-compact p {
        margin: 0.5rem 0 0;
        color: #64748b;
        font-size: 0.8rem;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.15rem; }
    [data-testid="stSidebar"] h1 {
        font-size: 1.15rem;
        line-height: 1.25;
        margin: 0 0 0.15rem;
        padding: 0;
    }
    [data-testid="stSidebar"] .compact-slider {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 0.6rem;
        margin: 0;
        font-size: 0.8rem;
        line-height: 1.2;
    }
    [data-testid="stSidebar"] .compact-slider span:last-child {
        font-weight: 600;
        white-space: nowrap;
    }
    [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.compact-slider),
    [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(h1) {
        min-height: 1.35rem;
    }
    [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stSlider"]) {
        min-height: 1.15rem;
    }
    [data-testid="stSidebar"] [data-testid="stSliderThumbValue"] { display: none; }
    [data-testid="stSidebar"] [data-testid="stSlider"] > div > div {
        padding-top: 0.15rem !important;
        padding-bottom: 0.2rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

sync_groups_from_widgets()
layer_totals = group_thicknesses(st.session_state.groups)
layer_cm = shared_thickness(layer_totals)

with st.sidebar:
    st.title("Hollow disk zone calculator")
    moderator = bounded_slider(
        "a",
        "shield moderator thickness (m)",
        1.0,
        4.0,
        2.0,
        0.1,
        compact=True,
    )
    absorber = bounded_slider(
        "abs",
        "shield absorber thickness (m)",
        0.01,
        0.5,
        0.01,
        0.01,
        compact=True,
    )
    reflector = bounded_slider(
        "refl",
        "reflector thickness (m)",
        0.1,
        1.0,
        0.5,
        0.1,
        compact=True,
    )
    if "b_pct" not in st.session_state:
        st.session_state.b_pct = _starting_b_percent(moderator)
    b_pct = bounded_slider("b_pct", "b (%)", 1, 100, 100, 1, "%.0f%%", compact=True)
    b = moderator * b_pct / 100
    w = bounded_slider("w", "w  (rim width)", 0.3, 3.0, 1.0, 0.1, compact=True)
    if "ratio_pct" not in st.session_state:
        st.session_state.ratio_pct = _starting_ratio_percent()
    ratio_pct = bounded_slider(
        "ratio_pct",
        "fuel / TPV",
        10,
        50,
        30,
        1,
        "%.0f%%",
        compact=True,
    )
    if "tpv_density" not in st.session_state:
        raw = st.query_params.get("tpv_density")
        try:
            value = float(raw) if raw is not None else 0.89
        except ValueError:
            value = 0.89
        st.session_state.tpv_density = value / 10 if value > 3.0 else value
    elif st.session_state.tpv_density > 3.0:
        st.session_state.tpv_density = st.session_state.tpv_density / 10
    tpv_density = bounded_slider(
        "tpv_density",
        "TPV power density (W/cm²)",
        0.01,
        3.0,
        0.89,
        0.01,
        compact=True,
    )
    tpv_eff_pct = bounded_slider(
        "tpv_eff_pct",
        "TPV efficiency",
        10,
        50,
        33,
        1,
        "%.0f%%",
        compact=True,
    )
    if layer_cm is None:
        st.warning(thickness_warning(layer_totals), title="Layers must have the same thickness")
    else:
        st.caption(f"Layer thickness {layer_cm:.2f} cm")
    stack_m = bounded_slider(
        "stack_m",
        "stack height (m)",
        0.1,
        20.0,
        1.0,
        0.1,
        compact=True,
    )
    columns = int(bounded_slider("columns", "columns", 1, 3, 1, 1, "%.0f", compact=True))
    if "dims" not in st.session_state:
        st.session_state.dims = saved_flag("dims", True)
    show_dims = st.checkbox("Show dimension lines", key="dims")

    st.divider()
    st.text_input("Configuration name", key="save_name")
    st.button(
        "Save",
        key="save_config",
        icon=":material/save:",
        width="stretch",
        on_click=on_save_configuration,
    )
    saved_names = list_configurations()
    if saved_names:
        if st.session_state.get("load_choice") not in saved_names:
            st.session_state.pop("load_choice", None)
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.selectbox("Saved configurations", saved_names, key="load_choice")
            if st.button(
                ":material/delete:",
                key="ask_delete_config",
                help="Delete this configuration",
            ):
                confirm_delete_configuration(st.session_state.load_choice)
        st.button(
            "Load",
            key="load_config",
            icon=":material/folder_open:",
            width="stretch",
            on_click=on_load_configuration,
        )
    else:
        st.session_state.pop("load_choice", None)
        st.caption("No saved configurations yet.")
    notice = st.session_state.pop("config_notice", None)
    if notice:
        kind, text = notice
        if kind == "error":
            st.error(text)
        else:
            st.success(text)
    st.caption("Configurations are stored in the save folder.")

layout = compute_layout_for_ratio(
    moderator, b, w, ratio_pct / 100, reflector, absorber
)

# At the feasible limit, zone 2 is exactly zero; float error can leave a tiny remainder.
zone2_gone = layout.opposite_area <= 1e-6 * layout.total_area
opposite_area = 0.0 if zone2_gone else layout.opposite_area
# Each slice has two faces. 1 W/cm² over 1 m² is 10 kW.
slice_power = 2 * tpv_density * 10 * opposite_area * columns
if layer_cm is None:
    n_slices = None
    stack_power = None
else:
    n_slices = stack_m / (layer_cm / 100)
    stack_power = slice_power * n_slices
# Cell density is electrical. Core thermal power is that output divided by the TPV efficiency.
thermal_power = None if stack_power is None else stack_power / (tpv_eff_pct / 100)

overview_tab, fuel_tab, designer_tab = st.tabs(
    ["Zones overview", "Fuel setup", "Layer designer"],
    key="tab",
    bind="query-params",
)

with overview_tab:
    chart_col, result_col = st.columns([2, 1], vertical_alignment="top")
    with chart_col:
        st.plotly_chart(build_figure(layout, show_dims, columns), width="stretch")
    with result_col:
        with st.container(border=True):
            st.subheader("Results")
            rows = (
                ("Thermal", "—" if thermal_power is None else format_power(thermal_power)),
                ("Stack", "—" if stack_power is None else format_power(stack_power)),
                ("Fuel", f"{layout.fuel_area * columns:.3g} m²"),
                ("Reflector", f"{layout.reflector_area * columns:.3g} m²"),
                ("TPV", f"{opposite_area * columns:.3g} m²"),
                ("Shield moderator", f"{layout.gap_area * columns:.3g} m²"),
                ("Shield absorber", f"{layout.absorber_area * columns:.3g} m²"),
                ("Disk", f"{layout.total_area * columns:.3g} m²"),
                ("Diameter", f"{2 * layout.r_outer:.3g} m"),
            )
            lines = "".join(f"<div><span>{label}</span><b>{value}</b></div>" for label, value in rows)
            if n_slices is None:
                note = LAYER_MATCH_NOTE
            else:
                note = (
                    f"{columns} column{'s' if columns != 1 else ''}, {n_slices:.4g} slices "
                    f"of {layer_cm:.2f} cm in {stack_m:.1f} m, both TPV faces"
                )
            st.markdown(
                f"<div class='results-compact'>{lines}<p>{note}</p></div>",
                unsafe_allow_html=True,
            )

    with st.container(horizontal=True, vertical_alignment="center"):
        copied = st.button(
            "Copy 3D model",
            key="copy_reactor_blend",
            icon=":material/content_copy:",
            help=(
                "Cylinder diameter is the disk diameter and height is the stack height. "
                "One object is copied per column."
            ),
        )
        st.caption(
            f"{SIDES} side faces, one cylinder per column. Paste in Blender's 3D View with Ctrl+V."
        )
    if copied:
        centers = [(x, y) for x, y, _rot in column_poses(columns, layout.r_outer)]
        try:
            with st.spinner("Copying the reactor into Blender"):
                copy_columns_to_blender(layout.r_outer, stack_m, centers)
        except BlenderClipboardError as error:
            st.error(str(error), title="Could not copy the 3D model")
        else:
            noun = "cylinder" if columns == 1 else "cylinders"
            st.toast(
                f"Copied {columns} {noun}. Paste in Blender's 3D View with Ctrl+V.",
                icon=":material/content_copy:",
                duration="long",
            )

with fuel_tab:
    setup_col, fuel_preview_col = st.columns([1.15, 1], vertical_alignment="top")
    with setup_col:
        enrichment_pct = bounded_slider(
            "enrichment_pct",
            "Fuel enrichment",
            0.1,
            20.0,
            5.0,
            0.1,
            "%.1f%%",
        )
        burnup = enrichment_pct / 100 * 1200
        st.metric("Burnup", f"{burnup:,.0f} MWd/kgHM", border=True)
        st.caption("Burnup is the enrichment fraction multiplied by 1200.")
        packing_pct = bounded_slider(
            "packing_pct",
            "Packing fraction",
            1,
            30,
            30,
            1,
            "%.0f%%",
        )
        hm_particle_pct = bounded_slider(
            "hm_particle_pct",
            "HM fraction per particle",
            20,
            60,
            30,
            1,
            "%.0f%%",
        )
        cylinder_diameter_mm = bounded_slider(
            "cylinder_diameter_mm",
            "Cylinder diameter",
            2.0,
            30.0,
            10.0,
            0.1,
            "%.1f mm",
        )
        wall_margin_mm = bounded_slider(
            "wall_margin_mm",
            "Fuel compact wall margin",
            0.0,
            5.0,
            0.5,
            0.1,
            "%.1f mm",
        )
        compact_spacing_mm = bounded_slider(
            "compact_spacing_mm",
            "Compact spacing",
            0.0,
            10.0,
            1.0,
            0.1,
            "%.1f mm",
        )
        if "reload_fraction" not in st.session_state:
            raw = st.query_params.get("reload_fraction")
            st.session_state.reload_fraction = raw if raw in RELOAD_FRACTIONS else "1/4"
        st.segmented_control(
            "Reload fraction",
            RELOAD_FRACTIONS,
            key="reload_fraction",
            required=True,
            width="content",
        )
    specs, mixed = material_library(enrichment_pct)
    fuel_rows, particle_in_cylinder, hm_fraction = apply_triso_fuel(
        cylinder_diameter_mm,
        wall_margin_mm,
        compact_spacing_mm,
        packing_pct,
        hm_particle_pct,
    )
    graphite_fraction = 1 - hm_fraction
    uo2_to_graphite = hm_fraction / graphite_fraction if graphite_fraction else float("inf")
    with fuel_preview_col:
        st.plotly_chart(
            build_compact_section(
                cylinder_diameter_mm,
                wall_margin_mm,
                compact_spacing_mm,
                packing_pct,
                hm_particle_pct,
                specs,
                mixed,
            ),
            width="stretch",
            alt="Cross section of two fuel compacts with wall margin and uranium dioxide kernels",
        )
        st.caption(
            "Two compacts. The dashed circle is the wall margin, and the kernels are the heavy metal in each particle."
        )
        st.plotly_chart(
            build_fuel_preview(fuel_rows, specs, mixed),
            width="stretch",
            alt="Graphite, uranium dioxide, and graphite in the fuel layer",
        )
        st.caption(
            f"TRISO particles fill {particle_in_cylinder * 100:.1f}% of each cylinder. "
            f"Heavy metal is {hm_fraction * 100:.2f}% of the {cylinder_diameter_mm / 10:.2f} cm fuel layer. "
            f"UO2 / graphite = {uo2_to_graphite:.3f}."
        )
        show_fuel_burnup(
            fuel_rows,
            fuel_area=layout.fuel_area,
            n_columns=columns,
            height_m=stack_m,
            pitch_cm=layer_cm,
            specific_burnup=burnup,
            thermal_kw=thermal_power,
            specs=specs,
            mixed=mixed,
            reload_label=st.session_state.reload_fraction,
        )

with designer_tab:
    editor_col, preview_col = st.columns([1.35, 1], vertical_alignment="top")
    with editor_col:
        st.caption(
            LAYER_MATCH_NOTE
            + " That thickness is the slice pitch. Drag a handle to reorder a material. The top row is the bottom of the bar."
        )
        disk_rows = st.session_state.groups["disk"]
        disk_cm = sum(layer["cm"] for layer in disk_rows)
        with st.container(border=True):
            st.markdown(f"**Disk layer** · {disk_cm:.2f} cm")
            mount_layer_list("disk", "Disk layer", disk_rows)
            for line in material_lines(disk_rows, specs, mixed):
                st.caption(line)
            st.button("Add material", key="ladd_disk", on_click=add_layer, args=("disk",))
        if layer_cm is None:
            st.warning(thickness_warning(layer_totals), title="Layers must have the same thickness")
        for group_id, title, _colors in LAYER_GROUPS:
            if group_id == "fuel":
                continue
            rows = st.session_state.groups[group_id]
            own_cm = sum(layer["cm"] for layer in rows)
            with st.container(border=True):
                st.markdown(f"**{title}** · {own_cm:.2f} cm")
                mount_layer_list(group_id, title, rows)
                for line in material_lines(rows, specs, mixed):
                    st.caption(line)
                st.button("Add material", key=f"ladd_{group_id}", on_click=add_layer, args=(group_id,))
    with preview_col:
        st.plotly_chart(
            build_layer_figure(st.session_state.groups, layer_cm, specs, mixed),
            width="stretch",
            alt="Stacked thickness of the fuel, reflector, shield, and TPV layers",
        )

st.query_params.update(
    a=f"{moderator:.2f}",
    abs=f"{absorber:.2f}",
    refl=f"{reflector:.2f}",
    b_pct=f"{b_pct:.0f}",
    w=f"{w:.2f}",
    ratio_pct=f"{ratio_pct:.0f}",
    tpv_density=f"{tpv_density:.2f}",
    tpv_eff_pct=f"{tpv_eff_pct:.0f}",
    enrichment_pct=f"{enrichment_pct:.1f}",
    packing_pct=f"{packing_pct:.0f}",
    hm_particle_pct=f"{hm_particle_pct:.0f}",
    cylinder_diameter_mm=f"{cylinder_diameter_mm:.1f}",
    wall_margin_mm=f"{wall_margin_mm:.1f}",
    compact_spacing_mm=f"{compact_spacing_mm:.1f}",
    reload_fraction=st.session_state.reload_fraction,
    layer_cm="" if layer_cm is None else f"{layer_cm:.2f}",
    layers=json.dumps(
        {
            group_id: [{"n": layer["name"], "cm": round(layer["cm"], 4)} for layer in rows]
            for group_id, rows in st.session_state.groups.items()
        },
        separators=(",", ":"),
    ),
    stack_m=f"{stack_m:.1f}",
    columns=f"{columns:.0f}",
    dims="1" if show_dims else "0",
    **({"cfg": st.session_state.loaded_cfg} if st.session_state.get("loaded_cfg") else {}),
)
if not st.session_state.get("loaded_cfg"):
    st.query_params.pop("cfg", None)
st.query_params.pop("percent_fuel", None)
st.query_params.pop("ratio", None)
st.query_params.pop("b", None)