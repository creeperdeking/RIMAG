from typing import Dict

import openmc

from assemblies import (
    make_emitter_only_assembly,
)
from drum_assemblies import (
    define_drum_emitter_boundary,
    make_drum_cells,
)
from common_lib.geometry import (
    define_geometry,
    get_base_geometry,
    GeometrySettings,
)
from common_lib.geometry_utils import (
    calculate_assembly_thickness,
)
from drum_design.drums import make_drums


def define_drum_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
):
    assembly_thickness, core_boundary, photovoltaic_boundary = get_base_geometry(
        geometry_settings,
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
            core_boundary=core_boundary,
            photovoltaic_boundary=photovoltaic_boundary,
        ),
        drums,
    )
