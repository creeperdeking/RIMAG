import glob
import openmc
import openmc.deplete
import os
import time
from typing import List, Dict, Literal
from tabulate import tabulate
import scipy.constants as cst
from common_lib.materials import MaterialChoice
from common_lib.assemblies import calculate_assembly_thickness


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


def generate_XML(geometry, settings, tallies, materials_dict):
    materials = openmc.Materials(materials_dict.values())

    materials.export_to_xml()
    geometry.export_to_xml()
    settings.export_to_xml()

    if tallies is not None:
        tallies.export_to_xml()


def run_sim(geometry, settings, materials_dict, tallies=None):
    generate_XML(geometry, settings, tallies, materials_dict)
    openmc.run(threads=16)
    # clean_directory()


WeightWindows = Literal["generate", "use", "no"]


def make_sim_settings(
    deterministic: bool = True,
    batches: int = 1500,
    weight_windows: WeightWindows = "no",
    window_radius: float = 0,
    window_height: float = 0,
    window_origin: tuple = (0, 0, 0),
):
    # Define neutron source
    source = openmc.Source(space=openmc.stats.Point((0, 0, 0)))

    # Define simulation settings
    settings = openmc.Settings()
    settings.source = source
    if weight_windows == "generate":
        settings.batches = 200
    else:
        settings.batches = batches
    print("batches", settings.batches)
    settings.inactive = 100
    settings.particles = 1000
    settings.seed = 42

    settings.rel_max_lost_particles = 0.01
    settings.confidence_intervals = True

    if not deterministic:
        settings.seed = int(time.time())

    if weight_windows == "generate":
        # ---------------- 2.1  spatial mesh that drives the WW -------------
        ww_mesh = openmc.RegularMesh()
        dimension_x = int(window_radius * 2 / 10)
        dimension_y = dimension_x
        dimension_z = max(int(window_height / 10), 1)
        ww_mesh.dimension = (dimension_x, dimension_y, dimension_z)
        ww_mesh.lower_left = (
            window_origin[0] - window_radius,
            window_origin[1] - window_radius,
            window_origin[2] - window_height / 2,
        )
        ww_mesh.upper_right = (
            window_origin[0] + window_radius,
            window_origin[1] + window_radius,
            window_origin[2] + window_height / 2,
        )

        # ---------------- 2.2  generator object ----------------------------
        wwg = openmc.WeightWindowGenerator(
            method="magic",  # or 'fw_cadis'
            mesh=ww_mesh,
            max_realizations=200,  # usually = # of batches
        )
        settings.weight_window_generators = wwg
    elif weight_windows == "use":
        settings.weight_window_checkpoints = {
            "collision": True,
            "surface": True,
        }  # apply at both
        settings.weight_windows_on = True
        settings.weight_windows = openmc.hdf5_to_wws("weight_windows.h5")
        settings.survival_biasing = False  # usually disable; WW handles weights
        settings.cutoff = {"weight": 1e-4, "weight_avg": 1.0}  # RR safety

    return settings


def run_keff_sim(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
):
    print()
    print("-------- Criticality simulation --------")
    print()
    print("Seed :", settings.seed, "\n")
    run_sim(geometry, settings, materials_dict)


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


def create_photovoltaic_tally(photovoltaic_cell, materials_dict):
    tally = openmc.Tally(name="photovoltaic")
    tally.filters = [openmc.CellFilter(photovoltaic_cell)]
    tally.scores = [
        "flux",
        "absorption",
        "events",
    ]  # careful, changing the order can mess up output
    return tally


def create_photovoltaic_energy_tally(photovoltaic_cell, materials_dict):
    cell_filter = openmc.CellFilter(
        [photovoltaic_cell.id]
    )  # replace cell.id with yours

    ##############################################################################
    # 2.  Denominator – plain flux  φ(E) dE
    ##############################################################################
    flux_tally = openmc.Tally(name="flux_in_cell")
    flux_tally.filters = [cell_filter]
    flux_tally.scores = ["flux"]  # ∫ φ(E) dE

    ##############################################################################
    # 3.  Numerator – E · φ(E) dE
    ##############################################################################
    # y(E)=E   (piece-wise linear, so two points is enough)
    Emin, Emax = 0.0, 20e6  # eV (0–20 MeV, change if needed)
    E_func_filter = openmc.EnergyFunctionFilter(
        energy=[Emin, Emax], y=[Emin, Emax]
    )  # multiplies score by energy

    Eflux_tally = openmc.Tally(name="E_flux_in_cell")
    Eflux_tally.filters = [cell_filter, E_func_filter]
    Eflux_tally.scores = ["flux"]  # ∫ E φ(E) dE
    return flux_tally, Eflux_tally


def create_emitter_tally(emitter_cell, materials_dict):
    tally = openmc.Tally(name="emitter")
    tally.filters = [openmc.CellFilter(emitter_cell)]
    tally.scores = [
        "flux",
        "absorption",
        "events",
    ]  # careful, changing the order can mess up output
    return tally


