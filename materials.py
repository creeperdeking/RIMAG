from typing import List, Optional, Dict


class Atom:
    atomic_weight: float


class AtomProportion:
    atom: Atom
    proportion: Optional[float] = 1

    def __init__(self, atom: Atom, proportion: Optional[float] = 1):
        self.atom = atom
        self.proportion = proportion


class Material:
    composition: List[AtomProportion]
    density: float  # g/cm3
    specific_heat: Optional[float] = None  # J/g/K
    thermal_conductivity: Optional[float] = None  # W/cm/K
    melting_point: Optional[float] = None  # K
    boiling_point: Optional[float] = None  # K


atoms: Dict[str, Atom] = {
    "U235": Atom(atomic_weight=235.0439299),
    "U238": Atom(atomic_weight=238.0507884),
    "H": Atom(atomic_weight=1.00794),
    "O": Atom(atomic_weight=15.9994),
    "D": Atom(atomic_weight=2.01410177812),
    "W": Atom(atomic_weight=183.84),
    "C": Atom(atomic_weight=12.0107),
}

uranium = Material(
    composition=[
        AtomProportion(atoms["U235"], 0.00711),
        AtomProportion(atoms["U238"], 0.99289),
    ],
    density=18.95,
)

materials: Dict[str, Material] = {
    "Uranium": uranium,
    "Water": Material(
        composition=[
            AtomProportion(atoms["H"], 2),
            AtomProportion(atoms["O"], 1),
        ],
        density=1,
    ),
    "Heavy Water": Material(
        composition=[
            AtomProportion(atoms["D"], 2),
            AtomProportion(atoms["O"], 1),
        ],
        density=1.105,
    ),
    "Tungsten": Material(
        composition=[
            AtomProportion(atoms["W"]),
        ],
        density=19.25,
    ),
    "Uranium Dioxide": Material(
        composition=uranium.composition + [AtomProportion(atoms["O"], 2)],
        density=10.97,
    ),
    "Uranium Carbide": Material(
        composition=uranium.composition + [AtomProportion(atoms["C"], 1)],
        density=11.69,
    ),
    "Graphite": Material(
        composition=[AtomProportion(atoms["C"])],
        density=1.8,
    ),
}
