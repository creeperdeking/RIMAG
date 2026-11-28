from common_lib.materials import (
    ISOTROPIC_GRAPHITE_DENSITY,
    MaterialChoice,
    atoms,
    borated_water_atom_proportions_from_boron_ppm,
    graphite_boron_weight_fractions,
    graphite_like_names,
    graphite_material_base_name,
    is_graphite_like,
    natural_graphite_atom_proportions,
    shield_boron_fields,
    shield_graphite_fields,
)


def _boron_mass_fraction(props):
    total_mass = sum(ap.proportion * ap.atom.atomic_weight for ap in props)
    boron_mass = sum(
        ap.proportion * ap.atom.atomic_weight for ap in props if ap.atom.name == "B"
    )
    return boron_mass / total_mass


def test_borated_water_zero_ppm_is_water():
    props = borated_water_atom_proportions_from_boron_ppm(0.0)
    h = next(ap for ap in props if ap.atom.name == "H")
    o = next(ap for ap in props if ap.atom.name == "O")
    b = next(ap for ap in props if ap.atom.name == "B")
    assert h.proportion == 2.0
    assert o.proportion == 1.0
    assert b.proportion == 0.0
    assert _boron_mass_fraction(props) == 0.0


def test_borated_water_mass_fraction_matches_ppm():
    ppm = 2000.0
    props = borated_water_atom_proportions_from_boron_ppm(ppm)
    w_B = _boron_mass_fraction(props)
    assert abs(w_B - ppm / 1e6) < 1e-9


def test_borated_water_monotonic_with_ppm():
    props_low = borated_water_atom_proportions_from_boron_ppm(500.0)
    props_high = borated_water_atom_proportions_from_boron_ppm(2000.0)
    assert _boron_mass_fraction(props_low) < _boron_mass_fraction(props_high)


def test_graphite_boron_weight_fraction_matches_ppm():
    carbon, boron = graphite_boron_weight_fractions(0.0)
    assert carbon == 1.0
    assert boron == 0.0
    carbon, boron = graphite_boron_weight_fractions(250.0)
    assert abs(boron - 250.0 / 1e6) < 1e-15
    assert abs(carbon + boron - 1.0) < 1e-15


def test_graphite_boron_weight_fraction_rejects_pure_boron():
    try:
        graphite_boron_weight_fractions(1_000_000.0)
        assert False, "Expected ValueError at 1e6 ppm"
    except ValueError:
        pass
    try:
        graphite_boron_weight_fractions(-1.0)
        assert False, "Expected ValueError for negative ppm"
    except ValueError:
        pass


def test_graphite_material_base_name():
    assert graphite_material_base_name("Graphite") == "Graphite"
    assert graphite_material_base_name("Graphite 2") == "Graphite"
    assert graphite_material_base_name("Low Density Graphite") == "Low Density Graphite"


def test_natural_graphite_matches_commercial_isostatic_impurities():
    props = natural_graphite_atom_proportions()
    assert ISOTROPIC_GRAPHITE_DENSITY == 1.82
    total = sum(part.proportion * part.atom.atomic_weight for part in props)
    ppm = {
        part.atom.name: part.proportion * part.atom.atomic_weight / total * 1e6
        for part in props
    }
    # Lee, Ghosh, and Loyalka, IG-11, Table 1. Vanadium dominates the ash.
    assert ppm["V"] > ppm["Ca"] > ppm["Fe"]
    assert abs(ppm["V"] - 177.2) < 1e-6
    assert abs(ppm["B"] - 2.9) < 1e-9
    assert abs(ppm["C"] - (1e6 - 222.27)) < 1e-6
    assert "O" not in ppm
    assert set(ppm) == {"C", "V", "Ca", "Fe", "Ni", "B", "Mg", "Si", "Co", "Li"}


def _choice(**overrides: str) -> MaterialChoice:
    fields = {name: "Void" for name in MaterialChoice.model_fields}
    fields.update(overrides)
    return MaterialChoice(**fields)


def test_shield_graphite_fields_cover_moderator_and_a_graphite_absorber():
    choice = _choice(
        neutron_shield_moderator="Graphite",
        shaft_shield_moderator="Graphite 2",
        outer_cold_shield_moderator="Graphite 3",
        shield_moderator_cladding="Graphite 4",
        neutron_absorber="Graphite 5",
        neutron_reflector="Graphite 6",
        fuel_cladding="Graphite 7",
    )
    assert shield_graphite_fields(choice) == [
        "neutron_shield_moderator",
        "shaft_shield_moderator",
        "outer_cold_shield_moderator",
        "shield_moderator_cladding",
        "neutron_absorber",
    ]


