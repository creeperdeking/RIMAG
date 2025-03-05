import openmc
from materials import materials_dict
from drums import CoreDesc, make_drums, DrumDesc
from assemblies import (
    get_assemblies_boundaries,
    calculate_assembly_thickness,
    make_assemblies_cells,
    create_outer_core_assembly_cells,
    create_assembly_cells,
    create_last_cell_outer_core,
    create_last_cell_core,
)
from geometry_utils import create_cylinder, MaterialChoice, AssemblySectionDesc


def define_geometry(
    core_desc: CoreDesc,
    drum_desc: DrumDesc,
    material_choice: MaterialChoice,
    assembly_section: AssemblySectionDesc,
    half_drum: bool = False,
):
    drums = make_drums(
        drum_desc,
        core_desc.core_radius,
        calculate_assembly_thickness(assembly_section),
        half_drum,
    )
    mirrored_drum_desc = None
    if half_drum:
        mirrored_drum_desc = DrumDesc(
            drum_core_distance=-drum_desc.drum_core_distance,
            drum_core_margin_outer=drum_desc.drum_core_margin_outer,
            drum_core_margin_inner=drum_desc.drum_core_margin_inner,
        )

    assemblies_boundary = get_assemblies_boundaries(
        assembly_section, drums, core_desc, drum_desc, core_desc.outer_core_radius
    )
    assemblies_boundary_other_side = None
    if half_drum:
        assemblies_boundary_other_side = get_assemblies_boundaries(
            assembly_section,
            drums,
            core_desc,
            mirrored_drum_desc,
            core_desc.outer_core_radius,
        )

    reflector_cylinder = create_cylinder(
        core_desc.reflector_radius,
        core_desc.reflector_height,
    )

    reflector_shape = (
        ~assemblies_boundary & reflector_cylinder & ~assemblies_boundary_other_side
    )
    if half_drum:
        reflector_shape = (
            ~assemblies_boundary & ~assemblies_boundary_other_side & reflector_cylinder
        )

    outer_boundary_shape = (
        -openmc.ZCylinder(
            r=core_desc.outer_core_radius,
            boundary_type="vacuum",
        )
        & -openmc.ZPlane(
            z0=core_desc.outer_core_height / 2,
            boundary_type="vacuum",
        )
        & +openmc.ZPlane(
            z0=-core_desc.outer_core_height / 2,
            boundary_type="vacuum",
        )
    )

    neutron_shield_shape = (
        ~reflector_cylinder
        & outer_boundary_shape
        & ~assemblies_boundary
        & ~assemblies_boundary_other_side
    )

    assembly_cells = make_assemblies_cells(
        create_assembly_cells,
        create_last_cell_core,
        assembly_section,
        core_desc,
        material_choice,
        drums,
        drum_desc,
    )
    assembly_cells_other_side = None
    if half_drum:
        assembly_cells_other_side = make_assemblies_cells(
            create_assembly_cells,
            create_last_cell_core,
            assembly_section,
            core_desc,
            material_choice,
            drums,
            mirrored_drum_desc,
        )
    assembly_outer_core_cells = make_assemblies_cells(
        create_outer_core_assembly_cells,
        create_last_cell_outer_core,
        assembly_section,
        core_desc,
        material_choice,
        drums,
        drum_desc,
    )
    assembly_outer_core_cells_other_side = None
    if half_drum:
        assembly_outer_core_cells_other_side = make_assemblies_cells(
            create_outer_core_assembly_cells,
            create_last_cell_outer_core,
            assembly_section,
            core_desc,
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
            *assembly_outer_core_cells,
            *(assembly_outer_core_cells_other_side if half_drum else []),
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe)
