from typing import Dict

import openmc

from common_lib.light import radiative_heat_flux_between_plates
from common_lib.materials import Material, MaterialChoice, heavy_metals_density


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
    fuel_cell: openmc.Cell,
    material_choice: MaterialChoice,
    materials_def: Dict[str, Material],
    hot_temp: float,
    cold_temp: float,
    photovoltaic_efficiency: float,
    photovoltaic_power_density: float,
    photovoltaic_cell: openmc.Cell,
    photovoltaic_thickness: float,
    fuel_burnup: float,
    fuel_thickness: float,
):
    # multiply by 2 because each section has two faces exposed to the fuel
    fuel_emissive_area = (fuel_cell.volume / fuel_thickness) * 2

    photovoltaic_area = photovoltaic_cell.volume / photovoltaic_thickness

    photovoltaic_power = photovoltaic_area * photovoltaic_power_density

    radiative_flux = radiative_heat_flux_between_plates(hot_temp, cold_temp, 0.9, 0.9)

    core_power = radiative_flux * fuel_emissive_area / 10000
    core_power_electric = core_power * photovoltaic_efficiency

    if core_power_electric < photovoltaic_power:
        print(
            f"❌ The temperature differential between the emitter surface and the fuel is insufficient, thus the calculated core power of {core_power_electric} Watts is inferior to the calculated photovoltaic power of {photovoltaic_power} W"
        )

    heavy_metal_mass = (
        fuel_cell.volume
        * heavy_metals_density(materials_def[material_choice.fuel])
        / 1000
    )

    energy_in_fuel = heavy_metal_mass * fuel_burnup * 24  # MWd

    fuel_lifetime = energy_in_fuel / (core_power / 1e6 * 3600 * 24)

    return (
        heavy_metal_mass,
        fuel_emissive_area,
        core_power,
        core_power_electric,
        radiative_flux,
        fuel_lifetime,
        photovoltaic_power,
        photovoltaic_area,
    )
