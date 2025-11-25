import gc
import glob
import openmc
import openmc.deplete
import os
import time
from typing import List, Dict, Literal
from tabulate import tabulate
import json
import scipy.constants as cst
from common_lib.materials import MonitoredNuclide
import numpy as np
import h5py
import math
import sys
from common_lib.geometry_utils import get_geometry_bounding_box
from common_lib.geometry_types import GeometrySettings
from common_lib.tallies import (
    create_C14_production_tally,
    create_tritium_production_tally,
    create_O16_activation_tally,
    create_dpa_tally,
    create_emitter_tally,
    create_energy_deposition_tallies,
    create_fission_energy_weighted_flux_tally,
    create_flux_band_tally,
    create_photovoltaic_flux_tally,
    create_photovoltaic_heating_absorption_tally,
    print_tallies,
)
from one_layer_disk_design.disks_core_characteristics import CoreCharacteristics


def clean_directory():
    patternlist = [
        "materials.xml",
        "settings.xml",
        "tallies.xml",
        "geometry.xml",
        "summary.h5",
        "particle*.h5",
        "particle*.h5",
        "statepoint*.h5",
        "openmc_*.h5",
    ]
    for pattern in patternlist:
        filelist = glob.glob(pattern)
        for file in filelist:
            try:
                os.remove(file)
            except OSError as e:
                pass


def clean_xml():
    patternlist = [
        "materials.xml",
        "settings.xml",
        "tallies.xml",
        "geometry.xml",
    ]
    for pattern in patternlist:
        filelist = glob.glob(pattern)
        for file in filelist:
            try:
                os.remove(file)
            except OSError as e:
                pass


def generate_XML(geometry, settings, tallies, materials_dict):
    clean_xml()
    materials = openmc.Materials(materials_dict.values())

    materials.export_to_xml()
    geometry.export_to_xml()
    settings.export_to_xml()

    if tallies is not None:
        tallies.export_to_xml()


def _get_threads_from_settings(default_threads: int = 20) -> int:
    """
    Read the number of threads from simsettings.json located in the current
    working directory (where Python was executed).
    Falls back to default_threads if the file or value is unavailable/invalid.
    """
    try:
        settings_path = "simsettings.json"
        if not os.path.exists(settings_path):
            return default_threads
        with open(settings_path, "r") as f:
            data = json.load(f)
        threads = int(data.get("threads", default_threads))
        if threads <= 0:
            return default_threads
        return threads
    except Exception:
        return default_threads


def run_sim(geometry, settings, materials_dict, tallies=None, quiet=False):
    generate_XML(geometry, settings, tallies, materials_dict)
    if settings.run_mode == "volume":
        print("[OpenMC] Running stochastic volume calculations...")
    threads = _get_threads_from_settings(default_threads=20)
    if quiet:
        # Redirect stdout and stderr to suppress OpenMC output
        with open(os.devnull, "w") as devnull:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull
            try:
                openmc.run(threads=threads, geometry_debug=True)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
    else:
        openmc.run(threads=threads, geometry_debug=False)
    # clean_directory()


WeightWindows = Literal["generate", "use", "no"]


def make_ww_mesh(
    lower_left_corner: tuple,
    upper_right_corner: tuple,
    cell_dimension: float = 20,
):
    ww_mesh = openmc.RegularMesh()
    dimension_x = max(
        int((upper_right_corner[0] - lower_left_corner[0]) / cell_dimension), 1
    )
    dimension_y = dimension_x
    dimension_z = max(
        int((upper_right_corner[2] - lower_left_corner[2]) / cell_dimension), 1
    )
    ww_mesh.dimension = (dimension_x, dimension_y, dimension_z)
    ww_mesh.lower_left = lower_left_corner
    ww_mesh.upper_right = upper_right_corner
    return ww_mesh


def check_ww_mesh_is_inside_geometry(mesh, geometry):
    # geometry extents
    ll_geom, ur_geom = geometry.bounding_box  # returns 2×3 array (x,y,z)
    # :contentReference[oaicite:0]{index=0}

    # does every coordinate lie inside the mesh?
    inside = np.all(mesh.lower_left <= ll_geom) and np.all(mesh.upper_right >= ur_geom)

    if inside:
        print("✅  mesh covers the whole geometry")
    else:
        print("❌  mesh misses part of the geometry")
        print("    geometry ll:", ll_geom, "  mesh ll:", mesh.lower_left)
        print("    geometry ur:", ur_geom, "  mesh ur:", mesh.upper_right)


