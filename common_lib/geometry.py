import math
from typing import Dict, List

import openmc
import numpy as np
from pydantic import BaseModel

from common_lib import math_utils
from common_lib.assemblies_types import (
    AssemblySections,
)
from common_lib.assemblies import (
    define_photovoltaic_boundary_large,
    make_outer_core_layers,
    calculate_assembly_thickness,
)
from common_lib.geometry_utils import (
    CoreBoundaryPlanesPoints,
    create_cylinder,
    get_outer_empty_zone_parameters,
    get_vertical_core_height,
    make_boundary_planes,
    make_core_boundary_planes_points,
    make_surface_plane,
    get_outer_zone_parameters,
    get_geometry_bounding_box_one_full_layer,
    offset_core_boundary_planes_points,
)

from common_lib.geometry_types import GeometrySettings

def get_shaft_boundary(
    geometry_settings: GeometrySettings,
    outer_core_layers_thickness: float,
    assembly_thickness: float,
):
    return create_cylinder(
        geometry_settings.rotary_assembly_desc,
        outer_core_layers_thickness / 2,
        assembly_thickness,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    )




def check_assembly_thickness_equal(
    assembly1: AssemblySections,
    assembly2: AssemblySections,
):
    assembly1_thickness = calculate_assembly_thickness(assembly1)
    assembly2_thickness = calculate_assembly_thickness(assembly2)
    if not math.isclose(assembly1_thickness, assembly2_thickness):
        raise ValueError(
            f"Assembly thickness must be the same. Assembly1 thickness: {assembly1_thickness}, Assembly2 thickness: {assembly2_thickness}"
        )


def check_assembly_compatibility(
    assembly1: AssemblySections, assembly2: AssemblySections, assembly_number=None
):
    check_assembly_thickness_equal(assembly1, assembly2)
    current_thickness_assembly1 = 0
    current_thickness_assembly2 = 0
    current_index_assembly2 = 0
    for i, part in enumerate(assembly1.parts):
        if part.is_emitter or part.is_emitter_placeholder:
            prev_thicknesses = [current_thickness_assembly2]
            while math_utils.strict_less_than(
                current_thickness_assembly2, current_thickness_assembly1
            ):
                current_thickness_assembly2 += assembly2.parts[
                    current_index_assembly2
                ].thickness
                current_index_assembly2 += 1
                prev_thicknesses.append(current_thickness_assembly2)
            if not math.isclose(
                current_thickness_assembly1, current_thickness_assembly2
            ) or not math.isclose(
                current_thickness_assembly1 + part.thickness,
                current_thickness_assembly2
                + assembly2.parts[current_index_assembly2].thickness,
            ):
                raise ValueError(
                    f"Element {i} of assembly {assembly_number} does not have an emmitter placeholder corresponding to the one in assembly {assembly_number + 1}"
                )
        current_thickness_assembly1 += part.thickness


def check_assemblies_compatibility(assemblies: List[AssemblySections]):
    for i in range(1, len(assemblies)):
        check_assembly_compatibility(assemblies[i - 1], assemblies[i], i - 1)

class BaseGeometry(BaseModel, arbitrary_types_allowed=True):
    assembly_thickness: float
    core_boundary: openmc.Region
    core_boundary_planes_points: CoreBoundaryPlanesPoints
    photovoltaic_boundary: openmc.Region
    shaft_boundary: openmc.Region
    inner_shaft_boundary: openmc.Region
    disk_boundary: openmc.Region
    outer_zone_boundary_cylinder: openmc.Region
    outer_core_boundary: openmc.Region
    outer_empty_zone_boundary: openmc.Region
    outer_empty_zone_midpoint: np.array
    multi_column_boundary: openmc.Region

