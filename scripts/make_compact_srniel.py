import numpy as np
import pathlib


def downsample_niel_desc(fname_in, fname_out, npts=30):
    """
    Down-sample an ASTM/SR-NIEL table with descending energies.

    Parameters
    ----------
    fname_in  : str or Path
        Input text file, two columns:
            Energy [MeV]  NIEL [MeV cm² g⁻¹]  (strictly descending energies)
    fname_out : str or Path
        Output text file, written with ascending energies.
    npts      : int
        Number of points to keep (≥ 3).
    """
    # 1) Load --------------------------------------------------------------
    E_MeV, D_niel, _, _ = np.loadtxt(fname_in, unpack=True)

    if not np.all(np.diff(E_MeV) < 0):
        raise ValueError("Input energies must be strictly descending.")

    # 2) Flip to ascending for processing ---------------------------------
    E_MeV = E_MeV[::-1]
    D_niel = D_niel[::-1]

    # 3) Build a log-uniform ascending grid -------------------------------
    E_min, E_max = E_MeV[0], E_MeV[-1]
    E_comp = np.geomspace(E_min, E_max, npts)  # log spacing preserves shape

    # 4) Interpolate NIEL values (units preserved) ------------------------
    D_comp = np.interp(E_comp, E_MeV, D_niel)

    # 5) Write out (ascending order) --------------------------------------
    hdr = (
        f"E_MeV   NIEL(MeV cm^2 g^-1) – down-sampled to {npts} points "
        f"from '{pathlib.Path(fname_in).name}'"
    )
    np.savetxt(
        fname_out, np.column_stack([E_comp, D_comp]), fmt="%.6e %.6e", header=hdr
    )

    print(
        f"Wrote {npts}-point table to {fname_out} "
        f"({E_min:.2e} – {E_max:.2e} MeV, ascending)"
    )


# USAGE EXAMPLE ---------------------------------------------------------------
downsample_niel_desc(
    "srniel_GaAs_E722-19.txt", "srniel_GaAs_E722-19_compact.txt", npts=30
)