def make_sim_settings(
    deterministic: bool = True,
    batches: int = 1500,
    weight_windows: WeightWindows = "no",
    lower_left_corner: tuple = (0, 0, 0),
    upper_right_corner: tuple = (0, 0, 0),
    geometry: openmc.Geometry = None,
    particle_type: Literal["neutron", "photon"] = "neutron",
    survival_biasing: bool = True,
):
    # Define neutron source
    source = openmc.IndependentSource(space=openmc.stats.Point((0, 0, 0)))
    # Define simulation settings
    settings = openmc.Settings()
    settings.volume_normalized_flux_tallies = False
    settings.inactive = 10
    settings.max_history_splits = 5000  # cap long histories
    UPDATE_INTERVAL = 8
    WEIGHT_WINDOWS_BATCHES = int(
        batches / 10
    )  # 30 * UPDATE_INTERVAL + settings.inactive
    settings.photon_transport = particle_type == "photon"
    settings.source = source
    if weight_windows == "generate":
        settings.batches = WEIGHT_WINDOWS_BATCHES
    else:
        settings.batches = batches
    print("batches", settings.batches)

    settings.particles = 10000
    settings.generations_per_batch = 10
    settings.seed = 42
    settings.survival_biasing = survival_biasing
    if survival_biasing:
        settings.cutoff = {
            "weight": 0.25,                  # w_c: roulette threshold
            "weight_avg": 1.0,               # w_s: post-survival weight
            # If you want cutoffs relative to starting weight instead of current weight:
            # "survival_normalization": True
        }

    settings.rel_max_lost_particles = 0.01
    settings.confidence_intervals = True

    if 1/(settings.particles * settings.generations_per_batch) >= 1/(math.sqrt(settings.batches)):
        raise ValueError("The number of particles per generation per batch is too low to achieve the desired confidence interval. Increase the number of particles per generation per batch or increase the number of batches.")

    if not deterministic:
        settings.seed = int(time.time())

    if weight_windows == "generate":
        ww_mesh = make_ww_mesh(lower_left_corner, upper_right_corner)
        check_ww_mesh_is_inside_geometry(ww_mesh, geometry)

        wwg = openmc.WeightWindowGenerator(
            method="magic",  # or 'fw_cadis'
            mesh=ww_mesh,
            max_realizations=WEIGHT_WINDOWS_BATCHES,  # usually = # of batches
            update_interval=UPDATE_INTERVAL,
        )

        settings.weight_window_generators = wwg
    elif weight_windows == "use":
        settings.weight_window_checkpoints = {
            "collision": True,
            "surface": False,
        }  # apply at both
        settings.weight_windows_on = True
        settings.weight_windows = openmc.hdf5_to_wws("weight_windows.h5")
        settings.survival_biasing = False  # usually disable; WW handles weights
        settings.cutoff = {"weight": 1e-4, "weight_avg": 1.0}  # RR safety

    return settings


def make_sim_photon_from_cells(
    source_cells: List[openmc.Cell],
    gamma_E_MeV: float = 1.27,  # MeV
    deterministic: bool = True,
    batches: int = 1500,
):
    settings = make_sim_settings(
        deterministic, batches, "no", (0, 0, 0), (0, 0, 0), None, "photon"
    )
    sources = []
    for c in source_cells:
        # Bounding box gives something to sample in; rejection via constraints keeps it inside
        ll, ur = c.bounding_box
        space_dist = openmc.stats.Box(ll, ur)  # uniform in the box
        energy_dist = openmc.stats.delta_function(gamma_E_MeV * 1e6)  # eV input
        angle_dist = openmc.stats.Isotropic()

        src = openmc.IndependentSource(
            particle="photon",
            space=space_dist,
            energy=energy_dist,
            angle=angle_dist,
            constraints={"domains": [c]},  # << keeps points inside cell
        )
        sources.append(src)
    settings.run_mode = "fixed source"
    settings.source = sources

    return settings


