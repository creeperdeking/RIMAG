"""Left-panel geometry controls and saved configurations."""

from __future__ import annotations

import streamlit as st

from configurations import list_configurations
from ui.layers import (
    confirm_delete_configuration,
    on_load_configuration,
    on_save_configuration,
    thickness_warning,
)
from ui.widgets import (
    _starting_b_percent,
    _starting_ratio_percent,
    bounded_slider,
    saved_flag,
)


def render_sidebar(layer_cm: float | None, layer_totals: list[tuple[str, float]]) -> dict:
    """Draw the sidebar and return the values the rest of the app needs."""
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

    return {
        "moderator": moderator,
        "absorber": absorber,
        "reflector": reflector,
        "b_pct": b_pct,
        "b": b,
        "w": w,
        "ratio_pct": ratio_pct,
        "tpv_density": tpv_density,
        "tpv_eff_pct": tpv_eff_pct,
        "stack_m": stack_m,
        "columns": columns,
        "show_dims": show_dims,
    }


def inject_styles() -> None:
    """Compact sidebar and results-panel styling."""
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
