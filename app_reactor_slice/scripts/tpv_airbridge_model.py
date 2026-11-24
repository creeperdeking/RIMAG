"""
Precompute the Roy-Layinde air-bridge cells for the chart.

Each cell is the corresponding ddiode_simulation_*.m script: measured FTIR
absorptance, a constant internal quantum efficiency, and the two-diode fit.
The view factor is a multiplier on current and absorbed heat, so this file
stores both at a view factor of 1. The page scales them and solves the diode.

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


def optics_at_view_factor_one(energy: list[float], absorptance: list[float], eg_eV: float, temp_c: float) -> tuple[float, float]:
    flux = photon_flux(energy, temp_c + 273.15)
    above_e = [e for e, a in zip(energy, absorptance) if e >= eg_eV]
    above_flux = [b * a for e, a, b in zip(energy, absorptance, flux) if e >= eg_eV]
    incident = [b * e for b, e in zip(flux, energy)]
    reflected = [b * e * (1.0 - a) for b, e, a in zip(flux, energy, absorptance)]
    jsc = Q_C * trapz(above_e, above_flux) * IQE
    qabs = Q_C * (trapz(energy, incident) - trapz(energy, reflected))
    return jsc, qabs


def main() -> None:
    spectra = Path("/tmp/airbridge")
    temps = list(range(600, 1601, 10))
    cells = []
    for cell in CELLS:
        energy, absorptance = load_absorptance(spectra / cell["spectrum"], cell["column_is_reflectance"])
        jsc = []
        qabs = []
        for temp_c in temps:
            j, q = optics_at_view_factor_one(energy, absorptance, cell["eg_eV"], temp_c)
            jsc.append(j)
            qabs.append(q)
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
            "jsc_A_cm2_vf1": jsc,
            "qabs_W_cm2_vf1": qabs,
        })
    out = {
        "temps_C": temps,
        "cell_temperature_K": TC_K,
        "iqe": IQE,
        "cells": cells,
        "note": "Roy-Layinde et al. air-bridge scripts. jsc and qabs are at view factor 1; both scale linearly with the view factor.",
    }
    dest = Path(__file__).resolve().parents[1] / "src" / "data" / "tpvAirbridge.json"
    dest.write_text(json.dumps(out))
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
