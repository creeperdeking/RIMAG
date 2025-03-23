from typing import Dict

import openmc

from assemblies import (
    define_drum_emitter_boundary,
    define_photovoltaic_boundary,
    make_drum_cells,
    make_emitter_only_assembly,
)
from common_lib.geometry import (
    define_geometry,
    GeometrySettings,
)
from common_lib.geometry_utils import (
    calculate_assembly_thickness,
    create_cylinder,
)
from drum_design.drums import make_drums


def define_drum_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )

    drums = make_drums(
        geometry_settings,
        assembly_thickness,
    )

    emitter_boundary = define_drum_emitter_boundary(
        geometry_settings.assembly_section_core,
        drums,
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
    )

    core_boundary = create_cylinder(
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )
    photovoltaic_boundary = define_photovoltaic_boundary(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc.assembly_core_distance,
        geometry_settings.double_assembly,
    )

    ### Making Cells

    core_assembly_cells = make_drum_cells(
        assembly_section=geometry_settings.assembly_section_core,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=core_boundary,
    )

    photovoltaic_assembly_cells = make_drum_cells(
        assembly_section=geometry_settings.photovoltaic_assembly,
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
        boundary_shape=photovoltaic_boundary,
    )

    emitter_assembly_cells = make_drum_cells(
        assembly_section=make_emitter_only_assembly(
            assembly_section=geometry_settings.assembly_section_core,
            emitter_assembly=geometry_settings.emitter_assembly,
        ),
        core_desc=geometry_settings.core_desc,
        drums=drums,
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        materials_dict=materials_dict,
    )

    return (
        *define_geometry(
            geometry_settings,
            materials_dict,
            photovoltaic_assembly_cells,
            core_assembly_cells,
            emitter_assembly_cells,
            emitter_boundary,
            outer_assembly_radius=drums[0].radius,
            inner_assembly_radius=drums[-1].radius - assembly_thickness,
        ),
        drums,
    )
