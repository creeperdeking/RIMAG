"""Zones overview tab: disk drawing, power results, and Blender copy."""

from __future__ import annotations

import streamlit as st

from blender_clipboard import SIDES, BlenderClipboardError, copy_columns_to_blender
from constants import LAYER_MATCH_NOTE
from geometry import ZoneLayout
from ui.widgets import format_power
from ui.zone_chart import build_figure, column_poses


def render_overview_tab(
    *,
    layout: ZoneLayout,
    show_dims: bool,
    columns: int,
    opposite_area: float,
    thermal_power: float | None,
    stack_power: float | None,
    n_slices: float | None,
    layer_cm: float | None,
    stack_m: float,
) -> None:
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
            lines = "".join(
                f"<div><span>{label}</span><b>{value}</b></div>" for label, value in rows
            )
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
