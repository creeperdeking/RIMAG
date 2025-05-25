import math
from typing import Dict, List, Optional

import openmc
from common_lib.assemblies import (
    create_outer_core_assembly_section,
    AssemblySections,
    CoreDesc,
    BoundariesGeometrySettings,
)
from common_lib.geometry_utils import (
    create_cylinder,
    create_hollow_cylinder,
    circle_intersection_area,
)
from common_lib.rotary_assembly import RotaryAssemblyDesc
from one_layer_disk_design.disks import (
    calculate_disks_surface_in_core,
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
        outer_radius=outer_radius,
        inner_radius=inner_radius,
        thickness=drums_end_height - drums_start_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
        height=(drums_end_height + drums_start_height) / 2,
    )
    return assemblies_boundary


def calculate_disks_fuel_volume(
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    assembly_section: AssemblySections,
    drums: List[DiskAssemblyLayer],
) -> float:
    fuel_thickness = 0
    for assembly_part in assembly_section.parts:
        if not assembly_part.is_emitter and assembly_part.is_fuel:
            fuel_thickness += assembly_part.thickness
            break

    fuel_volume = (
        calculate_disks_surface_in_core(drums, drum_desc, core_desc) * fuel_thickness
    )

    return fuel_volume


def calculate_photovoltaic_volume(
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    assembly_section: AssemblySections,
    drums: List[DiskAssemblyLayer],
) -> float:
    print(f"Rotary assembly radius: {drum_desc.rotary_assembly_radius}")
    print(f"Assembly core distance: {drum_desc.assembly_core_distance}")
    print(f"Core outer radius: {core_desc.outer_core_radius}")
    # First, calculate the area of one photovoltaic layer
    photovoltaic_area = (
        drum_desc.rotary_assembly_radius**2 * math.pi
        - circle_intersection_area(
            core_desc.outer_core_radius,
            drum_desc.rotary_assembly_radius,
            drum_desc.assembly_core_distance,
        )
    )
    print(f"Photovoltaic area: {photovoltaic_area}")
    photovoltaic_thickness = 0
    for assembly_part in assembly_section.parts:
        if assembly_part.is_photovoltaic:
            photovoltaic_thickness += assembly_part.thickness
    print(f"Photovoltaic thickness: {photovoltaic_thickness}")

    photovoltaic_volume = photovoltaic_area * photovoltaic_thickness * len(drums)

    return photovoltaic_volume


def calculate_disks_emitter_volume(
    assembly_section: AssemblySections,
    emitter_assembly: AssemblySections,
    drums: List[DiskAssemblyLayer],
    drum_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
) -> float:
    emitter_thickness = 0
    for assembly_part in emitter_assembly.parts:
        if assembly_part.is_emitter:
            emitter_thickness += assembly_part.thickness
    emitters_per_layer = 0
    for assembly_part in assembly_section.parts:
        if assembly_part.is_emitter:
            emitters_per_layer += 1

    total_emitter_thickness = emitter_thickness * emitters_per_layer
    emitter_volume = (
        (
            drums[0].radius ** 2 * math.pi
            - ((drums[0].radius - core_desc.core_radius * 2) ** 2 * math.pi)
        )
        * total_emitter_thickness
        * len(drums)
    )

    return emitter_volume


def make_disks_cells(
    assembly_section: AssemblySections,
    core_desc: CoreDesc,
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
                shape = create_cylinder(
                    disk.radius,
                    assembly_part.thickness,
                    distance_from_origin=rotary_assembly_desc.assembly_core_distance,
                    height=current_height + assembly_part.thickness / 2,
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
    drum_desc: RotaryAssemblyDesc,
    inner_core_penetration: float,
) -> openmc.Intersection:
    outer_core_assembly_section = create_outer_core_assembly_section(assembly_section)
    boundary_shape = None
    for disk in disks:
        current_height = disk.height
        for assembly_part in outer_core_assembly_section.parts:
            if assembly_part.is_emitter:
                additional_boundary_shape = create_hollow_cylinder(
                    outer_radius=disk.radius,
                    inner_radius=disk.radius
                    - core_desc.core_radius * 2
                    - inner_core_penetration,
                    thickness=assembly_part.thickness,
                    distance_from_origin=drum_desc.assembly_core_distance,
                    height=current_height + assembly_part.thickness / 2,
                )
                boundary_shape = (
                    additional_boundary_shape
                    if boundary_shape is None
                    else boundary_shape | additional_boundary_shape
                )
            current_height += assembly_part.thickness

    return boundary_shape
