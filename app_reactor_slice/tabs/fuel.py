"""Fuel setup tab: TRISO packing, compact preview, and burnup."""

from __future__ import annotations

import streamlit as st

from configurations import RELOAD_FRACTIONS
from geometry import ZoneLayout
from ui.fuel_charts import (
    apply_triso_fuel,
    build_compact_section,
    build_fuel_preview,
    fuel_burnup_time,
)
from ui.materials import material_library
from ui.widgets import bounded_slider


def render_fuel_tab(
    *,
    layout: ZoneLayout,
    columns: int,
    stack_m: float,
    layer_cm: float | None,
    thermal_power: float | None,
) -> dict:
    """Draw the fuel tab and return the values that persist in the page address."""
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
        burnup_card = st.container()
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
    burnup_time, burnup_note = fuel_burnup_time(
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
    with burnup_card:
        with st.container(border=True):
            burnup_col, time_col = st.columns(2)
            burnup_col.metric("Burnup", f"{burnup:,.0f} MWd/kgHM")
            time_col.metric("Burnup time", burnup_time)
        if burnup_note:
            st.caption(burnup_note)
        else:
            st.caption("Burnup is the enrichment fraction multiplied by 1200.")

    return {
        "enrichment_pct": enrichment_pct,
        "packing_pct": packing_pct,
        "hm_particle_pct": hm_particle_pct,
        "cylinder_diameter_mm": cylinder_diameter_mm,
        "wall_margin_mm": wall_margin_mm,
        "compact_spacing_mm": compact_spacing_mm,
        "specs": specs,
        "mixed": mixed,
    }
