from common_lib.materials import MaterialChoice, make_materials
from common_lib.runlib import ParticleType, RunMode, UseWeightWindows, start_program

from one_layer_disk_design.disks_core_characteristics import (
    calculate_disk_core_characteristics,
)
from one_layer_disk_design.disks_geometry import (
    DiskGeometryParams,
    make_disk_geometry_params,
)
from one_layer_disk_design.frustum_geometry_definition import make_simulation_geometry

### Simulation parameters

run_mode: RunMode = "keff"
print_core_characteristics = True
batches = 1200  # 2500  # 1250
weight_windows: UseWeightWindows = "no"
particle_type: ParticleType = "neutron"
# Tally absoption only for this particular nuclide:
monitored_nuclide = None  # MonitoredNuclide(nuclide="Si30")

# Parameter used for keff_emitter_gamma_source simulations
emitter_gamma_energy_MeV = 0.01  # MeV
emitter_gamma_rate_per_cm3 = 3.35e6  # photons/cm3/s

### Geometry parameters

fuel_thickness = 0.12
total_fuel_thickness = 0.5
thickness_photovoltaic = 0.02
disk_geometry_params = make_disk_geometry_params(
    DiskGeometryParams(
        core_diameter=125,
        moderator_cladding_thickness=0.05,
        shield_moderator_cladding_thickness=0.05,
        fuel_thickness=fuel_thickness,
        fuel_cladding_thickness=(total_fuel_thickness - fuel_thickness) / 2,
        moderator_thickness=1 * 5 / 4,
        fuel_emitter_gap=0.1,
        emitter_thickness=0.5,
        thickness_photovoltaic=thickness_photovoltaic,
        rotary_axle_thickness=10,
        reflector_thickness=20,
        neutron_shield_moderator_thickness=50,  # 175
        neutron_shield_moderator_cladding_thickness=0.05,
        neutron_shield_absorber_thickness=10,
        gamma_shield_thickness=10,
        frustum_pitch=2,
    )
)

### Thermodynamic parameters

hot_temp = 1250 + 273  # K
min_cold_temp = 1100 + 273  # K
photovoltaic_efficiency = 0.33
photovoltaic_power_density = 0.89  # 0.61  # W/cm2

### Nuclear parameters

u235_enrichment = 9.5
gadolinium_oxide_in_fuel_proportion = 0.0005 * 0
fuel_burnup = 75  # MWd/kgHM
borated_moderator_ppm = 3000 * 0
moderator_density = 1.016
add_xe135 = False

### Material definition

# TODO: current bug with the implementation: in order to tally regions of the reactor properly,
# we need to have a unique material for each cell.
material_choice = MaterialChoice(
    moderator="Borated Water Moderator",
    neutron_absorber="Boron Carbide",
    neutron_reflector="Graphite",
    bottom_reflector="Graphite",
    rotary_axle="Graphite",
    fuel="Uranium Oxy-Carbide with Gadolinium Oxide",
    moderator_cladding="Zirconium",
    coolant_cladding="Stainless Steel",
    emitter="Graphite",
    fuel_cladding="Graphite",
    void="Void",
    photovoltaic="InGaAsP",
    coolant="Borated Water",
    neutron_shield_moderator="Titanium Hydride",
    shaft_shield_moderator="Borated Water",
    shield_moderator_cladding="TZM",
    gamma_shield="Tungsten",
)

materials_dict, colors, updated_material_choice = make_materials(
    u235_enrichment,
    material_choice,
    borated_moderator_ppm,
    moderator_density,
    gadolinium_oxide_in_fuel_proportion,
)
material_choice = updated_material_choice

make_simulation_geometry_result = make_simulation_geometry(
    material_choice=material_choice,
    disk_geometry_params=disk_geometry_params,
    materials_dict=materials_dict,
)


def calculate_core_characteristics():
    return calculate_disk_core_characteristics(
        tracked_cells=make_simulation_geometry_result.tracked_cells,
        material_choice=material_choice,
        materials_dict=materials_dict,
        hot_temp=hot_temp,
        photovoltaic_efficiency=photovoltaic_efficiency,
        photovoltaic_power_density=photovoltaic_power_density,
        photovoltaic_thickness=thickness_photovoltaic,
        fuel_burnup=fuel_burnup,
        fuel_thickness=fuel_thickness,
        vertical_core_height=make_simulation_geometry_result.geometry_settings.core_desc.core_vertical_height,
        rotary_axle_radius=make_simulation_geometry_result.geometry_settings.rotary_assembly_desc.rotary_assembly_radius,
        min_cold_temp=min_cold_temp,
    )


start_program(
    run_mode=run_mode,
    calculate_core_characteristics=calculate_core_characteristics,
    universe=make_simulation_geometry_result.universe,
    geometry=make_simulation_geometry_result.geometry,
    colors=colors,
    materials_dict=materials_dict,
    geometry_settings=make_simulation_geometry_result.geometry_settings,
    batches=batches,
    weight_windows=weight_windows,
    particle_type=particle_type,
    tracked_cells=make_simulation_geometry_result.tracked_cells,
    material_choice=material_choice,
    emitter_gamma_rate=emitter_gamma_rate_per_cm3,
    monitored_nuclide=monitored_nuclide,
    emitter_gamma_energy_MeV=emitter_gamma_energy_MeV,
    print_characteristics=print_core_characteristics,
    add_xe135=add_xe135,
)
