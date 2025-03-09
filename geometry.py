import openmc
from drums import CoreDesc, make_drums, DrumDesc
from assemblies import (
    get_assemblies_boundaries,
    calculate_assembly_thickness,
    make_assemblies_cells,
    make_reflector_assembly_zone_shape,
    make_neutron_shield_assembly_zone_shape,
)
import numpy as np
from typing import Dict
from geometry_utils import create_cylinder, AssemblySections
from pydantic import BaseModel
from materials import MaterialChoice


class GeometrySettings(BaseModel):
    core_desc: CoreDesc
    drum_desc: DrumDesc
    material_choice: MaterialChoice
    assembly_section_inner: AssemblySections
    assembly_section_reflector: AssemblySections
    assembly_section_absorber: AssemblySections
    assembly_section_last: AssemblySections
    half_drum: bool = False


def define_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    last_assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_last
    )
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_inner
    )
    assembly_thickness_reflector = calculate_assembly_thickness(
        geometry_settings.assembly_section_reflector
    )
    assembly_thickness_absorber = calculate_assembly_thickness(
        geometry_settings.assembly_section_absorber
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
        geometry_settings.drum_desc,
        geometry_settings.core_desc.core_radius,
        assembly_thickness,
        geometry_settings.half_drum,
    )
    mirrored_drum_desc = None
    if geometry_settings.half_drum:
        mirrored_drum_desc = DrumDesc(
            drum_core_distance=-geometry_settings.drum_desc.drum_core_distance,
            drum_core_margin_outer=geometry_settings.drum_desc.drum_core_margin_outer,
            drum_core_margin_inner=geometry_settings.drum_desc.drum_core_margin_inner,
        )

    assemblies_boundary = get_assemblies_boundaries(
        assembly_thickness,
        last_assembly_thickness,
        drums,
        geometry_settings.core_desc,
        geometry_settings.drum_desc,
        geometry_settings.core_desc.outer_core_radius,
    )
    assemblies_boundary_other_side = None
    if geometry_settings.half_drum:
        assemblies_boundary_other_side = get_assemblies_boundaries(
            assembly_thickness,
            last_assembly_thickness,
            drums,
            geometry_settings.core_desc,
            mirrored_drum_desc,
            geometry_settings.core_desc.outer_core_radius,
        )

    reflector_cylinder = create_cylinder(
        geometry_settings.core_desc.reflector_radius,
        geometry_settings.core_desc.reflector_height,
    )

    reflector_shape = ~assemblies_boundary & reflector_cylinder
    if geometry_settings.half_drum:
        reflector_shape = (
            ~assemblies_boundary & ~assemblies_boundary_other_side & reflector_cylinder
        )

    neutron_shield_cylinder = (
        -openmc.ZCylinder(
            r=geometry_settings.core_desc.outer_core_radius,
            boundary_type="vacuum",
        )
        & -openmc.ZPlane(
            z0=geometry_settings.core_desc.outer_core_height / 2,
            boundary_type="vacuum",
        )
        & +openmc.ZPlane(
            z0=-geometry_settings.core_desc.outer_core_height / 2,
            boundary_type="vacuum",
        )
    )

    neutron_shield_shape = (
        ~reflector_cylinder & neutron_shield_cylinder & ~assemblies_boundary
    )
    if geometry_settings.half_drum:
        neutron_shield_shape = (
            ~reflector_cylinder
            & neutron_shield_cylinder
            & ~assemblies_boundary
            & ~assemblies_boundary_other_side
        )
    ### Making Cells
    core_shape = -openmc.ZCylinder(r=geometry_settings.core_desc.core_radius)
    assembly_cells = make_assemblies_cells(
        geometry_settings.assembly_section_inner,
        geometry_settings.assembly_section_last,
        geometry_settings.core_desc,
        drums,
        geometry_settings.drum_desc,
        core_shape,
        materials_dict,
    )
    assembly_cells_other_side = None
    if geometry_settings.half_drum:
        assembly_cells_other_side = make_assemblies_cells(
            geometry_settings.assembly_section_inner,
            geometry_settings.assembly_section_last,
            geometry_settings.core_desc,
            drums,
            mirrored_drum_desc,
            core_shape,
            materials_dict,
        )

    reflector_assembly_shape = make_reflector_assembly_zone_shape(
        geometry_settings.core_desc
    )

    assembly_reflector_cells = make_assemblies_cells(
        geometry_settings.assembly_section_reflector,
        geometry_settings.assembly_section_last,
        geometry_settings.core_desc,
        drums,
        geometry_settings.drum_desc,
        reflector_assembly_shape,
        materials_dict,
    )
    assembly_reflector_cells_other_side = None
    if geometry_settings.half_drum:
        assembly_reflector_cells_other_side = make_assemblies_cells(
            geometry_settings.assembly_section_reflector,
            geometry_settings.assembly_section_last,
            geometry_settings.core_desc,
            drums,
            mirrored_drum_desc,
            reflector_assembly_shape,
            materials_dict,
        )

    neutron_shield_assembly_shape = make_neutron_shield_assembly_zone_shape(
        geometry_settings.core_desc
    )
    assembly_absorber_cells = make_assemblies_cells(
        geometry_settings.assembly_section_absorber,
        geometry_settings.assembly_section_last,
        geometry_settings.core_desc,
        drums,
        geometry_settings.drum_desc,
        neutron_shield_assembly_shape,
        materials_dict,
    )
    assembly_absorber_cells_other_side = None
    if geometry_settings.half_drum:
        assembly_absorber_cells_other_side = make_assemblies_cells(
            geometry_settings.assembly_section_absorber,
            geometry_settings.assembly_section_last,
            geometry_settings.core_desc,
            drums,
            mirrored_drum_desc,
            neutron_shield_assembly_shape,
            materials_dict,
        )

    reflector = openmc.Cell(name="reflector")
    reflector.fill = materials_dict[geometry_settings.material_choice.reflector]
    reflector.region = reflector_shape

    neutron_shield = openmc.Cell(name="neutron_shield")
    neutron_shield.fill = materials_dict[
        geometry_settings.material_choice.neutron_shield
    ]
    neutron_shield.region = neutron_shield_shape

    universe = openmc.Universe(
        cells=[
            *assembly_cells,
            *(assembly_cells_other_side if geometry_settings.half_drum else []),
            *assembly_reflector_cells,
            *(
                assembly_reflector_cells_other_side
                if geometry_settings.half_drum
                else []
            ),
            *assembly_absorber_cells,
            *(
                assembly_absorber_cells_other_side
                if geometry_settings.half_drum
                else []
            ),
            reflector,
            neutron_shield,
        ]
    )

    return (openmc.Geometry(universe), universe, drums)
