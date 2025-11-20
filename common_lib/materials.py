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


class MonitoredNuclide(BaseModel):
    nuclide: str


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
    neutron_absorber: str
    neutron_reflector: str
    neutron_shield_moderator: str
    bottom_reflector: str
    fuel: str
    moderator_cladding: str
    coolant_cladding: str
    shield_moderator_cladding: str
    shaft_shield_moderator: str
    emitter: str
    fuel_cladding: str
    void: str
    photovoltaic: str
    coolant: str
    gamma_shield: str
    rotary_axle: str
    moduler_spacer: str


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
    "Na": Atom(name="Na", atomic_weight=22.98976928),
    "Mg": Atom(name="Mg", atomic_weight=24.305),
    "Fe": Atom(name="Fe", atomic_weight=55.845),
    "Ca": Atom(name="Ca", atomic_weight=40.078),
    "K": Atom(name="K", atomic_weight=39.0983),
    "Nb": Atom(name="Nb", atomic_weight=92.90638),
    "Ga": Atom(name="Ga", atomic_weight=69.723),
    "As": Atom(name="As", atomic_weight=74.9216),
    "In": Atom(name="In", atomic_weight=114.818),
    "P": Atom(name="P", atomic_weight=30.973762),
    "Cr": Atom(name="Cr", atomic_weight=51.9961),
    "Ni": Atom(name="Ni", atomic_weight=58.6934),
    "Mn": Atom(name="Mn", atomic_weight=54.938045),
    "S": Atom(name="S", atomic_weight=32.065),
    "Ti": Atom(name="Ti", atomic_weight=47.867),
    "Cl": Atom(name="Cl", atomic_weight=35.453),
    "Ar": Atom(name="Ar", atomic_weight=39.948),
    "Li": Atom(name="Li", atomic_weight=6.941),
}


def borated_water_atom_proportions_from_boron_ppm(
    boron_ppm: float,
    include_dissolved_air: bool = True,
) -> List[AtomProportion]:
    """
    Create atom proportions for a water solution containing boron (as boric acid, H3BO3)
    at a specified elemental boron concentration in ppm by mass, and (optionally) the
    typical dissolved-air species for aerated, purified freshwater at ~25 °C, 1 atm.

    Returns a "chemical-like" atomic formula for H, O, B, and (if enabled) C, N, Ar.

    Notes
    -----
    - ppm is parts-per-million by mass of elemental B: mass fraction w_B = ppm / 1e6
    - Boron is present solely as H3BO3
    - We take y = 1 for H2O and x = r for H3BO3, with:
          r = (w_B * M_H2O) / (M_B - w_B * M_H3BO3)
    - Dissolved-air adders are expressed as atoms per ~1 H2O molecule and assumed
      independent of trace boron (good approximation for typical ppm B).
    """
    # --- Dissolved-air atom adders per ~1 H2O molecule (25 °C, 1 atm, freshwater)
    # Extra oxygen from dissolved O2 and CO2:
    O_EXTRA = 8.79e-06

    # Dissolved inorganic carbon from air CO2 (atoms of C per H2O):
    C_PER_H2O = 2.46712e-07

    # Dissolved nitrogen and argon (atoms per H2O):
    N_PER_H2O = 1.968756e-05
    AR_PER_H2O = 1.803825e-07

    # Handle non-positive boron quickly (still include dissolved air if requested)
    if boron_ppm <= 0:
        props = [
            AtomProportion(atom=atoms["H"],  proportion=2.0),
            AtomProportion(atom=atoms["O"],  proportion=1.0 + (O_EXTRA if include_dissolved_air else 0.0)),
            AtomProportion(atom=atoms["B"],  proportion=0.0),
        ]
        if include_dissolved_air:
            props += [
                AtomProportion(atom=atoms["C"],  proportion=C_PER_H2O),
                AtomProportion(atom=atoms["N"],  proportion=N_PER_H2O),
                AtomProportion(atom=atoms["Ar"], proportion=AR_PER_H2O),
            ]
        return props

    # Convert ppm to mass fraction
    w_B = boron_ppm / 1_000_000.0

    mass_B = atoms["B"].atomic_weight
    mass_H = atoms["H"].atomic_weight
    mass_O = atoms["O"].atomic_weight

    mass_H2O = 2.0 * mass_H + mass_O
    mass_H3BO3 = mass_B + 3.0 * mass_H + 3.0 * mass_O

    max_boron_mass_fraction = mass_B / mass_H3BO3
    if w_B >= max_boron_mass_fraction:
        raise ValueError(
            f"Boron ppm too high: maximum elemental boron mass fraction in pure boric acid is "
            f"{max_boron_mass_fraction:.6f} (≈ {max_boron_mass_fraction * 1e6:.0f} ppm). "
            f"Got {boron_ppm} ppm."
        )

    r = (w_B * mass_H2O) / (mass_B - w_B * mass_H3BO3)

    # Base H2O + boric acid contributions
    H = 2.0 + 3.0 * r
    O = 1.0 + 3.0 * r
    B = r

    # Add dissolved-air contributions
    if include_dissolved_air:
        O += O_EXTRA
        C = C_PER_H2O
        N = N_PER_H2O
        Ar = AR_PER_H2O
    else:
        C = 0.0
        N = 0.0
        Ar = 0.0

    return [
        AtomProportion(atom=atoms["H"],  proportion=H),
        AtomProportion(atom=atoms["O"],  proportion=O),
        AtomProportion(atom=atoms["B"],  proportion=B),
        AtomProportion(atom=atoms["C"],  proportion=C),
        AtomProportion(atom=atoms["N"],  proportion=N),
        AtomProportion(atom=atoms["Ar"], proportion=Ar),
    ]


