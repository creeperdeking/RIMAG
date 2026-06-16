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

# ========= PAPER RELEVANT PARAMETERS ===========

# ===============================================

run_mode: RunMode = ""
print_core_characteristics = True
batches = 200  # 2500  # 1250
weight_windows: UseWeightWindows = "no"
particle_type: ParticleType = "neutron"
# Tally absoption only for this particular nuclide:
monitored_nuclide = None  # MonitoredNuclide(nuclide="Si30")

# Parameter used for keff_emitter_gamma_source simulations
emitter_gamma_energy_MeV = 0.01  # MeV
emitter_gamma_rate_per_cm3 = 3.35e6  # photons/cm3/s

### Geometry parameters

reload_fraction = 1/4
enrichment_multiplicator = 1 / 2

fuel_thickness = 0.017 / enrichment_multiplicator
total_fuel_thickness = 1
thickness_photovoltaic = 2e-4 * 100 # cm
disk_geometry_params = make_disk_geometry_params(
    DiskGeometryParams(
        core_diameter=100,
        moderator_cladding_thickness=0.05, # not relevant since same material as moderator
        shield_moderator_cladding_thickness=0.05, # not relevant since same material as moderator
        fuel_thickness=fuel_thickness,
        fuel_cladding_thickness=(total_fuel_thickness - fuel_thickness) / 2,
        moderator_thickness=1,
        fuel_emitter_gap=0.1,
        emitter_thickness=1.0,
        thickness_photovoltaic=thickness_photovoltaic,
        rotary_axle_thickness=1,
        reflector_thickness=30,
        neutron_shield_moderator_thickness=2380,  # 175
        neutron_shield_moderator_cladding_thickness=0.1,
        neutron_shield_absorber_thickness=10,
        gamma_shield_thickness=10,
        frustum_pitch=2,
        number_of_reactor_columns=1,
    )
)

### Thermodynamic parameters

hot_temp = 1360 + 273  # K
min_cold_temp = 1100 + 273  # K
photovoltaic_efficiency = 0.33
photovoltaic_power_density = 0.89 # W/cm2

### Nuclear parameters

equivalent_enrichment = (reload_fraction**2)*(1/reload_fraction)*(1/reload_fraction+1)/2
u235_fresh_enrichment = 19.5 * enrichment_multiplicator
u235_enrichment = u235_fresh_enrichment * equivalent_enrichment
gadolinium_oxide_in_fuel_proportion = 0.0005 * 0
fuel_burnup = u235_fresh_enrichment * 12  # MWd/kgHM
borated_moderator_ppm = 3000 * 0
moderator_density = 1
add_xe135 = False

### Material definition

material_choice = MaterialChoice(
    moderator="Graphite",
    neutron_absorber="Boron Carbide",
    neutron_reflector="Graphite",
    bottom_reflector="Graphite",
    rotary_axle="Graphite",
    fuel="Uranium Dioxide",
    moderator_cladding="Graphite",
    coolant_cladding="Stainless Steel",
    emitter="Graphite",
    fuel_cladding="Graphite",
    void="Void",
    outer_empty_zone="Void",
    photovoltaic="InGaAs",
    coolant="Light Water",
    shaft_shield_moderator="Polyethylene",
    outer_cold_shield_moderator="Polyethylene",
    neutron_shield_moderator="Polyethylene",
    shield_moderator_cladding="Polyethylene",
    gamma_shield="", # not used
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
