from common_lib.core import compute_core_desc
from common_lib.geometry import GeometrySettings
from common_lib.geometry_utils import (
    Assembly,
    AssemblySections,
    calculate_assembly_thickness,
    EmitterPlaceholder,
)
from common_lib.light import radiative_heat_flux_between_plates
from common_lib.materials import MaterialChoice, heavy_metals_density, make_materials
from common_lib.rotary_assembly import RotaryAssemblyDesc
from common_lib.simlib import (
    make_sim_settings,
    render_geometry,
    run_depletion_sim,
    run_keff_sim,
    # run_sim_with_photovoltaic_tally,
)
from drum_design.drum_assemblies import calculate_drums_fuel_volume
from drum_design.drum_geometry import define_drum_geometry
from drum_design.drums import calculate_drums_surface_in_core

core_diameter = 50
core_height = 50
moderator_cladding_thickness = 0.05
fuel_cladding_thickness = 0.05
fuel_thickness = 0.25
moderator_thickness = fuel_thickness / 0.3
fuel_drum_gap = 0.09
drum_thickness = 0.01
half_assembly = True

hot_temp = 2000 + 273
cold_temp = 1800 + 273

reflector_thickness = 30
neutron_shield_thickness = 40

u235_enrichment = 9.5 / 100
fuel_hm_density = 0.25

render = True
keff_simulation = False
depletion_sim = False

batches = 1500

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Boron Carbide",
    reflector="Graphite",
    fuel="TRISO",
    moderator_cladding="Aluminum",
    emitter="Graphite",
    fuel_cladding="Silicon Carbide",
    void="Void",
    photovoltaic="Silicon",
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
            thickness=fuel_drum_gap,
        ),
        ### Drum
        Assembly(
            material=material_choice.emitter,
            thickness=drum_thickness,
        ),
        ### Void
        Assembly(
            material="Void",
            thickness=fuel_drum_gap,
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
        ### Cladding
        Assembly(material="Aluminum", thickness=moderator_cladding_thickness),
        ### Water
        Assembly(material="Light Water", thickness=moderator_thickness - 0.02 * 2),
        ### Cladding
        Assembly(material="Aluminum", thickness=moderator_cladding_thickness),
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

# geometry, universe, drums, photovoltaic_cell, photovoltaic_slice_volume = (
#    define_drum_geometry(geometry_settings, materials_dict)
# )

geometry, universe, drums = define_drum_geometry(geometry_settings, materials_dict)

photovolatic_volume = calculate_drums_fuel_volume(
    drum_desc=rotary_assembly_desc,
    core_desc=core_desc,
    assembly_section=geometry_settings.assembly_section_core,
    drums=drums,
    half_assembly=half_assembly,
)

fuel_volume = calculate_drums_fuel_volume(
    drum_desc=rotary_assembly_desc,
    core_desc=core_desc,
    assembly_section=geometry_settings.assembly_section_core,
    drums=drums,
    half_assembly=half_assembly,
)

materials_dict[material_choice.fuel].volume = fuel_volume

# multiply by 2 because each drum section has two faces exposed to the fuel, and then by 2 again if there are two drum assemblies
emissive_surface = (
    (calculate_drums_surface_in_core(drums, rotary_assembly_desc, core_desc) / 10000)
    * (2 if half_assembly else 1)
    * 2
)

radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)

core_power = radiative_flux * emissive_surface

# print core characteristics

print()
print(
    "thicc: ",
    calculate_assembly_thickness(geometry_settings.assembly_section_core),
)
print(core_desc)
print("biggest drum radius", drums[0].radius)
print("half drum", half_assembly)
print("emissive_surface", round(emissive_surface, 2), "m2")
print(
    "Radiative flux",
    round(
        radiative_flux,
    ),
    "W/m2",
)
print("core power", round(core_power / 1e6, 2), "MW")
print()


print("fuel volume", fuel_volume, "cm3")
heavy_metal_mass = (
    fuel_volume * heavy_metals_density(materials_def[material_choice.fuel]) / 1000
)
print(
    "fuel mass",
    heavy_metal_mass,
    "kg",
)

if render:
    render_geometry(
        universe,
        universe_radius=(core_desc.outer_core_radius + 50),
        pixels=(2500, 2500),
        basis="xy",
        origin=(0, 0, 0.0),
        geometry=geometry,
        colors=colors,
        materials_dict=materials_dict,
    )

settings = make_sim_settings(deterministic=True, batches=batches)

if keff_simulation:
    run_keff_sim(geometry, settings, materials_dict)
    # run_sim_with_photovoltaic_tally(
    #     geometry,
    #     settings,
    #     materials_dict,
    #     photovoltaic_cell,
    #     core_power,
    #     photovoltaic_slice_volume,
    #     batches,
    # )

if depletion_sim:
    run_depletion_sim(
        thermal_power=core_power,
        geometry=geometry,
        settings=settings,
        materials=materials_dict.values(),
        materials_dict=materials_dict,
        material_choice=material_choice,
        fuel_mass=heavy_metal_mass,
        sim_steps=[1, 3, 6],  # [1, 3, 6, 10, 10, 10, 10, 10],
        steps_units="MWd/kg",
    )
