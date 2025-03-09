from geometry_utils import (
    AssemblySections,
    Assembly,
)
from materials import make_materials, MaterialChoice, filter_materials
from geometry import (
    define_geometry,
    calculate_assembly_thickness,
    GeometrySettings,
)
from drums import (
    calculate_drums_surface_in_core,
    radiative_heat_flux_between_plates,
    DrumDesc,
    compute_core_desc,
)
from simlib import (
    render_geometry,
    criticality_simulation,
    run_depletion_sim,
    make_sim_settings,
)
from assemblies import calculate_fuel_volume

core_diameter = 50
core_height = 120
moderator_cladding_thickness = 0.05
fuel_cladding_thickness = 0.05
fuel_thickness = 0.25
moderator_thickness = fuel_thickness / 0.3
fuel_drum_gap = 0.09
drum_thickness = 0.01
half_drum = False

hot_temp = 2000 + 273
cold_temp = 1800 + 273

reflector_thickness = 10
neutron_shield_thickness = 10

u235_enrichment = 9.5 / 100
fuel_hm_density = 0.25

render = False
keff_simulation = False
depletion_sim = True

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Boron Carbide",
    reflector="Beryllium Oxide",
    fuel="TRISO",
    moderator_cladding="Aluminum",
    drum="Molybdenum",
    fuel_cladding="Silicon Carbide",
    void="Void",
)

drum_assembly = AssemblySections(
    parts=[
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_drum_gap,
        ),
        ### Drum
        Assembly(
            material=material_choice.drum,
            thickness=drum_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_drum_gap,
        ),
    ],
)


inner_assembly_unique_parts1 = AssemblySections(
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
    ],
)

inner_assembly_unique_parts2 = AssemblySections(
    parts=[
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
)

inner_assembly_unique_parts_complete = AssemblySections(
    parts=[
        *inner_assembly_unique_parts1.parts,
        *drum_assembly.parts,
        *inner_assembly_unique_parts2.parts,
    ],
)

inner_assembly_unique_parts1_thickness = calculate_assembly_thickness(
    inner_assembly_unique_parts1
)

inner_assembly_unique_parts2_thickness = calculate_assembly_thickness(
    inner_assembly_unique_parts2
)

core_desc = compute_core_desc(
    core_radius=core_diameter / 2,
    core_height=core_height,
    reflector_thickness=reflector_thickness,
    neutron_shield_thickness=neutron_shield_thickness,
)

drum_desc = DrumDesc(
    drum_core_distance=core_desc.core_radius
    + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    + 3,
    drum_core_margin_inner=2,
    drum_core_margin_outer=0.5,
)

geometry_settings = GeometrySettings(
    assembly_section_inner=AssemblySections(
        parts=[
            *drum_assembly.parts,
            *inner_assembly_unique_parts_complete.parts,
        ],
    ),
    assembly_section_reflector=AssemblySections(
        parts=[
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.reflector,
                thickness=inner_assembly_unique_parts1_thickness,
            ),
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.reflector,
                thickness=inner_assembly_unique_parts2_thickness,
            ),
        ],
    ),
    assembly_section_absorber=AssemblySections(
        parts=[
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.neutron_shield,
                thickness=inner_assembly_unique_parts1_thickness,
            ),
            *drum_assembly.parts,
            ### Reflector
            Assembly(
                material=material_choice.neutron_shield,
                thickness=inner_assembly_unique_parts2_thickness,
            ),
        ],
    ),
    assembly_section_last=AssemblySections(
        parts=[*drum_assembly.parts],
    ),
    half_drum=half_drum,
    core_desc=core_desc,
    drum_desc=drum_desc,
    material_choice=material_choice,
)


materials_dict, colors = make_materials(u235_enrichment, material_choice)

geometry, universe, drums = define_geometry(geometry_settings, materials_dict)

fuel_volume = calculate_fuel_volume(
    drum_desc=drum_desc,
    core_desc=core_desc,
    assembly_section=geometry_settings.assembly_section_inner,
    drums=drums,
    half_drum=half_drum,
)

materials_dict[material_choice.fuel].volume = fuel_volume

# multiply by 2 because each drum section has two faces exposed to the fuel, and then by 2 again if there are two drum assemblies
emissive_surface = (
    (calculate_drums_surface_in_core(drums, drum_desc, core_desc) / 10000)
    * (2 if half_drum else 1)
    * 2
)

radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)

core_power = radiative_flux * emissive_surface

# print core characteristics

print()
print(
    "thicc: ",
    calculate_assembly_thickness(geometry_settings.assembly_section_inner),
)
print(core_desc)
print("biggest drum radius", drums[0].radius)
print("half drum", half_drum)
print("emissive_surface", emissive_surface)
print("Radiative flux", radiative_flux)
print("core power", core_power)
print()


print("fuel volume", fuel_volume, "cm3")
fuel_mass = fuel_volume * 0.25 * 11 / 1000
print(
    "fuel mass",
    fuel_mass,
    "kg",
)

if render:
    render_geometry(
        universe,
        universe_radius=(core_desc.outer_core_radius),
        pixels=(2500, 2500),
        basis="xy",
        origin=(0, 0, 0.0),
        geometry=geometry,
    )

settings = make_sim_settings(deterministic=True)

if keff_simulation:
    criticality_simulation(
        geometry,
        settings,
        materials_dict,
    )

if depletion_sim:
    print(materials_dict)
    run_depletion_sim(
        thermal_power=core_power,
        geometry=geometry,
        settings=settings,
        materials=materials_dict.values(),
        materials_dict=materials_dict,
        material_choice=material_choice,
        fuel_mass=fuel_mass,
        sim_timesteps=[5, 10, 20, 25] + [25 for i in range(15 * 3)],
        timesteps_units="",
    )