def test_shield_graphite_fields_leave_a_carbide_wedge_alone():
    choice = _choice(
        neutron_shield_moderator="Graphite",
        neutron_absorber="Boron Carbide",
        neutron_reflector="Graphite",
    )
    assert shield_graphite_fields(choice) == ["neutron_shield_moderator"]


def _nuclides(mat) -> set[str]:
    return set(mat.get_nuclide_atom_densities())


def test_shield_boron_dopes_shield_graphite_and_leaves_the_carbide_wedge():
    from common_lib.materials import (
        apply_boron_ppm_to_fuel_graphite,
        apply_boron_ppm_to_shield_graphite,
        make_materials,
    )

    fields = {name: "Void" for name in MaterialChoice.model_fields}
    fields.update(
        {
            "moderator": "Graphite",
            "neutron_reflector": "Graphite",
            "bottom_reflector": "Graphite",
            "neutron_shield_moderator": "Graphite",
            "shaft_shield_moderator": "Graphite",
            "outer_cold_shield_moderator": "Graphite",
            "shield_moderator_cladding": "Graphite",
            "fuel_cladding": "Graphite",
            "emitter": "Graphite",
            "coolant_cladding": "Graphite",
            "neutron_absorber": "Boron Carbide",
        }
    )
    materials, colors, choice = make_materials(
        9.7, MaterialChoice(**fields), extra_names=["Graphite", "Boron Carbide"]
    )
    reflector_name = choice.neutron_reflector
    fuel_name = choice.fuel_cladding
    apply_boron_ppm_to_fuel_graphite(materials, choice, 200, colors)
    apply_boron_ppm_to_shield_graphite(materials, choice, 740, colors)

    assert choice.neutron_shield_moderator == "Shield graphite"
    assert choice.shaft_shield_moderator == "Shield graphite"
    assert choice.outer_cold_shield_moderator == "Shield graphite"
    assert choice.shield_moderator_cladding == "Shield graphite"
    assert choice.neutron_absorber == "Boron Carbide"
    assert choice.neutron_reflector == reflector_name
    assert choice.fuel_cladding == fuel_name
    shield = _nuclides(materials["Shield graphite"])
    assert any(nuc.startswith("B") for nuc in shield)
    assert not any(nuc.startswith("B") for nuc in _nuclides(materials[reflector_name]))
    assert any(nuc.startswith("B") for nuc in _nuclides(materials[fuel_name]))


def test_shield_boron_zero_ppm_leaves_the_choice_unchanged():
    from common_lib.materials import apply_boron_ppm_to_shield_graphite

    choice = _choice(neutron_shield_moderator="Graphite", neutron_absorber="Boron Carbide")
    apply_boron_ppm_to_shield_graphite({}, choice, 0)
    assert choice.neutron_shield_moderator == "Graphite"
    assert choice.neutron_absorber == "Boron Carbide"


def test_shield_graphite_fields_include_other_graphite_like_materials():
    choice = _choice(
        neutron_shield_moderator="Natural Graphite",
        shaft_shield_moderator="Low Density Graphite",
        outer_cold_shield_moderator="Graphite NO Scattering",
        neutron_absorber="Boron Carbide",
        neutron_reflector="Graphite",
    )
    assert shield_graphite_fields(choice) == [
        "neutron_shield_moderator",
        "shaft_shield_moderator",
        "outer_cold_shield_moderator",
    ]


