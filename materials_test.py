from typing import List, Optional, Dict
import openmc

from pydantic import BaseModel

from materials import create_volumic_blend, Material, AtomProportion, Atom


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