def get_base_geometry(
    geometry_settings: GeometrySettings,
):
    core_boundary_planes_points = make_core_boundary_planes_points(geometry_settings)
    boundary_planes = make_boundary_planes(
        core_boundary_planes_points,
    )

    outer_core_boundary_planes_points = offset_core_boundary_planes_points(
        core_boundary_planes_points,
        geometry_settings,
        geometry_settings.outer_core_thickness,
    )
    outer_core_boundary_planes = make_boundary_planes(
        outer_core_boundary_planes_points,
    )

    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )

    disk_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
        geometry_settings.core_desc.core_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    )
    core_boundary = (
        create_cylinder(
            geometry_settings.rotary_assembly_desc,
            geometry_settings.core_desc.core_radius,
            geometry_settings.core_desc.core_height,
        )
        | (
            -boundary_planes.positive_y_plane
            & +boundary_planes.negative_y_plane
            & -boundary_planes.upper_boundary_plane
        )
        & disk_boundary
    )

    outer_core_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.outer_core_radius,
        geometry_settings.core_desc.core_height,
    ) | (
        -outer_core_boundary_planes.positive_y_plane
        & +outer_core_boundary_planes.negative_y_plane
        & -outer_core_boundary_planes.upper_boundary_plane
    )
    photovoltaic_boundary = define_photovoltaic_boundary_large(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
        outer_core_boundary,
    )
    outer_core_layers_thickness = calculate_assembly_thickness(
        geometry_settings.outer_core_layers_inside_shaft
    )

    shaft_boundary = get_shaft_boundary(
        geometry_settings, outer_core_layers_thickness, assembly_thickness
    )
    inner_shaft_boundary = get_shaft_boundary(
        geometry_settings,
        outer_core_layers_thickness
        - geometry_settings.rotary_assembly_desc.rotary_axle_thickness * 2,
        assembly_thickness,
    )
    outer_zone_parameters = get_outer_zone_parameters(geometry_settings)
    outer_zone_boundary_cylinder = -openmc.ZCylinder(
        r=outer_zone_parameters.radius,
        x0=outer_zone_parameters.x0,
        boundary_type="transmission",
    )

    outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)
    
    outer_empty_zone_upper_contact_point = (
        np.array([-math.cos(math.pi/6), math.sin(math.pi/6), 0]) * outer_empty_zone_parameters.radius
    ) + np.array([outer_empty_zone_parameters.x0, 0, 0])
    outer_empty_zone_lower_contact_point = np.array([
        outer_empty_zone_upper_contact_point[0],
        -outer_empty_zone_upper_contact_point[1],
        outer_empty_zone_upper_contact_point[2]
    ])
    midpoint_distance = outer_empty_zone_parameters.radius/(math.cos(math.pi/6))
    outer_empty_zone_midpoint = (np.array([-midpoint_distance,0,0]) +np.array([outer_empty_zone_parameters.x0, 0, 0]) )
    outer_empty_zone_boundary_transmissive_upper_plane = -openmc.Plane.from_points(outer_empty_zone_upper_contact_point, outer_empty_zone_midpoint, outer_empty_zone_upper_contact_point + np.array([0, 0, 1]))
    outer_empty_zone_boundary_transmissive_lower_plane = +openmc.Plane.from_points(outer_empty_zone_lower_contact_point, outer_empty_zone_midpoint, outer_empty_zone_lower_contact_point + np.array([0, 0, 1]))
    outer_empty_zone_boundary_vacuum_plane = -openmc.XPlane(
        x0=outer_empty_zone_parameters.x0 + outer_empty_zone_parameters.radius,
    )

    multi_column_boundary = -openmc.ZCylinder(
        r=midpoint_distance + geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
        x0=outer_empty_zone_midpoint[0],
        boundary_type="vacuum",
    )

    outer_empty_zone_boundary = (
         outer_empty_zone_boundary_transmissive_upper_plane
        & outer_empty_zone_boundary_transmissive_lower_plane &
         outer_empty_zone_boundary_vacuum_plane
    )

    outer_empty_zone_boundary_cylinder = -openmc.ZCylinder(
        r=outer_empty_zone_parameters.radius,
        x0=outer_empty_zone_parameters.x0,
        boundary_type="vacuum",
    )

    if geometry_settings.rotary_assembly_desc.number_of_reactor_columns == 1:
        outer_empty_zone_boundary = outer_empty_zone_boundary_cylinder
        multi_column_boundary = outer_empty_zone_boundary_cylinder


    return BaseGeometry(
        assembly_thickness=assembly_thickness,
        core_boundary=core_boundary,
        core_boundary_planes_points=core_boundary_planes_points,
        photovoltaic_boundary=photovoltaic_boundary,
        shaft_boundary=shaft_boundary,
        inner_shaft_boundary=inner_shaft_boundary,
        disk_boundary=disk_boundary,
        outer_zone_boundary_cylinder=outer_zone_boundary_cylinder,
        outer_core_boundary=outer_core_boundary,
        outer_empty_zone_boundary=outer_empty_zone_boundary,
        outer_empty_zone_midpoint=outer_empty_zone_midpoint,
        multi_column_boundary=multi_column_boundary,
    )

