import openmc
from typing import List, Literal
import scipy.constants as cst
from common_lib.materials import MonitoredNuclide
import numpy as np


def get_srniel_table():
    # --- 1.  Load the SR-NIEL table -----------------------------
    # Assume the first two columns are Energy [MeV] and NIEL [MeV cm2 g-1]
    E_MeV, NIEL_MeV_cm2_g = np.loadtxt(
        "scripts/srniel_GaAs_E722-19_compact.txt", usecols=(0, 1), unpack=True
    )

    # --- 2.  Convert energies to eV for OpenMC ------------------
    E_eV = E_MeV * 1.0e6

    return E_eV, NIEL_MeV_cm2_g


def create_photovoltaic_heating_absorption_tally(
    photovoltaic_cells: List[openmc.Cell],
    particle_type: Literal["neutron", "photon"],
    monitored_nuclide: MonitoredNuclide = None,
):
    tally = openmc.Tally(name="photovoltaic")
    tally.filters = [
        openmc.CellFilter(photovoltaic_cells),
        openmc.ParticleFilter(particle_type),
    ]
    if monitored_nuclide is not None:
        tally.nuclides = [monitored_nuclide.nuclide]
    tally.scores = [
        "(n,gamma)",
        "heating",
    ]  # careful, changing the order can mess up output
    return tally


def create_tritium_production_tally(
    cells: List[openmc.Cell],
    suffix: str = "",
):
    tally = openmc.Tally(name=f"tritium_production{suffix}")
    tally.filters = [
        openmc.CellFilter(cells),
        openmc.ParticleFilter("neutron"),
    ]
    tally.scores = ["H3-production"]
    return tally

def create_C14_production_tally(
    cells: List[openmc.Cell],
    suffix: str = "",
):
    tally = openmc.Tally(name=f"C14_production{suffix}")
    tally.filters = [
        openmc.CellFilter(cells),
        openmc.ParticleFilter("neutron"),
    ]
    tally.nuclides = ["N14", "O17", "N15", "O16"] # could not add C13 because not in library
    tally.scores   = ["(n,p)", "(n,a)", "(n,d)", "(n,3He)"]
    return tally


def create_O16_activation_tally(
    cells: List[openmc.Cell],
    suffix: str = "",
):
    tally = openmc.Tally(name=f"O16_activation{suffix}")
    tally.filters = [
        openmc.CellFilter(cells),
        openmc.ParticleFilter("neutron"),
    ]
    tally.nuclides = ["O16"]
    tally.scores = ["(n,p)"]
    return tally


def create_photovoltaic_flux_tally(
    photovoltaic_cells: List[openmc.Cell],
    particle_type: Literal["neutron", "photon"],
):
    E_eV, D_norm = get_srniel_table()
    tally = openmc.Tally(name="photovoltaic_ddd")
    tally.filters = [
        openmc.CellFilter(photovoltaic_cells),
        openmc.ParticleFilter(particle_type),
        openmc.EnergyFunctionFilter(E_eV, D_norm),
    ]
    tally.scores = [
        "flux",
    ]
    return tally


def create_emitter_tally(
    emitter_cells: List[openmc.Cell],
    materials_dict,
    particle_type: Literal["neutron", "photon"],
    monitored_nuclide: MonitoredNuclide = None,
):
    tally = openmc.Tally(name="emitter")
    tally.filters = [
        openmc.CellFilter(emitter_cells),
        openmc.ParticleFilter(particle_type),
    ]
    tally.scores = [
        "(n,gamma)",
    ]  # careful, changing the order can mess up output
    if monitored_nuclide is not None:
        tally.nuclides = [monitored_nuclide.nuclide]
    return tally


def get_energy_bands():
    E_bands = np.array([0.0, 0.625, 1.0e5, 2.0e7])
    return E_bands


