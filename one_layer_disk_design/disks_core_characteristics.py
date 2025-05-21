from typing import Dict, List

from common_lib.assemblies import CoreDesc
from common_lib.geometry import GeometrySettings
from common_lib.light import radiative_heat_flux_between_plates
from common_lib.materials import Material, MaterialChoice, heavy_metals_density
from common_lib.rotary_assembly import RotaryAssemblyDesc
from one_layer_disk_design.disks_assemblies import (
    calculate_disks_emitter_volume,
    calculate_disks_fuel_volume,
)
from one_layer_disk_design.disks import (
    DiskAssemblyLayer,
    calculate_disks_surface_in_core,
)


def calculate_disk_core_characteristics(
    rotary_assembly_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    geometry_settings: GeometrySettings,
    disks: List[DiskAssemblyLayer],
    half_assembly: bool,
    material_choice: MaterialChoice,
    materials_def: Dict[str, Material],
    hot_temp: float,
    cold_temp: float,
    photovoltaic_efficiency: float,
):
    photovolatic_volume = calculate_disks_fuel_volume(
        drum_desc=rotary_assembly_desc,
        core_desc=core_desc,
        assembly_section=geometry_settings.assembly_section_core,
        drums=disks,
        half_assembly=half_assembly,
    )

    fuel_volume = calculate_disks_fuel_volume(
        drum_desc=rotary_assembly_desc,
        core_desc=core_desc,
        assembly_section=geometry_settings.assembly_section_core,
        drums=disks,
        half_assembly=half_assembly,
    )

    emitter_volume = calculate_disks_emitter_volume(
        assembly_section=geometry_settings.assembly_section_core,
        drums=disks,
        drum_desc=rotary_assembly_desc,
        core_desc=core_desc,
        half_assembly=half_assembly,
    )

    # multiply by 2 because each drum section has two faces exposed to the fuel, and then by 2 again if there are two drum assemblies
    emissive_surface = (
        (
            calculate_disks_surface_in_core(disks, rotary_assembly_desc, core_desc)
            / 10000
        )
        * 2
        * 2
    )

    radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)

    core_power = radiative_flux * emissive_surface
    core_power_electric = core_power * photovoltaic_efficiency

    heavy_metal_mass = (
        fuel_volume * heavy_metals_density(materials_def[material_choice.fuel]) / 1000
    )

    return (
        heavy_metal_mass,
        emissive_surface,
        core_power,
        core_power_electric,
        fuel_volume,
        emitter_volume,
        photovolatic_volume,
        radiative_flux,
    )
