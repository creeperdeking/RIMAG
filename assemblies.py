from typing import List, Dict, Optional
import openmc


from common_lib.geometry_utils import (
    Assembly,
    AssemblySections,
    create_hollow_cylinder,
    create_cylinder,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc, RotaryAssemblyLayer
from common_lib.core import CoreDesc


class BoundariesGeometrySettings:
    emitter_assembly: AssemblySections
    rotary_assembly_desc: RotaryAssemblyDesc
    core_desc: CoreDesc
    double_assembly: bool


def get_assemblies_boundaries(
    geometry_settings: BoundariesGeometrySettings,
    drums: List[RotaryAssemblyLayer],
    assembly_thickness: float,
) -> openmc.Cell:

    assemblies_boundary = create_hollow_cylinder(
        drums[0].radius,
        drums[-1].radius - assembly_thickness,
        geometry_settings.core_desc.core_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    )

    if geometry_settings.double_assembly:
        assemblies_boundary = assemblies_boundary | create_hollow_cylinder(
            drums[0].radius,
            drums[-1].radius - assembly_thickness,
            geometry_settings.core_desc.core_height,
            distance_from_origin=-geometry_settings.rotary_assembly_desc.assembly_core_distance,
        )
    return assemblies_boundary


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


def make_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
    drums: List[RotaryAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    materials_dict: Dict[str, openmc.Material],
    boundary_shape: Optional[openmc.Intersection] = None,
) -> List[openmc.Cell]:
    shapes = {}
    for drum in drums:
        current_radius = drum.radius
        for assembly_part in assembly_section.parts:
            if not assembly_part.is_emitter and assembly_part.material is not None:
                shape = create_hollow_cylinder(
                    current_radius,
                    current_radius - assembly_part.thickness,
                    core_desc.core_height,
                    distance_from_origin=rotary_assembly_desc.assembly_core_distance,
                )
                if assembly_part.material in shapes:
                    shapes[assembly_part.material] = (
                        shapes[assembly_part.material] | shape
                    )
                else:
                    shapes[assembly_part.material] = shape
            current_radius -= assembly_part.thickness
    cells = []
    for material, shape in shapes.items():
        cell = openmc.Cell(name=f"{material}")
        if boundary_shape is not None:
            cell.region = shape & boundary_shape
        else:
            cell.region = shape
        cell.fill = materials_dict[material]
        cells.append(cell)
    return cells


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
    if double_assembly:
        boundary_shape = boundary_shape | create_cylinder(
            core_desc.core_radius,
            core_desc.core_height,
            distance_from_origin=-assembly_core_distance * 2,
        )
    return boundary_shape


def define_emitter_boundary(
    assembly_section: AssemblySections,
    drums: List[RotaryAssemblyLayer],
    core_desc: CoreDesc,
    drum_desc: RotaryAssemblyDesc,
) -> openmc.Intersection:
    outer_core_assembly_section = create_outer_core_assembly_section(assembly_section)
    boundary_shape = None
    for drum in drums:
        curent_radius = drum.radius
        for assembly_part in outer_core_assembly_section.parts:
            if assembly_part.is_emitter:
                additional_boundary_shape = create_hollow_cylinder(
                    curent_radius,
                    curent_radius - assembly_part.thickness,
                    core_desc.core_height,
                    distance_from_origin=drum_desc.assembly_core_distance,
                )
                boundary_shape = (
                    additional_boundary_shape
                    if boundary_shape is None
                    else boundary_shape | additional_boundary_shape
                )
            curent_radius -= assembly_part.thickness

    return boundary_shape


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
        core_cylinder = create_cylinder(
            previous_layer_radius, previous_layer_radius * 2
        )
        cylinder = (
            create_cylinder(current_layer_radius, current_layer_radius * 2)
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
