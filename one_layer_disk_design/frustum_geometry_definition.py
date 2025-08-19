from typing import Dict, List

from pydantic import BaseModel
from common_lib.assemblies import (
    calculate_assembly_thickness,
    compute_core_desc,
    mirror_assembly,
)
import openmc
from common_lib.assemblies_types import (
    Assembly,
    AssemblySections,
    OuterCoreAssemblySections,
    EmitterPlaceholder,
)
from common_lib.geometry import (
    check_assemblies_compatibility,
)
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
    emitter_assembly = AssemblySections(
        parts=[
            ### Void
            Assembly(
                material="Void",
                thickness=disk_geometry_params.fuel_emitter_gap,
                is_emitter_placeholder=True,
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
                is_emitter_placeholder=True,
            ),
        ],
    )

    emitter_assembly_placeholder = EmitterPlaceholder(
        thickness=calculate_assembly_thickness(emitter_assembly),
    )

    assembly_section_core = mirror_assembly(
        AssemblySections(
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
                    thickness=disk_geometry_params.fuel_thickness / 2,
                    is_fuel=True,
                ),
            ],
        )
    )

    assembly_section_photovoltaic = mirror_assembly(
        AssemblySections(
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
                    thickness=(
                        disk_geometry_params.fuel_thickness
                        - disk_geometry_params.thickness_photovoltaic * 2
                        + disk_geometry_params.fuel_cladding_thickness * 2
                    )
                    / 2,
                ),
            ]
        )
    )

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
            # Assembly(
            #     material=material_choice.gamma_shield,
            #     thickness=disk_geometry_params.gamma_shield_thickness,
            # ),
            Assembly(
                material=material_choice.neutron_absorber,
                thickness=disk_geometry_params.neutron_shield_absorber_thickness,
            ),
        ],
    )

    outer_core_layers_between_disks = [
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
                        ### Reflector
                        Assembly(
                            material=material_choice.neutron_reflector,
                            thickness=(
                                disk_geometry_params.moderator_thickness
                                - disk_geometry_params.thickness_photovoltaic * 2
                                + disk_geometry_params.moderator_cladding_thickness * 2
                            )
                            / 2
                            + disk_geometry_params.thickness_photovoltaic,
                        ),
                        ### Emitter Assembly
                        emitter_assembly_placeholder,
                        ### Reflector
                        Assembly(
                            material=material_choice.neutron_reflector,
                            thickness=disk_geometry_params.thickness_photovoltaic
                            + (
                                disk_geometry_params.fuel_thickness
                                - disk_geometry_params.thickness_photovoltaic * 2
                                + disk_geometry_params.fuel_cladding_thickness * 2
                            )
                            / 2,
                        ),
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.reflector_thickness,
        ),
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
                        ### Shield Moderator
                        Assembly(
                            material=material_choice.neutron_shield_moderator,
                            thickness=disk_geometry_params.moderator_thickness / 2
                            + disk_geometry_params.moderator_cladding_thickness,
                        ),
                        ### Emitter Assembly
                        emitter_assembly_placeholder,
                        ### Scattering Material
                        Assembly(
                            material=material_choice.neutron_shield_moderator,
                            thickness=disk_geometry_params.fuel_cladding_thickness
                            + disk_geometry_params.fuel_thickness / 2,
                        ),
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.neutron_shield_moderator_thickness,
        ),
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
                        ### Shield Moderator
                        Assembly(
                            material=material_choice.neutron_absorber,
                            thickness=disk_geometry_params.moderator_thickness / 2
                            + disk_geometry_params.moderator_cladding_thickness,
                        ),
                        ### Emitter Assembly
                        emitter_assembly_placeholder,
                        ### Neutron Absorber
                        Assembly(
                            material=material_choice.neutron_absorber,
                            thickness=disk_geometry_params.fuel_cladding_thickness
                            + disk_geometry_params.fuel_thickness / 2,
                        ),
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.neutron_shield_absorber_thickness,
        ),
    ]

    total_thickness_outer_core_layers_between_disks = 0
    for assembly in outer_core_layers_between_disks:
        total_thickness_outer_core_layers_between_disks += assembly.layer_thickness
    outer_core_layers_inside_shaft_thickness = calculate_assembly_thickness(
        outer_core_layers_inside_shaft
    )

    if (
        outer_core_layers_inside_shaft_thickness
        != total_thickness_outer_core_layers_between_disks
    ):
        raise ValueError(
            f"outer_core_layers_inside_shaft has a thickness of {outer_core_layers_inside_shaft_thickness} which is not the same as total_thickness_outer_core_layers_between_disks which has a thickness of {total_thickness_outer_core_layers_between_disks}"
        )

    check_assemblies_compatibility(
        [
            assembly_section_core,
            assembly_section_photovoltaic,
            *outer_core_layers_between_disks,
        ]
    )

    assembly_thickness = calculate_assembly_thickness(assembly_section_core)

    core_desc = compute_core_desc(
        core_radius=disk_geometry_params.core_diameter / 2,
        core_height=assembly_thickness,
        outer_core_assembly=outer_core_layers_inside_shaft,
        frustum_pitch=disk_geometry_params.frustum_pitch,
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
