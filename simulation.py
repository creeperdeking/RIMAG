from typing import List

from materials import materials_dict
from drums import CoreDesc, DrumLayer, make_drum_layers
from pydantic import BaseModel
import openmc
import pytime
from simlib import clean_directory


class AssemblySectionDesc(BaseModel):
    fuel_thickness: float
    fuel_cladding_gap: float
    cladding_thickness: float
    cladding_emitter_gap: float
    emitter_thickness: float


class CompleteDrumDescription(BaseModel):
    drums: List[DrumLayer]
    assembly_section: AssemblySectionDesc


def assembly_section_thickness(section: AssemblySectionDesc) -> float:
    return (
        section.fuel_thickness
        + section.fuel_cladding_gap * 2
        + section.cladding_thickness * 2
        + section.cladding_emitter_gap * 2
        + section.emitter_thickness
    )


def make_assembly_sections(
    assembly_section: AssemblySectionDesc,
    core: CoreDesc,
    outer_drum: DrumLayer,
    distance_between_drums: float,
    last_drum_core_margin: float,
) -> CompleteDrumDescription:
    drums = make_drum_layers(
        outer_drum, core.core_radius, distance_between_drums, last_drum_core_margin
    )
    return CompleteDrumDescription(
        drums=drums[:-1],
        assembly_section=assembly_section,
    )


def create_cylinder(radius: float, height: float, boundary_type: str = "transmission"):
    return (
        -openmc.ZCylinder(r=radius, boundary_type=boundary_type)
        & -openmc.ZPlane(z0=height / 2, boundary_type=boundary_type)
        & +openmc.ZPlane(z0=-height / 2, boundary_type=boundary_type)
    )


class MaterialChoice(BaseModel):
    neutron_shield: str
    reflector: str
    fuel: str


def define_geometry(
    core: CoreDesc,
    material_choice: MaterialChoice,
    assembly_section: AssemblySectionDesc,
):

    core_shape = create_cylinder(core.core_diameter / 2, core.core_height)

    reflector_shape = ~core_shape & create_cylinder(
        core.core_diameter / 2 + core.reflector_thickness, core.core_height
    )

    outer_boundary_shape = (
        -openmc.ZCylinder(
            r=core.core_diameter / 2
            + core.reflector_thickness
            + core.neutron_shield_thickness,
            boundary_type="vacuum",
        )
        & -openmc.ZPlane(
            z0=core.core_height / 2
            + core.reflector_thickness
            + core.neutron_shield_thickness,
            boundary_type="vacuum",
        )
        & +openmc.ZPlane(
            z0=-core.core_height / 2
            - core.reflector_thickness
            - core.neutron_shield_thickness,
            boundary_type="vacuum",
        )
    )

    neutron_shield_shape = ~core_shape & outer_boundary_shape

    fuel = openmc.Cell(name="fuel")
    fuel.fill = materials_dict[material_choice.fuel]
    fuel.region = core_shape
    # fuel.temperature = 900

    reflector = openmc.Cell(name="reflector")
    reflector.fill = materials_dict[material_choice.reflector]
    reflector.region = reflector_shape

    neutron_shield = openmc.Cell(name="neutron_shield")
    neutron_shield.fill = materials_dict[material_choice.neutron_shield]
    neutron_shield.region = neutron_shield_shape

    # Return universe and geometry
    universe = openmc.Universe(
        cells=[
            fuel,
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe)


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
        core_diameter=100,
        core_height=100,
        reflector_thickness=20,
        neutron_shield_thickness=20,
        gamma_shield_thickness=10,
    ),
    MaterialChoice(
        neutron_shield="Boron Carbide",
        reflector="Molybdenum",
        fuel="Uranium Carbide",
    ),
    AssemblySectionDesc(
        fuel_thickness=1,
        fuel_cladding_gap=0.1,
        cladding_thickness=0.1,
        cladding_emitter_gap=0.1,
        emitter_thickness=1,
    ),
)

criticality_simulation(
    geometry,
    universe,
)
