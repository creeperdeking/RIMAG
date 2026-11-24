import math
from typing import Dict, List

import openmc
from pydantic import BaseModel

from common_lib.materials import (
    MaterialChoice,
    heavy_metal_density,
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


class DiskInventory(BaseModel):
    fuel_cell_volume: float
    photovoltaic_cell_volume: float
    fuel_emissive_area: float
    photovoltaic_area: float
    heavy_metal_mass: float


def disk_inventory(
    tracked_cells: Dict[str, List[openmc.Cell]],
    material_choice: MaterialChoice,
    materials_dict: Dict[str, openmc.Material],
    photovoltaic_thickness: float,
    fuel_thickness: float,
) -> DiskInventory:
    fuel_cells = tracked_cells[material_choice.fuel]
    photovoltaic_cells = tracked_cells[material_choice.photovoltaic]
    fuel_cell_volume = sum(cell.volume for cell in fuel_cells)
    photovoltaic_cell_volume = sum(cell.volume for cell in photovoltaic_cells)
    # Two faces of each fuel section.
    fuel_emissive_area = (fuel_cell_volume / fuel_thickness) * 2
    photovoltaic_area = photovoltaic_cell_volume / photovoltaic_thickness
    heavy_metal_mass = (
        fuel_cell_volume
        * heavy_metal_density(materials_dict[material_choice.fuel])
        / 1000
    )
    return DiskInventory(
        fuel_cell_volume=fuel_cell_volume,
        photovoltaic_cell_volume=photovoltaic_cell_volume,
        fuel_emissive_area=fuel_emissive_area,
        photovoltaic_area=photovoltaic_area,
        heavy_metal_mass=heavy_metal_mass,
    )


def characteristics_from_thermodynamics(
    inventory: DiskInventory,
    *,
    shell_temp_c: float,
    thermal_w: float,
    electric_w: float,
    absorbed_w_per_cm2: float,
    photovoltaic_power_density: float,
    fuel_burnup: float,
    fuel_thickness: float,
    vertical_core_height: float,
    rotary_axle_radius: float,
) -> CoreCharacteristics:
    """Power and shell temperature are the thermodynamics-tab results for this period.

    ``thermal_w`` and ``electric_w`` are the modeled slice, already taken from
    the tab. Nothing here solves a temperature or a heat flux.
    """
    energy_in_fuel = inventory.heavy_metal_mass * fuel_burnup * 24  # MWh
    if thermal_w > 0:
        fuel_lifetime = energy_in_fuel / (thermal_w / 1e6 * 3600)
    else:
        fuel_lifetime = math.inf
    per_m = (
        electric_w * (100.0 / vertical_core_height) if vertical_core_height > 0 else 0.0
    )
    return CoreCharacteristics(
        heavy_metal_mass=inventory.heavy_metal_mass,
        fuel_emissive_area=inventory.fuel_emissive_area,
        fuel_thickness=fuel_thickness,
        core_power=thermal_w,
        core_power_electric=electric_w,
        cold_temp=shell_temp_c + 273.15,
        radiative_flux=absorbed_w_per_cm2 * 1.0e4,
        fuel_lifetime=fuel_lifetime,
        photovoltaic_power=electric_w,
        photovoltaic_area=inventory.photovoltaic_area,
        photovoltaic_power_density=photovoltaic_power_density,
        photovoltaic_power_per_m=per_m,
        rotary_axle_radius=rotary_axle_radius,
        vertical_core_height=vertical_core_height,
    )
