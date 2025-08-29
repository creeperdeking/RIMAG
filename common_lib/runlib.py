import openmc
import openmc.deplete
from typing import Any, List, Dict, Literal
from common_lib.materials import MonitoredNuclide
from common_lib.geometry_utils import (
    get_geometry_bounding_box,
)
from common_lib.geometry_types import GeometrySettings
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
)

type RunMode = Literal[
    "keff",
    "keff_notallies",
    "render",
    "depletion",
    "keff_emitter_gamma_source",
    "norun",
]

type UseWeightWindows = Literal["use", "generate", "no"]
type ParticleType = Literal["photon", "neutron"]


def start_program(
    run_mode: RunMode,
    calculate_core_characteristics: Any,
    universe: openmc.Universe,
    geometry: openmc.Geometry,
    colors: Dict[Any, Any],
    materials_dict: Dict[str, openmc.Material],
    geometry_settings: GeometrySettings,
    batches: float,
    weight_windows: UseWeightWindows,
    particle_type: ParticleType,
    tracked_cells: Dict[str, List[openmc.Cell]],
    material_choice: Dict[str, openmc.Material],
    emitter_gamma_rate: float,  # particle per cm3
    monitored_nuclide: MonitoredNuclide,
    emitter_gamma_energy_MeV: float,
    add_xe135: bool,
    print_characteristics=True,
    deterministic=False,
):
    ### Calculate core characteristics

    core_characteristics = None
    if run_mode != "keff_notallies" and run_mode != "render" or print_characteristics:
        geometry = stochastic_volume_calculation(
            [cell for _, cell in geometry.get_all_cells().items()],
            geometry,
            materials_dict,
            geometry_settings,
        )

        core_characteristics = calculate_core_characteristics()

    if add_xe135 and core_characteristics is not None:
        add_xe135_to_geometry(
            geometry,
            materials_dict,
            material_choice,
            core_characteristics,
        )

    if print_characteristics:
        print_core_characteristics(core_characteristics)

    lower_left_corner, upper_right_corner = get_geometry_bounding_box(geometry_settings)

    if weight_windows == "generate":
        settings = make_sim_settings(
            deterministic=deterministic,
            batches=batches,
            weight_windows=weight_windows,
            lower_left_corner=lower_left_corner,
            upper_right_corner=upper_right_corner,
            geometry=geometry,
            particle_type=particle_type,
        )
        run_keff_sim(geometry, settings, materials_dict)
        weight_windows = "use"

    settings = make_sim_settings(
        deterministic=deterministic,
        batches=batches,
        weight_windows=weight_windows,
        lower_left_corner=lower_left_corner,
        upper_right_corner=upper_right_corner,
        geometry=geometry,
        particle_type=particle_type,
    )

    ### Run simulation

    moderator_cells = tracked_cells[material_choice.moderator]

    if run_mode == "keff":
        run_sim_with_tallies(
            geometry=geometry,
            settings=settings,
            materials_dict=materials_dict,
            photovoltaic_cells=tracked_cells[material_choice.photovoltaic],
            photovoltaic_density=materials_dict[material_choice.photovoltaic].density,
            emitter_cells=tracked_cells[material_choice.emitter],
            fuel_cells=tracked_cells[material_choice.fuel],
            moderator_cells=moderator_cells,
            shield_moderator_cells=tracked_cells[
                material_choice.neutron_shield_moderator
            ],
            electric_power=core_characteristics.core_power_electric,
            heat_deposition_cells=[
                *tracked_cells[material_choice.emitter],
                *tracked_cells[material_choice.fuel],
                *tracked_cells[material_choice.fuel_cladding],
            ],
            source_strength=calculate_source_strength(core_characteristics.core_power),
            batches=batches,
            particle_type=particle_type,
            monitored_nuclide=monitored_nuclide,
            coolant_cells=tracked_cells[material_choice.coolant],
        )

    if run_mode == "keff_notallies":
        run_keff_sim(geometry, settings, materials_dict)

    if run_mode == "keff_emitter_gamma_source":
        settings = make_sim_photon_from_cells(
            tracked_cells[material_choice.emitter],
            gamma_E_MeV=emitter_gamma_energy_MeV,
            deterministic=deterministic,
            batches=batches,
        )
        run_sim_with_tallies(
            geometry=geometry,
            settings=settings,
            materials_dict=materials_dict,
            photovoltaic_cells=tracked_cells[material_choice.photovoltaic],
            photovoltaic_density=materials_dict[material_choice.photovoltaic].density,
            emitter_cells=tracked_cells[material_choice.emitter],
            fuel_cells=tracked_cells[material_choice.fuel],
            moderator_cells=moderator_cells,
            shield_moderator_cells=tracked_cells[
                material_choice.neutron_shield_moderator
            ],
            coolant_cells=tracked_cells[material_choice.coolant],
            electric_power=core_characteristics.core_power_electric,
            heat_deposition_cells=[
                *tracked_cells[material_choice.emitter],
                *tracked_cells[material_choice.fuel],
                *tracked_cells[material_choice.fuel_cladding],
            ],
            source_strength=emitter_gamma_rate
            * sum(cell.volume for cell in tracked_cells[material_choice.emitter]),
            batches=batches,
            particle_type="photon",
            monitored_nuclide=monitored_nuclide,
        )

    if run_mode == "render":
        disk_radius = geometry_settings.rotary_assembly_desc.rotary_assembly_radius
        render_geometry(
            universe,
            universe_radius=disk_radius + 10,
            universe_height=geometry_settings.core_desc.core_height
            * 1.5,  # disk_radius * 2 + 10,
            pixels=(5000, 5000),
            basis="xy",
            origin=(
                geometry_settings.rotary_assembly_desc.assembly_core_distance,
                0,
                (disk_radius * 2 + 10) / 2,
            ),
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
