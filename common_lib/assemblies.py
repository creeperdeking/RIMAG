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
    CoreBoundaryPlanesPoints,
    create_cylinder,
    get_z_scaling,
    make_boundary_planes,
    offset_core_boundary_planes_points,
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
    outer_core_boundary: openmc.Region,
) -> openmc.Intersection:
    boundary_shape = (
        create_cylinder(
            rotary_assembly_desc,
            rotary_assembly_desc.rotary_assembly_radius,
            core_desc.core_height,
            distance_from_origin=rotary_assembly_desc.assembly_core_distance,
        )
        & ~outer_core_boundary
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
    core_boundary_planes_points: CoreBoundaryPlanesPoints,
) -> List[openmc.Cell]:
    cells = []
    outer_core_radius_delta = (
        geometry_settings.outer_core_thickness
        - calculate_assembly_thickness(outer_core_layers)
    ) / 2
    inner_layer_radius = core_desc.core_radius + outer_core_radius_delta
    current_boundary_planes_points = offset_core_boundary_planes_points(
        core_boundary_planes_points,
        geometry_settings,
        outer_core_radius_delta,
    )
    for i, layer in enumerate(outer_core_layers.parts):
        offset_boundary_planes_points = offset_core_boundary_planes_points(
            current_boundary_planes_points,
            geometry_settings,
            layer.thickness,
        )
        inner_boundary_planes = make_boundary_planes(
            current_boundary_planes_points,
        )
        inner_boundary = +openmc.ZCylinder(r=inner_layer_radius, x0=0, y0=0) & (
            +inner_boundary_planes.positive_y_plane
            | -inner_boundary_planes.negative_y_plane
            | +inner_boundary_planes.upper_boundary_plane
        )
        outer_boundary_planes = make_boundary_planes(
            offset_boundary_planes_points,
        )
        outer_boundary = -openmc.ZCylinder(
            r=inner_layer_radius + layer.thickness, x0=0, y0=0
        ) | (
            -outer_boundary_planes.positive_y_plane
            & +outer_boundary_planes.negative_y_plane
            & -outer_boundary_planes.upper_boundary_plane
        )
        layer_boundary = None
        if i == 0:
            layer_boundary = outer_boundary
        else:
            layer_boundary = inner_boundary & outer_boundary

        cell = openmc.Cell(name=f"outer_core_layer_{layer.material}_{i}")
        cell.region = layer_boundary & boundary_shape
        cell.fill = materials_dict[layer.material]
        cells.append(cell)
        inner_layer_radius = inner_layer_radius + layer.thickness
        current_boundary_planes_points = offset_boundary_planes_points
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
