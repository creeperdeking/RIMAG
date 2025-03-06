import openmc
from materials import materials_dict
from drums import CoreDesc, make_drums, DrumDesc
from assemblies import (
    get_assemblies_boundaries,
    calculate_assembly_thickness,
    make_assemblies_cells,
)
import numpy as np
from geometry_utils import create_cylinder, MaterialChoice, AssemblySections


def define_geometry(
    core_desc: CoreDesc,
    drum_desc: DrumDesc,
    material_choice: MaterialChoice,
    assembly_section_inner: AssemblySections,
    assembly_section_reflector: AssemblySections,
    assembly_section_absorber: AssemblySections,
    assembly_section_last: AssemblySections,
    half_drum: bool = False,
):
    last_assembly_thickness = calculate_assembly_thickness(assembly_section_last)
    assembly_thickness = calculate_assembly_thickness(assembly_section_inner)
    assembly_thickness_reflector = calculate_assembly_thickness(
        assembly_section_reflector
    )
    assembly_thickness_absorber = calculate_assembly_thickness(
        assembly_section_absorber
    )

    if not np.isclose(assembly_thickness, assembly_thickness_reflector):
        raise ValueError(
            "Inner assembly and reflector sections must have the same thickness"
        )
    if not np.isclose(assembly_thickness, assembly_thickness_absorber):
        raise ValueError(
            "Inner assembly and absorber sections must have the same thickness"
        )

    drums = make_drums(
        drum_desc,
        core_desc.core_radius,
        assembly_thickness,
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
        assembly_thickness,
        last_assembly_thickness,
        drums,
        core_desc,
        drum_desc,
        core_desc.outer_core_radius,
    )
    assemblies_boundary_other_side = None
    if half_drum:
        assemblies_boundary_other_side = get_assemblies_boundaries(
            assembly_thickness,
            last_assembly_thickness,
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

    neutron_shield_cylinder = (
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
        & neutron_shield_cylinder
        & ~assemblies_boundary
        & ~assemblies_boundary_other_side
    )

    ### Making Cells
    core_shape = -openmc.ZCylinder(r=core_desc.core_radius)
    assembly_cells = make_assemblies_cells(
        assembly_section_inner,
        assembly_section_last,
        core_desc,
        drums,
        drum_desc,
        core_shape,
    )
    assembly_cells_other_side = None
    if half_drum:
        assembly_cells_other_side = make_assemblies_cells(
            assembly_section_inner,
            assembly_section_last,
            core_desc,
            drums,
            mirrored_drum_desc,
            core_shape,
        )

    assembly_reflector_cells = make_assemblies_cells(
        assembly_section_reflector,
        assembly_section_last,
        core_desc,
        drums,
        drum_desc,
        reflector_cylinder,
    )
    assembly_reflector_cells_other_side = None
    if half_drum:
        assembly_reflector_cells_other_side = make_assemblies_cells(
            assembly_section_reflector,
            assembly_section_last,
            core_desc,
            drums,
            mirrored_drum_desc,
            reflector_cylinder,
        )

    assembly_absorber_cells = make_assemblies_cells(
        assembly_section_absorber,
        assembly_section_last,
        core_desc,
        drums,
        drum_desc,
        neutron_shield_cylinder,
    )
    assembly_absorber_cells_other_side = None
    if half_drum:
        assembly_absorber_cells_other_side = make_assemblies_cells(
            assembly_section_absorber,
            assembly_section_last,
            core_desc,
            drums,
            mirrored_drum_desc,
            neutron_shield_cylinder,
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
            *assembly_reflector_cells,
            *(assembly_reflector_cells_other_side if half_drum else []),
            *assembly_absorber_cells,
            *(assembly_absorber_cells_other_side if half_drum else []),
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe)
