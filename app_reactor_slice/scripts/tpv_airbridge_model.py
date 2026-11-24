"""
Precompute the Roy-Layinde air-bridge cells for the chart.

Each cell is the corresponding ddiode_simulation_*.m script: measured FTIR
absorptance, a constant internal quantum efficiency, and the two-diode fit.
The page integrates each spectrum. A black shell reproduces the scripts.
A gray shell uses the closed-gap exchange, with reflected light returned to
the shell. The view factor stays a multiplier on that illumination.

Spectra are the deposited files (doi:10.7302/7qsw-je08):
  ftir_0.74ev_narrow_exp2.txt  column 2 is reflectance
  ftir_0.9ev.txt               column 2 is absorptance
  ftir_1.1ev.txt               column 2 is reflectance
"""
from __future__ import annotations

import json
import math
from pathlib import Path

C_CM_S = 2.99792458e10
H_EV_S = 4.13566766225e-15
KB_EV_K = 8.617330350e-5
Q_C = 1.60217662e-19

TC_K = 304.5
IQE = 0.984

CELLS = (
    {
        "id": "0.74",
        "label": "0.74 eV",
        "color": "#7c3aed",
        "eg_eV": 0.74,
        "j0": 10 ** -8.8332,
        "jgr": 10 ** -5.705042,
        "rs_ohm_cm2": 0.03,
        "rsh_ohm_cm2": 10 ** 3.0518,
        "script_view_factor": 0.35,
        "spectrum": "ftir_0.74ev.txt",
        "column_is_reflectance": True,
    },
    {
        "id": "0.90",
        "label": "0.90 eV",
        "color": "#ea580c",
        "eg_eV": 0.88,
        "j0": 10 ** -11.1904215,
        "jgr": 10 ** -7.469844,
        "rs_ohm_cm2": 0.042,
        "rsh_ohm_cm2": 10 ** 6.1565,
        "script_view_factor": 0.3214,
        "spectrum": "ftir_0.9ev.txt",
        "column_is_reflectance": False,
    },
    {
        "id": "1.10",
        "label": "1.10 eV",
        "color": "#16a34a",
        "eg_eV": 1.08,
        "j0": 10 ** -14.01,
        "jgr": 10 ** -8.69,
        "rs_ohm_cm2": 0.18,
        "rsh_ohm_cm2": None,
        "script_view_factor": 0.27,
        "spectrum": "ftir_1.1ev.txt",
        "column_is_reflectance": True,
    },
)


def load_absorptance(path: Path, column_is_reflectance: bool) -> tuple[list[float], list[float]]:
    energy: list[float] = []
    absorptance: list[float] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        e_ev, value = (float(part) for part in line.split()[:2])
        raw = 1.0 - value if column_is_reflectance else value
        energy.append(e_ev)
        absorptance.append(min(1.0, max(0.0, raw)))
    return energy, absorptance


def trapz(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    for i in range(len(xs) - 1):
        total += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
    return total


def photon_flux(energy_eV: list[float], temp_k: float) -> list[float]:
    out: list[float] = []
    for energy in energy_eV:
        x = energy / (KB_EV_K * temp_k)
        if x > 700:
            out.append(0.0)
        else:
            out.append((2 * math.pi * energy * energy) / (C_CM_S**2 * H_EV_S**3 * math.expm1(x)))
    return out


def cavity_weight(absorptance: float, emissivity: float) -> float:
    """Closed-gap absorptance. A black shell returns the FTIR absorptance."""
    if emissivity >= 1:
        return absorptance
    return absorptance * emissivity / (emissivity + absorptance * (1.0 - emissivity))


def optics_at_view_factor_one(
    energy: list[float],
    absorptance: list[float],
    eg_eV: float,
    temp_c: float,
    emissivity: float = 1,
) -> tuple[float, float]:
    flux = photon_flux(energy, temp_c + 273.15)
    weight = [cavity_weight(a, emissivity) for a in absorptance]
    above_e = [e for e, w in zip(energy, weight) if e >= eg_eV]
    above_flux = [b * w for e, w, b in zip(energy, weight, flux) if e >= eg_eV]
    heat = [b * e * w for b, e, w in zip(flux, energy, weight)]
    jsc = Q_C * trapz(above_e, above_flux) * IQE
    qabs = Q_C * trapz(energy, heat)
    return jsc, qabs


def main() -> None:
    spectra = Path("/tmp/airbridge")
    temps = list(range(600, 1601, 10))
    cells = []
    for cell in CELLS:
        energy, absorptance = load_absorptance(spectra / cell["spectrum"], cell["column_is_reflectance"])
        black = optics_at_view_factor_one(energy, absorptance, cell["eg_eV"], 1150)
        gray = optics_at_view_factor_one(energy, absorptance, cell["eg_eV"], 1150, 0.2)
        print(
            f"{cell['id']} 1150°C black J {black[0]:.4f} q {black[1]:.4f}; "
            f"ε=0.2 J {gray[0]:.4f} ({100 * gray[0] / black[0]:.1f}%) "
            f"q {gray[1]:.4f} ({100 * gray[1] / black[1]:.1f}%)"
        )
        cells.append({
            "id": cell["id"],
            "label": cell["label"],
            "color": cell["color"],
            "eg_eV": cell["eg_eV"],
            "j0_A_cm2": cell["j0"],
            "jgr_A_cm2": cell["jgr"],
            "rs_ohm_cm2": cell["rs_ohm_cm2"],
            "rsh_ohm_cm2": cell["rsh_ohm_cm2"],
            "script_view_factor": cell["script_view_factor"],
            "energy_eV": energy,
            "absorptance": absorptance,
        })
    out = {
        "temps_C": temps,
        "cell_temperature_K": TC_K,
        "iqe": IQE,
        "c_cm_s": C_CM_S,
        "h_eV_s": H_EV_S,
        "kB_eV_K": KB_EV_K,
        "q_C": Q_C,
        "cells": cells,
        "note": (
            "Roy-Layinde et al. air-bridge spectra. The page integrates them. "
            "A black shell matches the scripts. A gray shell uses the closed-gap exchange."
        ),
    }
    dest = Path(__file__).resolve().parents[1] / "src" / "data" / "tpvAirbridge.json"
    dest.write_text(json.dumps(out))
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
