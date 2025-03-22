from common_lib.core import compute_core_desc
from common_lib.geometry import GeometrySettings
from common_lib.geometry_utils import (
    Assembly,
    AssemblySections,
    calculate_assembly_thickness,
)
from common_lib.light import radiative_heat_flux_between_plates
from common_lib.materials import MaterialChoice, heavy_metals_density, make_materials
from common_lib.rotary_assembly import RotaryAssemblyDesc
from common_lib.simlib import (
    make_sim_settings,
    render_geometry,
    run_depletion_sim,
    run_sim_with_photovoltaic_tally,
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
half_assembly = False

hot_temp = 2000 + 273
cold_temp = 1800 + 273

reflector_thickness = 30
neutron_shield_thickness = 40

u235_enrichment = 9.5 / 100
fuel_hm_density = 0.25

render = False
keff_simulation = True
depletion_sim = False

batches = 1500

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_shield="Zirconium Hydride Boron",
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
        *emitter_assembly.parts,
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
    outer_core_assembly=outer_core_layers,
)

rotary_assembly_desc = RotaryAssemblyDesc(
    assembly_core_distance=core_desc.core_radius
    + (core_desc.outer_core_radius - core_desc.core_radius) / 2
    + 3,
    assembly_core_margin=1,
)

geometry_settings = GeometrySettings(
    assembly_section_inner=AssemblySections(
        parts=[
            *emitter_assembly.parts,
            *inner_assembly_unique_parts_complete.parts,
        ],
    ),
    assembly_section_outer_core=AssemblySections(
        parts=[
            *emitter_assembly.parts,
            ### Reflector
            Assembly(
                thickness=inner_assembly_unique_parts1_thickness,
            ),
            *emitter_assembly.parts,
            ### Reflector
            Assembly(
                thickness=inner_assembly_unique_parts2_thickness,
            ),
        ],
    ),
    assembly_section_last=AssemblySections(
        parts=[*emitter_assembly.parts],
    ),
    half_assembly=half_assembly,
    core_desc=core_desc,
    rotary_assembly_desc=rotary_assembly_desc,
    material_choice=material_choice,
    outer_core_layers=outer_core_layers,
)


materials_dict, materials_def, colors = make_materials(u235_enrichment, material_choice)

geometry, universe, drums, photovoltaic_cell, photovoltaic_slice_volume = (
    define_drum_geometry(geometry_settings, materials_dict)
)

fuel_volume = calculate_drums_fuel_volume(
    drum_desc=rotary_assembly_desc,
    core_desc=core_desc,
    assembly_section=geometry_settings.assembly_section_inner,
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
    calculate_assembly_thickness(geometry_settings.assembly_section_inner),
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
        basis="xz",
        origin=(0, 0, 0.0),
        geometry=geometry,
        colors=colors,
        materials_dict=materials_dict,
    )

settings = make_sim_settings(deterministic=True, batches=batches)

if keff_simulation:
    run_sim_with_photovoltaic_tally(
        geometry,
        settings,
        materials_dict,
        photovoltaic_cell,
        core_power,
        photovoltaic_slice_volume,
        batches,
    )
    # criticality_simulation(
    #     geometry,
    #     settings,
    #     materials_dict,
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
