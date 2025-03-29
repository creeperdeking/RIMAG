from typing import Dict

import openmc

from common_lib.assemblies import make_emitter_only_assembly
from common_lib.geometry import GeometrySettings, define_geometry, get_base_geometry
from drum_design.drum_assemblies import (
    define_drum_emitter_boundary,
    make_drum_cells,
    get_drum_assemblies_boundaries,
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
    assemblies_boundary = get_drum_assemblies_boundaries(
        geometry_settings,
        drums[0].radius,
        drums[-1].radius - assembly_thickness,
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

    geometry, universe, cells = define_geometry(
        geometry_settings,
        materials_dict,
        photovoltaic_assembly_cells,
        core_assembly_cells,
        emitter_assembly_cells,
        emitter_boundary,
        assemblies_boundary,
        core_boundary,
        photovoltaic_boundary,
    )

    return (
        geometry,
        universe,
        cells,
        drums,
    )
