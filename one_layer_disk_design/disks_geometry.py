from typing import Dict

import openmc

from common_lib.assemblies import make_emitter_only_assembly
from common_lib.geometry import GeometrySettings, define_geometry, get_base_geometry
from one_layer_disk_design.disks_assemblies import (
    define_discs_emitter_boundary,
    make_disks_cells,
    get_disks_boundaries,
)
from one_layer_disk_design.disks import make_disks


def define_disks_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    assembly_thickness, core_boundary, photovoltaic_boundary = get_base_geometry(
        geometry_settings,
    )

    disks = make_disks(
        geometry_settings,
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
        disks[0].radius,
        geometry_settings.rotary_assembly_desc.assembly_core_distance
        - geometry_settings.core_desc.core_radius,
        assembly_thickness,
        disks,
    )

    ### Making Cells

    core_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.assembly_section_core,
        core_desc=geometry_settings.core_desc,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=core_boundary,
    )

    photovoltaic_assembly_cells = make_disks_cells(
        assembly_section=geometry_settings.photovoltaic_assembly,
        core_desc=geometry_settings.core_desc,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=photovoltaic_boundary,
    )

    emitter_assembly_cells = make_disks_cells(
        assembly_section=make_emitter_only_assembly(
            assembly_section=geometry_settings.assembly_section_core,
            emitter_assembly=geometry_settings.emitter_assembly,
        ),
        core_desc=geometry_settings.core_desc,
        disks=disks,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=assemblies_boundary,
    )

    geometry, universe, tracked_cells = define_geometry(
        geometry_settings,
        materials_dict,
        photovoltaic_assembly_cells,
        core_assembly_cells,
        emitter_assembly_cells,
        emitter_boundary,
        assemblies_boundary,
        core_boundary=core_boundary,
        photovoltaic_boundary=photovoltaic_boundary,
    )

    return (
        geometry,
        universe,
        tracked_cells,
        disks,
    )
