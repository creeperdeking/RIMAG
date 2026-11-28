"""The inner hole shield can use a different material from the rotating disc."""

from app_slice_design.materials_map import inner_shield_material_name
from app_slice_design.setup import AppSliceSetup, LayerRow


def _setup(inner: str | None) -> AppSliceSetup:
    layers = {
        "disk": [LayerRow(name="Graphite", cm=1)],
        "fuel": [LayerRow(name="Uranium Dioxide", cm=1)],
        "reflector": [LayerRow(name="Graphite", cm=1)],
        "shield_moderator": [LayerRow(name="Graphite", cm=1)],
        "shield_absorber": [LayerRow(name="Boron Carbide", cm=1)],
        "tpv": [LayerRow(name="InGaAs", cm=1)],
    }
    if inner is not None:
        layers["inner_shield_moderator"] = [LayerRow(name=inner, cm=1)]
    return AppSliceSetup.model_validate(
        {
            "a": 2.0,
            "abs": 0.1,
            "refl": 0.3,
            "b_pct": 50,
            "w": 1.7,
            "ratio_pct": 40,
            "tpv_density": 1,
            "enrichment_pct": 9.7,
            "packing_pct": 20,
            "hm_particle_pct": 30,
            "cylinder_diameter_mm": 10,
            "wall_margin_mm": 0.5,
            "compact_spacing_mm": 1,
            "tpv_eff_pct": 30,
            "stack_m": 1,
            "columns": 1,
            "layers": layers,
        }
    )


def test_missing_inner_layer_keeps_the_disc_material():
    assert inner_shield_material_name(_setup(None), "Natural Graphite") == "Natural Graphite"


def test_placeholder_inner_layer_keeps_the_disc_material():
    assert (
        inner_shield_material_name(_setup("Inner neutron shield moderator"), "Beryllium Oxide")
        == "Beryllium Oxide"
    )


def test_named_inner_layer_is_independent():
    assert inner_shield_material_name(_setup("Beryllium Oxide"), "Graphite") == "Beryllium Oxide"


def _cells(universe):
    found = []
    for cell in universe.cells.values():
        found.append(cell)
        fill = cell.fill
        if fill is not None and hasattr(fill, "cells"):
            found.extend(_cells(fill))
    return found


def test_hole_fill_follows_the_inner_material_and_the_disc_does_not():
    import openmc

    from app_slice_design.geometry import make_app_slice_geometry
    from app_slice_design.materials_map import material_choice_from_setup
    from app_slice_design.setup import AppSliceRunConfig, AppSliceSimulationParams
    from common_lib.materials import make_materials

    setup = _setup("Beryllium Oxide")
    choice = material_choice_from_setup(setup, "Graphite")
    materials, _, choice = make_materials(
        9.7,
        choice,
        borated_water_moderator_boron_ppm=0.0,
        moderator_density=1.0,
        gadolinium_oxide_in_fuel_proportion=0.0,
    )
    config = AppSliceRunConfig(
        setup=setup,
        simulation=AppSliceSimulationParams(conical_pitch=0, n_batches=1, n_threads=1),
    )
    geom = make_app_slice_geometry(
        config,
        materials,
        choice,
        inner_shield_fill=choice.inner_neutron_shield_moderator,
    )
    cells = _cells(geom.universe)
    hole = next(cell for cell in cells if cell.name == "hole_shield_moderator")
    disc = [cell for cell in cells if cell.name.startswith("shield_moderator_")]
    assert disc, "rotating disc shield moderator cells missing"
    hole_name = hole.fill.name if isinstance(hole.fill, openmc.Material) else ""
    disc_names = {cell.fill.name for cell in disc if isinstance(cell.fill, openmc.Material)}
    assert hole_name == "Beryllium Oxide"
    assert all(name.startswith("Graphite") for name in disc_names)
    assert hole_name not in disc_names
