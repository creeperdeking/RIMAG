from __future__ import annotations

import openmc
import openmc.deplete
from typing import Any, List, Dict, Literal, Optional
from common_lib.materials import MonitoredNuclide
from common_lib.simlib import (
    add_xe135_to_geometry,
    calculate_source_strength,
    make_sim_photon_from_cells,
    make_sim_settings,
    print_core_characteristics,
    print_depletion_result,
    render_geometry,
    run_depletion_sim,
    run_keff_sim,
    run_sim_with_tallies,
    stochastic_volume_calculation,
    write_ww_meta,
)

type RunMode = Literal[
    "keff",
    "keff_notallies",
    "render",
    "depletion",
    "keff_emitter_gamma_source",
    "keff_gamma_dose",
    "norun",
]

type UseWeightWindows = Literal["use", "generate", "no", "seed", "refine"]
type ParticleType = Literal["photon", "neutron"]


def start_program(
    run_mode: RunMode,
    calculate_core_characteristics: Any,
    universe: openmc.Universe,
    geometry: openmc.Geometry,
    colors: Dict[Any, Any],
    materials_dict: Dict[str, openmc.Material],
    batches: float,
    weight_windows: UseWeightWindows,
    particle_type: ParticleType,
    tracked_cells: Dict[str, List[openmc.Cell]],
    material_choice: Dict[str, openmc.Material],
    emitter_gamma_rate: float,  # particle per cm3
    monitored_nuclide: MonitoredNuclide,
    emitter_gamma_energy_MeV: float,
    add_xe135: bool,
    dose_time: float,
    print_characteristics=True,
    deterministic=False,
    bounding_box=None,
    render_view: Optional[Dict[str, Any]] = None,
    survival_biasing: bool = True,
    ww_mesh_cm: float = 10.0,
    ww_energy_groups: int = 10,
    ddd_tallies_only: bool = False,
):
    ### Calculate core characteristics

    def cells_for(role: str) -> List[openmc.Cell]:
        return list(tracked_cells.get(role, []))

    core_characteristics = None
    if run_mode != "keff_notallies" and run_mode != "render" or print_characteristics:
        # Only material cells need volumes (mass / power). Universe-filled parents
        # (boundary_layer, column, …) are large/thin wedges of the sample box.
        material_cells = [
            cell
            for _, cell in geometry.get_all_cells().items()
            if isinstance(cell.fill, openmc.Material)
        ]
        geometry = stochastic_volume_calculation(
            material_cells,
            geometry,
            materials_dict,
            bounding_box=bounding_box,
        )

        core_characteristics = calculate_core_characteristics()

        print("Tracked cells mass:")
        for name, cells in tracked_cells.items():
            if name not in materials_dict or not cells:
                continue
            slice_volume = sum((cell.volume or 0.0) for cell in cells)
            density = materials_dict[name].density
            volume = slice_volume  # cm3 / slice
            mass = density * volume  # g / slice
            power = getattr(core_characteristics, "core_power_electric", 0.0) or 0.0
            mass_per_kW = mass / power if power else float("inf")

            print(
                f"'{name} ({', '.join([cell.name for cell in cells])})': mass per kW = {mass_per_kW:.2f} kg/kW"
            )

    if add_xe135 and core_characteristics is not None:
        add_xe135_to_geometry(
            geometry,
            materials_dict,
            material_choice,
            core_characteristics,
        )

    if print_characteristics:
        print_core_characteristics(core_characteristics)

    if bounding_box is None:
        raise ValueError("bounding_box is required")
    lower_left_corner, upper_right_corner = bounding_box

    if weight_windows in ("generate", "seed", "refine"):
        settings = make_sim_settings(
            deterministic=deterministic,
            batches=batches,
            weight_windows=weight_windows,
            lower_left_corner=lower_left_corner,
            upper_right_corner=upper_right_corner,
            geometry=geometry,
            particle_type=particle_type,
            survival_biasing=survival_biasing,
            ww_mesh_cm=ww_mesh_cm,
            ww_energy_groups=ww_energy_groups,
        )
        run_keff_sim(geometry, settings, materials_dict)
        write_ww_meta(
            pass_kind="seed" if weight_windows in ("generate", "seed") else "refine",
            mesh_cm=ww_mesh_cm,
            energy_groups=ww_energy_groups,
            batches=int(settings.batches),
        )
        # seed / refine stop here so the UI can iterate deep shields.
        # generate keeps the old one-shot behaviour: seed then tally with WW.
        if weight_windows in ("seed", "refine"):
            print(
                "Weight-window pass finished. "
                "Run refine again to push deeper, or set weight_windows=use for tallies."
            )
            return
        weight_windows = "use"

    settings = make_sim_settings(
        deterministic=deterministic,
        batches=batches,
        weight_windows=weight_windows,
        lower_left_corner=lower_left_corner,
        upper_right_corner=upper_right_corner,
        geometry=geometry,
        particle_type="neutron" if run_mode == "keff_gamma_dose" else particle_type,
        survival_biasing=survival_biasing,
        ww_mesh_cm=ww_mesh_cm,
        ww_energy_groups=ww_energy_groups,
        transport_photons=run_mode == "keff_gamma_dose",
    )

    ### Run simulation

    moderator_cells = cells_for(material_choice.moderator)

    if run_mode == "keff":
        run_sim_with_tallies(
            geometry=geometry,
            settings=settings,
            materials_dict=materials_dict,
            photovoltaic_cells=cells_for(material_choice.photovoltaic),
            photovoltaic_density=materials_dict[material_choice.photovoltaic].density,
            emitter_cells=cells_for(material_choice.emitter),
            fuel_cells=cells_for(material_choice.fuel),
            moderator_cells=moderator_cells,
            shield_moderator_cells=cells_for(material_choice.neutron_shield_moderator),
            electric_power=core_characteristics.core_power_electric,
            heat_deposition_cells=[
                *cells_for(material_choice.emitter),
                *cells_for(material_choice.fuel),
                *cells_for(material_choice.fuel_cladding),
            ],
            source_strength=calculate_source_strength(core_characteristics.core_power),
            batches=batches,
            particle_type=particle_type,
            monitored_nuclide=monitored_nuclide,
            coolant_cells=cells_for(material_choice.coolant),
            dose_time=dose_time,
            ddd_tallies_only=ddd_tallies_only,
        )

    if run_mode == "keff_gamma_dose":
        if core_characteristics is None:
            raise SystemExit("InGaAs gamma dose needs the slice thermal power.")
        run_sim_with_tallies(
            geometry=geometry,
            settings=settings,
            materials_dict=materials_dict,
            photovoltaic_cells=cells_for(material_choice.photovoltaic),
            photovoltaic_density=materials_dict[material_choice.photovoltaic].density,
            emitter_cells=cells_for(material_choice.emitter),
            fuel_cells=cells_for(material_choice.fuel),
            moderator_cells=moderator_cells,
            shield_moderator_cells=cells_for(material_choice.neutron_shield_moderator),
            electric_power=core_characteristics.core_power_electric,
            heat_deposition_cells=[
                *cells_for(material_choice.emitter),
                *cells_for(material_choice.fuel),
                *cells_for(material_choice.fuel_cladding),
            ],
            source_strength=calculate_source_strength(core_characteristics.core_power),
            batches=batches,
            particle_type="neutron",
            monitored_nuclide=monitored_nuclide,
            coolant_cells=cells_for(material_choice.coolant),
            dose_time=dose_time,
            gamma_dose_only=True,
        )

    if run_mode == "keff_notallies":
        run_keff_sim(geometry, settings, materials_dict)

    if run_mode == "keff_emitter_gamma_source":
        emitter_cells = cells_for(material_choice.emitter)
        settings = make_sim_photon_from_cells(
            emitter_cells,
            gamma_E_MeV=emitter_gamma_energy_MeV,
            deterministic=deterministic,
            batches=batches,
        )
        run_sim_with_tallies(
            geometry=geometry,
            settings=settings,
            materials_dict=materials_dict,
            photovoltaic_cells=cells_for(material_choice.photovoltaic),
            photovoltaic_density=materials_dict[material_choice.photovoltaic].density,
            emitter_cells=emitter_cells,
            fuel_cells=cells_for(material_choice.fuel),
            moderator_cells=moderator_cells,
            shield_moderator_cells=cells_for(material_choice.neutron_shield_moderator),
            coolant_cells=cells_for(material_choice.coolant),
            electric_power=core_characteristics.core_power_electric,
            heat_deposition_cells=[
                *emitter_cells,
                *cells_for(material_choice.fuel),
                *cells_for(material_choice.fuel_cladding),
            ],
            source_strength=emitter_gamma_rate
            * sum((cell.volume or 0.0) for cell in emitter_cells),
            batches=batches,
            particle_type="photon",
            monitored_nuclide=monitored_nuclide,
            dose_time=dose_time,
            ddd_tallies_only=ddd_tallies_only,
        )

    if run_mode == "render":
        if render_view is None:
            raise ValueError("render_view is required for render")
        disk_radius = float(render_view["universe_radius"])
        universe_height = float(render_view.get("universe_height", disk_radius * 1.5))
        origin = tuple(render_view.get("origin", (0.0, 0.0, 0.0)))
        render_geometry(
            universe,
            universe_radius=disk_radius,
            universe_height=universe_height,
            pixels=(5000, 5000),
            basis="xy",
            origin=origin,
            geometry=geometry,
            colors=colors,
            materials_dict=materials_dict,
        )

    if run_mode == "depletion":
        run_depletion_sim(
            thermal_power=core_characteristics.core_power,
            geometry=geometry,
            settings=settings,
            materials=materials_dict.values(),
            sim_steps=[
                0.01,
                0.1,
                0.89,
                1,
                5,
                23,
                60,
                30 * 3,
                30 * 6,
                30 * 6,
                30 * 6,
                30 * 6,
                30 * 6,
                30 * 6,
            ],  # [1, 3, 6, 10, 10, 10, 10, 10],
            steps_units="d",
        )
        print_depletion_result(
            materials_dict,
            material_choice,
            core_characteristics.core_power,
            core_characteristics.heavy_metal_mass,
        )
