from common_lib.assemblies import (
    calculate_assembly_thickness,
    compute_core_desc,
    Assembly,
    AssemblySections,
    EmitterPlaceholder,
)
from common_lib.geometry import GeometrySettings
from common_lib.materials import MaterialChoice, make_materials
from common_lib.rotary_assembly import RotaryAssemblyDesc
from common_lib.geometry_utils import SPACING_CONSTANT
from common_lib.simlib import (
    run_keff_sim,
    run_sim_with_photovoltaic_tally,
    make_sim_settings,
    render_geometry,
    run_depletion_sim,
    print_core_characteristics,
    print_depletion_result,
)
from one_layer_disk_design.disks_geometry import define_disks_geometry
from one_layer_disk_design.disks_core_characteristics import (
    calculate_disk_core_characteristics,
)
from one_layer_disk_design.disks import get_disks_radius

core_diameter = 80
moderator_cladding_thickness = 0.05
fuel_cladding_thickness = 0.94 / 2
fuel_thickness = 0.24 / 4 / 2
moderator_thickness = 0.4  # fuel_thickness * 4 * 5
fuel_emitter_gap = 0.1
emitter_thickness = 0.5
thickness_photovoltaic = 0.02

hot_temp = 1250 + 273
cold_temp = 1150 + 273

photovoltaic_efficiency = 0.34

reflector_thickness = 30
neutron_shield_thickness = 90

u235_enrichment = 19.5
fuel_hm_density = 0.25

# values are 'keff', 'render', 'depletion' or 'none' (to just show the calculated core characteristics)
run_mode = "keff"
# values are 'generate', 'use' or 'no'
weight_windows = "no"


batches = 7500

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Boron Carbide",
    reflector="Graphite",
    fuel="Uranium Oxy-Carbide",
    moderator_cladding="Zirconium",
    emitter="Graphite 2",
    fuel_cladding="Graphite",
    void="Void",
    photovoltaic="Silicon",
    coolant="Light Water",
)

outer_core_layers = AssemblySections(
    parts=[
        Assembly(material=material_choice.reflector, thickness=reflector_thickness),
        Assembly(
            material=material_choice.neutron_shield, thickness=neutron_shield_thickness
        ),
    ],
)

emitter_assembly = AssemblySections(
    parts=[
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_emitter_gap,
            is_emitter_gap=True,
        ),
        ### Emitter
        Assembly(
            material=material_choice.emitter,
            thickness=emitter_thickness,
            is_emitter=True,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_emitter_gap,
            is_emitter_gap=True,
        ),
    ],
)

emitter_assembly_placeholder = EmitterPlaceholder(
    thickness=calculate_assembly_thickness(emitter_assembly),
)

assembly_section_core = AssemblySections(
    parts=[
        ### Cladding
        Assembly(
            material=material_choice.moderator_cladding,
            thickness=moderator_cladding_thickness,
        ),
        ### Moderator
        Assembly(
            material=material_choice.moderator,
            thickness=moderator_thickness,
        ),
        ### Cladding
        Assembly(
            material=material_choice.moderator_cladding,
            thickness=moderator_cladding_thickness,
        ),
        ### Emitter Assembly
        emitter_assembly_placeholder,
        Assembly(
            material=material_choice.fuel_cladding,
            thickness=fuel_cladding_thickness,
        ),
        ### Fuel
        Assembly(
            material=material_choice.fuel,
            thickness=fuel_thickness,
            is_fuel=True,
        ),
    ],
)

assembly_thickness = calculate_assembly_thickness(assembly_section_core)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=assembly_thickness + SPACING_CONSTANT * 2,
    outer_core_assembly=outer_core_layers,
)
assembly_core_distance = (
    core_desc.core_radius
    + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    + 3
)
rotary_assembly_desc = RotaryAssemblyDesc(
    assembly_core_distance=assembly_core_distance,
    assembly_core_margin=1,
    rotary_assembly_radius=get_disks_radius(
        assembly_core_distance, core_desc.core_radius
    ),
)


assembly_section_photovoltaic = AssemblySections(
    parts=[
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Water
        Assembly(
            material=material_choice.coolant,
            thickness=moderator_thickness
            - thickness_photovoltaic * 2
            + moderator_cladding_thickness * 2,
        ),
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Emitter Assembly
        emitter_assembly_placeholder,
        ### Void
        Assembly(
            material="Void", thickness=fuel_cladding_thickness * 2 + fuel_thickness
        ),
    ]
)


geometry_settings = GeometrySettings(
    assembly_section_core=assembly_section_core,
    photovoltaic_assembly=assembly_section_photovoltaic,
    emitter_assembly=emitter_assembly,
    core_desc=core_desc,
    rotary_assembly_desc=rotary_assembly_desc,
    material_choice=material_choice,
    outer_core_layers=outer_core_layers,
)


materials_dict, materials_def, colors = make_materials(u235_enrichment, material_choice)

geometry, universe, cells, drums = define_disks_geometry(
    geometry_settings, materials_dict
)

(
    heavy_metal_mass,
    emissive_surface,
    core_power,
    core_power_electric,
    fuel_volume,
    emitter_core_volume,
    photovolatic_volume,
    radiative_flux,
) = calculate_disk_core_characteristics(
    rotary_assembly_desc,
    core_desc,
    geometry_settings,
    drums,
    material_choice,
    materials_def,
    hot_temp,
    cold_temp,
    photovoltaic_efficiency,
)


materials_dict[material_choice.fuel].volume = fuel_volume


print_core_characteristics(
    heavy_metal_mass,
    emissive_surface,
    core_power,
    core_power_electric,
    geometry_settings.assembly_section_core,
    radiative_flux,
    fuel_volume,
    drums,
)

print(
    "reactor diameter",
    drums[0].radius + core_desc.outer_core_radius - core_desc.core_radius,
)

print("core_height", core_desc.core_height)

if run_mode == "render":
    render_geometry(
        universe,
        universe_radius=(drums[0].radius * 2),
        universe_height=core_desc.core_height
        * 1.5,  # core_desc.core_height * 1.5, # drums[0].radius * 2 + 10,
        pixels=(2500, 2500),
        basis="xz",
        origin=(
            rotary_assembly_desc.assembly_core_distance,
            0,
            -0,
        ),
        geometry=geometry,
        colors=colors,
        materials_dict=materials_dict,
    )

settings = make_sim_settings(
    deterministic=False,
    batches=batches,
    weight_windows=weight_windows,
    window_radius=drums[0].radius,
    window_height=core_desc.core_height,
    window_origin=(rotary_assembly_desc.assembly_core_distance, 0, 0),
)

if run_mode == "keff":
    # run_keff_sim(geometry, settings, materials_dict)
    run_sim_with_photovoltaic_tally(
        geometry,
        settings,
        materials_dict,
        cells[material_choice.photovoltaic],
        cells[material_choice.emitter],
        core_power,
        photovolatic_volume,
        emitter_core_volume,
        batches,
    )

if run_mode == "depletion":
    run_depletion_sim(
        thermal_power=core_power,
        geometry=geometry,
        settings=settings,
        materials=materials_dict.values(),
        sim_steps=[
            0.01,
            0.1,
            0.89,
            1,
            5,
            23,
            60,
            30 * 3,
            30 * 6,
            30 * 6,
            30 * 6,
            30 * 6,
            30 * 6,
            30 * 6,
        ],  # [1, 3, 6, 10, 10, 10, 10, 10],
        steps_units="d",
    )
    print_depletion_result(
        materials_dict, material_choice, core_power, heavy_metal_mass
    )
