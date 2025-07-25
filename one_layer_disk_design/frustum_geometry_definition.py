from typing import Dict, List, Tuple

from pydantic import BaseModel
from common_lib.assemblies import (
    calculate_assembly_thickness,
    compute_core_desc,
)
import openmc
from common_lib.assemblies_types import (
    Assembly,
    AssemblySections,
    EmitterPlaceholder,
)
from common_lib.geometry import check_assembly_thickness_equal
from common_lib.geometry_types import GeometrySettings
from common_lib.materials import Material, MaterialChoice
from common_lib.rotary_assembly import RotaryAssemblyDesc

from one_layer_disk_design.disks import DiskAssemblyLayer, get_disks_radius
from one_layer_disk_design.disks_geometry import (
    DiskGeometryParams,
    define_disks_geometry,
)


class MakeSimulationGeometryResult(BaseModel, arbitrary_types_allowed=True):
    geometry: openmc.Geometry
    universe: openmc.Universe
    tracked_cells: Dict[str, openmc.Cell]
    drums: List[DiskAssemblyLayer]
    materials_def: Dict[str, Material]
    geometry_settings: GeometrySettings


def make_simulation_geometry(
    material_choice: MaterialChoice,
    disk_geometry_params: DiskGeometryParams,
    materials_dict: Dict[str, openmc.Material],
    materials_def: Dict[str, Material],
) -> MakeSimulationGeometryResult:
    outer_core_layers_inside_shaft = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.neutron_reflector,
                thickness=disk_geometry_params.reflector_thickness,
            ),
            Assembly(
                material=material_choice.neutron_shield_moderator,
                thickness=disk_geometry_params.neutron_shield_moderator_thickness,
            ),
            Assembly(
                material=material_choice.neutron_absorber,
                thickness=disk_geometry_params.neutron_shield_absorber_thickness,
            ),
            Assembly(
                material=material_choice.gamma_shield,
                thickness=disk_geometry_params.gamma_shield_thickness,
            ),
        ],
    )

    outer_core_layers_between_disks = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.neutron_reflector,
                thickness=disk_geometry_params.reflector_thickness,
            ),
            Assembly(
                material=material_choice.neutron_shield_moderator,
                thickness=disk_geometry_params.neutron_shield_moderator_thickness,
            ),
            Assembly(
                material=material_choice.neutron_absorber,
                thickness=disk_geometry_params.neutron_shield_absorber_thickness,
            ),
            Assembly(
                material=material_choice.gamma_shield,
                thickness=disk_geometry_params.gamma_shield_thickness,
            ),
        ],
    )

    check_assembly_thickness_equal(
        outer_core_layers_inside_shaft,
        outer_core_layers_between_disks,
    )

    emitter_assembly = AssemblySections(
        parts=[
            ### Void
            Assembly(
                material="Void",
                thickness=disk_geometry_params.fuel_emitter_gap,
                is_emitter_gap=True,
            ),
            ### Emitter
            Assembly(
                material=material_choice.emitter,
                thickness=disk_geometry_params.emitter_thickness,
                is_emitter=True,
            ),
            ### Void
            Assembly(
                material="Void",
                thickness=disk_geometry_params.fuel_emitter_gap,
                is_emitter_gap=True,
            ),
        ],
    )

    emitter_assembly_placeholder = EmitterPlaceholder(
        thickness=calculate_assembly_thickness(emitter_assembly),
    )

    assembly_section_core = AssemblySections(
        parts=[
            ### Moderator
            Assembly(
                material=material_choice.moderator,
                thickness=disk_geometry_params.moderator_thickness / 2,
            ),
            ### Cladding
            Assembly(
                material=material_choice.moderator_cladding,
                thickness=disk_geometry_params.moderator_cladding_thickness,
            ),
            ### Emitter Assembly
            emitter_assembly_placeholder,
            ### Fuel Cladding
            Assembly(
                material=material_choice.fuel_cladding,
                thickness=disk_geometry_params.fuel_cladding_thickness,
            ),
            ### Fuel
            Assembly(
                material=material_choice.fuel,
                thickness=disk_geometry_params.fuel_thickness,
                is_fuel=True,
            ),
            ### Fuel Cladding
            Assembly(
                material=material_choice.fuel_cladding,
                thickness=disk_geometry_params.fuel_cladding_thickness,
            ),
            ### Emitter Assembly
            emitter_assembly_placeholder,
            ### Cladding
            Assembly(
                material=material_choice.moderator_cladding,
                thickness=disk_geometry_params.moderator_cladding_thickness,
            ),
            ### Moderator
            Assembly(
                material=material_choice.moderator,
                thickness=disk_geometry_params.moderator_thickness / 2,
            ),
        ],
    )

    assembly_thickness = calculate_assembly_thickness(assembly_section_core)

    core_desc = compute_core_desc(
        core_radius=disk_geometry_params.core_diameter / 2,
        core_height=assembly_thickness,
        outer_core_assembly=outer_core_layers_inside_shaft,
    )
    assembly_core_distance = (
        core_desc.core_radius
        + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    )
    rotary_assembly_desc = RotaryAssemblyDesc(
        assembly_core_distance=assembly_core_distance,
        assembly_core_margin=1,
        rotary_assembly_radius=get_disks_radius(
            assembly_core_distance, core_desc.core_radius
        ),
        frustum_pitch=disk_geometry_params.frustum_pitch,
    )

    assembly_section_photovoltaic = AssemblySections(
        parts=[
            ### Water
            Assembly(
                material=material_choice.coolant,
                thickness=(
                    disk_geometry_params.moderator_thickness
                    - disk_geometry_params.thickness_photovoltaic * 2
                    + disk_geometry_params.moderator_cladding_thickness * 2
                )
                / 2,
            ),
            ### Photovoltaic
            Assembly(
                material=material_choice.photovoltaic,
                thickness=disk_geometry_params.thickness_photovoltaic,
                is_photovoltaic=True,
            ),
            ### Emitter Assembly
            emitter_assembly_placeholder,
            ### Photovoltaic
            Assembly(
                material=material_choice.photovoltaic,
                thickness=disk_geometry_params.thickness_photovoltaic,
                is_photovoltaic=True,
            ),
            ### Water
            Assembly(
                material=material_choice.coolant,
                thickness=disk_geometry_params.fuel_thickness
                - disk_geometry_params.thickness_photovoltaic * 2
                + disk_geometry_params.fuel_cladding_thickness * 2,
            ),
            ### Photovoltaic
            Assembly(
                material=material_choice.photovoltaic,
                thickness=disk_geometry_params.thickness_photovoltaic,
                is_photovoltaic=True,
            ),  # is_fuel is set to True to make the volume calculation work
            ### Emitter Assembly
            emitter_assembly_placeholder,
            ### Photovoltaic
            Assembly(
                material=material_choice.photovoltaic,
                thickness=disk_geometry_params.thickness_photovoltaic,
                is_photovoltaic=True,
            ),  # is_fuel is set to True to make the volume calculation work
            ### Water
            Assembly(
                material=material_choice.coolant,
                thickness=(
                    disk_geometry_params.moderator_thickness
                    - disk_geometry_params.thickness_photovoltaic * 2
                    + disk_geometry_params.moderator_cladding_thickness * 2
                )
                / 2,
            ),
        ]
    )

    geometry_settings = GeometrySettings(
        assembly_section_core=assembly_section_core,
        photovoltaic_assembly=assembly_section_photovoltaic,
        emitter_assembly=emitter_assembly,
        core_desc=core_desc,
        rotary_assembly_desc=rotary_assembly_desc,
        material_choice=material_choice,
        outer_core_layers_inside_shaft=outer_core_layers_inside_shaft,
        outer_core_layers_between_disks=outer_core_layers_between_disks,
    )

    geometry, universe, tracked_cells, drums = define_disks_geometry(
        geometry_settings, materials_dict
    )
    geometry_settings = GeometrySettings(
        assembly_section_core=assembly_section_core,
        photovoltaic_assembly=assembly_section_photovoltaic,
        emitter_assembly=emitter_assembly,
        core_desc=core_desc,
        rotary_assembly_desc=rotary_assembly_desc,
        material_choice=material_choice,
        outer_core_layers_inside_shaft=outer_core_layers_inside_shaft,
        outer_core_layers_between_disks=outer_core_layers_between_disks,
    )
    return MakeSimulationGeometryResult(
        geometry=geometry,
        universe=universe,
        tracked_cells=tracked_cells,
        drums=drums,
        materials_def=materials_def,
        geometry_settings=geometry_settings,
    )
