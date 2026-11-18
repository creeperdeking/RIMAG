"""Layer designer tab: editable stacks and thickness chart."""

from __future__ import annotations

import streamlit as st

from constants import LAYER_GROUPS, LAYER_MATCH_NOTE
from layer_editor import mount_layer_list
from ui.layer_chart import build_layer_figure
from ui.layers import add_layer, thickness_warning
from ui.materials import material_lines


def render_designer_tab(
    *,
    layer_cm: float | None,
    layer_totals: list[tuple[str, float]],
    specs: dict,
    mixed: dict,
) -> None:
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
                st.button(
                    "Add material",
                    key=f"ladd_{group_id}",
                    on_click=add_layer,
                    args=(group_id,),
                )
    with preview_col:
        st.plotly_chart(
            build_layer_figure(st.session_state.groups, layer_cm, specs, mixed),
            width="stretch",
            alt="Stacked thickness of the fuel, reflector, shield, and TPV layers",
        )