def run_keff_sim(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
    quiet: bool = False,
):
    print()
    print("-------- Criticality simulation --------")
    print()
    print("Seed :", settings.seed, "\n")
    run_sim(geometry, settings, materials_dict, quiet=quiet)


def render_geometry(
    universe,
    universe_radius,
    pixels,
    basis,
    origin,
    geometry,
    colors,
    materials_dict,
    universe_height=None,
):
    if universe_height is None:
        universe_height = universe_radius * 2
    materials = openmc.Materials(materials_dict.values())
    materials.export_to_xml()
    geometry.export_to_xml()
    print("Rendering geometry")
    plot = openmc.Plot()
    plot.width = [universe_radius * 2, universe_height]
    plot.pixels = pixels
    plot.basis = basis
    plot.color_by = "material"
    plot.colors = colors
    plot.origin = origin
    plot.show_overlaps = True
    plot.overlap_color = "red"
    image = plot.to_ipython_image()

    # Save the image to a local file
    with open("plot.png", "wb") as f:
        f.write(image.data)


def stochastic_volume_calculation(
    cells: List[openmc.Cell],
    geometry: openmc.Geometry,
    materials_dict: Dict[str, openmc.Material],
    geometry_settings: GeometrySettings,
    samples: int = 10000000,
):
    """
    Stochastic volume calculation, adds volume information to the cells
    """
    if any(c.volume is None for c in cells):
        lower_left_corner, upper_right_corner = get_geometry_bounding_box(
            geometry_settings
        )
        # 1e5 samples per cell is usually enough for <1 % error
        volcalc = openmc.VolumeCalculation(
            domains=cells,
            samples=samples,
            lower_left=lower_left_corner,
            upper_right=upper_right_corner,
        )
        settings = openmc.Settings()
        settings.volume_calculations = [volcalc]
        settings.run_mode = "volume"
        settings.export_to_xml()
        run_sim(geometry, settings, materials_dict, quiet=True)

        # Read uncertainty directly from HDF5 file
        all_ok = True
        with h5py.File("volume_1.h5", "r") as f:
            for cell in cells:
                cell_id = cell.id
                vol_data = f[f"domain_{cell_id}/volume"][:]
                volume = vol_data[0]
                std_dev = vol_data[1]
                rel_uncertainty = std_dev / volume * 100 if volume > 0 else float("inf")
                if rel_uncertainty == float("inf") or "boundary_layer" in cell.name:
                    # Ignore this cell, set its volume to zero
                    cell.volume = 0.0
                    continue
                if rel_uncertainty > 5.0:
                    all_ok = False
                    raise ValueError(
                        f"❌ Volume calculation uncertainty too high ({rel_uncertainty:.1f}%) for cell '{cell.name}' (ID {cell_id}).\n"
                        f"    Increase number of samples or check geometry."
                    )
        if all_ok:
            print("✅ All volume calculation uncertainties are below 5%.")

        vol_calc = openmc.VolumeCalculation.from_hdf5("volume_1.h5")
        geometry.add_volume_information(vol_calc)  # attaches .volume to each cell
    return geometry


def compute_burnup(
    thermal_power: float,  # W
    time_table: List[float],  # d
    fuel_mass: float,  # kg
) -> List[float]:
    burnup = []
    for time in time_table:
        burnup.append(thermal_power / 1e6 * time / fuel_mass)
    return burnup


