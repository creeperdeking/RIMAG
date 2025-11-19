from typing import Dict, Literal

import openmc
from pydantic import BaseModel

from common_lib.assemblies import (
    calculate_assembly_thickness,
    make_emitter_only_assembly,
)
from common_lib.geometry import GeometrySettings, define_geometry, get_base_geometry
from common_lib.geometry_utils import (
    make_boundary_planes,
    offset_core_boundary_planes_points,
)
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
    neutron_shield_moderator_cladding_thickness: float
    fuel_thickness: float
    fuel_cladding_thickness: float
    moderator_thickness: float
    fuel_emitter_gap: float
    emitter_thickness: float
    thickness_photovoltaic: float
    rotary_axle_thickness: float

    # Additional spacing between modules to increase the size of the cold side shield moderator
    # To prevent also increasing the reactor moderator thickness, a layer of graphite is added
    # between the modules on the reactor side
    additional_module_spacing: float 

    reflector_thickness: float
    neutron_shield_moderator_thickness: float
    neutron_shield_absorber_thickness: float
    gamma_shield_thickness: float

    frustum_pitch: float  # degrees
    number_of_reactor_columns: Literal[1, 2, 3]


def make_disk_geometry_params(disk_geometry_params: DiskGeometryParams):
    # sanity_check_triso_fuel_volume(
    #     disk_geometry_params.fuel_thickness,
    #     disk_geometry_params.fuel_cladding_thickness * 2,
    # )
    if disk_geometry_params.number_of_reactor_columns != 1 and disk_geometry_params.number_of_reactor_columns != 3:
        raise ValueError(f"{disk_geometry_params.number_of_reactor_columns} reactor columns are not supported")
    return disk_geometry_params


def define_disks_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    bg = get_base_geometry(
        geometry_settings,
    )

    disks = make_disks(
        bg.assembly_thickness,
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
        bg.assembly_thickness,
        disks,
    )

    ### Making Cells

    core_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.assembly_section_core,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=bg.core_boundary & bg.disk_boundary,
    )

    photovoltaic_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.photovoltaic_assembly,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=bg.photovoltaic_boundary & bg.disk_boundary,
    )

    between_disks_shielding_cells = []
    previous_radius = geometry_settings.core_desc.core_radius
    current_boundary_planes_points = bg.core_boundary_planes_points
    for outer_core_layer in geometry_settings.outer_core_layers_between_disks:
        offset_boundary_planes_points = offset_core_boundary_planes_points(
            current_boundary_planes_points,
            geometry_settings,
            outer_core_layer.layer_thickness,
        )
        inner_boundary_planes = make_boundary_planes(
            current_boundary_planes_points,
        )
        inner_boundary = +openmc.ZCylinder(r=previous_radius, x0=0, y0=0) & (
            +inner_boundary_planes.positive_y_plane
            | -inner_boundary_planes.negative_y_plane
            | +inner_boundary_planes.upper_boundary_plane
        )
        outer_boundary_planes = make_boundary_planes(
            offset_boundary_planes_points,
        )
        outer_boundary = -openmc.ZCylinder(
            r=previous_radius + outer_core_layer.layer_thickness, x0=0, y0=0
        ) | (
            -outer_boundary_planes.positive_y_plane
            & +outer_boundary_planes.negative_y_plane
            & -outer_boundary_planes.upper_boundary_plane
        )

        layer_boundary = inner_boundary & outer_boundary

        between_disks_shielding_cells.append(
            make_disks_cells(
                assembly_section=outer_core_layer,
                disks=disks,
                rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
                materials_dict=materials_dict,
                boundary_shape=layer_boundary & bg.disk_boundary & ~bg.shaft_boundary,
            )
        )

        previous_radius += outer_core_layer.layer_thickness
        current_boundary_planes_points = offset_boundary_planes_points

    emitter_assembly_cells = make_disks_cells(
        assembly_section=make_emitter_only_assembly(
            assembly_section=geometry_settings.assembly_section_core,
            emitter_assembly=geometry_settings.emitter_assembly,
        ),
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=assemblies_boundary & bg.disk_boundary,
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
        core_boundary=bg.core_boundary,
        photovoltaic_boundary=bg.photovoltaic_boundary,
    )

    return (
        geometry,
        universe,
        tracked_cells,
        disks,
    )
