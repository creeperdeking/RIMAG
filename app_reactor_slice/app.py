import json
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from geometry import ZoneLayout, compute_layout, percent_fuel_for_ratio

ZONE_COLORS = {
    "fuel": "#f59e0b",
    "opposite": "#3b82f6",
    "reflector": "#0f766e",
    "gap": "#94a3b8",
}
LAYER_COLORS = ["#334155", "#f59e0b", "#3b82f6", "#94a3b8", "#10b981", "#e11d48", "#8b5cf6"]


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
        # Reflector sits against the fuel; shielding is on its far side.
        refl_left = (fuel[1], fuel[1] + refl_deg)
        shield_left = (refl_left[1], refl_left[1] + shield_deg)
        refl_right = (fuel[0] - refl_deg, fuel[0])
        shield_right = (refl_right[0] - shield_deg, refl_right[0])

        # Flat shield edge: whichever of the fuel-clearance line and the
        # TPV/shielding chord lies further toward the TPV. Clearance from the
        # nearest fuel point is the shielding thickness plus the reflector
        # thickness. The edge is never short of the junction, and it crosses
        # the inner rim past that junction when the clearance line is further.
        y_fuel = ri * math.cos(layout.fuel_angle / 2)
        y_meet = -ri * math.cos(layout.opposite_angle / 2)
        y_shield = min(y_fuel - (layout.a + layout.reflector), y_meet)
        cuts = [("gap", "Shielding", y_shield)]
        if layout.reflector > 1e-9:
            # Straight reflector edge through the inner-rim points where the
            # reflector meets the shielding.
            y_refl = ri * math.cos(layout.fuel_angle / 2 + layout.reflector_angle)
            cuts.append(("reflector", "Reflector", y_refl))
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
                    legendgroup=color_key if color_key == "gap" else "reflector",
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
            "Shielding",
            layout.gap_area / 2,
            layout.gap_angle,
            legendgroup="gap",
        )
        add_zone(
            shield_right,
            ZONE_COLORS["gap"],
            "Shielding",
            layout.gap_area / 2,
            layout.gap_angle,
            showlegend=False,
            legendgroup="gap",
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

        # Inner-corner chords of each layer, each equal to that layer's thickness.
        if show_dims:
            dim_spans = [
                (shield_left, "shielding thickness", layout.a, legend),
                (shield_right, "shielding thickness", layout.a, False),
            ]
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
        dim_parts.append((y_after_refl, y_after_shield, "shield"))
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


def bounded_slider(
    key: str,
    label: str,
    low: float,
    high: float,
    default: float,
    step: float,
    number_format: str | None = None,
) -> float:
    """Slider whose saved value is pulled back inside the current limits."""
    current = st.session_state[key] if key in st.session_state else saved_number(key, default, low, high, step)
    st.session_state[key] = on_grid(current, low, high, step)
    if number_format is None:
        return st.slider(label, low, high, step=step, key=key)
    return st.slider(label, low, high, step=step, key=key, format=number_format)


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


def initial_layers() -> list[dict]:
    raw = st.query_params.get("layers")
    if raw:
        try:
            data = json.loads(raw)
            layers = [{"name": str(item["n"]), "cm": float(item["cm"])} for item in data]
            if layers and all(layer["cm"] > 0 for layer in layers):
                return layers
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    cm = 1.0
    if "layer_cm" in st.query_params:
        try:
            cm = float(st.query_params["layer_cm"])
        except ValueError:
            cm = 1.0
    return [{"name": "Reference", "cm": max(cm, 0.01)}]


def clear_layer_widgets() -> None:
    for key in list(st.session_state):
        if key.startswith("lname_") or key.startswith("lcm_"):
            del st.session_state[key]


def sync_layers_from_widgets() -> None:
    if "layers" not in st.session_state:
        st.session_state.layers = initial_layers()
        return
    count = len(st.session_state.layers)
    if count and all(
        f"lname_{i}" in st.session_state and f"lcm_{i}" in st.session_state for i in range(count)
    ):
        st.session_state.layers = [
            {
                "name": str(st.session_state[f"lname_{i}"]).strip() or "Layer",
                "cm": max(float(st.session_state[f"lcm_{i}"]), 0.01),
            }
            for i in range(count)
        ]


def add_layer() -> None:
    st.session_state.layers.append(
        {"name": f"Layer {len(st.session_state.layers)}", "cm": 0.1}
    )
    clear_layer_widgets()


def remove_layer(index: int) -> None:
    if index > 0 and index < len(st.session_state.layers):
        st.session_state.layers.pop(index)
        clear_layer_widgets()


def build_layer_figure(layers: list[dict]) -> go.Figure:
    fig = go.Figure()
    for i, layer in enumerate(layers):
        fig.add_trace(
            go.Bar(
                x=["Slice"],
                y=[layer["cm"]],
                name=f"{layer['name']}  {layer['cm']:.2f} cm",
                marker_color=LAYER_COLORS[i % len(LAYER_COLORS)],
                hovertemplate=f"<b>{layer['name']}</b><br>{layer['cm']:.2f} cm<extra></extra>",
            )
        )
    total = sum(layer["cm"] for layer in layers)
    fig.update_layout(
        barmode="stack",
        height=520,
        margin=dict(l=10, r=130, t=36, b=10),
        title=f"Layer thickness {total:.2f} cm",
        yaxis=dict(title="cm", rangemode="tozero"),
        xaxis=dict(visible=False),
        legend=dict(orientation="v", yanchor="top", y=1, x=1.02, xanchor="left"),
        plot_bgcolor="white",
    )
    return fig


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
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.35rem; }
    [data-testid="stSidebar"] h1 {
        font-size: 1.15rem;
        line-height: 1.25;
        margin: 0 0 0.15rem;
        padding: 0;
    }
    [data-testid="stSidebar"] label { font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

sync_layers_from_widgets()
layer_cm = sum(layer["cm"] for layer in st.session_state.layers)

with st.sidebar:
    st.title("Hollow disk zone calculator")
    a = bounded_slider(
        "a",
        "shielding thickness (m)",
        1.0,
        4.0,
        2.0,
        0.1,
    )
    reflector = bounded_slider(
        "refl",
        "reflector thickness (m)",
        0.0,
        4.0,
        0.5,
        0.1,
    )
    if "b_pct" not in st.session_state:
        st.session_state.b_pct = _starting_b_percent(a)
    b_pct = bounded_slider("b_pct", "b (%)", 1, 100, 100, 1, "%.0f%%")
    b = a * b_pct / 100
    w = bounded_slider("w", "w  (rim width)", 0.3, 3.0, 1.0, 0.1)
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
    )
    tpv_density = bounded_slider(
        "tpv_density",
        "TPV power density (kW/m²)",
        0.1,
        30.0,
        8.9,
        0.1,
    )
    st.caption(f"Layer thickness {layer_cm:.2f} cm")
    stack_m = bounded_slider(
        "stack_m",
        "stack height (m)",
        0.1,
        20.0,
        1.0,
        0.1,
    )
    columns = int(bounded_slider("columns", "columns", 1, 3, 1, 1, "%.0f"))
    show_dims = st.checkbox("Show dimension lines", value=saved_flag("dims", True))

