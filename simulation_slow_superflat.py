from common_lib.assemblies import (
    calculate_assembly_thickness,
    compute_core_desc,
)
from common_lib.assemblies_types import (
    Assembly,
    AssemblySections,
    EmitterPlaceholder,
)
from common_lib.geometry import (
    GeometrySettings,
    check_assembly_thickness_equal,
)
from common_lib.geometry_utils import (
    SPACING_CONSTANT,
    get_outer_empty_zone_parameters,
)
from common_lib.materials import MaterialChoice, MonitoredNuclide, make_materials
from common_lib.rotary_assembly import RotaryAssemblyDesc
from common_lib.simlib import (
    calculate_source_strength,
    make_sim_photon_from_cells,
    make_sim_settings,
    print_core_characteristics,
    print_depletion_result,
    render_geometry,
    run_depletion_sim,
    run_keff_sim,
    run_sim_with_tallies,
    stochastic_volume_calculation,
)
from one_layer_disk_design.disks import get_disks_radius
from one_layer_disk_design.disks_core_characteristics import (
    calculate_disk_core_characteristics,
    sanity_check_triso_fuel_volume,
)
from one_layer_disk_design.disks_geometry import define_disks_geometry

core_diameter = 80
moderator_cladding_thickness = 0.05
fuel_thickness = 0.12
fuel_cladding_thickness = (1 - fuel_thickness) / 2
moderator_thickness = 1
fuel_emitter_gap = 0.1
emitter_thickness = 0.5
thickness_photovoltaic = 0.02

hot_temp = 1250 + 273
cold_temp = 1150 + 273

photovoltaic_efficiency = 0.34

reflector_thickness = 40
neutron_shield_moderator_thickness = 70
neutron_shield_absorber_thickness = 15
gamma_shield_thickness = 10

u235_enrichment = 19.5
fuel_burnup = 75  # MWd/kgHM

# values are 'keff', 'render', 'depletion', 'keff_emitter_gamma_source' or 'none' (to just show the calculated core characteristics)
run_mode = "keff"
# values are 'generate', 'use' or 'no'
weight_windows = "no"
particle_type = "neutron"
# This will measure absoption only for this particular nuclide
monitored_nuclide = None  # MonitoredNuclide(nuclide="Si30")

batches = 2000  # 2500  # 1250

# Parameter used for keff_emitter_gamma_source simulations
emitter_gamma_energy_MeV = 0.01  # MeV
emitter_gamma_rate_per_cm3 = 3.35e6  # photons/cm3/s

sanity_check_triso_fuel_volume(fuel_thickness, fuel_cladding_thickness * 2)

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Boron Carbide",
    reflector="Graphite",
    fuel="Uranium Oxy-Carbide",
    moderator_cladding="Zirconium",
    emitter="Graphite",
    fuel_cladding="Graphite",
    void="Void",
    photovoltaic="Silicon",
    coolant="Light Water",
    neutron_shield_2="Boron Carbide",
    gamma_shield="Tungsten",
)

outer_core_layers_inside_shaft = AssemblySections(
    parts=[
        Assembly(material=material_choice.reflector, thickness=reflector_thickness),
        Assembly(material="Light Water", thickness=neutron_shield_moderator_thickness),
        Assembly(
            material=material_choice.neutron_shield,
            thickness=neutron_shield_absorber_thickness,
        ),
        Assembly(
            material=material_choice.gamma_shield,
            thickness=gamma_shield_thickness,
        ),
    ],
)

outer_core_layers_between_disks = AssemblySections(
    parts=[
        Assembly(material=material_choice.reflector, thickness=reflector_thickness),
        Assembly(
            material=material_choice.reflector,
            thickness=neutron_shield_moderator_thickness,
        ),
        Assembly(
            material=material_choice.neutron_shield_2,
            thickness=neutron_shield_absorber_thickness,
        ),
        Assembly(
            material=material_choice.gamma_shield,
            thickness=gamma_shield_thickness,
        ),
    ],
)

check_assembly_thickness_equal(
    outer_core_layers_inside_shaft,
    outer_core_layers_between_disks,
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
        ### Moderator
        Assembly(
            material=material_choice.moderator,
            thickness=moderator_thickness / 2,
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
            thickness=moderator_thickness / 2,
        ),
    ],
)

