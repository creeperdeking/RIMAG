from pydantic import BaseModel
import openmc
from materials import materials_dict
from drums import CoreDesc, make_drums
from assemblies import (
    get_assemblies_boundaries,
    calculate_assembly_thickness,
    make_assemblies_cells,
)


class DrumDesc(BaseModel):
    distance_from_core: float
    drum_core_distance: float
    drum_core_margin: float
    height: float


class AssemblySectionDesc(BaseModel):
    fuel_thickness: float
    fuel_cladding_gap: float
    cladding_thickness: float
    cladding_drum_gap: float
    drum_thickness: float


class MaterialChoice(BaseModel):
    neutron_shield: str
    reflector: str
    fuel: str
    cladding: str
    drum: str


def create_cylinder(radius: float, height: float, boundary_type: str = "transmission"):
    return (
        -openmc.ZCylinder(r=radius, boundary_type=boundary_type)
        & -openmc.ZPlane(z0=height / 2, boundary_type=boundary_type)
        & +openmc.ZPlane(z0=-height / 2, boundary_type=boundary_type)
    )


def create_hollow_cylinder(
    outer_radius: float,
    inner_radius,
    height: float,
    distance_from_origin: float = 0,
):
    return (
        -openmc.ZCylinder(r=outer_radius, origin=(distance_from_origin, 0, 0))
        & +openmc.ZCylinder(r=inner_radius, origin=(distance_from_origin, 0, 0))
        & -openmc.ZPlane(z0=height / 2)
        & +openmc.ZPlane(z0=-height / 2)
    )


def define_geometry(
    core: CoreDesc,
    drum_desc: DrumDesc,
    material_choice: MaterialChoice,
    assembly_section: AssemblySectionDesc,
):

    drums = make_drums(
        drum_desc,
        core.core_diameter,
        calculate_assembly_thickness(assembly_section),
    )

    assemblies_boundary = get_assemblies_boundaries(
        assembly_section, drums, core.core_diameter
    )

    reflector_cylinder = create_cylinder(
        core.core_diameter / 2 + core.reflector_thickness, core.core_height
    )

    reflector_shape = ~assemblies_boundary & reflector_cylinder

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

    neutron_shield_shape = ~reflector_cylinder & outer_boundary_shape

    assembly_cells = make_assemblies_cells(
        assembly_section,
        core,
        material_choice,
        drums,
    )

    reflector = openmc.Cell(name="reflector")
    reflector.fill = materials_dict[material_choice.reflector]
    reflector.region = reflector_shape

    neutron_shield = openmc.Cell(name="neutron_shield")
    neutron_shield.fill = materials_dict[material_choice.neutron_shield]
    neutron_shield.region = neutron_shield_shape

    universe = openmc.Universe(
        cells=[
            *assembly_cells,
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe)
