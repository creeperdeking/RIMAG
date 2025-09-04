from copy import copy
from typing import List, Dict
import openmc

from common_lib.assemblies_types import (
    Assembly,
    AssemblySections,
    CoreDesc,
    OuterCoreAssemblySections,
)
from common_lib.geometry_types import GeometrySettings
from common_lib.geometry_utils import (
    create_cylinder,
    get_z_scaling,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc


def compute_core_desc(
    core_radius: float,
    core_height: float,
    outer_core_thickness: float,
    frustum_pitch: float,
):
    z_scaling = get_z_scaling(frustum_pitch)
    return CoreDesc(
        core_radius=core_radius,
        core_height=core_height,
        core_vertical_height=core_height * z_scaling,
        outer_core_radius=core_radius + outer_core_thickness,
    )


def define_photovoltaic_boundary_large(
    core_desc: CoreDesc,
    rotary_assembly_desc: RotaryAssemblyDesc,
) -> openmc.Intersection:
    boundary_shape = create_cylinder(
        rotary_assembly_desc,
        rotary_assembly_desc.rotary_assembly_radius,
        core_desc.core_height,
        distance_from_origin=rotary_assembly_desc.assembly_core_distance,
    ) & +openmc.ZCylinder(
        r=core_desc.outer_core_radius,
    )
    return boundary_shape


def define_photovoltaic_boundary_small(
    core_desc: CoreDesc,
    rotary_assembly_desc: RotaryAssemblyDesc,
) -> openmc.Intersection:
    boundary_shape = create_cylinder(
        rotary_assembly_desc,
        core_desc.core_radius,
        core_desc.core_height,
        distance_from_origin=rotary_assembly_desc.assembly_core_distance * 2,
    )
    return boundary_shape


def make_emitter_only_assembly(
    assembly_section: AssemblySections, emitter_assembly: AssemblySections
):
    parts = []
    current_part_thickness = 0
    for assembly_part in assembly_section.parts:
        if assembly_part.is_emitter:
            if current_part_thickness > 0:
                parts.append(Assembly(material=None, thickness=current_part_thickness))
            new_parts = []
            for part in emitter_assembly.parts:
                if part.is_emitter:
                    part_dict = part.model_dump()
                    part_dict.pop("is_emitter", None)
                    new_parts.append(Assembly(**part_dict, is_emitter=False))
                else:
                    new_parts.append(part)
            parts.extend(new_parts)
            current_part_thickness = 0
        else:
            current_part_thickness += assembly_part.thickness
    if current_part_thickness > 0:
        parts.append(Assembly(material=None, thickness=current_part_thickness))
    return AssemblySections(parts=parts)


def make_outer_core_layers(
    geometry_settings: GeometrySettings,
    rotary_assembly_desc: RotaryAssemblyDesc,
    outer_core_layers: AssemblySections,
    core_desc: CoreDesc,
    materials_dict: Dict[str, openmc.Material],
    boundary_shape: openmc.Region,
) -> List[openmc.Cell]:
    cells = []
    outer_core_radius_delta = (
        geometry_settings.outer_core_thickness
        - calculate_assembly_thickness(outer_core_layers)
    ) / 2
    current_layer_radius = core_desc.core_radius + outer_core_radius_delta
    previous_layer_radius = current_layer_radius
    for i, layer in enumerate(outer_core_layers.parts):
        current_layer_radius = current_layer_radius + layer.thickness
        core_cylinder = -openmc.ZCylinder(
            r=previous_layer_radius,
        )
        cylinder = (
            create_cylinder(
                rotary_assembly_desc,
                current_layer_radius,
                core_desc.core_height,
            )
            & ~core_cylinder
        )
        cell = openmc.Cell(name=f"outer_core_layer_{layer.material}_{i}")
        cell.region = cylinder & boundary_shape
        cell.fill = materials_dict[layer.material]
        cells.append(cell)
        previous_layer_radius = current_layer_radius
    return cells


def create_outer_core_assembly_section(
    assembly_section_core: AssemblySections,
) -> AssemblySections:
    parts = []
    current_part_thickness = 0
    for part in assembly_section_core.parts:
        if part.is_emitter:
            if current_part_thickness > 0:
                parts.append(Assembly(material=None, thickness=current_part_thickness))
            parts.append(part)
            current_part_thickness = 0
        else:
            current_part_thickness += part.thickness
    if current_part_thickness > 0:
        parts.append(Assembly(material=None, thickness=current_part_thickness))

    return AssemblySections(parts=parts)


def calculate_layers_thickness(layers: List[OuterCoreAssemblySections]) -> float:
    return sum(layer.layer_thickness for layer in layers)


def calculate_assembly_thickness(assembly_section: AssemblySections) -> float:
    return sum(part.thickness for part in assembly_section.parts)


# The assembly parts will be repeated but flipped
def mirror_assembly(assembly: AssemblySections) -> AssemblySections:
    first_part = assembly.parts[0:-1]
    middle_part = copy(assembly.parts[-1])
    middle_part.thickness *= 2
    second_part = copy(first_part)
    second_part.reverse()
    new_assembly = first_part + [middle_part] + second_part
    return AssemblySections(parts=new_assembly)