def print_neutron_energy(
    batches,
):
    statepoint = openmc.StatePoint(f"statepoint.{batches}.h5")
    φ = statepoint.get_tally(name="flux_in_cell").mean.flatten()[0]  # ∫φ
    Eφ = statepoint.get_tally(name="E_flux_in_cell").mean.flatten()[0]  # ∫Eφ
    avg_E_eV = Eφ / φ
    avg_E_MeV = avg_E_eV / 1e6
    avg_E_keV = avg_E_MeV * 1e3
    print(f"Average neutron energy in cell = {avg_E_keV:.3f} keV")


def print_neutron_fluence_cm2s(
    power_output_watts,
    photovoltaic_slice_volume,
    emitter_slice_volume,
    batches,
):
    results = openmc.StatePoint(f"statepoint.{batches}.h5")
    fluence_photovoltaic = results.get_tally(name="photovoltaic")
    fluence_emitter = results.get_tally(name="emitter")

    # Get normalized flux (particle-cm per source particle)
    normalized_flux_photovoltaic = fluence_photovoltaic.mean[0][0][0]
    normalized_flux_emitter = fluence_emitter.mean[0][0][0]

    # Calculate neutrons per second based on power output
    # Average energy released per fission: ~200 MeV = 3.2e-11 Joules
    energy_per_fission = 200 * 1.6e-13  # Joules
    neutrons_per_fission = 2.4  # Average number of neutrons per fission

    # Calculate fissions per second based on power
    fissions_per_second = power_output_watts / energy_per_fission

    # Calculate source strength (neutrons/second)
    source_strength = fissions_per_second * neutrons_per_fission

    # Calculate absolute flux (neutrons/cm²-s)
    absolute_flux_photovoltaic = (
        normalized_flux_photovoltaic * source_strength / photovoltaic_slice_volume
    )
    absolute_flux_emitter = (
        normalized_flux_emitter * source_strength / emitter_slice_volume
    )
    print("--------------------------------")
    print("photovoltaic")
    print(
        f"Normalized flux: {normalized_flux_photovoltaic:.4e} particle-cm per source particle"
    )
    print(f"Source strength: {source_strength:.4e} neutrons/second")
    print(f"Absolute neutron flux: {absolute_flux_photovoltaic:.4e} neutrons/cm²-s")
    print(
        f"Yearly neutron fluence: {absolute_flux_photovoltaic * 365 * 24 * 60 * 60:.4e} neutrons/cm²"
    )
    print("--------------------------------")

    print("emitter")
    print(
        f"Normalized flux: {normalized_flux_emitter:.4e} particle-cm per source particle"
    )
    print(f"Source strength: {source_strength:.4e} neutrons/second")
    print(f"Absolute neutron flux: {absolute_flux_emitter:.4e} neutrons/cm²-s")
    print(
        f"Yearly neutron fluence: {absolute_flux_emitter * 365 * 24 * 60 * 60:.4e} neutrons/cm²"
    )
    print("--------------------------------")


def run_sim_with_photovoltaic_tally(
    geometry,
    settings,
    materials_dict,
    photovoltaic_cell,
    emitter_cell,
    power_output_watts,
    photovoltaic_slice_volume,
    emitter_slice_volume,
    batches,
):
    tally_photovoltaic = create_photovoltaic_tally(photovoltaic_cell, materials_dict)
    flux_tally, Eflux_tally = create_photovoltaic_energy_tally(
        photovoltaic_cell, materials_dict
    )
    tally_emitter = create_emitter_tally(emitter_cell, materials_dict)
    tallies = openmc.Tallies(
        [tally_photovoltaic, flux_tally, Eflux_tally, tally_emitter]
    )
    run_sim(geometry, settings, materials_dict, tallies)
    print_neutron_fluence_cm2s(
        power_output_watts,
        photovoltaic_slice_volume,
        emitter_slice_volume,
        batches,
    )
    print_neutron_energy(
        batches,
    )
    clean_directory()


def print_core_characteristics(
    heavy_metal_mass,
    emissive_surface,
    core_power,
    core_power_electric,
    assembly_section_core,
    radiative_flux,
    fuel_volume,
    disks: List = None,
):
    print(
        "thicc: ",
        calculate_assembly_thickness(assembly_section_core),
    )
    if disks is not None:
        print("disks radius", disks[0].radius, "m")
    print("emissive_surface", round(emissive_surface, 2), "m2")
    print(
        "Radiative flux",
        round(
            radiative_flux,
        ),
        "W/m2",
    )
    print("core power", round(core_power / 1e6, 2), "MW")
    print("core power electric", round(core_power_electric / 1e6, 2), "MW")

    print("fuel volume", fuel_volume, "cm3")

    print(
        "heavy metal mass",
        heavy_metal_mass,
        "kg",
    )