def create_fission_energy_weighted_flux_tally(
    fuel_cells: List[openmc.Cell],
):
    E_bands = get_energy_bands()
    t_flux = openmc.Tally(name="phi_E")
    t_flux.filters = [
        openmc.CellFilter(fuel_cells),
        openmc.ParticleFilter("neutron"),
        openmc.EnergyFilter(E_bands),
    ]
    t_flux.scores = ["flux"]
    # --- build tallies ---
    t_nufi = openmc.Tally(name="nufis_E")
    t_nufi.filters = t_flux.filters
    t_nufi.scores = ["nu-fission"]

    Egrid = np.logspace(-5, np.log10(2e7), 1200)  # eV
    Efunc = openmc.EnergyFunctionFilter(Egrid, Egrid)  # y(E)=E

    t_Enufi = openmc.Tally(name="E_nufi")
    t_Enufi.filters = [
        openmc.CellFilter(fuel_cells),
        openmc.ParticleFilter("neutron"),
        Efunc,
    ]
    t_Enufi.scores = ["nu-fission"]
    return t_flux, t_nufi, t_Enufi


def create_flux_band_tally(
    cells: List[openmc.Cell],
    tally_name: str = "phi_E_cell",
):
    """
    Flux-by-energy for one cell, binned into thermal / epithermal / fast.
    Returns (t_flux, E_bands_eV).
    """
    E_bands_eV = get_energy_bands()

    t_flux = openmc.Tally(name=tally_name)
    t_flux.filters = [
        openmc.CellFilter(cells),
        openmc.ParticleFilter("neutron"),
        openmc.EnergyFilter(E_bands_eV),
    ]
    t_flux.scores = [
        "flux"
    ]  # track-length flux per energy bin (integral over each bin)

    return t_flux


def create_dpa_tally(
    cells: List[openmc.Cell],
    suffix: str = "",
):
    # all materials present in that cell (handles universes/lattices too)
    mats_in_cell = [mat for cell in cells for mat in cell.get_all_materials().values()]

    # expand to real nuclide names (e.g., "C12", "C13") and deduplicate
    nuclide_names = sorted({n for m in mats_in_cell for n in m.get_nuclides()})
    cell_filter = openmc.CellFilter(cells)  # the cell you care about
    t_dam = openmc.Tally(name=f"damage-energy_cell{suffix}")
    t_dam.filters = [cell_filter]
    t_dam.scores = ["damage-energy"]  # MT=444
    t_dam.nuclides = nuclide_names

    return t_dam


def calculate_dpa(
    sp: openmc.StatePoint,
    tally_name: str,
    source_strength: float,
    cells: List[openmc.Cell],
):
    t_dam = sp.get_tally(name=tally_name)
    T_eV_per_source = t_dam.get_values(scores=["damage-energy"], value="mean").ravel()
    T_eV = T_eV_per_source * source_strength
    Ed_eV = {
        "Fe56": 40.0,
        "Cr52": 40.0,
        "Ni58": 40.0,
        "C0": 24,
        "W182": 90.0,
        "W183": 90.0,
        "W184": 90.0,
        "W186": 90.0,
        "Mo92": 68.0,
        "Mo94": 68.0,
        "Mo95": 68.0,
        "Mo96": 68.0,
        "Mo97": 68.0,
        "Mo98": 68.0,
        "Mo100": 68.0,
        "Zr90": 40.0,
        "Zr91": 40.0,
        "Zr92": 40.0,
        "Zr94": 40.0,
        "Zr96": 40.0,
        "Ti46": 30.0,
        "Ti47": 30.0,
        "Ti48": 30.0,
        "Ti49": 30.0,
        "Ti50": 30.0,
    }
    nucs = t_dam.nuclides

    # Get number of atoms of each nuclide in the cell’s material (or number density × volume)
    mat = list(cells[0].get_all_materials().values())[0]
    atoms = mat.get_nuclide_atoms(
        volume=sum(cell.volume for cell in cells)
    )  # returns dict {nuc: atoms}
    dpa_rate_by_nuc = {}
    for nuc, Tdot in zip(nucs, T_eV):
        if nuc in Ed_eV and atoms.get(nuc, 0.0) > 0.0:
            dpa_rate_by_nuc[nuc] = (
                0.8 * Tdot / (2.0 * Ed_eV[nuc]) / atoms[nuc]
            )  # [1/s]'
        else:
            print(f"❌ Nuclide {nuc} not found in Ed_eV, aborting DPA calculation")
            return 0.0

    N_tot = sum(atoms.get(n, 0.0) for n in nucs if n in Ed_eV)
    dpa_rate_cell = (
        sum(dpa_rate_by_nuc[n] * atoms[n] for n in dpa_rate_by_nuc) / N_tot
    )  # [1/s]

    return dpa_rate_cell * 365 * 24 * 60 * 60


