from common_lib.materials import (
    Material,
    AtomProportion,
    Atom,
    heavy_metals_density,
)


def test_heavy_metals_density():
    mat = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=245), proportion=0.5),
        ],
        density=1,
    )

    assert heavy_metals_density(mat) == 1


def test_heavy_metals_density_with_multiple_atoms():
    mat = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=245), proportion=0.5),
            AtomProportion(atom=Atom(name="U238", atomic_weight=238), proportion=0.5),
        ],
        density=1,
    )

    assert heavy_metals_density(mat) == 1


def test_heavy_metals_density_with_multiple_atoms2():
    mat = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=245), proportion=0.5),
            AtomProportion(atom=Atom(name="Si", atomic_weight=28), proportion=1),
        ],
        density=1,
    )

    assert heavy_metals_density(mat) == 245 / (245 + 28 * 2)


def test_heavy_metals_density_with_multiple_atoms3():
    mat = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=245), proportion=2),
            AtomProportion(atom=Atom(name="U235", atomic_weight=238), proportion=1),
            AtomProportion(atom=Atom(name="Si", atomic_weight=28), proportion=3),
        ],
        density=3,
    )

    assert heavy_metals_density(mat) == (245 * 2 + 238) / (245 * 2 + 238 + 28 * 3) * 3
