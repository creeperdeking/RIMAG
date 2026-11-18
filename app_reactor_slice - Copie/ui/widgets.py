"""Sliders and small display helpers shared by the sidebar and tabs."""

from __future__ import annotations

import html

import streamlit as st


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



def saved_flag(name: str, default: bool) -> bool:
    raw = st.query_params.get(name)
    if raw is None:
        return default
    return raw == "1"
