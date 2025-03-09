import glob
import openmc
import os
import pytime
from typing import List, Dict
from tabulate import tabulate
import scipy.constants as cst


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


def make_sim_settings(
    deterministic: bool = True,
):
    # Define neutron source
    source = openmc.Source(space=openmc.stats.Point((0, 0, 0)))

    # Define simulation settings
    settings = openmc.Settings()
    settings.source = source
    settings.batches = 1500
    settings.inactive = 50
    settings.particles = 100
    settings.seed = 42
    settings.rel_max_lost_particles = 0.1
    if not deterministic:
        settings.seed = int(pytime.time())

    return settings


def criticality_simulation(
    geometry: openmc.Geometry,
    settings: openmc.Settings,
    materials_dict: Dict[str, openmc.Material],
):
    print()
    print("-------- Criticality simulation --------")
    print()
    print("Seed :", settings.seed, "\n")
    run_sim(geometry, settings, materials_dict)


def render_geometry(universe, universe_radius, pixels, basis, origin, geometry):
    materials = openmc.Materials(materials_dict.values())
    materials.export_to_xml()
    geometry.export_to_xml()
    print("Rendering geometry")
    plot = openmc.Plot()
    plot.width = [universe_radius * 2, universe_radius * 2]
    plot.pixels = pixels
    plot.basis = basis
    plot.color_by = "material"
    plot.colors = colors
    plot.origin = origin
    plot.show_overlaps = True
    plot.overlap_color = "blue"
    image = plot.to_ipython_image()

    # Save the image to a local file
    with open("plot.png", "wb") as f:
        f.write(image.data)
    clean_directory()


def compute_burnup(thermal_power, time_table, fuel_mass):
    burnup = []
    for time in time_table:
        burnup.append(1000 * thermal_power / 1000000 * time / fuel_mass)
    return burnup


def compute_fuel_mass(
    fuel_surface_area: float,
    fuel_hm_density: float,
    fuel_thickness: float,
    fuel_density: float,
):
    return fuel_surface_area * fuel_thickness * fuel_density * fuel_hm_density


def run_depletion_sim(
    thermal_power: float,
    geometry,
    settings,
    materials,
    fuel_mass: float,
    sim_timesteps: List[float] = [],
    timesteps_units: str = "d",
):
    fission_q = {"U235": 202.5e6}  # energy in eV # "U233": 200.1e6, "Pu239": 211.5e6
    model = openmc.Model(geometry, materials, settings)
    op = openmc.deplete.CoupledOperator(
        model, "chain_endfb71_pwr.xml", fission_q=fission_q
    )
    max_step = 2 * op.heavy_metal / thermal_power * 1e3
    # Check if any timestep exceeds the maximum allowed step size
    for step in sim_timesteps:
        if step > max_step:
            raise ValueError(
                f"Timestep {step} {timesteps_units} exceeds maximum allowed step size of {max_step:.2f} {timesteps_units}. "
                f"This limit is based on the heavy metal content and thermal power."
            )

    openmc.deplete.CECMIntegrator(
        op, sim_timesteps, thermal_power, timestep_units=timesteps_units
    ).integrate()

    results = openmc.deplete.Results("depletion_results.h5")
    time, keff = results.get_keff(time_units="d")
    uranium_burnups = compute_burnup(thermal_power, time, fuel_mass)
    results.export_to_materials(burnup_index=1)
    results_table = [
        ["Time (year)"] + [round(t / 365, 3) for t in time],
        ["Keff"] + [round(a[0], 3) for a in keff],
        ["Uranium Burnup (MWd/kgHM)"] + [round(a, 3) for a in uranium_burnups],
        ["U232 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(mat=u233f6, nuc="U232", time_units="d")[1]
        ],
        ["U233 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(mat=u233f6, nuc="U233", time_units="d")[1]
        ],
        ["U234 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(mat=u233f6, nuc="U234", time_units="d")[1]
        ],
        ["U235 (mol)"]
        + [
            round(a / cst.Avogadro, 3)
            for a in results.get_atoms(mat=u233f6, nuc="U235", time_units="d")[1]
        ],
        ["Xe135 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(mat=u233f6, nuc="Xe135", time_units="d")[1]
        ],
        ["Sm149 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(mat=u233f6, nuc="Sm149", time_units="d")[1]
        ],
        ["Gd157 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(mat=u233f6, nuc="Gd157", time_units="d")[1]
        ],
        ["Blanket Th232 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=thorium_tetrafluoride, nuc="Th232", time_units="d"
            )[1]
        ],
        ["Blanket U232 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=thorium_tetrafluoride, nuc="U232", time_units="d"
            )[1]
        ],
        ["Blanket U233 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=thorium_tetrafluoride, nuc="U233", time_units="d"
            )[1]
        ],
        ["Blanket Pa233 (mol)"]
        + [
            round(a / cst.Avogadro, 5)
            for a in results.get_atoms(
                mat=thorium_tetrafluoride, nuc="Pa233", time_units="d"
            )[1]
        ],
    ]

    print(tabulate(results_table))
