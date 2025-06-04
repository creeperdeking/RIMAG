from typing import List, Optional, Dict
import openmc

from pydantic import BaseModel


class Atom(BaseModel):
    name: str
    atomic_weight: float


class AtomProportion(BaseModel):
    atom: Atom
    proportion: Optional[float] = 1
    enrichment: Optional[float] = None
    enrichment_target: Optional[str] = None


class Material(BaseModel):
    composition: List[AtomProportion]
    density: float  # g/cm3
    specific_heat: Optional[float] = None  # J/g/K
    thermal_conductivity: Optional[float] = None  # W/cm/K
    melting_point: Optional[float] = None  # K
    boiling_point: Optional[float] = None  # K
    color: Optional[str] = None
    scattering: Optional[str] = None


class MixedMaterial(BaseModel):
    materials: List[str]
    proportions: List[float]


class MaterialChoice(BaseModel):
    moderator: str
    neutron_shield: str
    reflector: str
    fuel: str
    moderator_cladding: str
    emitter: str
    fuel_cladding: str
    void: str
    photovoltaic: str
    coolant: str
    neutron_shield_2: str
    gamma_shield: str


atoms: Dict[str, Atom] = {
    "U235": Atom(name="U235", atomic_weight=235.0439299),
    "U234": Atom(name="U234", atomic_weight=234.040947),
    "U238": Atom(name="U238", atomic_weight=238.0507884),
    "U": Atom(name="U", atomic_weight=238.02891338),
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
    "Gd": Atom(name="Gd", atomic_weight=157.25),
    "He": Atom(name="He", atomic_weight=4.002602),
}


def heavy_metals_density(material: Material) -> float:
    return (
        material.density
        * sum(
            atom_prop.proportion * atom_prop.atom.atomic_weight
            for atom_prop in material.composition
            if atom_prop.atom.atomic_weight > 200
        )
        / sum(
            atom_prop.proportion * atom_prop.atom.atomic_weight
            for atom_prop in material.composition
        )
    )


