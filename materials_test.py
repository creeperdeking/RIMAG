from typing import List, Optional, Dict
import openmc

from pydantic import BaseModel

from materials import (
    create_volumic_blend,
    Material,
    AtomProportion,
    Atom,
    heavy_metals_density,
)


def test_create_volumic_blend_with_one_material():
    mat1 = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
        ],
        density=1,
    )
    mat2 = Material(
        composition=[
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )

    res = create_volumic_blend(1, mat1, mat2)

    assert res == Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=1),
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0),
        ],
        density=1,
    )


def test_create_volumic_blend_equal():
    mat1 = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
        ],
        density=1,
    )
    mat2 = Material(
        composition=[
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )

    res = create_volumic_blend(0.5, mat1, mat2)

    assert res == Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )


def test_create_volumic_blend_different_densities():
    mat1 = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
        ],
        density=2,
    )
    mat2 = Material(
        composition=[
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )

    res = create_volumic_blend(0.5, mat1, mat2)

    assert res == Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1.5,
    )


def test_create_volumic_blend_bigger_proportion_of_material_1():
    mat1 = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
        ],
        density=1,
    )
    mat2 = Material(
        composition=[
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )

    res = create_volumic_blend(0.75, mat1, mat2)
    print(res)

    assert res == Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.75),
            AtomProportion(
                atom=Atom(name="Si", atomic_weight=10), proportion=0.24999999999999994
            ),
        ],
        density=1.0,
    )


def test_create_volumic_blend_bigger_proportion_of_material_2():
    mat1 = Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.5),
        ],
        density=1,
    )
    mat2 = Material(
        composition=[
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.5),
        ],
        density=1,
    )

    res = create_volumic_blend(0.25, mat1, mat2)
    print(res)

    assert res == Material(
        composition=[
            AtomProportion(atom=Atom(name="U235", atomic_weight=40), proportion=0.25),
            AtomProportion(atom=Atom(name="Si", atomic_weight=10), proportion=0.75),
        ],
        density=1.0,
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