def make_module_stack_surfaces(geometry_settings: GeometrySettings):
    vertical_core_height = get_vertical_core_height(geometry_settings)
    lower_left_corner, upper_right_corner = get_geometry_bounding_box_one_full_layer(
        geometry_settings,
    )

    number_of_layers_above = math.ceil(
        0.5 - lower_left_corner[2] / vertical_core_height
    )
    number_of_layers_below = math.ceil(
        0.5 + upper_right_corner[2] / vertical_core_height
    )

    number_of_layers = number_of_layers_above + number_of_layers_below + 1
    start_index = number_of_layers_below

    surfaces = [
        make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-geometry_settings.core_desc.core_height / 2,
            boundary_type="transmission",
        )
    ]

    for i in range(number_of_layers):
        surfaces.append(
            make_surface_plane(
                geometry_settings.rotary_assembly_desc,
                z0=geometry_settings.core_desc.core_height / 2
                + geometry_settings.core_desc.core_height * (i - start_index),
                boundary_type="transmission",
            )
        )
    return surfaces, number_of_layers, start_index

def define_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_assembly_cells: Dict[str, openmc.Cell],
    core_assembly_cells: Dict[str, openmc.Cell],
    outer_core_layers_between_disks_scells: List[Dict[str, openmc.Cell]],
    emitter_assembly_cells: Dict[str, openmc.Cell],
    emitter_boundary: openmc.Region,
    assemblies_boundary: openmc.Region,
    core_boundary: openmc.Region,
    photovoltaic_boundary: openmc.Region,
):
    bg = get_base_geometry(geometry_settings)

    check_assembly_thickness_equal(
        geometry_settings.assembly_section_core,
        geometry_settings.photovoltaic_assembly,
    )

    surfaces, number_of_layers, start_index = make_module_stack_surfaces(geometry_settings)

    outer_zone_boundary = (
        bg.outer_zone_boundary_cylinder
        & -make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=geometry_settings.core_desc.core_height / 2 , 
            boundary_type="transmission",
        )
        & +make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-geometry_settings.core_desc.core_height / 2 ,
            boundary_type="transmission",
        )
    )

    outer_empty_zone_bounded_boundary = (
        bg.outer_empty_zone_boundary
        & -make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=geometry_settings.core_desc.core_height / 2 , 
            boundary_type="transmission",
        )
        & +make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-geometry_settings.core_desc.core_height / 2 ,
            boundary_type="transmission",
        )
    )

    shaft_region = bg.shaft_boundary & ~bg.inner_shaft_boundary

    ### Making Cells

    outer_core_layers_inside_shaft = make_outer_core_layers(
        geometry_settings,
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_inside_shaft,
        geometry_settings.core_desc,
        materials_dict,
        bg.inner_shaft_boundary,
        bg.core_boundary_planes_points,
    )

    shaft_cell = openmc.Cell(
        region=shaft_region,
        fill=materials_dict[geometry_settings.material_choice.rotary_axle],
        name="shaft",
    )

    outer_core_layers_bottom_cells = make_outer_core_layers(
        geometry_settings,
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_bottom,
        geometry_settings.core_desc,
        materials_dict,
        outer_zone_boundary & ~bg.disk_boundary,
        bg.core_boundary_planes_points,
    )

    outer_zone = (
        outer_zone_boundary
        & ~bg.outer_core_boundary
        & ~photovoltaic_boundary
        & ~emitter_boundary
    )

    outer_zone_cell = openmc.Cell(name="outer_zone")
    outer_zone_cell.region = outer_zone
    outer_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    outer_empty_zone = (
        outer_empty_zone_bounded_boundary
        & ~outer_zone_boundary
    )

    outer_empty_zone_cell = openmc.Cell(name="outer_empty_zone")
    outer_empty_zone_cell.region = outer_empty_zone
    outer_empty_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    flattenned_between_disks_shielding_cells = []
    for shielding_layer in outer_core_layers_between_disks_scells:
        flattenned_between_disks_shielding_cells.extend(shielding_layer.values())

    cells = [
        *core_assembly_cells.values(),
        *flattenned_between_disks_shielding_cells,
        *outer_core_layers_inside_shaft,
        *outer_core_layers_bottom_cells,
        *photovoltaic_assembly_cells.values(),
        *emitter_assembly_cells.values(),
        outer_zone_cell,
        outer_empty_zone_cell,
        shaft_cell,
    ]

    ### Make the reactor universe

    layer_universe = openmc.Universe(cells=cells)

    vertical_core_height = get_vertical_core_height(
        geometry_settings
    )

    layer_cells = []
    layers_universes = [layer_universe] * number_of_layers
    for k, u in enumerate(layers_universes):
        region = bg.outer_empty_zone_boundary & +surfaces[k] & -surfaces[k + 1]
        c = openmc.Cell(region=region, fill=u, name=f"boundary_layer_{k}")
        c.translation = (
            0,
            0,
            (vertical_core_height) * (k - start_index),
        )
        layer_cells.append(c)

    z_bot = openmc.ZPlane(
        z0=-vertical_core_height / 2, boundary_type="periodic"
    )
    z_top = openmc.ZPlane(
        z0=vertical_core_height / 2, boundary_type="periodic"
    )
    z_bot.periodic_surface = z_top

    reactor_column_universe_1 = openmc.Universe(cells=layer_cells)
    reactor_universe = reactor_column_universe_1

    if geometry_settings.rotary_assembly_desc.number_of_reactor_columns == 1:
        reactor_universe = reactor_column_universe_1
    else:
        angle = 2*math.pi/3
        # Build parent-level regions for each column (two wedges around the same midpoint)
        outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)
        upper_contact_point = (
            np.array(
                [
                    -math.cos(math.pi / 6),
                    math.sin(math.pi / 6),
                    0,
                ]
            )
            * outer_empty_zone_parameters.radius
            + np.array([outer_empty_zone_parameters.x0, 0, 0])
        )
        lower_contact_point = np.array(
            [upper_contact_point[0], -upper_contact_point[1], upper_contact_point[2]]
        )
        midpoint = bg.outer_empty_zone_midpoint

        # Unrotated wedge planes (vertical) defined by midpoint and contact points
        upper_plane = -openmc.Plane.from_points(
            upper_contact_point,
            midpoint,
            upper_contact_point + np.array([0, 0, 1]),
        )
        lower_plane = +openmc.Plane.from_points(
            lower_contact_point,
            midpoint,
            lower_contact_point + np.array([0, 0, 1]),
        )
        region_col1 = upper_plane & lower_plane

        # Rotation utilities (about z-axis around the wedge midpoint)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        rot_z = np.array(
            [
                [cos_a, -sin_a, 0.0],
                [sin_a, cos_a, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )

        def rotate_point_around_midpoint(p: np.ndarray) -> np.ndarray:
            return rot_z @ (p - midpoint) + midpoint

        # Rotated wedge planes
        upper_contact_point_rot = rotate_point_around_midpoint(upper_contact_point)
        lower_contact_point_rot = rotate_point_around_midpoint(lower_contact_point)
        upper_plane_rot = -openmc.Plane.from_points(
            upper_contact_point_rot,
            midpoint,
            upper_contact_point_rot + np.array([0, 0, 1]),
        )
        lower_plane_rot = +openmc.Plane.from_points(
            lower_contact_point_rot,
            midpoint,
            lower_contact_point_rot + np.array([0, 0, 1]),
        )
        region_col2 = upper_plane_rot & lower_plane_rot

        # Negative rotation utilities and planes (rotate by -angle)
        rot_z_neg = rot_z.T

        def rotate_point_around_midpoint_neg(p: np.ndarray) -> np.ndarray:
            return rot_z_neg @ (p - midpoint) + midpoint

        upper_contact_point_rot_neg = rotate_point_around_midpoint_neg(upper_contact_point)
        lower_contact_point_rot_neg = rotate_point_around_midpoint_neg(lower_contact_point)
        upper_plane_rot_neg = -openmc.Plane.from_points(
            upper_contact_point_rot_neg,
            midpoint,
            upper_contact_point_rot_neg + np.array([0, 0, 1]),
        )
        lower_plane_rot_neg = +openmc.Plane.from_points(
            lower_contact_point_rot_neg,
            midpoint,
            lower_contact_point_rot_neg + np.array([0, 0, 1]),
        )
        region_col3 = upper_plane_rot_neg & lower_plane_rot_neg

        # Create two cells: original column and a rotated clone around the midpoint
        col1_cell = openmc.Cell(region=region_col1, fill=reactor_column_universe_1, name="reactor_column_1")

        col2_cell = openmc.Cell(region=region_col2, fill=reactor_column_universe_1, name="reactor_column_2_rotated")
        # Apply rotation around midpoint: x' = R x + t, choose t so that midpoint is fixed
        # OpenMC applies transforms in a way that requires using the inverse
        # (transpose) for the desired visual/world rotation direction.
        R = rot_z.T
        translation_fix = midpoint - R @ midpoint
        col2_cell.rotation = R
        col2_cell.translation = (float(translation_fix[0]), float(translation_fix[1] + 157), float(translation_fix[2]))

        # Third cell rotated by -angle
        col3_cell = openmc.Cell(region=region_col3, fill=reactor_column_universe_1, name="reactor_column_3_rotated_neg")
        # For a world rotation of -angle, use the inverse (which is +angle)
        R_neg = rot_z
        translation_fix_neg = midpoint - R_neg @ midpoint
        col3_cell.rotation = R_neg
        col3_cell.translation = (float(translation_fix_neg[0]), float(translation_fix_neg[1] - 157), float(translation_fix_neg[2]))

        reactor_universe = openmc.Universe(cells=[col1_cell, col2_cell, col3_cell])

    reactor_slice_cell = openmc.Cell(
        region=bg.multi_column_boundary & +z_bot & -z_top,
        fill=reactor_universe,
    )
    reactor_slice_universe = openmc.Universe(cells=[reactor_slice_cell])

    from collections import defaultdict

    # Collect all key-value pairs
    tracked_cells = defaultdict(list)
    for cell in cells:
        tracked_cells[cell.fill.name].append(cell)

    return (
        openmc.Geometry(
            reactor_slice_universe, merge_surfaces=True, surface_precision=5
        ),
        reactor_slice_universe,
        tracked_cells,
    )