def flux_band_percentages(
    sp: openmc.StatePoint, tally_name: str, E_bands_eV: np.ndarray
):
    """
    Compute % of total flux in each energy band for the given tally.
    Uses tally arithmetic so uncertainties are correctly propagated.
    Returns (labels, pct_mean, pct_sd).
    """
    # Keep EnergyFilter for binwise values; remove only the CellFilter.
    phi_bins = sp.get_tally(name=tally_name).summation(
        filter_type=openmc.CellFilter, remove_filter=True
    )
    # Scalar total over all energy bins.
    phi_total = (
        sp.get_tally(name=tally_name)
        .summation(filter_type=openmc.CellFilter, remove_filter=True)
        .summation(filter_type=openmc.EnergyFilter, remove_filter=True)
    )

    # Derived tally: per-bin fraction = phi_bins / phi_total (vector / scalar)
    frac = phi_bins / phi_total

    pct_mean = 100.0 * frac.mean.ravel()
    pct_sd = 100.0 * frac.std_dev.ravel()

    # Human-friendly labels
    labels = [
        f"[{E_bands_eV[i]:.3g}, {E_bands_eV[i + 1]:.3g}) eV"
        for i in range(len(E_bands_eV) - 1)
    ]
    return labels, pct_mean, pct_sd


def create_energy_deposition_tallies(
    cells: List[openmc.Cell],
    *,
    tally_prefix: str = "dep_",
    use_heating_local: bool = False,
):
    """
    Tallies for energy deposition fractions in a set of cells.

    - dep_heat_cells: heating (or heating-local) in the specified cells
    - dep_heat_total: global heating (or heating-local)
    - dep_kapf_total: global kappa-fission (recoverable fission energy)

    Parameters
    ----------
    cells : list of openmc.Cell
        Cells where you want to measure deposited heat.
    tally_prefix : str
        Prefix for tally names.
    use_heating_local : bool
        True for neutron-only runs (credits γ energy locally).
        False when transporting photons (credits where γ actually deposits).

    Returns
    -------
    tuple[openmc.Tally, openmc.Tally, openmc.Tally]
    """
    heat_score = "heating-local" if use_heating_local else "heating"

    # Heat deposited in the target cells (all particles; don't add ParticleFilter)
    t_heat_cells = openmc.Tally(name=f"{tally_prefix}heat_cells")
    t_heat_cells.filters = [openmc.CellFilter(cells)]
    t_heat_cells.scores = [heat_score]

    # Total deposited heat over the whole geometry (no filters)
    t_heat_total = openmc.Tally(name=f"{tally_prefix}heat_total")
    t_heat_total.scores = [heat_score]

    # Total recoverable fission energy produced (no spatial filter)
    t_kapf_total = openmc.Tally(name=f"{tally_prefix}kapf_total")
    t_kapf_total.filters = [openmc.ParticleFilter("neutron")]
    t_kapf_total.scores = ["kappa-fission"]

    return t_heat_cells, t_heat_total, t_kapf_total


