from typing import Dict

import openmc
from pydantic import BaseModel

from common_lib.assemblies import (
    calculate_assembly_thickness,
    make_emitter_only_assembly,
)
from common_lib.geometry import GeometrySettings, define_geometry, get_base_geometry
from one_layer_disk_design.disks_assemblies import (
    define_discs_emitter_boundary,
    make_disks_cells,
    get_disks_boundaries,
)
from one_layer_disk_design.disks import make_disks
from one_layer_disk_design.disks_core_characteristics import (
    sanity_check_triso_fuel_volume,
)


class DiskGeometryParams(BaseModel):
    core_diameter: float
    moderator_cladding_thickness: float
    fuel_thickness: float
    fuel_cladding_thickness: float
    moderator_thickness: float
    fuel_emitter_gap: float
    emitter_thickness: float
    thickness_photovoltaic: float
    rotary_axle_thickness: float

    reflector_thickness: float
    neutron_shield_moderator_thickness: float
    neutron_shield_absorber_thickness: float
    gamma_shield_thickness: float

    frustum_pitch: float  # degrees


def make_disk_geometry_params(disk_geometry_params: DiskGeometryParams):
    sanity_check_triso_fuel_volume(
        disk_geometry_params.fuel_thickness,
        disk_geometry_params.fuel_cladding_thickness * 2,
    )
    return disk_geometry_params


def define_disks_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    (
        assembly_thickness,
        core_boundary,
        photovoltaic_boundary,
        shaft_boundary,
        _,
        disk_boundary,
        _,
    ) = get_base_geometry(
        geometry_settings,
    )

    disks = make_disks(
        assembly_thickness,
    )

    emitter_boundary = define_discs_emitter_boundary(
        geometry_settings.assembly_section_core,
        disks,
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
        0.0,
    )

    assemblies_boundary = get_disks_boundaries(
        geometry_settings,
        geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
        calculate_assembly_thickness(geometry_settings.outer_core_layers_inside_shaft)
        / 2,
        assembly_thickness,
        disks,
    )

    ### Making Cells

    core_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.assembly_section_core,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=core_boundary & disk_boundary,
    )

    photovoltaic_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.photovoltaic_assembly,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=photovoltaic_boundary & disk_boundary,
    )

    between_disks_shielding_cells = []
    previous_radius = geometry_settings.core_desc.core_radius
    for outer_core_layer in geometry_settings.outer_core_layers_between_disks:
        inner_boundary = openmc.ZCylinder(r=previous_radius, x0=0, y0=0)
        outer_boundary = openmc.ZCylinder(
            r=previous_radius + outer_core_layer.layer_thickness, x0=0, y0=0
        )

        layer_boundary = +inner_boundary & -outer_boundary

        between_disks_shielding_cells.append(
            make_disks_cells(
                assembly_section=outer_core_layer,
                disks=disks,
                rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
                materials_dict=materials_dict,
                boundary_shape=layer_boundary & disk_boundary & ~shaft_boundary,
            )
        )

        previous_radius += outer_core_layer.layer_thickness

    emitter_assembly_cells = make_disks_cells(
        assembly_section=make_emitter_only_assembly(
            assembly_section=geometry_settings.assembly_section_core,
            emitter_assembly=geometry_settings.emitter_assembly,
        ),
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=assemblies_boundary & disk_boundary,
    )

    geometry, universe, tracked_cells = define_geometry(
        geometry_settings=geometry_settings,
        materials_dict=materials_dict,
        photovoltaic_assembly_cells=photovoltaic_assembly_cells,
        core_assembly_cells=core_assembly_cells,
        outer_core_layers_between_disks_scells=between_disks_shielding_cells,
        emitter_assembly_cells=emitter_assembly_cells,
        emitter_boundary=emitter_boundary,
        assemblies_boundary=assemblies_boundary,
        core_boundary=core_boundary,
        photovoltaic_boundary=photovoltaic_boundary,
    )

    return (
        geometry,
        universe,
        tracked_cells,
        disks,
    )
