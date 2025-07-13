from typing import Dict, List

import openmc
from common_lib.assemblies_types import CoreDesc
from common_lib.light import radiative_heat_flux_between_plates
from common_lib.materials import Material, MaterialChoice, heavy_metals_density
from common_lib.rotary_assembly import RotaryAssemblyDesc
from one_layer_disk_design.disks import (
    DiskAssemblyLayer,
    calculate_disks_surface_in_core,
)


def sanity_check_triso_fuel_volume(hm_volume: float, graphite_volume: float):
    actual_volume_ratio = hm_volume / (hm_volume + graphite_volume)
    TRISO_HM_VOLUME_FRACTION = 0.5
    MAX_TRISO_PACKING_FRACTION = 0.5
    PACKED_TRISO_VOLUME_RATIO = (
        TRISO_HM_VOLUME_FRACTION * MAX_TRISO_PACKING_FRACTION
    )  # cm3 / cm3
    if actual_volume_ratio > PACKED_TRISO_VOLUME_RATIO:
        raise ValueError(
            f"❌ Actual volume ratio {actual_volume_ratio} is greater than the maximum allowed {PACKED_TRISO_VOLUME_RATIO}"
        )
    else:
        print(
            f"✅ Actual volume ratio {actual_volume_ratio} is less than the maximum allowed {PACKED_TRISO_VOLUME_RATIO}"
        )


def calculate_disk_core_characteristics(
    rotary_assembly_desc: RotaryAssemblyDesc,
    core_desc: CoreDesc,
    fuel_cell: openmc.Cell,
    disks: List[DiskAssemblyLayer],
    material_choice: MaterialChoice,
    materials_def: Dict[str, Material],
    hot_temp: float,
    cold_temp: float,
    photovoltaic_efficiency: float,
    fuel_burnup: float,
):
    # multiply by 2 because each drum section has two faces exposed to the fuel
    emissive_surface = (
        calculate_disks_surface_in_core(disks, rotary_assembly_desc, core_desc) / 10000
    ) * 2

    radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)

    core_power = radiative_flux * emissive_surface
    core_power_electric = core_power * photovoltaic_efficiency

    heavy_metal_mass = (
        fuel_cell.volume
        * heavy_metals_density(materials_def[material_choice.fuel])
        / 1000
    )

    energy_in_fuel = heavy_metal_mass * fuel_burnup * 24  # MWd

    fuel_lifetime = energy_in_fuel / (core_power / 1e6 * 3600 * 24)

    return (
        heavy_metal_mass,
        emissive_surface,
        core_power,
        core_power_electric,
        radiative_flux,
        fuel_lifetime,
    )
