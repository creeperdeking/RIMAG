import math
from typing import Dict, List

import openmc
from pydantic import BaseModel

from common_lib.light import (
    calc_T2_radiative_heat_flux_between_plates,
)
from common_lib.materials import (
    MaterialChoice,
    heavy_metal_density,
)


def sanity_check_triso_fuel_volume(hm_volume: float, graphite_volume: float):
    actual_volume_ratio = hm_volume / (hm_volume + graphite_volume)
    TRISO_HM_VOLUME_FRACTION = 0.3
    MAX_TRISO_PACKING_FRACTION = 0.3
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


class CoreCharacteristics(BaseModel):
    heavy_metal_mass: float
    fuel_emissive_area: float
    fuel_thickness: float
    core_power: float
    core_power_electric: float
    cold_temp: float
    radiative_flux: float
    fuel_lifetime: float
    photovoltaic_power: float
    photovoltaic_area: float
    photovoltaic_power_density: float
    photovoltaic_power_per_m: float
    rotary_axle_radius: float
    vertical_core_height: float


def calculate_disk_core_characteristics(
    tracked_cells: Dict[str, List[openmc.Cell]],
    material_choice: MaterialChoice,
    materials_dict: Dict[str, openmc.Material],
    hot_temp: float,
    photovoltaic_efficiency: float,
    photovoltaic_power_density: float,
    photovoltaic_thickness: float,
    fuel_burnup: float,
    fuel_thickness: float,
    vertical_core_height: float,
    rotary_axle_radius: float,
    min_cold_temp: float,
) -> CoreCharacteristics:
    fuel_cells = tracked_cells[material_choice.fuel]
    photovoltaic_cells = tracked_cells[material_choice.photovoltaic]

    fuel_cell_volume = sum(cell.volume for cell in fuel_cells)
    photovoltaic_cell_volume = sum(cell.volume for cell in photovoltaic_cells)

    # multiply by 2 because each section has two faces exposed to the fuel
    fuel_emissive_area = (fuel_cell_volume / fuel_thickness) * 2

    photovoltaic_area = photovoltaic_cell_volume / photovoltaic_thickness

    ratio_photovoltaic_to_fuel = photovoltaic_area / fuel_emissive_area

    photovoltaic_power = photovoltaic_area * photovoltaic_power_density

    photovoltaic_power_density_total = (
        photovoltaic_power_density / photovoltaic_efficiency
    )
    photovoltaic_power_per_m2_fuel_area = (
        photovoltaic_power_density_total * 10000 * ratio_photovoltaic_to_fuel
    )

    cold_temp = calc_T2_radiative_heat_flux_between_plates(
        hot_temp,
        photovoltaic_power_per_m2_fuel_area,
        0.92,
        0.92,
    )
    assert cold_temp > 0 and cold_temp < hot_temp
    if cold_temp < min_cold_temp:
        print(
            f"❌ The cold temperature {cold_temp - 273}°C is below the minimum allowed {min_cold_temp - 273}°C"
        )

    core_power = photovoltaic_power_per_m2_fuel_area * fuel_emissive_area / 10000
    core_power_electric = core_power * photovoltaic_efficiency

    photovoltaic_power_per_m = photovoltaic_power * (100 / vertical_core_height)

    assert math.isclose(core_power_electric, photovoltaic_power)

    heavy_metal_mass = (
        fuel_cell_volume
        * heavy_metal_density(materials_dict[material_choice.fuel])
        / 1000
    )

    energy_in_fuel = heavy_metal_mass * fuel_burnup * 24  # MWh

    fuel_lifetime = energy_in_fuel / (core_power / 1e6 * 3600)

    return CoreCharacteristics(
        heavy_metal_mass=heavy_metal_mass,
        fuel_emissive_area=fuel_emissive_area,
        fuel_thickness=fuel_thickness,
        core_power=core_power,
        core_power_electric=core_power_electric,
        cold_temp=cold_temp,
        radiative_flux=photovoltaic_power_per_m2_fuel_area,
        fuel_lifetime=fuel_lifetime,
        photovoltaic_power=photovoltaic_power,
        photovoltaic_area=photovoltaic_area,
        photovoltaic_power_density=photovoltaic_power_density,
        photovoltaic_power_per_m=photovoltaic_power_per_m,
        rotary_axle_radius=rotary_axle_radius,
        vertical_core_height=vertical_core_height,
    )
