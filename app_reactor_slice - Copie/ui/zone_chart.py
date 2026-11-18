"""Zone overview Plotly figure for the hollow-disk columns."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from constants import ZONE_COLORS
from geometry import ZoneLayout, absorber_front, center_cuts


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
