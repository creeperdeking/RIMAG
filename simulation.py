from materials import materials_dict, colors
from drums import CoreDesc, DrumDesc
import openmc
import pytime
import matplotlib.pyplot as plt
from simlib import clean_directory
from geometry import (
    AssemblySectionDesc,
    MaterialChoice,
    define_geometry,
    calculate_assembly_thickness,
)


def assembly_section_thickness(section: AssemblySectionDesc) -> float:
    return (
        section.fuel_thickness
        + section.fuel_cladding_gap * 2
        + section.cladding_thickness * 2
        + section.cladding_drum_gap * 2
        + section.drum_thickness
    )


def generate_XML(materials, geometry, settings, tallies):
    materials.export_to_xml()
    geometry.export_to_xml()
    settings.export_to_xml()

    if tallies is not None:
        tallies.export_to_xml()


def run_sim(geometry, settings, materials, tallies=None):
    generate_XML(materials, geometry, settings, tallies)
    openmc.run(threads=16)
    clean_directory()


def criticality_simulation(
    geometry: openmc.Geometry,
    universe: openmc.Universe,
    deterministic: bool = True,
    keffsim: bool = True,
):
    # Define neutron source
    source = openmc.Source(space=openmc.stats.Point((0, 0, 0)))

    # Define simulation settings
    settings = openmc.Settings()
    settings.source = source
    settings.batches = 5000
    settings.inactive = 50
    settings.particles = 100
    settings.seed = 42
    settings.rel_max_lost_particles = 0.1

    if not deterministic:
        settings.seed = int(pytime.time())

    materials = openmc.Materials(materials_dict.values())

    if keffsim:
        print()
        print("-------- Criticality simulation --------")
        print()
        print("Seed :", settings.seed, "\n")
        run_sim(geometry, settings, materials)


fuel_thicc = 0.45
assembly_section = AssemblySectionDesc(
    fuel_thickness=fuel_thicc,
    fuel_cladding_gap=fuel_thicc * 0.1 * 0.5,
    cladding_thickness=0.03,
    cladding_drum_gap=0.07,
    drum_thickness=0.01,
)

print("thicc")
print(calculate_assembly_thickness(assembly_section))

core_diameter = 120
geometry, universe = define_geometry(
    CoreDesc(
        core_diameter=core_diameter,
        core_height=core_diameter,
        reflector_thickness=20,
        neutron_shield_thickness=20,
        gamma_shield_thickness=10,
    ),
    DrumDesc(
        drum_core_distance=core_diameter + 30 / 2,
        drum_core_margin_inner=2,
        drum_core_margin_outer=0.5,
        height=core_diameter,
    ),
    MaterialChoice(
        neutron_shield="Boron Carbide",
        reflector="Molybdenum",
        fuel="Plutonium Carbide",
        cladding="Molybdenum",
        drum="Molybdenum",
    ),
    assembly_section=assembly_section,
    half_drum=True,
)


def render_geometry(universe, universe_radius, pixels, basis, origin):
    print("Rendering geometry")
    universe.plot(
        width=(universe_radius * 2, universe_radius * 2),
        pixels=pixels,
        basis=basis,
        color_by="material",
        colors=colors,
        origin=origin,
    )
    plt.savefig("plot.png")


render = False
if render:
    render_geometry(
        universe,
        universe_radius=(100),
        pixels=(2500, 2500),
        basis="xy",
        origin=(0, 0.0, 0.0),
    )
else:
    criticality_simulation(
        geometry,
        universe,
    )