def deposition_percentages(sp: openmc.StatePoint, tally_prefix: str = "dep_"):
    """
    Compute deposited-heat percentages using tally arithmetic (with uncertainties).

    Returns
    -------
    dict with:
      - agg_pct_of_kapf_mean, agg_pct_of_kapf_sd
      - agg_pct_of_heat_mean, agg_pct_of_heat_sd
      - per_cell: list of (cell_id, pct_of_kapf_mean, sd, pct_of_heat_mean, sd)
    """
    name = lambda s: f"{tally_prefix}{s}"

    # Fetch tallies
    heat_cells = sp.get_tally(name=name("heat_cells"))  # has CellFilter
    heat_total = sp.get_tally(name=name("heat_total"))  # scalar
    kapf_total = sp.get_tally(name=name("kapf_total"))  # scalar

    # Aggregate over the provided cell list
    heat_cells_sum = heat_cells.summation(
        filter_type=openmc.CellFilter, remove_filter=True
    )

    # Fractions via tally arithmetic (keeps uncertainty correct)
    agg_frac_of_kapf = heat_cells_sum / kapf_total
    agg_frac_of_heat = heat_cells_sum / heat_total

    results = {
        "agg_pct_of_kapf_mean": 100.0 * agg_frac_of_kapf.mean.item(),
        "agg_pct_of_kapf_sd": 100.0 * agg_frac_of_kapf.std_dev.item(),
        "agg_pct_of_heat_mean": 100.0 * agg_frac_of_heat.mean.item(),
        "agg_pct_of_heat_sd": 100.0 * agg_frac_of_heat.std_dev.item(),
        "per_cell": [],
    }

    # Per-cell breakdown (relative to global totals)
    # Keep CellFilter to preserve one value per cell
    per_cell_frac_kapf = heat_cells / kapf_total
    per_cell_frac_heat = heat_cells / heat_total

    # Pull cell IDs from the filter for labeling
    cell_filter = next(
        f for f in heat_cells.filters if isinstance(f, openmc.CellFilter)
    )
    cell_ids = list(cell_filter.bins)

    mean_kapf = 100.0 * per_cell_frac_kapf.mean.ravel()
    sd_kapf = 100.0 * per_cell_frac_kapf.std_dev.ravel()
    mean_heat = 100.0 * per_cell_frac_heat.mean.ravel()
    sd_heat = 100.0 * per_cell_frac_heat.std_dev.ravel()

    for cid, mk, sk, mh, sh in zip(cell_ids, mean_kapf, sd_kapf, mean_heat, sd_heat):
        results["per_cell"].append(
            {
                "cell_id": int(cid),
                "pct_of_kapf_mean": float(mk),
                "pct_of_kapf_sd": float(sk),
                "pct_of_heat_mean": float(mh),
                "pct_of_heat_sd": float(sh),
            }
        )

    return results


def calculate_tritium_production(
    sp: openmc.StatePoint, source_strength, electric_power, tally_name: str
):
    """
    Calculate tritium production in Ci/year/GWe.
    """
    curie_per_mol_tritium = 2.9e4  # Ci/mol
    t_tritium_production = sp.get_tally(name=tally_name)
    # Get mean and std_dev for the tally
    mean_val = t_tritium_production.get_values(scores=["(n,Xt)"], value="mean").sum()
    std_val = t_tritium_production.get_values(scores=["(n,Xt)"], value="std_dev").sum()
    # Calculate tritium production and its standard deviation
    factor = (
        source_strength
        / electric_power
        / cst.Avogadro
        * 365
        * 24
        * 60
        * 60
        * 1e9
        * curie_per_mol_tritium
    )
    tritium_production = mean_val * factor
    tritium_production_sd = std_val * factor
    return tritium_production, tritium_production_sd

def calculate_C14_production(
    sp: openmc.StatePoint, source_strength, electric_power, tally_name: str
):
    """
    Calculate C14 production in Ci/year/GWe by summing all pathways that yield 14C.
    Assumes `tally_name` contains bins for the listed (nuclide, score) pairs.
    """

    # Specific activity of pure C-14 (Ci/mol):  lambda * N_A / 3.7e10
    # Using T_1/2 = 5730 y gives ~62.43 Ci/mol
    curie_per_mol_c14 = 62.432885931801984

    # Get the tally
    t = sp.get_tally(name=tally_name)

    # Pull results as a DataFrame so we can mask on (nuclide, score) pairs
    df = t.get_pandas_dataframe()

    # Valid parent/reaction pairs that produce 14C
    valid_pairs = {
        ("N14", "(n,p)"),      # 14N(n,p)14C
        ("O17", "(n,alpha)"),  # 17O(n,α)14C
        ("N15", "(n,d)"),      # 15N(n,d)14C   (usually small)
        ("O16", "(n,He3)"),    # 16O(n,3He)14C (usually small)
    }  # could not add C13 because not in library

    mask = df.apply(lambda r: (r["nuclide"], r["score"]) in valid_pairs, axis=1)

    mean_val = df.loc[mask, "mean"].to_numpy().sum()
    std_val  = df.loc[mask, "std. dev."].to_numpy().sum()

    # Convert reactions/source → (Ci/year)/GWe, matching your tritium normalization
    factor = (
        source_strength        # source particles per second
        / electric_power       # per GWe (will multiply by 1e9 below)
        / cst.Avogadro
        * 365 * 24 * 60 * 60   # seconds/year
        * 1e9                  # W per GWe (keeps your existing convention)
        * curie_per_mol_c14    # Ci/mol for C-14
    )

    c14_production    = mean_val * factor
    c14_production_sd = std_val * factor
    return c14_production, c14_production_sd


