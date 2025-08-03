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
print_core_characteristics = False
batches = 2000  # 2500  # 1250
weight_windows: UseWeightWindows = "generate"
particle_type: ParticleType = "neutron"
# Tally absoption only for this particular nuclide:
monitored_nuclide = None  # MonitoredNuclide(nuclide="Si30")

# Parameter used for keff_emitter_gamma_source simulations
emitter_gamma_energy_MeV = 0.01  # MeV
emitter_gamma_rate_per_cm3 = 3.35e6  # photons/cm3/s

### Geometry parameters

fuel_thickness = 0.12
thickness_photovoltaic = 0.02
disk_geometry_params = make_disk_geometry_params(
    DiskGeometryParams(
        core_diameter=115,
        moderator_cladding_thickness=0.05,
        fuel_thickness=fuel_thickness,
        fuel_cladding_thickness=(1 - fuel_thickness) / 2,
        moderator_thickness=1,
        fuel_emitter_gap=0.1,
        emitter_thickness=0.5,
        thickness_photovoltaic=thickness_photovoltaic,
        reflector_thickness=20,
        neutron_shield_moderator_thickness=70,
        neutron_shield_absorber_thickness=20,
        gamma_shield_thickness=10,
        frustum_pitch=45,
    )
)

### Thermodynamic parameters

hot_temp = 1250 + 273  # K
cold_temp = 1150 + 273  # K

photovoltaic_efficiency = 0.40
photovoltaic_power_density = 0.61  # W/cm2

### Nuclear parameters

u235_enrichment = 19.5
fuel_burnup = 75  # MWd/kgHM

### Material definition

material_choice = MaterialChoice(
    moderator="Light Water",
    neutron_absorber="Borated Water",
    neutron_reflector="Light Water",
    fuel="Uranium Oxy-Carbide",
    moderator_cladding="Zirconium",
    emitter="Graphite",
    fuel_cladding="Graphite",
    void="Void",
    photovoltaic="Silicon",
    coolant="Light Water",
    neutron_shield_moderator="Light Water",
    gamma_shield="Tungsten",
)

materials_dict, materials_def, colors = make_materials(u235_enrichment, material_choice)

make_simulation_geometry_result = make_simulation_geometry(
    material_choice=material_choice,
    disk_geometry_params=disk_geometry_params,
    materials_dict=materials_dict,
    materials_def=materials_def,
)


def calculate_core_characteristics():
    return calculate_disk_core_characteristics(
        tracked_cells=make_simulation_geometry_result.tracked_cells,
        material_choice=material_choice,
        materials_def=materials_def,
        hot_temp=hot_temp,
        cold_temp=cold_temp,
        photovoltaic_efficiency=photovoltaic_efficiency,
        photovoltaic_power_density=photovoltaic_power_density,
        photovoltaic_thickness=thickness_photovoltaic,
        fuel_burnup=fuel_burnup,
        fuel_thickness=fuel_thickness,
    )


start_program(
    run_mode=run_mode,
    calculate_core_characteristics=calculate_core_characteristics,
    universe=make_simulation_geometry_result.universe,
    geometry=make_simulation_geometry_result.geometry,
    colors=colors,
    materials_dict=materials_dict,
    geometry_settings=make_simulation_geometry_result.geometry_settings,
    assembly_thickness=make_simulation_geometry_result.geometry_settings.core_desc.core_height,
    batches=batches,
    weight_windows=weight_windows,
    particle_type=particle_type,
    tracked_cells=make_simulation_geometry_result.tracked_cells,
    material_choice=material_choice,
    emitter_gamma_rate=emitter_gamma_rate_per_cm3,
    monitored_nuclide=monitored_nuclide,
    emitter_gamma_energy_MeV=emitter_gamma_energy_MeV,
    print_characteristics=print_core_characteristics,
)