def print_depletion_result(materials_dict, material_choice, thermal_power, fuel_mass):
    results = openmc.deplete.Results("depletion_results.h5")
    time, keff = results.get_keff(time_units="d")
    uranium_burnups = compute_burnup(thermal_power, time, fuel_mass)
    results.export_to_materials(burnup_index=1)
    hm_results_table = [
        ["Time (year)"] + [round(t / 365, 3) for t in time],
        ["Keff"] + [round(a[0], 3) for a in keff],
        ["Uranium Burnup (MWd/kgHM)"] + [round(a, 3) for a in uranium_burnups],
        ["U232 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U232", time_units="d"
            )[1]
        ],
        ["U233 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U233", time_units="d"
            )[1]
        ],
        ["U234 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U234", time_units="d"
            )[1]
        ],
        ["U235 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U235", time_units="d"
            )[1]
        ],
        ["U236 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U236", time_units="d"
            )[1]
        ],
        ["Np237 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Np237", time_units="d"
            )[1]
        ],
        ["Pu238 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu238", time_units="d"
            )[1]
        ],
        ["U238 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="U238", time_units="d"
            )[1]
        ],
        ["Pu239 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu239", time_units="d"
            )[1]
        ],
        ["Pu240 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu240", time_units="d"
            )[1]
        ],
        ["Pu241 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu241", time_units="d"
            )[1]
        ],
        ["Pu242 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Pu242", time_units="d"
            )[1]
        ],
    ]
    fission_products_results_table = [
        ["Time (year)"] + [round(t / 365, 3) for t in time],
        ["Keff"] + [round(a[0], 3) for a in keff],
        ["Uranium Burnup (MWd/kgHM)"] + [round(a, 3) for a in uranium_burnups],
        ["Xe135 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Xe135", time_units="d"
            )[1]
        ],
        ["Sm149 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Sm149", time_units="d"
            )[1]
        ],
        ["Gd157 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=materials_dict[material_choice.fuel], nuc="Gd157", time_units="d"
            )[1]
        ],
    ]
    print("Heavy metals")
    print(tabulate(hm_results_table))
    print("Notable fission products")
    print(tabulate(fission_products_results_table))


def run_depletion_sim(
    thermal_power: float,
    geometry,
    settings,
    materials,
    sim_steps: List[float] = [],
    steps_units: str = "d",
):
    fission_q = {"U235": 202.5e6}  # energy in eV # "U233": 200.1e6, "Pu239": 211.5e6
    model = openmc.Model(geometry, materials, settings)
    op = openmc.deplete.CoupledOperator(
        model, "chain_endfb71_pwr.xml", fission_q=fission_q
    )
    max_step = 2 * op.heavy_metal / thermal_power * 1e3
    # Check if any timestep exceeds the maximum allowed step size
    for step in sim_steps:
        if step > max_step:
            print(
                f"Timestep {step} {steps_units} exceeds maximum allowed step size of {max_step:.2f} {steps_units}. "
                f"This limit is based on the heavy metal content and thermal power."
            )

    openmc.deplete.CECMIntegrator(
        op, sim_steps, thermal_power, timestep_units=steps_units
    ).integrate()


def calculate_source_strength(
    power_output_watts,
):
    # Calculate neutrons per second based on power output
    # Average energy released per fission: ~200 MeV = 3.2e-11 Joules
    energy_per_fission = 200 * 1.6e-13  # Joules
    neutrons_per_fission = 2.4  # Average number of neutrons per fission

    # Calculate fissions per second based on power
    fissions_per_second = power_output_watts / energy_per_fission

    # Calculate source strength (neutrons/second)
    source_strength = fissions_per_second * neutrons_per_fission

    return source_strength