def make_materials(uranium_enrichment: float, material_choice: MaterialChoice):
    natural_uranium = Material(
        composition=[
            AtomProportion(atom=atoms["U"], proportion=1),
        ],
        density=18.95,
        color="green",
    )
    # reactor_grade_plutonium = Material(
    #     composition=create_plutonium(
    #         pu239_enrichment=0.8, pu240_enrichment=0.15, pu241_enrichment=0.05
    #     ),
    #     density=19.84,
    #     color="green",
    # )
    # mixed_uranium_plutonium = Material(
    #     composition=create_mixed_uranium_plutonium(
    #         pu239_enrichment=0.8,
    #         pu240_enrichment=0.15,
    #         pu241_enrichment=0.05,
    #         plutonium_proportion=0.15,
    #     ),
    #     density=18.95,
    #     color="green",
    # )

    enriched_uranium = Material(
        composition=[
            AtomProportion(
                atom=atoms["U"], proportion=1, enrichment=uranium_enrichment
            ),
        ],
        density=18.95,
        color="green",
    )

    depleted_uranium = Material(
        composition=[
            AtomProportion(atom=atoms["U"], proportion=1, enrichment=0.03),
        ],
        density=18.95,
        color="green",
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

    graphite = Material(
        composition=[AtomProportion(atom=atoms["C"])],
        density=2.26,
        color="black",
        scattering="c_Graphite",
    )

    silicon_carbide = Material(
        composition=[
            AtomProportion(atom=atoms["Si"], proportion=1),
            AtomProportion(atom=atoms["C"], proportion=1),
        ],
        density=3.6,
        color="darkgray",
    )

    boron = Material(
        composition=[AtomProportion(atom=atoms["B"])],
        density=2.34,
        color="lightgray",
    )

    zirconium_carbide = Material(
        composition=[
            AtomProportion(atom=atoms["Zr"], proportion=1),
            AtomProportion(atom=atoms["C"], proportion=1),
        ],
        density=6.2,
        color="darkgray",
    )

    polyethylene = Material(
        composition=[
            AtomProportion(atom=atoms["C"], proportion=2),
            AtomProportion(atom=atoms["H"], proportion=4),
        ],
        density=0.96,
        color="lightgray",
    )

    materials_def: Dict[str, Material] = {
        "Depleted Uranium": depleted_uranium,
        "Gadolinium Oxide": Material(
            composition=[
                AtomProportion(atom=atoms["Gd"], proportion=1),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=7.9,
            color="gray",
        ),
        "Light Water": Material(
            composition=[
                AtomProportion(atom=atoms["H"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=1,
            color="blue",
            scattering="c_H_in_H2O",
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
            # scattering="c_B_in_BeO",
        ),
        "Zirconium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Zr"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=1.6),
            ],
            density=5.9,
            color="gray",
        ),
        "Zirconium Hydride Boron": Material(
            composition=[
                AtomProportion(atom=atoms["Zr"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=1.6),
                AtomProportion(atom=atoms["B"], proportion=1),
            ],
            density=6.2,
            color="gray",
        ),
        "Silicon": Material(
            composition=[AtomProportion(atom=atoms["Si"])],
            density=2.33,
            color="lightblue",
        ),
        "Silicon Carbide": silicon_carbide,
        "Zirconium Carbide": zirconium_carbide,
        "Heavy Water": Material(
            composition=[
                AtomProportion(atom=atoms["H2"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=1.105,
            color="darkblue",
            scattering="c_D_in_D2O",
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
        "Uranium Oxy-Carbide": uranium_oxy_carbide,
        # "Plutonium-Uranium Carbide": Material(
        #     composition=mixed_uranium_plutonium.composition
        #     + [AtomProportion(atom=atoms["C"], proportion=1)],
        #     density=13.63,
        #     color="green",
        # ),
        # "Plutonium-Uranium Oxide": Material(
        #     composition=mixed_uranium_plutonium.composition
        #     + [AtomProportion(atom=atoms["O"], proportion=2)],
        #     density=10.97,
        #     color="green",
        # ),
        "Graphite": graphite,
        "Graphite 2": Material(
            composition=[AtomProportion(atom=atoms["C"])],
            density=2.26,
            color="yellow",
            scattering="c_Graphite",
        ),
        "Graphite NO Scattering": Material(
            composition=[AtomProportion(atom=atoms["C"])],
            density=2.26,
            color="yellow",
            scattering=None,
        ),
        "Lead": Material(
            composition=[AtomProportion(atom=atoms["Pb"])], density=11.34, color="gray"
        ),
        "Boron Carbide": Material(
            composition=[
                AtomProportion(atom=atoms["B"], proportion=4),
                AtomProportion(atom=atoms["C"], proportion=1),
            ],
            density=2.52,
            color="lightgray",
        ),
        "Molybdenum": Material(
            composition=[AtomProportion(atom=atoms["Mo"])],
            density=10.28,
            color="darkgray",
        ),
        "Void": Material(
            composition=[AtomProportion(atom=atoms["He"])],
            density=1e-10,
            color="purple",
        ),
        "Boron": boron,
        "Polyethylene": polyethylene,
    }

    material_mixed_def = {
        "Borotron": MixedMaterial(
            materials=["Boron", "Polyethylene"],
            proportions=[0.05, 0.95],
        ),
        "Borated Graphite": MixedMaterial(
            materials=["Graphite NO Scattering", "Boron Carbide"],
            proportions=[0.9, 0.1],
        ),
    }

    materials_dict = {}

    used_materials = set(material_choice.model_dump().values())
    for name, material in material_mixed_def.items():
        if name in used_materials:
            used_materials.update(material.materials)

    for name, material in materials_def.items():
        if name not in used_materials:
            continue
        materials_dict[name] = openmc.Material(name=name)
        for atom_prop in material.composition:
            if atom_prop.atom.name == "U":
                materials_dict[name].add_element(
                    atom_prop.atom.name,
                    atom_prop.proportion,
                    enrichment=atom_prop.enrichment,
                )
            else:
                try:
                    materials_dict[name].add_element(
                        atom_prop.atom.name,
                        atom_prop.proportion,
                        enrichment=atom_prop.enrichment,
                        enrichment_target=atom_prop.enrichment_target,
                    )
                except Exception as e:
                    # for nuclides we use weight percent because it is how enrichment is given
                    materials_dict[name].add_nuclide(
                        atom_prop.atom.name,
                        atom_prop.proportion,
                    )
        if material.scattering is not None:
            materials_dict[name].add_s_alpha_beta(material.scattering)
        materials_dict[name].set_density("g/cm3", material.density)

    for name, mixed_material in material_mixed_def.items():
        if name in used_materials:
            mat_list = [
                materials_dict[material_name] for material_name in mixed_material.materials
            ]
            materials_dict[name] = openmc.Material.mix_materials(
                mat_list, mixed_material.proportions, "wo"
            )

    colors = {}
    for name, material in materials_def.items():
        if name not in material_choice.model_dump().values():
            continue
        colors[materials_dict[name]] = (
            "orange" if material.color is None else material.color
        )
    return materials_dict, materials_def, colors
