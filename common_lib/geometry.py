import math
from typing import Dict, List

import openmc
import openmc.model


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
    create_cylinder,
    get_vertical_core_height_with_margin,
    make_surface_plane,
    SPACING_CONSTANT,
    get_outer_empty_zone_parameters,
    get_geometry_bounding_box_one_full_layer,
)

from common_lib.geometry_types import GeometrySettings


def get_base_geometry(
    geometry_settings: GeometrySettings,
):
    assembly_thickness = calculate_assembly_thickness(
        geometry_settings.assembly_section_core
    )
    core_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.core_radius,
        geometry_settings.core_desc.core_height,
    )
    disk_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
        geometry_settings.core_desc.core_height,
        distance_from_origin=geometry_settings.rotary_assembly_desc.assembly_core_distance,
    )
    photovoltaic_boundary = define_photovoltaic_boundary_large(
        geometry_settings.core_desc,
        geometry_settings.rotary_assembly_desc,
    )
    outer_core_layers_thickness = calculate_assembly_thickness(
        geometry_settings.outer_core_layers_inside_shaft
    )

    shaft_boundary = get_shaft_boundary(
        geometry_settings, outer_core_layers_thickness, assembly_thickness
    )
    outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)
    outer_empty_zone_boundary_cylinder = -openmc.ZCylinder(
        r=outer_empty_zone_parameters.radius,
        x0=outer_empty_zone_parameters.x0,
        boundary_type="vacuum",
    )
    return (
        assembly_thickness,
        core_boundary,
        photovoltaic_boundary,
        shaft_boundary,
        disk_boundary,
        outer_empty_zone_boundary_cylinder,
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


def get_shaft_boundary(
    geometry_settings: GeometrySettings,
    outer_core_layers_thickness: float,
    assembly_thickness: float,
):
    return create_cylinder(
        geometry_settings.rotary_assembly_desc,
        outer_core_layers_thickness / 2,
        assembly_thickness,
        distance_from_origin=geometry_settings.core_desc.core_radius
        + outer_core_layers_thickness / 2,
    )


def define_geometry(
    geometry_settings: GeometrySettings,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_assembly_cells: Dict[str, openmc.Cell],
    core_assembly_cells: Dict[str, openmc.Cell],
    between_disks_shielding_cells: List[Dict[str, openmc.Cell]],
    emitter_assembly_cells: Dict[str, openmc.Cell],
    emitter_boundary: openmc.Region,
    assemblies_boundary: openmc.Region,
    core_boundary: openmc.Region,
    photovoltaic_boundary: openmc.Region,
):
    (
        _,
        _,
        photovoltaic_boundary,
        shaft_boundary,
        _,
        outer_empty_zone_boundary_cylinder,
    ) = get_base_geometry(geometry_settings)
    check_assembly_thickness_equal(
        geometry_settings.assembly_section_core,
        geometry_settings.photovoltaic_assembly,
    )

    outer_core_boundary = create_cylinder(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.core_desc.outer_core_radius,
        geometry_settings.core_desc.core_height,
    )

    core_height_with_margin = (
        geometry_settings.core_desc.core_height + SPACING_CONSTANT * 2
    )

    vertical_core_height_with_margin = get_vertical_core_height_with_margin(
        geometry_settings
    )

    lower_left_corner, upper_right_corner = get_geometry_bounding_box_one_full_layer(
        geometry_settings,
    )

    number_of_layers_above = math.ceil(
        0.5 - lower_left_corner[2] / vertical_core_height_with_margin
    )
    number_of_layers_below = math.ceil(
        0.5 + upper_right_corner[2] / vertical_core_height_with_margin
    )

    number_of_layers = number_of_layers_above + number_of_layers_below + 1
    start_index = number_of_layers_below

    surfaces = [
        make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-core_height_with_margin / 2,
            boundary_type="transmission",
        )
    ]

    for i in range(number_of_layers):
        surfaces.append(
            make_surface_plane(
                geometry_settings.rotary_assembly_desc,
                z0=core_height_with_margin / 2
                + core_height_with_margin * (i - start_index),
                boundary_type="transmission",
            )
        )

    outer_empty_zone_boundary = (
        outer_empty_zone_boundary_cylinder
        & -make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=geometry_settings.core_desc.core_height / 2 + SPACING_CONSTANT,
            boundary_type="transmission",
        )
        & +make_surface_plane(
            geometry_settings.rotary_assembly_desc,
            z0=-geometry_settings.core_desc.core_height / 2 - SPACING_CONSTANT,
            boundary_type="transmission",
        )
    )

    ### Making Cells

    outer_core_layers_inside_shaft = make_outer_core_layers(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_inside_shaft,
        geometry_settings.core_desc,
        materials_dict,
        shaft_boundary & ~emitter_boundary,
    )

    outer_core_layers_bottom_cells = make_outer_core_layers(
        geometry_settings.rotary_assembly_desc,
        geometry_settings.outer_core_layers_bottom,
        geometry_settings.core_desc,
        materials_dict,
        outer_empty_zone_boundary & ~emitter_boundary,
    )

    outer_empty_zone = (
        outer_empty_zone_boundary
        & ~outer_core_boundary
        & ~photovoltaic_boundary
        & ~emitter_boundary
    )

    outer_empty_zone_cell = openmc.Cell(name="outer_empty_zone")
    outer_empty_zone_cell.region = outer_empty_zone
    outer_empty_zone_cell.fill = materials_dict[geometry_settings.material_choice.void]

    flattenned_between_disks_shielding_cells = []
    for shielding_layer in between_disks_shielding_cells:
        flattenned_between_disks_shielding_cells.extend(shielding_layer.values())

    cells = [
        *core_assembly_cells.values(),
        *flattenned_between_disks_shielding_cells,
        *outer_core_layers_inside_shaft,
        *outer_core_layers_bottom_cells,
        *photovoltaic_assembly_cells.values(),
        *emitter_assembly_cells.values(),
        outer_empty_zone_cell,
    ]

    ### Make the reactor universe

    layer_universe = openmc.Universe(cells=cells)

    layer_cells = []
    layers_universes = [layer_universe] * number_of_layers
    for k, u in enumerate(layers_universes):
        region = outer_empty_zone_boundary_cylinder & +surfaces[k] & -surfaces[k + 1]
        c = openmc.Cell(region=region, fill=u, name=f"boundary_layer_{k}")
        c.translation = (
            0,
            0,
            (vertical_core_height_with_margin) * (k - start_index),
        )
        layer_cells.append(c)

    reactor_universe = openmc.Universe(cells=layer_cells)
    z_bot = openmc.ZPlane(
        z0=-vertical_core_height_with_margin / 2, boundary_type="periodic"
    )
    z_top = openmc.ZPlane(
        z0=vertical_core_height_with_margin / 2, boundary_type="periodic"
    )
    z_bot.periodic_surface = z_top

    reactor_universe = openmc.Universe(cells=layer_cells)

    reactor_slice_cell = openmc.Cell(
        region=outer_empty_zone_boundary_cylinder & +z_bot & -z_top,
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