def heavy_metal_density(mat, elements=None, z_min=90):
    """
    Return the heavy-metal mass density of an OpenMC Material in g/cm^3.

    Parameters
    ----------
    mat : openmc.Material
        The material to evaluate.
    elements : set of str, optional
        If given, only nuclides whose element symbol is in this set are counted
        (e.g., {'U','Pu','Th'}). Symbols are case-sensitive.
        If None, all nuclides with atomic number >= z_min are counted.
    z_min : int, optional
        Minimum atomic number to include (default 90 for actinides).

    Notes
    -----
    - Uses `Material.get_nuclide_atom_densities()` which returns densities
      in atom/b-cm, independent of how `mat` density was originally specified.
    - Converts atom/b-cm → atoms/cm^3 via 1e24, then to mass with the
      tabulated atomic mass and Avogadro’s number.

    Returns
    -------
    float
        Heavy-metal mass density in g/cm^3.
    """
    # Atom densities for every nuclide in atom/b-cm
    adens = mat.get_nuclide_atom_densities()

    hm_rho = 0.0
    for nuc, n_bcm in adens.items():
        Z, _, _ = openmc.data.zam(nuc)  # atomic number, mass number, metastable
        symbol = openmc.data.ATOMIC_SYMBOL[Z]

        include = (elements is not None and symbol in elements) or (
            elements is None and Z >= z_min
        )
        if not include:
            continue

        # atomic_mass() is in g/mol; convert atoms/b-cm → g/cm^3
        hm_rho += n_bcm * 1.0e24 * openmc.data.atomic_mass(nuc) / openmc.data.AVOGADRO

    return hm_rho