st.query_params.update(
    a=f"{a:.2f}",
    refl=f"{reflector:.2f}",
    b_pct=f"{b_pct:.0f}",
    w=f"{w:.2f}",
    ratio_pct=f"{ratio_pct:.0f}",
    tpv_density=f"{tpv_density:.1f}",
    layer_cm=f"{layer_cm:.2f}",
    layers=json.dumps(
        [{"n": layer["name"], "cm": round(layer["cm"], 4)} for layer in st.session_state.layers],
        separators=(",", ":"),
    ),
    stack_m=f"{stack_m:.1f}",
    columns=f"{columns:.0f}",
    dims="1" if show_dims else "0",
)
st.query_params.pop("percent_fuel", None)
st.query_params.pop("ratio", None)
st.query_params.pop("b", None)

layout = compute_layout(
    a, b, w, percent_fuel_for_ratio(a, b, ratio_pct / 100, reflector), reflector
)

# At the feasible limit, zone 2 is exactly zero; float error can leave a tiny remainder.
zone2_gone = layout.opposite_area <= 1e-6 * layout.total_area
opposite_area = 0.0 if zone2_gone else layout.opposite_area
# Each slice has two faces, so the active TPV area is twice the drawn zone.
slice_power = 2 * tpv_density * opposite_area * columns
n_slices = stack_m / (layer_cm / 100)
stack_power = slice_power * n_slices

overview_tab, designer_tab = st.tabs(["Zones overview", "Layer designer"])

with overview_tab:
    chart_col, result_col = st.columns([2, 1], vertical_alignment="top")
    with chart_col:
        st.plotly_chart(build_figure(layout, show_dims, columns), width="stretch")
    with result_col:
        with st.container(border=True):
            st.subheader("Results")
            rows = (
                ("Per slice", format_power(slice_power)),
                ("Stack", format_power(stack_power)),
                ("Fuel", f"{layout.fuel_area * columns:.3g} m²"),
                ("Reflector", f"{layout.reflector_area * columns:.3g} m²"),
                ("TPV", f"{opposite_area * columns:.3g} m²"),
                ("Shielding", f"{layout.gap_area * columns:.3g} m²"),
                ("Disk", f"{layout.total_area * columns:.3g} m²"),
                ("Diameter", f"{2 * layout.r_outer:.3g} m"),
            )
            lines = "".join(f"<div><span>{label}</span><b>{value}</b></div>" for label, value in rows)
            st.markdown(
                f"<div class='results-compact'>{lines}"
                f"<p>{columns} column{'s' if columns != 1 else ''}, {n_slices:.4g} slices "
                f"of {layer_cm:.2f} cm in {stack_m:.1f} m, both TPV faces</p></div>",
                unsafe_allow_html=True,
            )

with designer_tab:
    editor_col, preview_col = st.columns([1, 1], vertical_alignment="top")
    with editor_col:
        st.caption("The slice thickness is the reference layer plus every layer added on it.")
        name_head, cm_head, _action_head = st.columns([2.2, 1.1, 1.15])
        name_head.markdown("**Layer**")
        cm_head.markdown("**cm**")
        for i, layer in enumerate(st.session_state.layers):
            if f"lname_{i}" not in st.session_state:
                st.session_state[f"lname_{i}"] = layer["name"]
            if f"lcm_{i}" not in st.session_state:
                st.session_state[f"lcm_{i}"] = float(layer["cm"])
            name_col, cm_col, action_col = st.columns([2.2, 1.1, 1.15])
            name_col.text_input("Layer", key=f"lname_{i}", label_visibility="collapsed")
            cm_col.number_input(
                "cm",
                key=f"lcm_{i}",
                min_value=0.01,
                max_value=20.0,
                step=0.05,
                format="%.2f",
                label_visibility="collapsed",
            )
            if i == 0:
                action_col.caption("base")
            else:
                action_col.button(
                    ":material/close:",
                    key=f"lrm_{i}",
                    help="Remove this layer",
                    on_click=remove_layer,
                    args=(i,),
                )
        st.button("Add layer", on_click=add_layer)
    with preview_col:
        st.plotly_chart(build_layer_figure(st.session_state.layers), width="stretch")