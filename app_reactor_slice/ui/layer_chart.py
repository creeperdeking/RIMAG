"""Stacked thickness chart for the layer designer."""

from __future__ import annotations

import plotly.graph_objects as go

from constants import LAYER_GROUPS
from ui.materials import material_fact


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