def separate_duplicate_materials(
    material_choice: MaterialChoice, materials_dict: Dict[str, openmc.Material]
):
    # If some elements of material_choice have the same value, create a duplicated material in material_dict named "[material_name] X"
    # For example, if "Graphite" is used for both "neutron_reflector" and "emitter", create "Graphite 2", "Graphite 3", etc.

    # Count occurrences of each material name in material_choice
    from collections import Counter, defaultdict

    material_values = list(material_choice.model_dump().values())
    value_counts = Counter(material_values)

    # For each value with count > 1, assign unique names for each occurrence
    value_indices = defaultdict(int)
    for field, value in material_choice.model_dump().items():
        count = value_counts[value]
        if count > 1:
            value_indices[value] += 1
            if value_indices[value] == 1:
                # The first occurrence keeps the original name
                continue
            # For subsequent occurrences, create a new material with a unique name
            new_name = f"{value} {value_indices[value]}"
            # Duplicate the material in materials_dict
            if value in materials_dict:
                # Copy the material
                import copy

                next_material = openmc.Material(name=new_name)
                next_id = next_material.next_id
                id = next_material.id

                new_material = copy.deepcopy(materials_dict[value])
                new_material.name = new_name
                new_material.next_id = next_id
                new_material.id = id
                materials_dict[new_name] = new_material

    # After duplicating materials for repeated values in material_choice,
    # update the fields in material_choice to refer to the new unique material names.
    # This ensures that each field points to the correct (possibly renamed) material.

    # Build a mapping from (field, value) to the correct material name
    value_indices = defaultdict(int)
    field_to_new_name = {}
    for field, value in material_choice.model_dump().items():
        count = value_counts[value]
        if count > 1:
            value_indices[value] += 1
            if value_indices[value] == 1:
                # First occurrence keeps the original name
                field_to_new_name[field] = value
            else:
                new_name = f"{value} {value_indices[value]}"
                field_to_new_name[field] = new_name
        else:
            field_to_new_name[field] = value

    # Create a new MaterialChoice with updated field values
    # (Assume MaterialChoice is a pydantic model or similar)
    updated_material_choice = type(material_choice)(**field_to_new_name)
    return materials_dict, updated_material_choice


def make_materials_dict(
    materials_def: Dict[str, Material],
    material_mixed_def: Dict[str, MixedMaterial],
    material_choice: MaterialChoice,
):
    materials_dict: Dict[str, openmc.Material] = {}

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
                materials_dict[material_name]
                for material_name in mixed_material.materials
            ]
            mixed_material = openmc.Material.mix_materials(
                mat_list, mixed_material.proportions, "wo"
            )
            mixed_material.name = name
            materials_dict[name] = mixed_material
    return materials_dict


