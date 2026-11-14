"""Fuel-tab charts, TRISO stack updates, and burnup time."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from constants import LAYER_FALLBACK_COLORS
from geometry import (
    burnup_days,
    format_burnup_time,
    triso_fuel_layers,
    triso_particle_layout,
    uranium_inventory_kg,
)
from ui.layers import bump_layer_widgets, same_layers
from ui.materials import material_fact
from ui.widgets import _reload_share


def fuel_burnup_time(
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
) -> tuple[str, str | None]:
    """Years and months the fuel-layer uranium lasts at the overview thermal power.

    Returns the burnup-time label and an optional caption. ``thermal_kw`` is the
    Zones overview thermal power, in kW. Density comes from the material library.
    """
    if thermal_kw is None or pitch_cm is None:
        return "—", "Shown once Zones overview has a thermal power."
    if not specs:
        return "—", "Material densities are unavailable."
    mass_kg, _counted, skipped = uranium_inventory_kg(
        rows, fuel_area, n_columns, height_m, pitch_cm, specs, mixed
    )
    extra = ""
    if skipped:
        names = ", ".join(f"'{name}'" for name in skipped)
        verb = "is" if len(skipped) == 1 else "are"
        extra = f" {names} {verb} left out of the fuel mass."
    if mass_kg <= 0:
        return "—", "This layer has no uranium-bearing material." + extra
    if thermal_kw <= 0:
        return "—", "Thermal power is zero." + extra
    # Same integer burnup the Fuel setup tab displays. The shown time is that
    # full life multiplied by the reload fraction.
    specific = round(specific_burnup)
    days = burnup_days(mass_kg, specific, thermal_kw) * _reload_share(reload_label)
    return format_burnup_time(days), None


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
        color = fact["color"] if fact else LAYER_FALLBACK_COLORS.get(name, "#94a3b8")
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
    if not same_layers(rows, layers):
        st.session_state.groups["fuel"] = layers
        bump_layer_widgets()
    return layers, particle_in_cylinder, hm_fraction