def test_shield_boron_keeps_each_graphite_like_material():
    from common_lib.materials import apply_boron_ppm_to_shield_graphite, make_materials

    fields = {name: "Void" for name in MaterialChoice.model_fields}
    fields.update(
        {
            "neutron_shield_moderator": "Natural Graphite",
            "shaft_shield_moderator": "Natural Graphite",
            "neutron_absorber": "Low Density Graphite",
            "neutron_reflector": "Graphite",
            "fuel_cladding": "Graphite NO Scattering",
        }
    )
    materials, colors, choice = make_materials(
        9.7,
        MaterialChoice(**fields),
        extra_names=["Natural Graphite", "Low Density Graphite", "Graphite", "Graphite NO Scattering"],
    )
    reflector_name = choice.neutron_reflector
    apply_boron_ppm_to_shield_graphite(materials, choice, 1000, colors)

    assert choice.neutron_shield_moderator == "Shield Natural Graphite"
    assert choice.shaft_shield_moderator == "Shield Natural Graphite"
    assert choice.neutron_absorber == "Shield Low Density Graphite"
    assert choice.neutron_reflector == reflector_name
    natural = materials["Shield Natural Graphite"]
    low = materials["Shield Low Density Graphite"]
    assert abs(natural.get_mass_density() - 1.82) < 1e-9
    assert abs(low.get_mass_density() - 2.26 * 0.1) < 1e-9
    assert any(nuc.startswith("B") for nuc in _nuclides(natural))
    assert any(nuc.startswith("B") for nuc in _nuclides(low))
    assert not any(nuc.startswith("B") for nuc in _nuclides(materials[reflector_name]))

    plain = {name: "Void" for name in MaterialChoice.model_fields}
    plain["neutron_shield_moderator"] = "Graphite NO Scattering"
    no_scatter_materials, _, no_scatter_choice = make_materials(
        9.7,
        MaterialChoice(**plain),
        extra_names=["Graphite NO Scattering"],
    )
    apply_boron_ppm_to_shield_graphite(no_scatter_materials, no_scatter_choice, 500)
    doped = no_scatter_materials["Shield Graphite NO Scattering"]
    assert abs(doped.get_mass_density() - 2.26) < 1e-9
    assert not getattr(doped, "_sab", None)


def test_shield_graphite_fields_ignore_a_non_graphite_moderator():
    choice = _choice(
        neutron_shield_moderator="Beryllium Oxide",
        neutron_absorber="Boron Carbide",
    )
    assert shield_graphite_fields(choice) == []


def test_shield_boron_fields_include_any_shield_except_void_and_carbide():
    choice = _choice(
        neutron_shield_moderator="Beryllium Oxide",
        inner_neutron_shield_moderator="Lead",
        shaft_shield_moderator="Void",
        neutron_absorber="Boron Carbide",
        neutron_reflector="Graphite",
    )
    assert shield_boron_fields(choice) == [
        "neutron_shield_moderator",
        "inner_neutron_shield_moderator",
    ]


def _element_ppm(material, element: str) -> float:
    import openmc

    total = 0.0
    wanted = 0.0
    for nuclide, density in material.get_nuclide_atom_densities().items():
        mass = float(density) * openmc.data.atomic_mass(str(nuclide))
        total += mass
        symbol = "".join(ch for ch in str(nuclide) if ch.isalpha())
        if symbol == element:
            wanted += mass
    if total <= 0.0:
        return 0.0
    return 1.0e6 * wanted / total


def test_shield_boron_dopes_a_non_graphite_moderator():
    from common_lib.materials import apply_boron_ppm_to_shield_graphite, make_materials

    fields = {name: "Void" for name in MaterialChoice.model_fields}
    fields.update(
        {
            "neutron_shield_moderator": "Beryllium Oxide",
            "inner_neutron_shield_moderator": "Lead",
            "neutron_absorber": "Boron Carbide",
            "neutron_reflector": "Graphite",
        }
    )
    materials, colors, choice = make_materials(
        9.7,
        MaterialChoice(**fields),
        extra_names=["Beryllium Oxide", "Lead", "Boron Carbide", "Graphite"],
    )
    reflector_name = choice.neutron_reflector
    plain_beo = _element_ppm(materials["Beryllium Oxide"], "Be")
    plain_oxygen = _element_ppm(materials["Beryllium Oxide"], "O")
    apply_boron_ppm_to_shield_graphite(materials, choice, 1000, colors)

    assert choice.neutron_shield_moderator == "Shield Beryllium Oxide"
    assert choice.inner_neutron_shield_moderator == "Shield Lead"
    assert choice.neutron_absorber == "Boron Carbide"
    assert choice.neutron_reflector == reflector_name
    beo = materials["Shield Beryllium Oxide"]
    lead = materials["Shield Lead"]
    assert abs(beo.get_mass_density() - 2.92) < 1e-9
    assert abs(lead.get_mass_density() - 11.34) < 1e-9
    assert abs(_element_ppm(beo, "B") - 1000) < 1.0
    assert abs(_element_ppm(lead, "B") - 1000) < 1.0
    assert abs(_element_ppm(beo, "Be") / _element_ppm(beo, "O") - plain_beo / plain_oxygen) < 1e-6
    assert _element_ppm(materials[reflector_name], "B") == 0.0
    assert beo in colors
    assert lead in colors


