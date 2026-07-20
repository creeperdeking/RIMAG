from common_lib.materials import (
    atoms,
    borated_water_atom_proportions_from_boron_ppm,
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