def run_sim_with_tallies(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_cells: List[openmc.Cell],
    photovoltaic_density: float,
    emitter_cells: List[openmc.Cell],
    fuel_cells: List[openmc.Cell],
    moderator_cells: List[openmc.Cell],
    shield_moderator_cells: List[openmc.Cell],
    coolant_cells: List[openmc.Cell],
    electric_power: float,
    heat_deposition_cells: List[openmc.Cell],
    source_strength: float,
    batches: int,
    particle_type: Literal["neutron", "photon"] = "neutron",
    monitored_nuclide: MonitoredNuclide = None,
):
    tally_photovoltaic = create_photovoltaic_heating_absorption_tally(
        photovoltaic_cells, particle_type, monitored_nuclide
    )
    photovoltaic_flux_tally = create_photovoltaic_flux_tally(
        photovoltaic_cells, particle_type
    )
    tally_tritium_production_moderator = create_tritium_production_tally(
        moderator_cells, suffix="_moderator"
    )
    tally_tritium_production_shield = create_tritium_production_tally(
        shield_moderator_cells, suffix="_shield_moderator"
    )
    tally_tritium_production_coolant = create_tritium_production_tally(
        coolant_cells, suffix="_coolant"
    )
    tally_C14_production_moderator = create_C14_production_tally(
        moderator_cells, suffix="_moderator"
    )
    tally_C14_production_shield = create_C14_production_tally(
        shield_moderator_cells, suffix="_shield_moderator"
    )
    tally_C14_production_coolant = create_C14_production_tally(
        coolant_cells, suffix="_coolant"
    )
    tally_O16_activation_moderator = create_O16_activation_tally(
        moderator_cells, suffix="_moderator"
    )
    tally_O16_activation_shield = create_O16_activation_tally(
        shield_moderator_cells, suffix="_shield_moderator"
    )
    tally_O16_activation_coolant = create_O16_activation_tally(
        coolant_cells, suffix="_coolant"
    )
    t_flux, t_nufi, t_Enufi = create_fission_energy_weighted_flux_tally(fuel_cells)
    tally_emitter = create_emitter_tally(
        emitter_cells, materials_dict, particle_type, monitored_nuclide
    )
    tally_photovoltaic_flux_band = create_flux_band_tally(
        photovoltaic_cells, "phi_E_photovoltaic"
    )
    t_heat_cells, t_heat_total, t_kapf_total = create_energy_deposition_tallies(
        heat_deposition_cells, use_heating_local=particle_type != "photon"
    )
    dpa_emitter = create_dpa_tally(emitter_cells, suffix="_emitter")
    t_heat_moderator_cells, t_heat_moderator_total, t_kapf_moderator_total = (
        create_energy_deposition_tallies(
            moderator_cells,
            use_heating_local=particle_type != "photon",
            tally_prefix="dep_moderator_",
        )
    )
    # IFP tally: no filters -> global; three scores in one tally
    tally_ifp = openmc.Tally(name="ifp-scores")
    tally_ifp.scores = ["ifp-time-numerator", "ifp-beta-numerator", "ifp-denominator"]

    tallies = openmc.Tallies(
        [
            tally_photovoltaic,
            photovoltaic_flux_tally,
            tally_emitter,
            tally_ifp,
            t_flux,
            t_nufi,
            t_Enufi,
            tally_photovoltaic_flux_band,
            t_heat_cells,
            t_heat_total,
            t_kapf_total,
            t_heat_moderator_cells,
            t_heat_moderator_total,
            t_kapf_moderator_total,
            tally_tritium_production_moderator,
            tally_tritium_production_shield,
            tally_tritium_production_coolant,
            tally_C14_production_moderator,
            tally_C14_production_shield,
            tally_C14_production_coolant,
            tally_O16_activation_moderator,
            tally_O16_activation_shield,
            tally_O16_activation_coolant,
            dpa_emitter,
        ]
    )
    run_sim(geometry, settings, materials_dict, tallies)
    print_tallies(
        source_strength,
        emitter_cells,
        sum(cell.volume for cell in photovoltaic_cells),
        photovoltaic_density,
        sum(cell.volume for cell in emitter_cells),
        electric_power,
        batches,
    )

    # clean_directory()


def xe135_peak_mass_g(
    P_th_W,
    # --- defaults (SI) ---
    thermal_flux=3.7e17,  # n·m^-2·s^-1  (≈3.7e13 n·cm^-2·s^-1 typical PWR)
    E_f_J=200e6 * 1.602176634e-19,  # J per fission (~200 MeV)
    y_I=6.28968e-2,  # I-135 cumulative yield per fission (U-235, thermal)
    t12_I_s=6.57 * 3600.0,  # I-135 half-life (s)
    t12_Xe_s=9.14 * 3600.0,  # Xe-135 half-life (s)
    M_Xe135_kg_per_mol=134.9072075e-3,  # kg·mol^-1
    N_A=6.02214076e23,  # mol^-1
):
    """
    Return the total mass (kg) of Xe-135 in the core at its post-shutdown maximum,
    assuming long full-power operation (I-135 at equilibrium) followed by shutdown.
    Inputs are SI; P_th_W is thermal power in watts.
    """

    # decay constants
    lam_I = math.log(2) / t12_I_s
    lam_Xe = math.log(2) / t12_Xe_s

    # fission rate (#/s)
    F = P_th_W / E_f_J

    # Xe-135 absorption removal rate during full power, r=0.02 is the epithermal index
    sigma_a_xe135 = 2.65e-22
    sigmaPhi = thermal_flux * sigma_a_xe135

    # Equilibrium inventories at power:
    # I0 = y_I * F / lam_I ; Xe0 not needed explicitly for the peak formula below
    I0 = y_I * F / lam_I

    # Time-to-peak after shutdown (Φ → 0) for the long-run steady state:
    # t_peak = ln[ (lam_Xe/lam_I)*((lam_I+sigmaPhi)/(lam_Xe+sigmaPhi)) ] / (lam_Xe - lam_I)
    bracket = (lam_Xe / lam_I) * ((lam_I + sigmaPhi) / (lam_Xe + sigmaPhi))
    t_peak = math.log(bracket) / (lam_Xe - lam_I)

    # At the peak, Xe = (lam_I/lam_Xe)*I(t_peak)
    I_tp = I0 * math.exp(-lam_I * t_peak)
    N_Xe_peak = (lam_I / lam_Xe) * I_tp  # atoms

    # convert atoms -> mass (g)
    m_g = (N_Xe_peak / N_A) * M_Xe135_kg_per_mol * 1e3
    return m_g


