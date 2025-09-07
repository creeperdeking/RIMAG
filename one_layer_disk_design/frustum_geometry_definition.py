from typing import Dict, List

from pydantic import BaseModel
from common_lib.assemblies import (
    calculate_assembly_thickness,
    calculate_layers_thickness,
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
    check_assembly_thickness_equal,
)
from common_lib.geometry_types import GeometrySettings
from common_lib.materials import MaterialChoice
from common_lib.rotary_assembly import RotaryAssemblyDesc

from one_layer_disk_design.disks import DiskAssemblyLayer, get_disks_radius
from one_layer_disk_design.disks_geometry import (
    DiskGeometryParams,
    define_disks_geometry,
)


class MakeSimulationGeometryResult(BaseModel, arbitrary_types_allowed=True):
    geometry: openmc.Geometry
    universe: openmc.Universe
    tracked_cells: Dict[str, List[openmc.Cell]]
    drums: List[DiskAssemblyLayer]
    geometry_settings: GeometrySettings


def make_simulation_geometry(
    material_choice: MaterialChoice,
    disk_geometry_params: DiskGeometryParams,
    materials_dict: Dict[str, openmc.Material],
) -> MakeSimulationGeometryResult:
    emitter_assembly = AssemblySections(
        parts=[
            ### Void
            Assembly(
                material=material_choice.void,
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
                material=material_choice.void,
                thickness=disk_geometry_params.fuel_emitter_gap,
                is_emitter_placeholder=True,
            ),
        ],
    )

    emitter_assembly_placeholder = EmitterPlaceholder(
        thickness=calculate_assembly_thickness(emitter_assembly),
    )

    half_fuel_element = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.fuel_cladding,
                thickness=disk_geometry_params.fuel_cladding_thickness,
            ),
            Assembly(
                material=material_choice.fuel,
                thickness=disk_geometry_params.fuel_thickness / 2,
                is_fuel=True,
            ),
        ]
    )
    fuel_element = mirror_assembly(half_fuel_element)

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
                emitter_assembly_placeholder,
                *fuel_element.parts,
                emitter_assembly_placeholder,
                *fuel_element.parts,
                emitter_assembly_placeholder,
                *half_fuel_element.parts,
            ],
        )
    )

    half_photovoltaic_element = AssemblySections(
        parts=[
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
        ],
    )

    photovoltaic_element = mirror_assembly(half_photovoltaic_element)

    assembly_section_photovoltaic = mirror_assembly(
        AssemblySections(
            parts=[
                Assembly(
                    material=material_choice.void,
                    thickness=disk_geometry_params.moderator_thickness / 2
                    + disk_geometry_params.moderator_cladding_thickness,
                ),
                ### Emitter Assembly
                emitter_assembly_placeholder,
                *photovoltaic_element.parts,
                emitter_assembly_placeholder,
                *photovoltaic_element.parts,
                emitter_assembly_placeholder,
                *half_photovoltaic_element.parts,
            ]
        )
    )

    check_assembly_thickness_equal(assembly_section_core, assembly_section_photovoltaic)

    check_assemblies_compatibility(
        [assembly_section_core, assembly_section_photovoltaic],
    )

    assert (
        disk_geometry_params.reflector_thickness
        - disk_geometry_params.neutron_shield_absorber_thickness
        > 0
    )

    outer_core_layers_inside_shaft = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.neutron_reflector,
                thickness=disk_geometry_params.reflector_thickness
                - disk_geometry_params.neutron_shield_absorber_thickness,
            ),
            Assembly(
                material=material_choice.neutron_shield_moderator,
                thickness=disk_geometry_params.neutron_shield_moderator_thickness,
            ),
            # Assembly(
            #     material=material_choice.gamma_shield,
            #     thickness=disk_geometry_params.gamma_shield_thickness,
            # ),
        ],
    )

    outer_core_layers_bottom = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.bottom_reflector,
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

    half_reflector_part = AssemblySections(
        parts=[
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
    )
    reflector_part = mirror_assembly(half_reflector_part)

    half_shield_moderator_part = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.coolant_cladding,
                thickness=disk_geometry_params.shield_moderator_cladding_thickness,
            ),
            Assembly(
                material=material_choice.neutron_shield_moderator,
                thickness=disk_geometry_params.fuel_cladding_thickness
                + disk_geometry_params.fuel_thickness / 2
                - disk_geometry_params.shield_moderator_cladding_thickness,
            ),
        ],
    )
    shield_moderator_part = mirror_assembly(half_shield_moderator_part)

    half_shield_absorber_part = AssemblySections(
        parts=[
            Assembly(
                material=material_choice.neutron_absorber,
                thickness=disk_geometry_params.fuel_cladding_thickness
                + disk_geometry_params.fuel_thickness / 2,
            ),
        ],
    )
    shield_absorber_part = mirror_assembly(half_shield_absorber_part)

    outer_core_layers_between_disks = [
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
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
                        emitter_assembly_placeholder,
                        *reflector_part.parts,
                        emitter_assembly_placeholder,
                        *reflector_part.parts,
                        emitter_assembly_placeholder,
                        *half_reflector_part.parts,
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.reflector_thickness,
        ),
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
                        Assembly(
                            material=material_choice.neutron_shield_moderator,
                            thickness=disk_geometry_params.moderator_thickness / 2
                            + disk_geometry_params.moderator_cladding_thickness
                            - disk_geometry_params.shield_moderator_cladding_thickness,
                        ),
                        Assembly(
                            material=material_choice.coolant_cladding,
                            thickness=disk_geometry_params.shield_moderator_cladding_thickness,
                        ),
                        emitter_assembly_placeholder,
                        *shield_moderator_part.parts,
                        emitter_assembly_placeholder,
                        *shield_moderator_part.parts,
                        emitter_assembly_placeholder,
                        *half_shield_moderator_part.parts,
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.neutron_shield_moderator_thickness,
        ),
        OuterCoreAssemblySections(
            parts=mirror_assembly(
                AssemblySections(
                    parts=[
                        Assembly(
                            material=material_choice.neutron_absorber,
                            thickness=disk_geometry_params.moderator_thickness / 2
                            + disk_geometry_params.moderator_cladding_thickness,
                        ),
                        emitter_assembly_placeholder,
                        *shield_absorber_part.parts,
                        emitter_assembly_placeholder,
                        *shield_absorber_part.parts,
                        emitter_assembly_placeholder,
                        *half_shield_absorber_part.parts,
                    ],
                ),
            ).parts,
            layer_thickness=disk_geometry_params.neutron_shield_absorber_thickness,
        ),
    ]

    outer_core_between_disks_thickness = calculate_layers_thickness(
        outer_core_layers_between_disks
    )

    assert outer_core_between_disks_thickness >= calculate_assembly_thickness(
        outer_core_layers_inside_shaft
    )

    assert (
        calculate_assembly_thickness(outer_core_layers_bottom)
        == outer_core_between_disks_thickness
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
        outer_core_thickness=outer_core_between_disks_thickness,
        frustum_pitch=disk_geometry_params.frustum_pitch,
    )
    assembly_core_distance = (
        core_desc.core_radius + outer_core_between_disks_thickness / 2
    )
    rotary_assembly_desc = RotaryAssemblyDesc(
        assembly_core_distance=assembly_core_distance,
        assembly_core_margin=1,
        rotary_assembly_radius=get_disks_radius(
            assembly_core_distance, core_desc.core_radius
        ),
        frustum_pitch=disk_geometry_params.frustum_pitch,
        rotary_axle_thickness=disk_geometry_params.rotary_axle_thickness,
    )

    geometry_settings = GeometrySettings(
        assembly_section_core=assembly_section_core,
        photovoltaic_assembly=assembly_section_photovoltaic,
        emitter_assembly=emitter_assembly,
        outer_core_thickness=outer_core_between_disks_thickness,
        core_desc=core_desc,
        rotary_assembly_desc=rotary_assembly_desc,
        material_choice=material_choice,
        outer_core_layers_inside_shaft=outer_core_layers_inside_shaft,
        outer_core_layers_between_disks=outer_core_layers_between_disks,
        outer_core_layers_bottom=outer_core_layers_bottom,
    )

    geometry, universe, tracked_cells, drums = define_disks_geometry(
        geometry_settings, materials_dict
    )
    return MakeSimulationGeometryResult(
        geometry=geometry,
        universe=universe,
        tracked_cells=tracked_cells,
        drums=drums,
        geometry_settings=geometry_settings,
    )
