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
    "Be": Atom(name="Be", atomic_weight=9.012182),
    "Si": Atom(name="Si", atomic_weight=28.0855),
    "N": Atom(name="N", atomic_weight=14.0067),
    "N15": Atom(name="N15", atomic_weight=15.000108),
    "N14": Atom(name="N14", atomic_weight=14.003074),
    "Al": Atom(name="Al", atomic_weight=26.9815385),
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


def normalize_material(material: Material) -> Material:
    total_proportion = sum(atom_prop.proportion for atom_prop in material.composition)
    return Material(
        composition=[
            AtomProportion(
                atom=atom_prop.atom, proportion=atom_prop.proportion / total_proportion
            )
            for atom_prop in material.composition
        ],
        **{k: v for k, v in material.model_dump().items() if k not in ["composition"]},
    )


def multiply_composition(material: Material, factor: float) -> List[AtomProportion]:
    return [
        AtomProportion(atom=atom_prop.atom, proportion=atom_prop.proportion * factor)
        for atom_prop in material.composition
    ]


def create_triso(
    packing_fraction: float, uranium_oxy_carbide: Material, silicon_carbide: Material
):
    density_uranium_oxy_carbide = uranium_oxy_carbide.density
    density_silicon_carbide = silicon_carbide.density
    volumic_ratio_hm = packing_fraction * 0.5

    return Material(composition=[], density=density_triso)


def make_materials(uranium_enrichment: float):
    natural_uranium = Material(
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
        composition=create_uranium(uranium_enrichment),
        density=18.95,
        color="green",
    )

    depleted_uranium = Material(
        composition=create_uranium(0.003), density=18.95, color="green"
    )

    uranium_oxy_carbide = Material(
        composition=[
            AtomProportion(atom=atoms["C"], proportion=0.2),
            *enriched_uranium.composition,
            AtomProportion(atom=atoms["O"], proportion=0.3),
        ],
        density=10.97,
        color="green",
    )

    silicon_carbide = Material(
        composition=[
            AtomProportion(atom=atoms["Si"], proportion=1),
            AtomProportion(atom=atoms["C"], proportion=1),
        ],
        density=3.6,
        color="darkgray",
    )

    materials_def: Dict[str, Material] = {
        "Depleted Uranium": depleted_uranium,
        "Light Water": Material(
            composition=[
                AtomProportion(atom=atoms["H"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=1,
            color="blue",
        ),
        "Zirconium": Material(
            composition=[AtomProportion(atom=atoms["Zr"])],
            density=6.52,
            color="gray",
        ),
        "Aluminum": Material(
            composition=[AtomProportion(atom=atoms["Al"])],
            density=2.7,
            color="lightblue",
        ),
        "Beryllium Oxide": Material(
            composition=[
                AtomProportion(atom=atoms["Be"], proportion=1),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=3.02,
            color="lightblue",
        ),
        "TRISO": Material(
            composition=[
                AtomProportion(atom=atoms["Si"], proportion=4),
                AtomProportion(atom=atoms["C"], proportion=4),
                *uranium_oxy_carbide.composition,
            ],
            density=3.6 * 0.75 + 10.8 * 0.25,
            color="green",
        ),
        "Silicon Carbide": Material(
            composition=[
                AtomProportion(atom=atoms["Si"], proportion=1),
                AtomProportion(atom=atoms["C"], proportion=1),
            ],
            density=3.6,
            color="darkgray",
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
            color="yellow",
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
            density=2.26,
            color="black",
        ),
        "Lead": Material(
            composition=[AtomProportion(atom=atoms["Pb"])], density=11.34, color="gray"
        ),
        "Boron Carbide": Material(
            composition=[
                AtomProportion(atom=atoms["B"]),
                AtomProportion(atom=atoms["C"]),
            ],
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
                materials_dict[name].add_element(
                    atom_prop.atom.name, atom_prop.proportion
                )
            except Exception as e:
                # for nuclides we use weight percent because it is how enrichment is given
                materials_dict[name].add_nuclide(
                    atom_prop.atom.name, atom_prop.proportion
                )
        materials_dict[name].set_density("g/cm3", material.density)

    colors = {}
    for name, material in materials_def.items():
        colors[materials_dict[name]] = (
            "orange" if material.color is None else material.color
        )
    return materials_dict, colors
