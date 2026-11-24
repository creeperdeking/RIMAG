"""Run a RIMAG simulation from an app_reactor_slice calculator export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app_slice_design.geometry import make_app_slice_geometry
from app_slice_design.materials_map import (
    collect_material_names,
    ensure_materials_available,
    material_choice_from_setup,
)
from app_slice_design.plot_defaults import write_plot_defaults
from app_slice_design.setup import load_app_slice_run_config
from common_lib.materials import apply_boron_ppm_to_fuel_graphite, make_materials
from common_lib.runlib import start_program
from one_layer_disk_design.disks_core_characteristics import (
    characteristics_from_thermodynamics,
    disk_inventory,
)


def period_share_of_stack(stack_m: float, period_cm: float) -> float:
    """Share of a uniform stack carried by one periodic slice.

    ``thermal_power_mw`` is the whole stack. The transport model is one period
    with periodic z boundaries, so source strength uses
    ``P_stack * period_height / stack_height``.
    """
    stack_cm = float(stack_m) * 100.0
    period = float(period_cm)
    if stack_cm <= 0.0 or period <= 0.0:
        return 1.0
    return min(1.0, period / stack_cm)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("Usage: python simulation_app_slice.py <app_slice_run.json>")

    config = load_app_slice_run_config(args[0])
    sim = config.simulation
    setup = config.setup

    print("--------------------------------")
    print("App-slice simulation parameters:")
    print(f"run_mode: {sim.run_mode}")
    print(f"n_batches: {sim.n_batches}")
    print(f"n_threads: {sim.n_threads}")
    print(f"nsm_material: {sim.nsm_material}")
    print(f"nsm_thickness: {sim.nsm_thickness}")
    print(f"conical_pitch: {sim.conical_pitch}")
    print(f"particle_type: {sim.particle_type}")
    print(f"weight_windows: {sim.weight_windows}")
    print(f"ww_mesh_cm: {sim.ww_mesh_cm}")
    print(f"ww_energy_groups: {sim.ww_energy_groups}")
    print(f"survival_biasing: {sim.survival_biasing}")
    print(f"dose_time: {sim.dose_time}")
    print(f"print_core_characteristics: {sim.print_core_characteristics}")
    print(f"boron_concentration_ppm: {sim.boron_concentration_ppm}")
    print(f"ddd_tallies_only: {sim.ddd_tallies_only}")
    print(
        "thermal_power_mw: "
        + (
            f"{sim.thermal_power_mw:g} (stack, shared onto this period)"
            if sim.thermal_power_mw is not None and sim.thermal_power_mw > 0
            else "unset (thermodynamics-tab period)"
        )
    )
    print(f"columns: {setup.columns}")
    print(f"enrichment_pct: {setup.enrichment_pct}")
    print(f"fuel_temp_c: {setup.fuel_temp_c}")
    print(f"tpv_density: {setup.tpv_density}")
    print(f"tpv_eff_pct: {setup.tpv_eff_pct}")
    print("--------------------------------")

    # Ensure OpenMC picks up the UI thread count (simlib reads simsettings.json).
    threads = max(1, min(256, int(sim.n_threads)))
    Path("simsettings.json").write_text(
        f"{json.dumps({'threads': threads}, indent=2)}\n",
        encoding="utf-8",
    )

    material_choice = material_choice_from_setup(setup, sim.nsm_material)
    # Equivalent enrichment is applied in the paper script; here use the slider enrichment.
    u235_enrichment = float(setup.enrichment_pct)

    materials_dict, colors, material_choice = make_materials(
        u235_enrichment,
        material_choice,
        borated_water_moderator_boron_ppm=0.0,
        moderator_density=1.0,
        gadolinium_oxide_in_fuel_proportion=0.0,
        extra_names=collect_material_names(setup, sim.nsm_material),
    )
    apply_boron_ppm_to_fuel_graphite(
        materials_dict,
        material_choice,
        sim.boron_concentration_ppm,
        colors,
    )
    ensure_materials_available(
        materials_dict,
        collect_material_names(setup, sim.nsm_material),
    )

    if sim.run_mode == "slab":
        from app_slice_design.slab_shield import run_slab_shield

        run_slab_shield(
            materials_dict,
            list(sim.slab_layers),
            particles=int(sim.slab_particles),
            batches=max(1, int(sim.n_batches)),
            threads=threads,
        )
        return

    geom = make_app_slice_geometry(config, materials_dict, material_choice)
    write_plot_defaults(geom.bounding_box, origin=geom.render_origin)

    print(
        f"Geometry: pitch={geom.pitch_cm:.3f} cm, "
        f"R_i={geom.layout.r_inner:.3f} m, R_o={geom.layout.r_outer:.3f} m, "
        f"fuel_thickness={geom.fuel_thickness_cm:.4f} cm, "
        f"tpv_thickness={geom.photovoltaic_thickness_cm:.4f} cm"
    )

    def calculate_core_characteristics():
        tab_thermal = setup.period_thermal_w
        tab_electric = setup.period_electric_w
        use_override = sim.thermal_power_mw is not None and sim.thermal_power_mw > 0
        if not use_override and (tab_thermal is None or tab_electric is None):
            raise SystemExit(
                "This run has no thermodynamics-tab power. Queue it from the app, "
                "or set thermal_power_mw."
            )
        if use_override:
            share = period_share_of_stack(setup.stack_m, geom.vertical_core_height_cm)
            thermal_w = float(sim.thermal_power_mw) * share * 1.0e6
            if tab_thermal is not None and tab_thermal > 0 and tab_electric is not None:
                electric_w = tab_electric * (thermal_w / tab_thermal)
            else:
                electric_w = thermal_w * (float(setup.tpv_eff_pct) / 100.0)
            tab_mw = f"{tab_thermal / 1e6:.4g} MW" if tab_thermal is not None else "absent"
            print(
                f"Thermal power: {sim.thermal_power_mw:g} MW over {setup.stack_m:g} m, "
                f"{thermal_w / 1e6:.4g} MW in the {geom.vertical_core_height_cm:.3f} cm period "
                f"({share:.4g} of the stack) used for source strength and DDD. "
                f"Thermodynamics-tab period is {tab_mw}."
            )
        else:
            thermal_w = float(tab_thermal)
            electric_w = float(tab_electric)
        shell_temp_c = setup.shell_temp_c
        if shell_temp_c is None:
            print("This run has no thermodynamics-tab shell temperature.")
            shell_temp_c = float("nan")
        inventory = disk_inventory(
            tracked_cells=geom.tracked_cells,
            material_choice=material_choice,
            materials_dict=materials_dict,
            photovoltaic_thickness=geom.photovoltaic_thickness_cm,
            fuel_thickness=geom.fuel_thickness_cm,
        )
        core = characteristics_from_thermodynamics(
            inventory,
            shell_temp_c=shell_temp_c,
            thermal_w=thermal_w,
            electric_w=electric_w,
            absorbed_w_per_cm2=setup.tpv_absorbed_w_per_cm2,
            photovoltaic_power_density=setup.tpv_density,
            fuel_burnup=u235_enrichment * 12.0,
            fuel_thickness=geom.fuel_thickness_cm,
            vertical_core_height=geom.vertical_core_height_cm,
            rotary_axle_radius=geom.rotary_axle_radius_cm,
        )
        shell_text = f"{shell_temp_c:.1f} °C" if shell_temp_c == shell_temp_c else "not recorded"
        print(
            f"Thermodynamics tab: shell {shell_text}, "
            f"{setup.tpv_absorbed_w_per_cm2:.4g} W/cm² absorbed, "
            f"{setup.tpv_density:.4g} W/cm² electric ({setup.tpv_eff_pct:.2f}%). "
            f"This period uses {core.core_power / 1e6:.4g} MW thermal / "
            f"{core.core_power_electric / 1e6:.4g} MW electric "
            f"for source strength and DDD."
        )
        return core

    start_program(
        run_mode=sim.run_mode,
        calculate_core_characteristics=calculate_core_characteristics,
        universe=geom.universe,
        geometry=geom.geometry,
        colors=colors,
        materials_dict=materials_dict,
        batches=int(sim.n_batches),
        weight_windows=sim.weight_windows,
        survival_biasing=sim.survival_biasing,
        ww_mesh_cm=sim.ww_mesh_cm,
        ww_energy_groups=sim.ww_energy_groups,
        ddd_tallies_only=sim.ddd_tallies_only,
        particle_type=sim.particle_type,
        tracked_cells=geom.tracked_cells,
        material_choice=material_choice,
        emitter_gamma_rate=3.35e6,
        monitored_nuclide=None,
        emitter_gamma_energy_MeV=0.01,
        print_characteristics=sim.print_core_characteristics,
        add_xe135=False,
        dose_time=365 * 24 * 60 * 60 * sim.dose_time,
        bounding_box=geom.bounding_box,
        render_view={
            "universe_radius": geom.render_radius,
            "universe_height": geom.render_height,
            "origin": geom.render_origin,
        },
    )


if __name__ == "__main__":
    main()
