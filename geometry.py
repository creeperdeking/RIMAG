import openmc
from materials import materials_dict
from drums import CoreDesc, make_drums, DrumDesc
from assemblies import (
    get_assemblies_boundaries,
    calculate_assembly_thickness,
    make_assemblies_cells,
)
from geometry_utils import create_cylinder, MaterialChoice, AssemblySectionDesc


def define_geometry(
    core: CoreDesc,
    drum_desc: DrumDesc,
    material_choice: MaterialChoice,
    assembly_section: AssemblySectionDesc,
    half_drum: bool = False,
):

    drums = make_drums(
        drum_desc,
        core.core_diameter,
        calculate_assembly_thickness(assembly_section),
        half_drum,
    )
    mirrored_drum_desc = None
    if half_drum:
        mirrored_drum_desc = DrumDesc(
            drum_core_distance=-drum_desc.drum_core_distance,
            drum_core_margin_outer=drum_desc.drum_core_margin_outer,
            drum_core_margin_inner=drum_desc.drum_core_margin_inner,
            height=drum_desc.height,
        )

    assemblies_boundary = get_assemblies_boundaries(
        assembly_section, drums, core.core_diameter, drum_desc
    )
    assemblies_boundary_other_side = None
    if half_drum:
        assemblies_boundary_other_side = get_assemblies_boundaries(
            assembly_section, drums, core.core_diameter, mirrored_drum_desc
        )

    reflector_cylinder = create_cylinder(
        core.core_diameter / 2 + core.reflector_thickness, core.core_height
    )

    reflector_shape = ~assemblies_boundary & reflector_cylinder
    if half_drum:
        reflector_shape = (
            ~assemblies_boundary & ~assemblies_boundary_other_side & reflector_cylinder
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

    neutron_shield_shape = ~reflector_cylinder & outer_boundary_shape

    assembly_cells = make_assemblies_cells(
        assembly_section,
        core,
        material_choice,
        drums,
        drum_desc,
    )
    assembly_cells_other_side = None
    if half_drum:
        assembly_cells_other_side = make_assemblies_cells(
            assembly_section,
            core,
            material_choice,
            drums,
            mirrored_drum_desc,
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
            *(assembly_cells_other_side if half_drum else []),
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe)
