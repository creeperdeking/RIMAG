import io, numpy as np
from openmc.data.endf import (
    Evaluation,
    get_head_record,
    get_tab1_record,
)  # documented API


def read_mt444_to_niel(path_ascii_endf, A_g_mol):
    ev = Evaluation(path_ascii_endf)  # parse ENDF-6
    sec = io.StringIO(ev.section[(3, 444)])  # MF=3, MT=444 section text
    _ = get_head_record(sec)  # advance past HEAD
    _, tab = get_tab1_record(sec)  # read TAB1 → energies, D(E)
    E_eV = tab.x  # energy in eV
    D_eV_b = tab.y  # damage-energy XS in eV·barn

    # Convert D(E) → NIEL(E) [MeV·cm^2·g^-1]: 1e-6 MeV/eV, 1 barn = 1e-24 cm^2
    NA = 6.02214076e23
    NIEL = D_eV_b * 1e-6 * 1e-24 * (NA / A_g_mol)
    E_MeV = E_eV * 1e-6
    return E_MeV, NIEL


def log_interp(x0, y0, x):
    return np.exp(np.interp(np.log(x), np.log(x0), np.log(np.maximum(y0, 1e-300))))


# Read element tables
E_Ga69, NIEL_Ga69 = read_mt444_to_niel("heatr_Ga69_t41_ascii.endf", 68.93)
E_Ga71, NIEL_Ga71 = read_mt444_to_niel("heatr_Ga71_t41_ascii.endf", 70.92)
E_As75, NIEL_As75 = read_mt444_to_niel("heatr_As75_t41_ascii.endf", 74.92)

Emin = max(E_Ga69.min(), E_Ga71.min(), E_As75.min())
Emax = min(E_Ga69.max(), E_Ga71.max(), E_As75.max())
E = np.logspace(np.log10(Emin), np.log10(Emax), 1200)

N_Ga69 = log_interp(E_Ga69, NIEL_Ga69, E)
N_Ga71 = log_interp(E_Ga71, NIEL_Ga71, E)
N_As75 = log_interp(E_As75, NIEL_As75, E)

A = {"Ga69": 68.93, "Ga71": 70.92, "As75": 74.92}
n = {"Ga69": 0.601, "Ga71": 0.399, "As75": 1}
W = {k: n[k] * A[k] for k in n}
M = sum(W.values())
w = {k: W[k] / M for k in n}  # mass fractions

NIEL_GaAs = w["Ga69"] * N_Ga69 + w["Ga71"] * N_Ga71 + w["As75"] * N_As75

np.savetxt(
    "NIEL_GaAs.txt",
    np.c_[E, NIEL_GaAs],
    fmt="%.8e",
    header="E_MeV  NIEL_MeV_cm2_g  (HEATR MT=444 → NIEL; Bragg mass-weighted compound)",
)