def test_shield_boron_keeps_boron_already_in_the_host():
    from common_lib.materials import apply_boron_ppm_to_shield_graphite, make_materials

    fields = {name: "Void" for name in MaterialChoice.model_fields}
    fields.update(
        {
            "neutron_shield_moderator": "Tungsten Diboride",
            "inner_neutron_shield_moderator": "Borated Water",
        }
    )
    materials, colors, choice = make_materials(
        0.0,
        MaterialChoice(**fields),
        extra_names=["Tungsten Diboride", "Borated Water"],
    )
    host_boron = _element_ppm(materials["Tungsten Diboride"], "B")
    water_boron = _element_ppm(materials["Borated Water"], "B")
    apply_boron_ppm_to_shield_graphite(materials, choice, 1000, colors)

    diboride = materials["Shield Tungsten Diboride"]
    water = materials["Shield Borated Water"]
    assert abs(diboride.get_mass_density() - 15.2) < 1e-6
    assert abs(water.get_mass_density() - 1.016) < 1e-6
    # The requested ppm is added on top of the boron the host already has.
    assert abs(_element_ppm(diboride, "B") - (host_boron * 0.999 + 1000)) < 5.0
    assert abs(_element_ppm(water, "B") - (water_boron * 0.999 + 1000)) < 5.0
    assert _thermal_names(water) == ["c_H_in_H2O"]


def _thermal_names(material) -> list[str]:
    names = []
    for entry in getattr(material, "_sab", None) or []:
        names.append(entry[0] if isinstance(entry, tuple) else str(entry))
    return names


def test_borated_water_raises_when_ppm_exceeds_pure_boric_acid_limit():
    mass_B = atoms["B"].atomic_weight
    mass_H = atoms["H"].atomic_weight
    mass_O = atoms["O"].atomic_weight
    mass_H3BO3 = mass_B + 3 * mass_H + 3 * mass_O
    max_w_B = mass_B / mass_H3BO3
    too_high_ppm = max_w_B * 1e6 + 1.0
    try:
        borated_water_atom_proportions_from_boron_ppm(too_high_ppm)
        assert False, "Expected ValueError for excessive ppm"
    except ValueError:
        pass


def test_graphite_like_flag_covers_carbon_moderators_only():
    assert is_graphite_like("Graphite")
    assert is_graphite_like("Graphite 2")
    assert is_graphite_like("Natural Graphite")
    assert is_graphite_like("Low Density Graphite")
    assert is_graphite_like("Graphite NO Scattering")
    assert not is_graphite_like("Beryllium Oxide")
    assert not is_graphite_like("Boron Carbide")
    assert not is_graphite_like("Borated Graphite")
    assert graphite_like_names() == {
        "Graphite",
        "Natural Graphite",
        "Low Density Graphite",
        "Graphite NO Scattering",
    }


def test_materials_json_matches_the_graphite_like_flag():
    import json
    from pathlib import Path

    catalog = json.loads(
        Path("app_reactor_slice/src/data/materials.json").read_text(encoding="utf-8")
    )
    flagged = {name for name, spec in catalog["specs"].items() if spec.get("graphite_like")}
    flagged.update(name for name, spec in catalog["mixed"].items() if spec.get("graphite_like"))
    assert flagged == graphite_like_names()


def test_graphite_like_zones_share_one_fuel_to_absorber_distance():
    import math

    from app_slice_design.layout import center_cuts, compute_layout_for_ratio
    from app_slice_design.materials_map import shared_graphite_chord
    from app_slice_design.setup import LayerRow

    graphite = [LayerRow(name="Graphite", cm=1)]
    natural = [LayerRow(name="Natural Graphite", cm=1)]
    beryllia = [LayerRow(name="Beryllium Oxide", cm=1)]
    assert shared_graphite_chord(graphite, natural)
    assert not shared_graphite_chord(beryllia, beryllia)
    assert not shared_graphite_chord(graphite, beryllia)
    assert shared_graphite_chord(
        [LayerRow(name="Graphite", cm=1), LayerRow(name="Void", cm=0.1)],
        [LayerRow(name="Low Density Graphite", cm=1)],
    )

    # fissiovolt-reference chords: reflector 0.3 m, shield moderator 3.7 m.
    layout = compute_layout_for_ratio(3.7, 1.85, 1.5, 0.4, 0.3, 0.2)
    cuts = center_cuts(layout, shared_chord=True)
    y_fuel = layout.r_inner * math.cos(layout.fuel_angle / 2.0)
    assert layout.reflector_angle > 0
    assert abs((y_fuel - cuts.reflector_y) - 0.3) < 1e-9
    assert abs((cuts.reflector_y - cuts.moderator_y) - 3.7) < 1e-9