def calculate_N16_production(
    sp: openmc.StatePoint, source_strength, electric_power, tally_name: str
):
    """
    Calculate N16 production in MBq/s/GWe.
    """
    mbq_per_mol_N16 = 5.85e16  # MBq/mol
    N16_production = sp.get_tally(name=tally_name)
    mean_val = N16_production.get_values(scores=["(n,p)"], value="mean").sum()
    std_val = N16_production.get_values(scores=["(n,p)"], value="std_dev").sum()
    factor = source_strength / electric_power / cst.Avogadro * 1e9 * mbq_per_mol_N16
    N16_production = mean_val * factor
    N16_production_sd = std_val * factor
    return N16_production, N16_production_sd


def print_tritium_production(sp: openmc.StatePoint, source_strength, electric_power):
    """
    Print tritium production in Ci/year/GWe.
    """
    tritium_production_shield, tritium_production_shield_sd = (
        calculate_tritium_production(
            sp,
            source_strength,
            electric_power,
            "tritium_production_shield_moderator",
        )
    )
    tritium_production_moderator, tritium_production_moderator_sd = (
        calculate_tritium_production(
            sp, source_strength, electric_power, "tritium_production_moderator"
        )
    )
    tritium_production_coolant, tritium_production_coolant_sd = (
        calculate_tritium_production(
            sp, source_strength, electric_power, "tritium_production_coolant"
        )
    )

    print(
        f"tritium production moderator: {tritium_production_moderator:.2e} Ci/year/GWe ± {tritium_production_moderator_sd:.2e} Ci/year/GWe"
    )
    print(
        f"tritium production shield: {tritium_production_shield:.2e} Ci/year/GWe ± {tritium_production_shield_sd:.2e} Ci/year/GWe"
    )
    print(
        f"tritium production coolant: {tritium_production_coolant:.2e} Ci/year/GWe ± {tritium_production_coolant_sd:.2e} Ci/year/GWe"
    )

def print_C14_production(sp: openmc.StatePoint, source_strength, electric_power):
    """
    Print C14 production in Ci/year/GWe.
    """
    C14_production_shield, C14_production_shield_sd = (
        calculate_C14_production(
            sp,
            source_strength,
            electric_power,
            "C14_production_shield_moderator",
        )
    )
    C14_production_moderator, C14_production_moderator_sd = (
        calculate_C14_production(
            sp, source_strength, electric_power, "C14_production_moderator"
        )
    )
    C14_production_coolant, C14_production_coolant_sd = (
        calculate_C14_production(
            sp, source_strength, electric_power, "C14_production_coolant"
        )
    )

    print(
        f"C14 production moderator: {C14_production_moderator:.2e} Ci/year/GWe ± {C14_production_moderator_sd:.2e} Ci/year/GWe"
    )
    print(
        f"C14 production shield: {C14_production_shield:.2e} Ci/year/GWe ± {C14_production_shield_sd:.2e} Ci/year/GWe"
    )
    print(
        f"C14 production coolant: {C14_production_coolant:.2e} Ci/year/GWe ± {C14_production_coolant_sd:.2e} Ci/year/GWe"
    )


