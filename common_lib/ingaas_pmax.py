"""Remaining InGaAs electrical power from an OpenMC damage-energy tally.

Wang et al., Progress in Nuclear Energy 163 (2023) 104807, fit the XPNR
fluence as P/P0 = 1 - 0.08302 * ln(1 + phi / 2.193e14 m^-2). The fluence
here is damage energy per atom divided by a provisional XPNR-averaged
MT=444 cross section for In0.68Ga0.32As. The atom count uses this model's
In0.53Ga0.47As, which is the alloy the tally actually scores.
"""

from __future__ import annotations

import math

NA = 6.02214076e23
# materials.py InGaAs: In 0.53, Ga 0.47, As 1. Two atoms per formula unit.
MODEL_INGAAS_M_G_MOL = 0.53 * 114.818 + 0.47 * 69.723 + 74.9216

WANG_C = 0.08302
WANG_D_M2 = 2.193e14
K_BASELINE = 4.89621364e-24
K_FAST = 5.84473946e-24
K_TRUNCATED = 5.71757122e-24
# First and last measured XPNR fluences in the Wang fit, m^-2.
FLUENCE_LO_M2 = 4.56e14
FLUENCE_HI_M2 = 1.0e17


def model_ingaas_atoms(volume_cm3: float, density_g_cm3: float) -> float:
    """Atoms in the tallied InGaAs. Volume is cm^3 and density is g/cm^3."""
    if (
        not math.isfinite(volume_cm3)
        or not math.isfinite(density_g_cm3)
        or volume_cm3 <= 0.0
        or density_g_cm3 <= 0.0
    ):
        return float("nan")
    return 2.0 * density_g_cm3 * volume_cm3 * NA / MODEL_INGAAS_M_G_MOL


def remaining_pmax(fluence_m2: float) -> float:
    if not math.isfinite(fluence_m2) or fluence_m2 < 0.0:
        return float("nan")
    return 1.0 - WANG_C * math.log1p(fluence_m2 / WANG_D_M2)


def pmax_from_damage(
    td_ev_per_source: float,
    td_std_ev_per_source: float,
    source_per_s: float,
    n_atoms: float,
    dose_s: float,
    k_ev_m2: float = K_BASELINE,
) -> dict | None:
    """Baseline remaining fraction, plus the two calibration sensitivities.

    ``td`` is the cell-total damage-energy tally, eV per source particle.
    The returned CI is a 95% relative percent of the remaining fraction and
    covers Monte Carlo statistics only.
    """
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (source_per_s, n_atoms, k_ev_m2)
    ):
        return None
    if not math.isfinite(dose_s) or dose_s < 0.0:
        return None
    if not math.isfinite(td_ev_per_source) or td_ev_per_source < 0.0:
        return None
    accumulated = td_ev_per_source * source_per_s * dose_s / n_atoms
    accumulated_sd = abs(td_std_ev_per_source) * source_per_s * dose_s / n_atoms
    fluence = accumulated / k_ev_m2
    remaining = remaining_pmax(fluence)
    denom = WANG_D_M2 * k_ev_m2 + accumulated
    if (
        math.isfinite(remaining)
        and remaining > 0.0
        and denom > 0.0
        and math.isfinite(accumulated_sd)
    ):
        # dP/dA = -C / (D*K + A)
        p_sd = WANG_C * accumulated_sd / denom
        ci95_pct = 100.0 * 1.96 * p_sd / remaining
    else:
        ci95_pct = float("nan")
    return {
        "remaining": remaining,
        "ci95_pct": ci95_pct,
        "fluence_m2": fluence,
        "outside": fluence < FLUENCE_LO_M2 or fluence > FLUENCE_HI_M2,
        "fast_remaining": remaining_pmax(accumulated / K_FAST),
        "truncated_remaining": remaining_pmax(accumulated / K_TRUNCATED),
        "zero_tally": td_ev_per_source == 0.0,
    }


def format_pmax_lines(report: dict, dose_years: float) -> tuple[str, str]:
    ci = f"{report['ci95_pct']:.2f}" if math.isfinite(report["ci95_pct"]) else "nan"
    outside = " (outside measured range)" if report["outside"] else ""
    main = (
        f"InGaAs Pmax remaining: {report['remaining']:.4e} of initial "
        f"over {dose_years:g} years "
        f"(± {ci}%, 95% CI), "
        f"XPNR-equivalent fluence {report['fluence_m2']:.4e} m^-2"
        f"{outside}"
    )
    sensitivity = (
        "InGaAs Pmax sensitivity: "
        f"fast-fluence {report['fast_remaining']:.4e}, "
        f"truncated spectrum {report['truncated_remaining']:.4e}"
    )
    return main, sensitivity
