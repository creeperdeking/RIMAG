import math
from typing import Dict

import numpy as np
import openmc
from drum_design.drums import make_drums

from assemblies import (
    calculate_assembly_thickness,
    get_assemblies_boundaries,
    make_assemblies_cells,
    make_neutron_shield_assembly_zone_shape,
    make_reflector_assembly_zone_shape,
)
from common_lib.geometry import GeometrySettings
from common_lib.geometry_utils import create_cylinder
from common_lib.rotary_assembly import RotaryAssemblyDesc


def define_drum_geometry(
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
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.core_radius,
        assembly_thickness,
        geometry_settings.half_assembly,
    )
    mirrored_drum_desc = None
    if geometry_settings.half_assembly:
        mirrored_drum_desc = RotaryAssemblyDesc(
            assembly_core_distance=-geometry_settings.rotary_assembly_desc.assembly_core_distance,
            assembly_core_margin=geometry_settings.rotary_assembly_desc.assembly_core_margin,
        )

    assemblies_boundary = get_assemblies_boundaries(
        last_assembly_thickness,
        drums,
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.outer_core_radius,
    )
    assemblies_boundary_other_side = None
    if geometry_settings.half_assembly:
        assemblies_boundary_other_side = get_assemblies_boundaries(
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
    if geometry_settings.half_assembly:
        reflector_shape = (
            ~assemblies_boundary & ~assemblies_boundary_other_side & reflector_cylinder
        )

    neutron_shield_cylinder = (
        -openmc.ZCylinder(
            r=geometry_settings.core_desc.outer_core_radius,
        )
        & -openmc.ZPlane(
            z0=geometry_settings.core_desc.outer_core_height / 2,
        )
        & +openmc.ZPlane(
            z0=-geometry_settings.core_desc.outer_core_height / 2,
        )
    )

    neutron_shield_shape = (
        ~reflector_cylinder & neutron_shield_cylinder & ~assemblies_boundary
    )
    if geometry_settings.half_assembly:
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
        geometry_settings.rotary_assembly_desc,
        core_shape,
        materials_dict,
    )
    assembly_cells_other_side = None
    if geometry_settings.half_assembly:
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
        geometry_settings.rotary_assembly_desc,
        reflector_assembly_shape,
        materials_dict,
    )
    assembly_reflector_cells_other_side = None
    if geometry_settings.half_assembly:
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
        geometry_settings.rotary_assembly_desc,
        neutron_shield_assembly_shape,
        materials_dict,
    )
    assembly_absorber_cells_other_side = None
    if geometry_settings.half_assembly:
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

    ### Define outer drum zone for solar cells tallies
    photovoltaic_slice = (
        -openmc.ZCylinder(
            r=geometry_settings.core_desc.core_radius,
            x0=geometry_settings.rotary_assembly_desc.assembly_core_distance * 2,
        )
        & -openmc.ZPlane(
            z0=geometry_settings.core_desc.core_height / 2,
        )
        & +openmc.ZPlane(
            z0=-geometry_settings.core_desc.core_height / 2,
        )
    )

    photovoltaic_slice_volume = (
        math.pi
        * (geometry_settings.core_desc.core_radius**2)
        * geometry_settings.core_desc.core_height
    )

    photovoltaic_cell = openmc.Cell(name="photovoltaic")
    photovoltaic_cell.region = photovoltaic_slice
    photovoltaic_cell.fill = materials_dict[
        geometry_settings.material_choice.photovoltaic
    ]

    outer_drum_zone = (
        (
            -openmc.ZCylinder(
                r=drums[0].radius
                + geometry_settings.rotary_assembly_desc.assembly_core_distance,
                # x0=geometry_settings.drum_desc.drum_core_distance,
                boundary_type="vacuum",
            )
            & -openmc.ZPlane(
                z0=geometry_settings.core_desc.outer_core_height / 2 + 1,
                boundary_type="vacuum",
            )
            & +openmc.ZPlane(
                z0=-geometry_settings.core_desc.outer_core_height / 2 - 1,
                boundary_type="vacuum",
            )
        )
        & ~neutron_shield_cylinder
        & ~photovoltaic_slice
    )

    outer_drum_zone_cell = openmc.Cell(name="outer_drum_zone")
    outer_drum_zone_cell.region = outer_drum_zone
    outer_drum_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    universe = openmc.Universe(
        cells=[
            *assembly_cells,
            *(assembly_cells_other_side if geometry_settings.half_assembly else []),
            *assembly_reflector_cells,
            *(
                assembly_reflector_cells_other_side
                if geometry_settings.half_assembly
                else []
            ),
            *assembly_absorber_cells,
            *(
                assembly_absorber_cells_other_side
                if geometry_settings.half_assembly
                else []
            ),
            reflector,
            neutron_shield,
            outer_drum_zone_cell,
            photovoltaic_cell,
        ]
    )

    return (
        openmc.Geometry(universe),
        universe,
        drums,
        photovoltaic_cell,
        photovoltaic_slice_volume,
    )
