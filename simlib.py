import glob
import openmc
import os
import pytime
from materials import materials_dict
import matplotlib.pyplot as plt
from materials import colors


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
    settings.batches = 1500
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
