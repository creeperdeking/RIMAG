from materials import materials_dict
from drums import CoreDesc, DrumDesc
import openmc
import pytime
from simlib import clean_directory
from geometry import AssemblySectionDesc, MaterialChoice, define_geometry


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
    openmc.run(threads=8)
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


geometry, universe = define_geometry(
    CoreDesc(
        core_diameter=80,
        core_height=80,
        reflector_thickness=20,
        neutron_shield_thickness=20,
        gamma_shield_thickness=10,
    ),
    DrumDesc(
        drum_core_distance=100,
        drum_core_margin=2,
        height=80,
    ),
    MaterialChoice(
        neutron_shield="Boron Carbide",
        reflector="Molybdenum",
        fuel="Uranium Carbide",
    ),
    AssemblySectionDesc(
        fuel_thickness=0.64,
        fuel_cladding_gap=0.03,
        cladding_thickness=0.05,
        cladding_drum_gap=0.075,
        drum_thickness=0.05,
    ),
)

criticality_simulation(
    geometry,
    universe,
)
