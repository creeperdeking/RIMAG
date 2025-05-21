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
from common_lib.simlib import (
    run_sim_with_photovoltaic_tally,
    make_sim_settings,
    render_geometry,
    run_depletion_sim,
    print_core_characteristics,
    print_depletion_result,
)
from disk_design.disks_geometry import define_disks_geometry
from disk_design.disks_core_characteristics import calculate_disk_core_characteristics

core_diameter = 150
core_height = 150
moderator_cladding_thickness = 0.05
fuel_cladding_thickness = 0.32 / 2
fuel_thickness = 0.12 / 4
moderator_thickness = 0.8  # 1.2  # fuel_thickness * 4 * 5
fuel_emitter_gap = 0.09
emitter_thickness = 0.5
half_assembly = False

hot_temp = 1250 + 273
cold_temp = 1170 + 273

photovoltaic_efficiency = 0.38

reflector_thickness = 30
neutron_shield_thickness = 80

u235_enrichment = 9.5
fuel_hm_density = 0.25


run_mode = "none"


batches = 15000

material_choice = MaterialChoice(
    moderator="Graphite",
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
        ),
        ### Emitter
        Assembly(
            material=material_choice.emitter,
            thickness=emitter_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_emitter_gap,
        ),
    ],
)

emitter_assembly_placeholder = EmitterPlaceholder(
    thickness=calculate_assembly_thickness(emitter_assembly),
)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=core_height,
    outer_core_assembly=outer_core_layers,
)

rotary_assembly_desc = RotaryAssemblyDesc(
    assembly_core_distance=core_desc.core_radius
    + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    + 3,
    assembly_core_margin=1,
)


assembly_section_photovoltaic = AssemblySections(
    parts=[
        ### Emitter Assembly
        emitter_assembly_placeholder,
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic, thickness=0.02, is_fuel=True
        ),  # is_fuel is set to True to make the volume calculation work
        ### Water
        Assembly(
            material=material_choice.coolant,
            thickness=moderator_thickness - 0.02 * 2 + moderator_cladding_thickness * 2,
        ),
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic, thickness=0.02, is_fuel=True
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
    assembly_section_core=AssemblySections(
        parts=[
            ### Emitter Assembly
            emitter_assembly_placeholder,
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
            ### Fuel Cladding
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
            ### Fuel Cladding
            Assembly(
                material=material_choice.fuel_cladding,
                thickness=fuel_cladding_thickness,
            ),
        ],
    ),
    photovoltaic_assembly=assembly_section_photovoltaic,
    emitter_assembly=emitter_assembly,
    double_assembly=half_assembly,
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
    half_assembly,
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
)

print(
    "reactor diameter",
    drums[0].radius + core_desc.outer_core_radius - core_desc.core_radius,
)

if run_mode == "render":
    render_geometry(
        universe,
        universe_radius=(drums[0].radius + 10),
        pixels=(2500, 2500),
        basis="xz",
        origin=(rotary_assembly_desc.assembly_core_distance, 0, 0),
        geometry=geometry,
        colors=colors,
        materials_dict=materials_dict,
    )

settings = make_sim_settings(deterministic=False, batches=batches)

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
