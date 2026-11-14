"""Hollow-disk reactor slice calculator.

Run from this directory: ``python -m streamlit run app.py``.
"""

from __future__ import annotations

import json
import sys

import streamlit as st

# The running server keeps local modules after the first import, so a signature
# change would stay invisible until restart. Drop geometry before each script run.
sys.modules.pop("geometry", None)

from geometry import compute_layout_for_ratio
from tabs.designer import render_designer_tab
from tabs.fuel import render_fuel_tab
from tabs.overview import render_overview_tab
from ui.layers import group_thicknesses, shared_thickness, sync_groups_from_widgets
from ui.sidebar import inject_styles, render_sidebar

st.set_page_config(page_title="Hollow disk zones", layout="wide")
inject_styles()

sync_groups_from_widgets()
layer_totals = group_thicknesses(st.session_state.groups)
layer_cm = shared_thickness(layer_totals)

with st.sidebar:
    side = render_sidebar(layer_cm, layer_totals)

layout = compute_layout_for_ratio(
    side["moderator"],
    side["b"],
    side["w"],
    side["ratio_pct"] / 100,
    side["reflector"],
    side["absorber"],
)

# At the feasible limit, zone 2 is exactly zero; float error can leave a tiny remainder.
zone2_gone = layout.opposite_area <= 1e-6 * layout.total_area
opposite_area = 0.0 if zone2_gone else layout.opposite_area
# Each slice has two faces. 1 W/cm² over 1 m² is 10 kW.
slice_power = 2 * side["tpv_density"] * 10 * opposite_area * side["columns"]
if layer_cm is None:
    n_slices = None
    stack_power = None
else:
    n_slices = side["stack_m"] / (layer_cm / 100)
    stack_power = slice_power * n_slices
# Cell density is electrical. Core thermal power is that output divided by the TPV efficiency.
thermal_power = None if stack_power is None else stack_power / (side["tpv_eff_pct"] / 100)

overview_tab, fuel_tab, designer_tab = st.tabs(
    ["Zones overview", "Fuel setup", "Layer designer"],
    key="tab",
    bind="query-params",
)

with overview_tab:
    render_overview_tab(
        layout=layout,
        show_dims=side["show_dims"],
        columns=side["columns"],
        opposite_area=opposite_area,
        thermal_power=thermal_power,
        stack_power=stack_power,
        n_slices=n_slices,
        layer_cm=layer_cm,
        stack_m=side["stack_m"],
    )

with fuel_tab:
    fuel = render_fuel_tab(
        layout=layout,
        columns=side["columns"],
        stack_m=side["stack_m"],
        layer_cm=layer_cm,
        thermal_power=thermal_power,
    )

with designer_tab:
    render_designer_tab(
        layer_cm=layer_cm,
        layer_totals=layer_totals,
        specs=fuel["specs"],
        mixed=fuel["mixed"],
    )

st.query_params.update(
    a=f"{side['moderator']:.2f}",
    abs=f"{side['absorber']:.2f}",
    refl=f"{side['reflector']:.2f}",
    b_pct=f"{side['b_pct']:.0f}",
    w=f"{side['w']:.2f}",
    ratio_pct=f"{side['ratio_pct']:.0f}",
    tpv_density=f"{side['tpv_density']:.2f}",
    tpv_eff_pct=f"{side['tpv_eff_pct']:.0f}",
    enrichment_pct=f"{fuel['enrichment_pct']:.1f}",
    packing_pct=f"{fuel['packing_pct']:.0f}",
    hm_particle_pct=f"{fuel['hm_particle_pct']:.0f}",
    cylinder_diameter_mm=f"{fuel['cylinder_diameter_mm']:.1f}",
    wall_margin_mm=f"{fuel['wall_margin_mm']:.1f}",
    compact_spacing_mm=f"{fuel['compact_spacing_mm']:.1f}",
    reload_fraction=st.session_state.reload_fraction,
    layer_cm="" if layer_cm is None else f"{layer_cm:.2f}",
    layers=json.dumps(
        {
            group_id: [{"n": layer["name"], "cm": round(layer["cm"], 4)} for layer in rows]
            for group_id, rows in st.session_state.groups.items()
        },
        separators=(",", ":"),
    ),
    stack_m=f"{side['stack_m']:.1f}",
    columns=f"{side['columns']:.0f}",
    dims="1" if side["show_dims"] else "0",
    **({"cfg": st.session_state.loaded_cfg} if st.session_state.get("loaded_cfg") else {}),
)
if not st.session_state.get("loaded_cfg"):
    st.query_params.pop("cfg", None)
st.query_params.pop("percent_fuel", None)
st.query_params.pop("ratio", None)
st.query_params.pop("b", None)
