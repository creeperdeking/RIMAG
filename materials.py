from typing import List, Optional, Dict
import openmc

from pydantic import BaseModel


class Atom(BaseModel):
    name: str
    atomic_weight: float


class AtomProportion(BaseModel):
    atom: Atom
    proportion: Optional[float] = 1


class Material(BaseModel):
    composition: List[AtomProportion]
    density: float  # g/cm3
    specific_heat: Optional[float] = None  # J/g/K
    thermal_conductivity: Optional[float] = None  # W/cm/K
    melting_point: Optional[float] = None  # K
    boiling_point: Optional[float] = None  # K
    color: Optional[str] = None


atoms: Dict[str, Atom] = {
    "U235": Atom(name="U235", atomic_weight=235.0439299),
    "U234": Atom(name="U234", atomic_weight=234.040947),
    "U238": Atom(name="U238", atomic_weight=238.0507884),
    "H": Atom(name="H", atomic_weight=1.00794),
    "O": Atom(name="O", atomic_weight=15.9994),
    "H2": Atom(name="H2", atomic_weight=2.01410177812),
    "W": Atom(name="W", atomic_weight=183.84),
    "C": Atom(name="C", atomic_weight=12.0107),
    "Pb": Atom(name="Pb", atomic_weight=207.2),
    "B": Atom(name="B", atomic_weight=10.811),
    "Mo": Atom(name="Mo", atomic_weight=95.94),
    "Zr": Atom(name="Zr", atomic_weight=91.224),
    "Pu239": Atom(name="Pu239", atomic_weight=239.052163),
    "Pu240": Atom(name="Pu240", atomic_weight=240.053813),
    "Pu241": Atom(name="Pu241", atomic_weight=241.056851),
}


def create_uranium(u235_enrichment, u234_enrichment=0):
    return [
        AtomProportion(atom=atoms["U235"], proportion=u235_enrichment),
        AtomProportion(atom=atoms["U234"], proportion=u234_enrichment),
        AtomProportion(
            atom=atoms["U238"], proportion=1 - u235_enrichment - u234_enrichment
        ),
    ]


def create_plutonium(pu239_enrichment, pu240_enrichment=0, pu241_enrichment=0):
    return [
        AtomProportion(atom=atoms["Pu239"], proportion=pu239_enrichment),
        AtomProportion(atom=atoms["Pu240"], proportion=pu240_enrichment),
        AtomProportion(atom=atoms["Pu241"], proportion=pu241_enrichment),
    ]


def create_mixed_uranium_plutonium(
    pu239_enrichment,
    pu240_enrichment,
    pu241_enrichment,
    plutonium_proportion,
):
    return [
        AtomProportion(atom=atoms["U238"], proportion=(1 - plutonium_proportion)),
        AtomProportion(
            atom=atoms["Pu239"], proportion=pu239_enrichment * plutonium_proportion
        ),
        AtomProportion(
            atom=atoms["Pu240"], proportion=pu240_enrichment * plutonium_proportion
        ),
        AtomProportion(
            atom=atoms["Pu241"], proportion=pu241_enrichment * plutonium_proportion
        ),
    ]


uranium = Material(
    composition=create_uranium(0.00711),
    density=18.95,
    color="green",
)
reactor_grade_plutonium = Material(
    composition=create_plutonium(
        pu239_enrichment=0.8, pu240_enrichment=0.15, pu241_enrichment=0.05
    ),
    density=19.84,
    color="green",
)
mixed_uranium_plutonium = Material(
    composition=create_mixed_uranium_plutonium(
        pu239_enrichment=0.8,
        pu240_enrichment=0.15,
        pu241_enrichment=0.05,
        plutonium_proportion=0.15,
    ),
    density=18.95,
    color="green",
)


enriched_uranium = Material(
    composition=create_uranium(0.20), density=18.95, color="green"
)

depleted_uranium = Material(
    composition=create_uranium(0.003), density=18.95, color="green"
)


materials_def: Dict[str, Material] = {
    "Uranium": depleted_uranium,
    "Water": Material(
        composition=[
            AtomProportion(atom=atoms["H"], proportion=2),
            AtomProportion(atom=atoms["O"], proportion=1),
        ],
        density=1,
        color="blue",
    ),
    "Heavy Water": Material(
        composition=[
            AtomProportion(atom=atoms["H2"], proportion=2),
            AtomProportion(atom=atoms["O"], proportion=1),
        ],
        density=1.105,
        color="darkblue",
    ),
    "Tungsten": Material(
        composition=[
            AtomProportion(atom=atoms["W"]),
        ],
        density=19.25,
        color="lightgray",
    ),
    "Uranium Dioxide": Material(
        composition=enriched_uranium.composition
        + [AtomProportion(atom=atoms["O"], proportion=2)],
        density=10.97,
        color="green",
    ),
    "Uranium Carbide": Material(
        composition=enriched_uranium.composition
        + [AtomProportion(atom=atoms["C"], proportion=1)],
        density=13.63,
        color="green",
    ),
    "Plutonium-Uranium Carbide": Material(
        composition=mixed_uranium_plutonium.composition
        + [AtomProportion(atom=atoms["C"], proportion=1)],
        density=13.63,
        color="green",
    ),
    "Plutonium-Uranium Oxide": Material(
        composition=mixed_uranium_plutonium.composition
        + [AtomProportion(atom=atoms["O"], proportion=2)],
        density=10.97,
        color="green",
    ),
    "Graphite": Material(
        composition=[AtomProportion(atom=atoms["C"])],
        density=1.8,
        color="black",
    ),
    "Lead": Material(
        composition=[AtomProportion(atom=atoms["Pb"])], density=11.34, color="gray"
    ),
    "Boron Carbide": Material(
        composition=[AtomProportion(atom=atoms["B"]), AtomProportion(atom=atoms["C"])],
        density=2.52,
        color="red",
    ),
    "Molybdenum": Material(
        composition=[AtomProportion(atom=atoms["Mo"])],
        density=10.28,
        color="darkgray",
    ),
    "Void": Material(
        composition=[AtomProportion(atom=atoms["Zr"])],
        density=0.01,
        color="purple",
    ),
}

materials_dict = {}

for name, material in materials_def.items():
    materials_dict[name] = openmc.Material(name=name)
    for atom_prop in material.composition:
        try:
            materials_dict[name].add_element(atom_prop.atom.name, atom_prop.proportion)
        except Exception as e:
            # for nuclides we use weight percent because it is how enrichment is given
            materials_dict[name].add_nuclide(atom_prop.atom.name, atom_prop.proportion)
    materials_dict[name].set_density("g/cm3", material.density)

colors = {}
for name, material in materials_def.items():
    colors[materials_dict[name]] = (
        "orange" if material.color is None else material.color
    )
print(colors)
