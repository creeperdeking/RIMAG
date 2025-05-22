from typing import List, Dict, Optional, Literal
import openmc
from pydantic import BaseModel

from common_lib.geometry_utils import (
    create_hollow_cylinder,
    create_cylinder,
    SPACING_CONSTANT,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc


class CoreDesc(BaseModel):
    core_radius: float
    core_height: float
    outer_core_radius: float
    outer_core_height: float


class Assembly(BaseModel):
    thickness: float
    material: Optional[str] = None
    is_fuel: bool = False
    is_emitter: Optional[bool] = False
    is_emitter_gap: Optional[bool] = False


class EmitterPlaceholder(BaseModel):
    thickness: float
    is_emitter: Literal[True] = True


class AssemblySections(BaseModel):
    parts: List[Assembly | EmitterPlaceholder]


class BoundariesGeometrySettings:
    emitter_assembly: AssemblySections
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def compute_core_desc(
    core_radius: float,
    core_height: float,
    outer_core_assembly: AssemblySections,
):
    outer_core_thickness = calculate_assembly_thickness(outer_core_assembly)
    return CoreDesc(
        core_radius=core_radius,
        core_height=core_height,
        outer_core_radius=core_radius + outer_core_thickness,
        outer_core_height=core_height,
    )


def define_photovoltaic_boundary(
    core_desc: CoreDesc,
    assembly_core_distance: float,
    double_assembly: bool,
) -> openmc.Intersection:
    boundary_shape = create_cylinder(
        core_desc.core_radius,
        core_desc.core_height,
        distance_from_origin=assembly_core_distance * 2,
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
            parts.extend(emitter_assembly.parts)
            current_part_thickness = 0
        else:
            current_part_thickness += assembly_part.thickness
    if current_part_thickness > 0:
        parts.append(Assembly(material=None, thickness=current_part_thickness))
    return AssemblySections(parts=parts)


def make_outer_core_layers(
    outer_core_layers: AssemblySections,
    core_desc: CoreDesc,
    emitter_boundary: openmc.Cell,
    materials_dict: Dict[str, openmc.Material],
) -> List[openmc.Cell]:

    cells = []
    current_layer_radius = core_desc.core_radius
    previous_layer_radius = current_layer_radius
    for i, layer in enumerate(outer_core_layers.parts):
        current_layer_radius = current_layer_radius + layer.thickness
        core_cylinder = -openmc.ZCylinder(
            r=previous_layer_radius,
        )
        cylinder = (
            create_cylinder(
                current_layer_radius,
                core_desc.core_height,
            )
            & ~core_cylinder
        )
        cell = openmc.Cell(name=f"outer_core_layer_{layer.material}_{i}")
        cell.region = cylinder & ~emitter_boundary
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


def calculate_assembly_thickness(assembly_section: AssemblySections) -> float:
    return sum(part.thickness for part in assembly_section.parts)
