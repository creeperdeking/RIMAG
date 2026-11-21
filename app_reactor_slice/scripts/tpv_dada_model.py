"""
Reimplement Dada et al. (2025) empirical TPV model for Fig. 8 tables.

Fig. 8 inputs (paper): VF=1, ε_abv=1, IQE=1, Tcell=25°C, Rseries=0.01 Ω·cm²,
Woc = radiative-limit(at 15 mA/cm²) + 70 mV (solid) or +140 mV (dashed),
ε_bel = 0.05 (95% R) or 0.01 (99% R).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

q = 1.602176634e-19
k = 1.380649e-23
h = 6.62607015e-34
c = 2.99792458e8
pi = np.pi
sigma = 5.670374419e-8

CM2_PER_M2 = 1e4


def spectral_energy(E: np.ndarray, T: float) -> np.ndarray:
    x = np.clip(E / (k * T), 0.0, 700.0)
    return (2 * pi / (h**3 * c**2)) * (E**3) / np.expm1(x)


def spectral_photon(E: np.ndarray, T: float) -> np.ndarray:
    x = np.clip(E / (k * T), 0.0, 700.0)
    return (2 * pi / (h**3 * c**2)) * (E**2) / np.expm1(x)


def integrate(func, emin: float, emax: float, n: int = 12000) -> float:
    e = np.linspace(emin, emax, n)
    trap = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    return float(trap(func(e), e))


def q_above(eg_ev: float, tem_c: float) -> float:
    eg = eg_ev * q
    t = tem_c + 273.15
    return integrate(lambda e: spectral_energy(e, t), eg, max(eg * 12, 50 * k * t))


def q_below(eg_ev: float, tem_c: float) -> float:
    eg = eg_ev * q
    t = tem_c + 273.15
    return integrate(lambda e: spectral_energy(e, t), max(eg * 1e-8, 1e-30), eg)


def n_above(eg_ev: float, tem_c: float) -> float:
    eg = eg_ev * q
    t = tem_c + 273.15
    return integrate(lambda e: spectral_photon(e, t), eg, max(eg * 12, 50 * k * t))


def j0_rad_a_m2(eg_ev: float, tcell_c: float = 25.0) -> float:
    return q * n_above(eg_ev, tcell_c)


def woc_rad(eg_ev: float, jsc_a_m2: float, tcell_c: float = 25.0) -> float:
    t = tcell_c + 273.15
    j0 = j0_rad_a_m2(eg_ev, tcell_c)
    voc = (k * t / q) * np.log(jsc_a_m2 / j0 + 1.0)
    return float(eg_ev - voc)


def j0_from_woc(eg_ev: float, woc_v: float, jsc_ref_a_m2: float, tcell_c: float = 25.0) -> float:
    """J0 such that Woc at jsc_ref equals woc_v."""
    t = tcell_c + 273.15
    voc = eg_ev - woc_v
    return float(jsc_ref_a_m2 / (np.exp(q * voc / (k * t)) - 1.0))


def solve_jv(
    jsc_a_cm2: float,
    j0_a_cm2: float,
    rseries_ohm_cm2: float,
    tcell_c: float = 25.0,
    n_v: int = 800,
) -> tuple[float, float, float]:
    """
    Paper Eq. (5): J = -Jsc + J0*(exp(q(V-J R)/kT)-1)
    Electrical power density is max(-J*V) in the generating quadrant.
    Returns (P_mpp W/cm2, V_mpp, J_mpp A/cm2).
    """
    t = tcell_c + 273.15
    vt = k * t / q

    # Voc estimate (ignore Rs first)
    voc0 = vt * np.log(jsc_a_cm2 / j0_a_cm2 + 1.0)
    voltages = np.linspace(0.0, max(voc0 * 1.05, 1e-3), n_v)

    best_p = 0.0
    best_v = 0.0
    best_j = 0.0

    for v in voltages:
        # solve J = -Jsc + J0*(exp((V - J R)/Vt) - 1) for J
        # fixed-point / Newton
        j = -jsc_a_cm2
        for _ in range(40):
            arg = (v - j * rseries_ohm_cm2) / vt
            if arg > 80:
                arg = 80.0
            exp_term = np.exp(arg)
            f = j + jsc_a_cm2 - j0_a_cm2 * (exp_term - 1.0)
            # dJ/dJ: 1 - J0 * exp * (-R/Vt)
            df = 1.0 + j0_a_cm2 * exp_term * (rseries_ohm_cm2 / vt)
            j_new = j - f / df
            if abs(j_new - j) < 1e-12:
                j = j_new
                break
            j = j_new
        p = -j * v  # W/cm2 if J in A/cm2, V in V
        if p > best_p:
            best_p = float(p)
            best_v = float(v)
            best_j = float(j)

    return best_p, best_v, best_j


def tpv_performance(
    eg_ev: float,
    tem_c: float,
    *,
    e_bel: float,
    woc_extra_v: float,
    vf: float = 1.0,
    e_abv: float = 1.0,
    iqe: float = 1.0,
    rseries_ohm_cm2: float = 0.01,
    tcell_c: float = 25.0,
    jsc_ref_a_cm2: float = 0.015,
) -> dict[str, float]:
    # Spectral quantities in SI (W/m2, 1/m2/s), then convert current to A/cm2
    qabs_si = vf * (e_bel * q_below(eg_ev, tem_c) + e_abv * q_above(eg_ev, tem_c))  # W/m2
    jsc_si = q * vf * iqe * e_abv * n_above(eg_ev, tem_c)  # A/m2
    jsc = jsc_si / CM2_PER_M2  # A/cm2
    qabs = qabs_si / CM2_PER_M2  # W/cm2

    jsc_ref_si = jsc_ref_a_cm2 * CM2_PER_M2
    woc = woc_rad(eg_ev, jsc_ref_si, tcell_c) + woc_extra_v
    j0_si = j0_from_woc(eg_ev, woc, jsc_ref_si, tcell_c)
    j0 = j0_si / CM2_PER_M2

    p_mpp, v_mpp, j_mpp = solve_jv(jsc, j0, rseries_ohm_cm2, tcell_c)
    eta = 0.0 if qabs <= 0 else 100.0 * p_mpp / qabs
    return {
        "eg_ev": eg_ev,
        "tem_c": tem_c,
        "e_bel": e_bel,
        "woc_extra_v": woc_extra_v,
        "woc_v": woc,
        "jsc_a_cm2": jsc,
        "qabs_w_cm2": qabs,
        "p_mpp_w_cm2": p_mpp,
        "eta_pct": eta,
        "v_mpp": v_mpp,
        "j_mpp": j_mpp,
    }


def midpoint(a: float, b: float) -> float:
    return 0.5 * (a + b)


def main() -> None:
    # sanity: Stefan-Boltzmann
    t = 1273.15
    qtot = integrate(lambda e: spectral_energy(e, t), 1e-30, 50 * k * t, n=25000)
    print(f"SB check ratio={qtot / (sigma * t**4):.4f} (want ~1)")

    jsc_ref_si = 0.015 * CM2_PER_M2
    print("Woc_rad @ 15 mA/cm2:")
    for eg in [0.4, 0.5, 0.6, 0.7, 0.8]:
        print(f"  {eg:.1f} eV -> {woc_rad(eg, jsc_ref_si):.4f} V")

    # paper anchors at 1000 C, e_bel=0.01, +140 mV
    print("Anchors @ 1000 C, e_bel=0.01, +140 mV:")
    for eg in [0.5, 0.8]:
        r = tpv_performance(eg, 1000.0, e_bel=0.01, woc_extra_v=0.140)
        print(f"  {eg} eV: P={r['p_mpp_w_cm2']:.3f} W/cm2 (paper 1.26 / 0.433), eta={r['eta_pct']:.1f}%")

    temps = list(range(600, 1601, 50))
    egs = [0.4, 0.5, 0.6, 0.7, 0.8]
    out: dict = {
        "source": "Dada et al. Sol. Energy Mater. Sol. Cells 289 (2025) 113666 Fig. 8 — regenerated from model",
        "params": {
            "VF": 1.0,
            "e_abv": 1.0,
            "IQE": 1.0,
            "Tcell_C": 25.0,
            "Rseries_ohm_cm2": 0.01,
            "Woc": "radiative_limit(15 mA/cm2) + {70|140} mV",
        },
        "temps_C": temps,
        "efficiency_R95": {},
        "efficiency_R99": {},
        "power_w_cm2": {},
    }

    for eg in egs:
        key = f"{eg:.1f}"
        eta95_lo, eta95_hi = [], []
        eta99_lo, eta99_hi = [], []
        p_lo, p_hi = [], []
        for tem in temps:
            a95 = tpv_performance(eg, tem, e_bel=0.05, woc_extra_v=0.070)
            b95 = tpv_performance(eg, tem, e_bel=0.05, woc_extra_v=0.140)
            a99 = tpv_performance(eg, tem, e_bel=0.01, woc_extra_v=0.070)
            b99 = tpv_performance(eg, tem, e_bel=0.01, woc_extra_v=0.140)
            # power independent of e_bel
            eta95_hi.append(a95["eta_pct"])
            eta95_lo.append(b95["eta_pct"])
            eta99_hi.append(a99["eta_pct"])
            eta99_lo.append(b99["eta_pct"])
            p_hi.append(a95["p_mpp_w_cm2"])
            p_lo.append(b95["p_mpp_w_cm2"])

        out["efficiency_R95"][key] = {
            "hi_plus70mV": eta95_hi,
            "lo_plus140mV": eta95_lo,
            "mid": [midpoint(a, b) for a, b in zip(eta95_hi, eta95_lo)],
        }
        out["efficiency_R99"][key] = {
            "hi_plus70mV": eta99_hi,
            "lo_plus140mV": eta99_lo,
            "mid": [midpoint(a, b) for a, b in zip(eta99_hi, eta99_lo)],
        }
        out["power_w_cm2"][key] = {
            "hi_plus70mV": p_hi,
            "lo_plus140mV": p_lo,
            "mid": [midpoint(a, b) for a, b in zip(p_hi, p_lo)],
        }

    out_path = Path(__file__).resolve().parents[1] / "src" / "data" / "tpvDadaFig8.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")

    # quick peek at peaks
    for eg in egs:
        key = f"{eg:.1f}"
        mid = out["efficiency_R99"][key]["mid"]
        i = int(np.argmax(mid))
        print(f"R99 {key} eV peak ~{mid[i]:.1f}% @ {temps[i]} C; P@1000={out['power_w_cm2'][key]['lo_plus140mV'][temps.index(1000)]:.3f}")


if __name__ == "__main__":
    main()
