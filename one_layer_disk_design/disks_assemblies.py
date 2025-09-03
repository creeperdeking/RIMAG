from typing import Dict, List, Optional

import openmc
from common_lib.assemblies import (
    create_outer_core_assembly_section,
)
from common_lib.assemblies_types import (
    AssemblySections,
    CoreDesc,
)
from common_lib.assemblies_types import BoundariesGeometrySettings
from common_lib.geometry_utils import (
    create_bounded_surface_plane,
    create_hollow_cylinder,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc
from one_layer_disk_design.disks import (
    DiskAssemblyLayer,
)


def get_disks_boundaries(
    geometry_settings: BoundariesGeometrySettings,
    outer_radius: float,
    inner_radius: float,
    assembly_thickness: float,
    drums: List[DiskAssemblyLayer],
) -> openmc.Region:
    drums_start_height = drums[0].height
    drums_end_height = drums[-1].height + assembly_thickness

    assemblies_boundary = create_hollow_cylinder(
        rotary_assembly_desc=geometry_settings.rotary_assembly_desc,
        outer_radius=outer_radius,
        inner_radius=inner_radius,
        thickness=drums_end_height - drums_start_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
        height=(drums_end_height + drums_start_height) / 2,
    )
    return assemblies_boundary


def make_disks_cells(
    assembly_section: AssemblySections,
    disks: List[DiskAssemblyLayer],
    rotary_assembly_desc: RotaryAssemblyDesc,
    materials_dict: Dict[str, openmc.Material],
    boundary_shape: Optional[openmc.Intersection] = None,
) -> Dict[str, openmc.Cell]:
    shapes = {}
    for disk in disks:
        current_height = disk.height
        for assembly_part in assembly_section.parts:
            if not assembly_part.is_emitter and assembly_part.material is not None:
                shape = create_bounded_surface_plane(
                    rotary_assembly_desc,
                    assembly_part.thickness,
                    z0=current_height + assembly_part.thickness / 2,
                    boundary_type="transmission",
                )

                if boundary_shape is not None:
                    shape = shape & boundary_shape
                if assembly_part.material in shapes:
                    shapes[assembly_part.material] = (
                        shapes[assembly_part.material] | shape
                    )
                else:
                    shapes[assembly_part.material] = shape
            current_height += assembly_part.thickness
    cells = {}
    for material, shape in shapes.items():
        cell = openmc.Cell(name=f"{material}")
        cell.region = shape
        cell.fill = materials_dict[material]
        cells[material] = cell
    return cells


def define_discs_emitter_boundary(
    assembly_section: AssemblySections,
    disks: List[DiskAssemblyLayer],
    core_desc: CoreDesc,
    rotary_assembly_desc: RotaryAssemblyDesc,
    inner_core_penetration: float,
) -> openmc.Intersection:
    outer_core_assembly_section = create_outer_core_assembly_section(assembly_section)
    boundary_shape = None
    for disk in disks:
        current_height = disk.height
        for assembly_part in outer_core_assembly_section.parts:
            if assembly_part.is_emitter:
                additional_boundary_shape = create_hollow_cylinder(
                    rotary_assembly_desc,
                    outer_radius=rotary_assembly_desc.rotary_assembly_radius,
                    inner_radius=rotary_assembly_desc.rotary_assembly_radius
                    - core_desc.core_radius * 2
                    - inner_core_penetration,
                    thickness=assembly_part.thickness,
                    distance_from_origin=rotary_assembly_desc.assembly_core_distance,
                    height=current_height + assembly_part.thickness / 2,
                )
                boundary_shape = (
                    additional_boundary_shape
                    if boundary_shape is None
                    else boundary_shape | additional_boundary_shape
                )
            current_height += assembly_part.thickness

    return boundary_shape