def make_materials(
    uranium_enrichment: float,
    material_choice: MaterialChoice,
    borated_water_moderator_boron_ppm: float = 2000,
    moderator_density: float = 1.016,
    gadolinium_oxide_in_fuel_proportion: float = 0.0,
):
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
                AtomProportion(atom=atoms["Gd"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=3),
            ],
            density=7.9,
            color="gray",
        ),
        "Light Water": Material( # Light Water from 
            composition=[
                AtomProportion(atom=atoms["H"], proportion=2.0),
                AtomProportion(atom=atoms["O"], proportion=1.0),
                AtomProportion(atom=atoms["N"], proportion=2.0e-5),
                AtomProportion(atom=atoms["Ar"], proportion=1.8e-7),
                AtomProportion(atom=atoms["C"], proportion=2.4e-7),
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
        "Stainless Steel": Material(
            composition=[
                AtomProportion(atom=atoms["Fe"], proportion=69.43),
                AtomProportion(atom=atoms["Cr"], proportion=19.53),
                AtomProportion(atom=atoms["Ni"], proportion=8.65),
                AtomProportion(atom=atoms["Mn"], proportion=1),
                AtomProportion(atom=atoms["Si"], proportion=0.977),
                AtomProportion(atom=atoms["N"], proportion=0.196),
                AtomProportion(atom=atoms["C"], proportion=0.16),
                AtomProportion(atom=atoms["P"], proportion=0.04),
                AtomProportion(atom=atoms["S"], proportion=0.013),
            ],
            density=8.0,
            color="gray",
        ),
        "Lithium Oxide": Material(
            composition=[
                AtomProportion(atom=atoms["Li"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=2.01,
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
        "Salt Water": Material(
            composition=[
                AtomProportion(atom=atoms["H"], proportion=2000),
                AtomProportion(atom=atoms["O"], proportion=1002),
                AtomProportion(atom=atoms["Na"], proportion=8.68),
                AtomProportion(atom=atoms["Cl"], proportion=10.10),
                AtomProportion(atom=atoms["Mg"], proportion=0.977),
                AtomProportion(atom=atoms["S"], proportion=0.522),
                AtomProportion(atom=atoms["Ca"], proportion=0.190),
                AtomProportion(atom=atoms["K"], proportion=0.189),
            ],
            density=1.023,
            color="darkblue",
        ),
        "TZM": Material(
            composition=[
                AtomProportion(atom=atoms["Mo"], proportion=0.99),
                AtomProportion(atom=atoms["Ti"], proportion=0.5),
                AtomProportion(atom=atoms["Zr"], proportion=0.08),
                AtomProportion(atom=atoms["C"], proportion=0.02),
            ],
            density=6.2,
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
        "Aluminium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Al"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=3),
            ],
            density=1.477,
            color="lightblue",
        ),
        "Calcium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Ca"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=2),
            ],
            density=1.477,
            color="lightblue",
        ),
        "Titanium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Ti"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=2),
            ],
            density=3.9,
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
        "Concrete": Material(
            composition=[
                AtomProportion(atom=atoms["H"], proportion=0.168759),
                AtomProportion(atom=atoms["C"], proportion=0.001416),
                AtomProportion(atom=atoms["O"], proportion=0.562524),
                AtomProportion(atom=atoms["Na"], proportion=0.011838),
                AtomProportion(atom=atoms["Mg"], proportion=0.0014),
                AtomProportion(atom=atoms["Al"], proportion=0.021354),
                AtomProportion(atom=atoms["Si"], proportion=0.204115),
                AtomProportion(atom=atoms["K"], proportion=0.005656),
                AtomProportion(atom=atoms["Ca"], proportion=0.018674),
                AtomProportion(atom=atoms["Fe"], proportion=0.00426),
            ],
            density=2.3,
            color="gray",
        ),
        "Sodium": Material(
            composition=[AtomProportion(atom=atoms["Na"])],
            density=0.97,
            color="lightblue",
        ),
        "Niobium": Material(
            composition=[AtomProportion(atom=atoms["Nb"])],
            density=8.57,
            color="gray",
        ),
        "Niobium 1-Zirconium": Material(
            composition=[
                AtomProportion(atom=atoms["Nb"], proportion=0.99),
                AtomProportion(atom=atoms["Zr"], proportion=0.01),
            ],
            density=8.57,
            color="gray",
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
        "Tungsten Diboride": Material(
            composition=[
                AtomProportion(atom=atoms["W"], proportion=1),
                AtomProportion(atom=atoms["B"], proportion=2),
            ],
            density=15.2,
            color="lightgray",
        ),
        "Boric Acid": Material(
            composition=[
                AtomProportion(atom=atoms["B"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=3),
                AtomProportion(atom=atoms["O"], proportion=3),
            ],
            density=2.4,
            color="lightgray",
        ),
        "Borated Water": Material(
            composition=borated_water_atom_proportions_from_boron_ppm(3000),
            density=1.016,
            color="darkblue",
            scattering="c_H_in_H2O",
        ),
        "Borated Water Moderator": Material(
            composition=borated_water_atom_proportions_from_boron_ppm(
                borated_water_moderator_boron_ppm
            ),
            density=moderator_density,
            color="darkblue",
            scattering="c_H_in_H2O",
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
        "Gallium Arsenide": Material(
            composition=[
                AtomProportion(atom=atoms["Ga"], proportion=1),
                AtomProportion(atom=atoms["As"], proportion=1),
            ],
            density=5.32,
            color="lightblue",
        ),
        "InGaAsP": Material(
            composition=[
                AtomProportion(atom=atoms["In"], proportion=0.83),
                AtomProportion(atom=atoms["Ga"], proportion=0.17),
                AtomProportion(atom=atoms["As"], proportion=0.37),
                AtomProportion(atom=atoms["P"], proportion=0.63),
            ],
            density=5.07,
            color="lightblue",
        ),
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
        "Uranium Oxy-Carbide with Gadolinium Oxide": MixedMaterial(
            materials=["Uranium Oxy-Carbide", "Gadolinium Oxide"],
            proportions=[
                1 - gadolinium_oxide_in_fuel_proportion,
                gadolinium_oxide_in_fuel_proportion,
            ],
        ),
    }

    materials_dict = make_materials_dict(
        materials_def, material_mixed_def, material_choice
    )

    updated_materials_dict, updated_material_choice = separate_duplicate_materials(
        material_choice, materials_dict
    )
    colors = {}
    for name, material in materials_def.items():
        if name not in updated_material_choice.model_dump().values():
            continue
        colors[updated_materials_dict[name]] = (
            "orange" if material.color is None else material.color
        )
    return updated_materials_dict, colors, updated_material_choice