assembly_thickness = calculate_assembly_thickness(assembly_section_core)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=assembly_thickness + SPACING_CONSTANT * 2,
    outer_core_assembly=outer_core_layers_inside_shaft,
)
assembly_core_distance = (
    core_desc.core_radius + (core_desc.outer_core_radius - core_desc.core_radius) / 2
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
        ### Water
        Assembly(
            material=material_choice.coolant,
            thickness=(
                moderator_thickness
                - thickness_photovoltaic * 2
                + moderator_cladding_thickness * 2
            )
            / 2,
        ),
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Emitter Assembly
        emitter_assembly_placeholder,
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Water
        Assembly(
            material=material_choice.coolant,
            thickness=fuel_thickness
            - thickness_photovoltaic * 2
            + fuel_cladding_thickness * 2,
        ),
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Emitter Assembly
        emitter_assembly_placeholder,
        ### Photovoltaic
        Assembly(
            material=material_choice.photovoltaic,
            thickness=thickness_photovoltaic,
            is_photovoltaic=True,
        ),  # is_fuel is set to True to make the volume calculation work
        ### Water
        Assembly(
            material=material_choice.coolant,
            thickness=(
                moderator_thickness
                - thickness_photovoltaic * 2
                + moderator_cladding_thickness * 2
            )
            / 2,
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
    outer_core_layers_inside_shaft=outer_core_layers_inside_shaft,
    outer_core_layers_between_disks=outer_core_layers_between_disks,
)


materials_dict, materials_def, colors = make_materials(u235_enrichment, material_choice)

geometry, universe, tracked_cells, drums = define_disks_geometry(
    geometry_settings, materials_dict
)
# geometry = stochastic_volume_calculation(
#     [cell for _, cell in geometry.get_all_cells().items()],
#     geometry,
#     materials_dict,
# )

# (
#     heavy_metal_mass,
#     emissive_surface,
#     core_power,
#     core_power_electric,
#     radiative_flux,
#     fuel_lifetime,
# ) = calculate_disk_core_characteristics(
#     rotary_assembly_desc,
#     core_desc,
#     tracked_cells[material_choice.fuel],
#     drums,
#     material_choice,
#     materials_def,
#     hot_temp,
#     cold_temp,
#     photovoltaic_efficiency,
#     fuel_burnup,
# )


# print_core_characteristics(
#     heavy_metal_mass,
#     emissive_surface,
#     core_power,
#     core_power_electric,
#     geometry_settings.assembly_section_core,
#     radiative_flux,
#     tracked_cells[material_choice.fuel],
#     fuel_lifetime,
#     drums,
# )

print(
    "reactor diameter",
    drums[0].radius + core_desc.outer_core_radius - core_desc.core_radius,
)

print("core_height", core_desc.core_height)

if run_mode == "render":
    render_geometry(
        universe,
        universe_radius=(drums[0].radius) + 10,
        universe_height=drums[0].radius * 2
        + 10,  # core_desc.core_height * 1.5, # drums[0].radius * 2 + 10,
        pixels=(5000, 5000),
        basis="xz",
        origin=(
            rotary_assembly_desc.assembly_core_distance,
            0,
            (drums[0].radius * 2 + 10) / 2,
        ),
        geometry=geometry,
        colors=colors,
        materials_dict=materials_dict,
    )

outer_empty_zone_parameters = get_outer_empty_zone_parameters(geometry_settings)

settings = make_sim_settings(
    deterministic=True,
    batches=batches,
    weight_windows=weight_windows,
    window_radius=outer_empty_zone_parameters.radius,
    window_height=core_desc.core_height,
    window_origin=(outer_empty_zone_parameters.x0, 0, 0),
    geometry=geometry,
    particle_type=particle_type,
)


if run_mode == "keff":
    run_keff_sim(geometry, settings, materials_dict)
    # run_sim_with_tallies(
    #     geometry,
    #     settings,
    #     materials_dict,
    #     tracked_cells[material_choice.photovoltaic],
    #     materials_dict[material_choice.photovoltaic].density,
    #     tracked_cells[material_choice.emitter],
    #     calculate_source_strength(core_power),
    #     batches,
    #     particle_type=particle_type,
    #     monitored_nuclide=monitored_nuclide,
    # )


if run_mode == "keff_emitter_gamma_source":
    settings = make_sim_photon_from_cells(
        [tracked_cells[material_choice.emitter]],
        gamma_E_MeV=emitter_gamma_energy_MeV,
        deterministic=False,
        batches=batches,
    )
    run_sim_with_tallies(
        geometry,
        settings,
        materials_dict,
        tracked_cells[material_choice.photovoltaic],
        materials_dict[material_choice.photovoltaic].density,
        tracked_cells[material_choice.emitter],
        emitter_gamma_rate_per_cm3 * tracked_cells[material_choice.emitter].volume,
        batches,
        particle_type="photon",
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