def add_xe135_to_geometry(
    geometry, materials_dict, material_choice, core_characteristics
):
    # For all cells in the geometry that have the same material as material_choice.fuel,
    # print their volume and change their composition to add 5% Xenon135 by weight

    # Find the material object for the fuel
    fuel_material = materials_dict[material_choice.fuel]

    # Get all cells in the geometry
    all_cells = [cell for _, cell in geometry.get_all_cells().items()]

    found_cells = []

    # Loop through all cells and find those with the same material as the fuel
    for cell in all_cells:
        # cell.fill can be a Material or a Universe; we want only Material
        if hasattr(cell, "fill") and isinstance(cell.fill, type(fuel_material)):
            if cell.fill is fuel_material:
                xe135 = openmc.Material(name="Xe135")
                xe135.add_nuclide("Xe135", 1.0, "wo")
                xe135.set_density("g/cm3", 12)
                weight_xe135 = xe135_peak_mass_g(core_characteristics.core_power)
                weight_fuel = cell.volume * fuel_material.density
                weight_total = weight_fuel + weight_xe135
                weight_xe135_fraction = weight_xe135 / weight_total
                new_material = openmc.Material.mix_materials(
                    [fuel_material, xe135],
                    [1 - weight_xe135_fraction, weight_xe135_fraction],
                    "wo",
                )
                new_material.name = "Fuel + Xe135"
                materials_dict[new_material.name] = new_material
                cell.fill = new_material
                found_cells.append(cell)
    if len(found_cells) > 1:
        raise ValueError("Found multiple cells with the same fuel material")


def print_core_characteristics(
    core_characteristics: CoreCharacteristics,
):
    print(
        "rotary axle diameter",
        round(core_characteristics.rotary_axle_radius * 2),
        "cm",
    )
    print(
        "vertical core height",
        round(core_characteristics.vertical_core_height, 2),
        "cm",
    )
    print(
        "cold temp",
        round(core_characteristics.cold_temp - 273),
        "°C",
    )
    print(
        "emissive_surface",
        round(core_characteristics.fuel_emissive_area / 1e4, 2),
        "m2",
    )
    print(
        "Radiative flux",
        round(
            core_characteristics.radiative_flux,
        ),
        "W/m2",
    )
    print("core power", round(core_characteristics.core_power / 1e6, 2), "MW")
    print(
        "core power electric",
        round(core_characteristics.core_power_electric / 1e6, 2),
        "MW",
    )
    print(
        "photovoltaic power",
        round(core_characteristics.photovoltaic_power / 1e6, 2),
        "MW",
    )

    print(
        "photovoltaic power density",
        round(core_characteristics.photovoltaic_power_density * 1e4, 2),
        "W/m2",
    )
    print(
        "photovoltaic power per m",
        round(core_characteristics.photovoltaic_power_per_m / 1e6, 2),
        "MW/m",
    )

    print(
        "photovoltaic area",
        round(core_characteristics.photovoltaic_area / 1e4, 2),
        "m2",
    )

    print("fuel lifetime", core_characteristics.fuel_lifetime, "years")
    print("fuel thickness", round(core_characteristics.fuel_thickness /10, 2), "mm")