def print_N16_production(sp: openmc.StatePoint, source_strength, electric_power):
    """
    Print N16 production in MBq/s/GWe.
    """
    N16_production_moderator, N16_production_moderator_sd = calculate_N16_production(
        sp, source_strength, electric_power, "O16_activation_moderator"
    )
    N16_production_shield, N16_production_shield_sd = calculate_N16_production(
        sp, source_strength, electric_power, "O16_activation_shield_moderator"
    )
    N16_production_coolant, N16_production_coolant_sd = calculate_N16_production(
        sp, source_strength, electric_power, "O16_activation_coolant"
    )
    print(
        f"N16 production moderator: {N16_production_moderator:.2e} MBq/s/GWe ± {N16_production_moderator_sd:.2e} MBq/s/GWe"
    )
    print(
        f"N16 production shield: {N16_production_shield:.2e} MBq/s/GWe ± {N16_production_shield_sd:.2e} MBq/s/GWe"
    )
    print(
        f"N16 production coolant: {N16_production_coolant:.2e} MBq/s/GWe ± {N16_production_coolant_sd:.2e} MBq/s/GWe"
    )


def print_tallies(
    source_strength,
    emitter_cells,
    photovoltaic_slice_volume,
    photovoltaic_density,
    emitter_slice_volume,
    electric_power,
    batches,
    dose_time,
):
    sp = openmc.StatePoint(f"statepoint.{batches}.h5")
    k_eff = sp.keff  # keff (mean)
    photovolatic = sp.get_tally(name="photovoltaic")
    ddd_photovoltaic = sp.get_tally(name="photovoltaic_ddd")
    fluence_emitter = sp.get_tally(name="emitter")
    ifp_scores = sp.get_tally(name="ifp-scores")

    results_heat_used = deposition_percentages(sp)
    print(
        f"useful heating percentages: {results_heat_used['agg_pct_of_heat_mean']:.2f}%"
    )
    results_heat_moderator = deposition_percentages(sp, tally_prefix="dep_moderator_")
    print(
        f"heating moderator percentages: {results_heat_moderator['agg_pct_of_heat_mean']:.2f}%"
    )

    print_tritium_production(sp, source_strength, electric_power)
    print_C14_production(sp, source_strength, electric_power)
    print_N16_production(sp, source_strength, electric_power)

    ###### Compute energy distribution in the fuel ######

    # --- binwise ν-fission fractions (this is the new bit) ---
    # Keep the EnergyFilter so we still have per-bin values
    nufi_byE = sp.get_tally(name="nufis_E").summation(
        filter_type=openmc.CellFilter, remove_filter=True
    )

    # Bin integrals (one per energy bin)
    nufi_vals = nufi_byE.mean.ravel()  # shape (nbins,)
    nufi_sum = nufi_vals.sum()
    nufi_pct = 100.0 * nufi_vals / nufi_sum

    # (Optional) rough 1σ on percentages via simple error propagation (ignores covariance)
    nufi_sd = nufi_byE.std_dev.ravel()
    nufi_sum_sd = np.sqrt((nufi_sd**2).sum())
    nufi_pct_sd = 100.0 * np.sqrt(
        (nufi_sd / nufi_sum) ** 2 + (nufi_vals * nufi_sum_sd / nufi_sum**2) ** 2
    )

    # Nice labels
    E_bands = get_energy_bands()
    labels = [
        f"[{E_bands[i]:.3g}, {E_bands[i + 1]:.3g}) eV" for i in range(len(E_bands) - 1)
    ]
    print("--------------------------------")
    print("Fission energy distribution")
    for lab, p in zip(labels, nufi_pct):
        print(f"{lab}: {p:.2f}%")
    print("--------------------------------")

    ######
    labels, pct_mean, pct_sd = flux_band_percentages(sp, "phi_E_photovoltaic", E_bands)
    print("--------------------------------")
    print("Flux band percentages in photovoltaic")
    for lab, p in zip(labels, pct_mean):
        print(f"{lab}: {p:.2f}%")
    print("--------------------------------")

    # Get normalized flux (MeV/g/source particle)
    normalized_ddd_photovoltaic = float(
        ddd_photovoltaic.get_values(scores=["flux"], value="mean")
    )
    normalized_ddd_photovoltaic_sd = float(
        ddd_photovoltaic.get_values(scores=["flux"], value="std_dev")
    )

    # Get absorption in photovoltaic
    normalized_absorption_photovoltaic = float(
        photovolatic.get_values(scores=["(n,gamma)"], value="mean")
    )
    # Get absorption in emitter
    normalized_absorption_emitter = float(
        fluence_emitter.get_values(scores=["(n,gamma)"], value="mean")
    )

    # Get heating in photovoltaic
    heating_photovoltaic = float(
        photovolatic.get_values(scores=["heating"], value="mean")
        / cst.value("joule-electron volt relationship")
    )  # J/particle

    mass_photovoltaic = photovoltaic_slice_volume * photovoltaic_density  # g

    # Calculate heating rate in photovoltaic
    heating_rate_photovoltaic = (
        heating_photovoltaic * source_strength / mass_photovoltaic
    )  # kGy/s
    yearly_heating_rate_photovoltaic = (
        heating_rate_photovoltaic * dose_time
    )  # kGy/year

    # Calculate Displacement Damage Dose Rate (MeV/g/s)
    absolute_ddd_photovoltaic = (
        normalized_ddd_photovoltaic * source_strength / photovoltaic_slice_volume # MeV/g/s
    )
    yearly_ddd_photovoltaic = absolute_ddd_photovoltaic * dose_time
    yearly_ddd_photovoltaic_ci95_pct = (
        100 * 1.96 * normalized_ddd_photovoltaic_sd / normalized_ddd_photovoltaic
        if normalized_ddd_photovoltaic != 0
        else float("nan")
    )

    absorption_photovoltaic = (
        normalized_absorption_photovoltaic * source_strength / photovoltaic_slice_volume
    )
    absorption_emitter = (
        normalized_absorption_emitter * source_strength / emitter_slice_volume
    )

    # Calculate beta-eff
    S_time = float(ifp_scores.get_values(scores=["ifp-time-numerator"], value="mean"))
    S_beta = float(ifp_scores.get_values(scores=["ifp-beta-numerator"], value="mean"))
    S_den = float(ifp_scores.get_values(scores=["ifp-denominator"], value="mean"))
    beta_eff = S_beta / S_den
    Lambda_eff = S_time / (S_den * k_eff)

    print("--------------------------------")
    print(f"Keff: {k_eff:.6e}")
    print(f"beta_eff: {beta_eff:.6e}")
    print(f"Lambda_eff : {Lambda_eff:.6e} seconds")
    print("--------------------------------")

    print("--------------------------------")
    print(f"Source strength: {source_strength:.4e} neutrons/second")
    print("--------------------------------")
    print("photovoltaic")
    print(
        f"Displacement damage: {yearly_ddd_photovoltaic:.4e} MeV/g/year (± {yearly_ddd_photovoltaic_ci95_pct:.2f}%, 95% CI)"
    )
    print(
        f"Absorption: {absorption_photovoltaic * dose_time:.4e} neutrons/cm3/year"
    )
    print(f"Dose rate: {yearly_heating_rate_photovoltaic:.4e} kGy/year")
    print("--------------------------------")

    print("emitter")
    dpa_emitter = calculate_dpa(
        sp, "damage-energy_cell_emitter", source_strength, emitter_cells
    )
    print(f"dpa emitter: {dpa_emitter:.2e} dpa/year")
    print(
        f"Absorption: {absorption_emitter * dose_time:.4e} neutrons/cm3/year"
    )
    print("--------------------------------")

    ddd_ci95p = (
        yearly_ddd_photovoltaic_ci95_pct / 100
        if np.isfinite(yearly_ddd_photovoltaic_ci95_pct)
        else None
    )
    with open("resultsim.json", "w") as f:
        f.write("{\n")
        f.write(f'  "ddd": [{yearly_ddd_photovoltaic:.4e}],\n')
        if ddd_ci95p is None:
            f.write('  "ddd_ci95p": null,\n')
        else:
            f.write(f'  "ddd_ci95p": {ddd_ci95p},\n')
        f.write(f'  "n_batches": {batches}\n')
        f.write("}\n")
