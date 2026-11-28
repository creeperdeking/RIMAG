from __future__ import annotations

from typing import Dict, Iterable, List, Optional

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
    # Carbon moderator. Reflector and shield-moderator zones of graphite-like
    # materials share one fuel-to-absorber distance even when the names differ.
    graphite_like: bool = False


class MixedMaterial(BaseModel):
    materials: List[str]
    proportions: List[float]
    graphite_like: bool = False


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
    outer_cold_shield_moderator: str
    emitter: str
    fuel_cladding: str
    void: str
    outer_empty_zone: str
    photovoltaic: str
    coolant: str
    gamma_shield: str
    rotary_axle: str
    # Hole on the fuel-to-TPV chord. The rotating-disc shield moderator stays
    # on neutron_shield_moderator, so the two can differ.
    inner_neutron_shield_moderator: str = "Graphite"


atoms: Dict[str, Atom] = {
    "U235": Atom(name="U235", atomic_weight=235.0439299),
    "U234": Atom(name="U234", atomic_weight=234.040947),
    "U238": Atom(name="U238", atomic_weight=238.0507884),
    "U": Atom(name="U", atomic_weight=238.02891338),
    "H": Atom(name="H", atomic_weight=1.00794),
    "O": Atom(name="O", atomic_weight=15.9994),
    "H2": Atom(name="H2", atomic_weight=2.01410177812),
    "W": Atom(name="W", atomic_weight=183.84),
    "Sn": Atom(name="Sn", atomic_weight=118.71),
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
    "Co": Atom(name="Co", atomic_weight=58.933194),
    "Mn": Atom(name="Mn", atomic_weight=54.938045),
    "S": Atom(name="S", atomic_weight=32.065),
    "Ti": Atom(name="Ti", atomic_weight=47.867),
    "Cl": Atom(name="Cl", atomic_weight=35.453),
    "Ar": Atom(name="Ar", atomic_weight=39.948),
    "Li": Atom(name="Li", atomic_weight=6.941),
    "V": Atom(name="V", atomic_weight=50.9415),
    "Ta": Atom(name="Ta", atomic_weight=180.94788),
    "F": Atom(name="F", atomic_weight=18.9984032),
    "Y": Atom(name="Y", atomic_weight=88.90584),
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


def graphite_boron_weight_fractions(boron_ppm: float) -> tuple[float, float]:
    """Carbon and elemental-boron weight fractions for graphite doped at ``boron_ppm``.

    ppm is parts per million by mass. The fractions sum to 1. Zero ppm is pure
    carbon. A value at or above 1e6 ppm would be pure boron, which is rejected.
    """
    if boron_ppm < 0:
        raise ValueError(f"Boron concentration must be >= 0 ppm. Got {boron_ppm} ppm.")
    weight_boron = boron_ppm / 1_000_000.0
    if weight_boron >= 1.0:
        raise ValueError(
            f"Boron concentration must be below 1e6 ppm so the material stays graphite. "
            f"Got {boron_ppm} ppm."
        )
    return 1.0 - weight_boron, weight_boron


def graphite_material_base_name(name: str) -> str:
    """'Graphite' for 'Graphite' and 'Graphite 2'; other names are unchanged."""
    base, _, suffix = name.rpartition(" ")
    if suffix.isdigit():
        return base
    return name


def graphite_like_names() -> set[str]:
    """Catalog names flagged ``graphite_like``, including mixed materials."""
    if not _MATERIAL_SPECS and not _MATERIAL_MIXED:
        material_definitions(0.0)
    names = {name for name, spec in _MATERIAL_SPECS.items() if spec.graphite_like}
    names.update(name for name, mix in _MATERIAL_MIXED.items() if mix.graphite_like)
    return names


def is_graphite_like(name: str) -> bool:
    """True when ``name`` is a graphite-like catalog material or a numbered copy."""
    return graphite_material_base_name(name or "") in graphite_like_names()


# IG-430 isotropic graphite bulk density, g/cm³.
# Campbell, Snead, and Katoh, J. Nucl. Mater. (2023), https://www.osti.gov/servlets/purl/1928952
ISOTROPIC_GRAPHITE_DENSITY = 1.82

# Commercial isostatic graphite, Toyo Tanso IG-11, weight ppm.
# IG-11 is the unpurified isostatic block from which nuclear IG-110 is made.
# Lee, Ghosh, and Loyalka, Table 1, Evans Analytical GDMS / ICP-OES.
# https://www.osti.gov/servlets/purl/1423049
# The paper reports ash above 200 ppm. Only elements given as measured
# values are included; detection-limit entries are left out. Carbon is
# the balance. IG-11's catalog density is 1.77 g/cm³; this card keeps the
# isotropic graphite density so it stays comparable with the pure graphite.
_ISOSTATIC_GRAPHITE_IMPURITY_PPM: tuple[tuple[str, float], ...] = (
    ("V", 177.2),
    ("Ca", 22.32),
    ("Fe", 9.59),
    ("Ni", 8.31),
    ("B", 2.9),
    ("Mg", 0.99),
    ("Si", 0.7),
    ("Co", 0.2),
    ("Li", 0.06),
)


def natural_graphite_atom_proportions() -> List[AtomProportion]:
    """Atom amounts for commercial isostatic graphite.

    Impurity masses are the IG-11 analysis above. The balance is carbon.
    """
    impurity_weight = sum(ppm for _, ppm in _ISOSTATIC_GRAPHITE_IMPURITY_PPM) * 1e-6
    moles: Dict[str, float] = {
        "C": (1.0 - impurity_weight) / atoms["C"].atomic_weight
    }
    for element, ppm in _ISOSTATIC_GRAPHITE_IMPURITY_PPM:
        moles[element] = ppm * 1e-6 / atoms[element].atomic_weight
    order = ["C", *(element for element, _ in _ISOSTATIC_GRAPHITE_IMPURITY_PPM)]
    return [AtomProportion(atom=atoms[name], proportion=moles[name]) for name in order]


def apply_boron_ppm_to_fuel_graphite(
    materials_dict: Dict[str, object],
    material_choice: MaterialChoice,
    boron_ppm: float,
    colors: Optional[Dict] = None,
) -> None:
    """Replace the fuel-layer graphite with the same graphite plus boron.

    Only ``material_choice.fuel_cladding`` is changed, and only when that
    material is graphite. Reflector, disk, and shield copies stay pure carbon.
    Non-positive ppm leaves the material untouched.
    """
    ppm = float(boron_ppm)
    if ppm <= 0:
        return
    weight_carbon, weight_boron = graphite_boron_weight_fractions(ppm)

    name = material_choice.fuel_cladding
    if graphite_material_base_name(name) != "Graphite":
        print(
            f"Boron concentration {ppm:g} ppm ignored: "
            f"fuel-layer material is '{name}', not graphite."
        )
        return
    if name not in materials_dict:
        raise ValueError(f"Fuel-layer graphite '{name}' is not in materials_dict")

    import openmc

    old = materials_dict[name]
    spec = _MATERIAL_SPECS.get("Graphite")
    density = spec.density if spec is not None else 1.82
    scattering = spec.scattering if spec is not None and spec.scattering else "c_Graphite"

    doped = openmc.Material(name=name)
    doped.add_element("C", weight_carbon, percent_type="wo")
    doped.add_element("B", weight_boron, percent_type="wo")
    doped.add_s_alpha_beta(scattering)
    doped.set_density("g/cm3", density)
    materials_dict[name] = doped
    if colors is not None and old in colors:
        colors[doped] = colors.pop(old)
    print(
        f"Fuel-layer graphite '{name}': {ppm:g} ppm boron by mass "
        f"(density {density} g/cm3, {scattering})."
    )


# Shield zones that take the append-menu boron concentration.
# The fuel-side reflector bump and the disk stay on their own materials.
# Void has nothing to dope. The boron-carbide wedge is already the absorber.
_SHIELD_BORON_FIELDS = (
    "neutron_shield_moderator",
    "shaft_shield_moderator",
    "outer_cold_shield_moderator",
    "shield_moderator_cladding",
    "neutron_absorber",
    "inner_neutron_shield_moderator",
)
_SHIELD_BORON_SKIP = {"", "Void", "Boron Carbide"}
SHIELD_GRAPHITE_NAME = "Shield graphite"


def shield_graphite_fields(material_choice: MaterialChoice) -> List[str]:
    """Choice fields whose shield material is graphite-like, in choice order."""
    return [
        field
        for field in _SHIELD_BORON_FIELDS
        if is_graphite_like(getattr(material_choice, field) or "")
    ]


def shield_boron_fields(material_choice: MaterialChoice) -> List[str]:
    """Shield fields that receive the append-menu boron concentration.

    Graphite-like or not. Void and a boron-carbide wedge are left alone.
    """
    fields = []
    for field in _SHIELD_BORON_FIELDS:
        base = graphite_material_base_name(getattr(material_choice, field) or "")
        if base in _SHIELD_BORON_SKIP:
            continue
        fields.append(field)
    return fields


def _doped_shield_name(base: str) -> str:
    if base == "Graphite":
        return SHIELD_GRAPHITE_NAME
    return f"Shield {base}"


def _thermal_scattering_names(material) -> List[str]:
    names = []
    for entry in getattr(material, "_sab", None) or []:
        if isinstance(entry, str):
            names.append(entry)
            continue
        if isinstance(entry, tuple) and entry:
            names.append(str(entry[0]))
            continue
        name = getattr(entry, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _nuclide_weight_fractions(material) -> List[tuple[str, float]]:
    import openmc

    total = 0.0
    weighted = []
    for nuclide, density in material.get_nuclide_atom_densities().items():
        mass = float(density) * float(openmc.data.atomic_mass(str(nuclide)))
        weighted.append((str(nuclide), mass))
        total += mass
    if total <= 0.0:
        raise ValueError(f"Material '{getattr(material, 'name', '')}' has no mass to dope.")
    return [(nuclide, mass / total) for nuclide, mass in weighted]


def _natural_boron_weight_fractions(weight_boron: float) -> List[tuple[str, float]]:
    """Isotopic weight fractions for ``weight_boron`` of natural elemental boron."""
    import openmc

    scratch = openmc.Material()
    scratch.add_element("B", 1.0, percent_type="wo")
    scratch.set_density("g/cm3", 2.34)
    return [
        (nuclide, fraction * weight_boron)
        for nuclide, fraction in _nuclide_weight_fractions(scratch)
    ]


def _material_density(material) -> float:
    density = getattr(material, "density", None)
    if isinstance(density, (int, float)):
        return float(density)
    return float(material.get_mass_density())


def _boron_added_copy(material, name: str, weight_boron: float):
    """Scale the host to make room, then add ``weight_boron`` of elemental boron.

    Boron already in the host stays, scaled with the rest of the composition,
    and the new boron is added on top. Each nuclide is written once so an
    isotopic host is not replaced by a second natural-boron card.
    """
    import openmc

    host = 1.0 - weight_boron
    combined: Dict[str, float] = {}
    for nuclide, fraction in _nuclide_weight_fractions(material):
        combined[nuclide] = fraction * host
    for nuclide, fraction in _natural_boron_weight_fractions(weight_boron):
        combined[nuclide] = combined.get(nuclide, 0.0) + fraction
    doped = openmc.Material(name=name)
    for nuclide, fraction in combined.items():
        if fraction <= 0.0:
            continue
        doped.add_nuclide(nuclide, fraction, percent_type="wo")
    for sab in _thermal_scattering_names(material):
        doped.add_s_alpha_beta(sab)
    doped.set_density("g/cm3", _material_density(material))
    return doped


def apply_boron_ppm_to_shield_graphite(
    materials_dict: Dict[str, object],
    material_choice: MaterialChoice,
    boron_ppm: float,
    colors: Optional[Dict] = None,
) -> None:
    """Point each neutron-shield material at a copy that carries ``boron_ppm``.

    Graphite-like shields become carbon plus that boron and keep the card's
    density and thermal-scattering law. Every other shield keeps its nuclides,
    scaled so the added elemental boron is ``boron_ppm`` by mass, and keeps
    its density and thermal scattering. Void and a boron-carbide wedge stay
    as they are. Fuel, disk, and reflector materials are not shield zones.
    Non-positive ppm leaves every zone untouched.
    """
    ppm = float(boron_ppm)
    if ppm <= 0:
        return
    fields = shield_boron_fields(material_choice)
    if not fields:
        print(
            f"Shield boron {ppm:g} ppm ignored: "
            f"neutron shield moderator is '{material_choice.neutron_shield_moderator}', "
            f"and no other shield material can take boron."
        )
        return
    _weight_carbon, weight_boron = graphite_boron_weight_fractions(ppm)

    import openmc

    grouped: Dict[str, List[str]] = {}
    for field in fields:
        base = graphite_material_base_name(getattr(material_choice, field) or "")
        grouped.setdefault(base, []).append(field)

    for base, group_fields in grouped.items():
        doped_name = _doped_shield_name(base)
        if is_graphite_like(base):
            spec = _MATERIAL_SPECS.get(base)
            density = spec.density if spec is not None else ISOTROPIC_GRAPHITE_DENSITY
            scattering = spec.scattering if spec is not None else "c_Graphite"
            doped = openmc.Material(name=doped_name)
            doped.add_element("C", 1.0 - weight_boron, percent_type="wo")
            doped.add_element("B", weight_boron, percent_type="wo")
            if scattering:
                doped.add_s_alpha_beta(scattering)
            doped.set_density("g/cm3", density)
            scatter_note = scattering if scattering else "no thermal scattering"
            kind = "graphite"
        else:
            source_name = getattr(material_choice, group_fields[0])
            source = materials_dict.get(source_name)
            if source is None:
                raise ValueError(
                    f"Shield material '{source_name}' is not in materials_dict."
                )
            doped = _boron_added_copy(source, doped_name, weight_boron)
            density = float(doped.get_mass_density())
            scatter_names = _thermal_scattering_names(doped)
            scatter_note = ", ".join(scatter_names) if scatter_names else "no thermal scattering"
            kind = "material"
        materials_dict[doped_name] = doped
        if colors is not None and doped not in colors:
            for field in group_fields:
                old = materials_dict.get(getattr(material_choice, field))
                if old is not None and old in colors:
                    colors[doped] = colors[old]
                    break
        for field in group_fields:
            setattr(material_choice, field, doped_name)
        print(
            f"Shield {kind} '{base}': {ppm:g} ppm boron by mass "
            f"({', '.join(group_fields)}; density {density} g/cm3, {scatter_note})."
        )


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
    import openmc

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

    import openmc

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
    extra_names: Optional[Iterable[str]] = None,
):
    import openmc

    materials_dict: Dict[str, openmc.Material] = {}

    used_materials = set(material_choice.model_dump().values())
    if extra_names:
        used_materials.update(name for name in extra_names if name)
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


_MATERIAL_SVG_COLORS: Dict[str, str] = {}
_MATERIAL_SPECS: Dict[str, Material] = {}
_MATERIAL_MIXED: Dict[str, MixedMaterial] = {}


def _svg_color(materials_def: Dict[str, Material], name: str) -> str:
    """Color for a material name, including duplicates such as 'Graphite 2'."""
    spec = materials_def.get(name)
    if spec is None:
        base, separator, suffix = name.rpartition(" ")
        if separator and suffix.isdigit():
            spec = materials_def.get(base)
    if spec is None or spec.color is None:
        return "orange"
    return spec.color


def material_svg_colors() -> Dict[str, str]:
    """SVG color for every material defined in this module."""
    if not _MATERIAL_SVG_COLORS:
        fields = {name: "Void" for name in MaterialChoice.model_fields}
        make_materials(
            0.0,
            MaterialChoice(**fields),
            0.0,
            1.0,
            0.0,
            _colors_only=True,
        )
    return dict(_MATERIAL_SVG_COLORS)


def material_definitions(
    uranium_enrichment: float,
    borated_water_moderator_boron_ppm: float = 2000,
    moderator_density: float = 1.016,
    gadolinium_oxide_in_fuel_proportion: float = 0.0,
) -> tuple[Dict[str, Material], Dict[str, MixedMaterial]]:
    """Compositions, densities, and colors, without building OpenMC materials.

    ``uranium_enrichment`` is the U-235 weight percent stored on uranium atoms.
    """
    fields = {name: "Void" for name in MaterialChoice.model_fields}
    make_materials(
        uranium_enrichment,
        MaterialChoice(**fields),
        borated_water_moderator_boron_ppm,
        moderator_density,
        gadolinium_oxide_in_fuel_proportion,
        _colors_only=True,
    )
    return dict(_MATERIAL_SPECS), dict(_MATERIAL_MIXED)


def color_for_openmc_material_name(name: str) -> str:
    """SVG color for an OpenMC material name, including numbered duplicates."""
    colors = material_svg_colors()
    if name in colors:
        return colors[name]
    base, separator, suffix = name.rpartition(" ")
    if separator and suffix.isdigit() and base in colors:
        return colors[base]
    return "orange"


def material_copy_number(name: str) -> int:
    """1 for the base material, 2 for 'Graphite 2', and so on."""
    colors = material_svg_colors()
    base, separator, suffix = name.rpartition(" ")
    if separator and suffix.isdigit() and base in colors:
        return int(suffix)
    return 1


def lighten_rgb(rgb, extra_copies: int) -> tuple:
    """Move an RGB color one percent toward white per extra copy."""
    fraction = min(max(extra_copies, 0) * 0.01, 1.0)
    return tuple(
        int(round(channel + (255 - channel) * fraction)) for channel in rgb
    )


def rgb_for_openmc_material_name(name: str) -> tuple:
    """Shaded RGB color for one material instance.

    The first instance keeps the color from materials.py. Each later copy of
    that same material is one percent lighter.
    """
    from openmc.plots import _SVG_COLORS

    svg_color = color_for_openmc_material_name(name).lower()
    rgb = _SVG_COLORS.get(svg_color, _SVG_COLORS["orange"])
    return lighten_rgb(rgb, material_copy_number(name) - 1)


def make_materials(
    uranium_enrichment: float,
    material_choice: MaterialChoice,
    borated_water_moderator_boron_ppm: float = 2000,
    moderator_density: float = 1.016,
    gadolinium_oxide_in_fuel_proportion: float = 0.0,
    _colors_only: bool = False,
    extra_names: Optional[Iterable[str]] = None,
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
        density=ISOTROPIC_GRAPHITE_DENSITY,
        color="black",
        scattering="c_Graphite",
        graphite_like=True,
    )
    natural_graphite = Material(
        composition=natural_graphite_atom_proportions(),
        density=ISOTROPIC_GRAPHITE_DENSITY,
        color="brown",
        scattering="c_Graphite",
        graphite_like=True,
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

    high_density_polyethylene = Material(
        composition=[
            AtomProportion(atom=atoms["C"], proportion=2),
            AtomProportion(atom=atoms["H"], proportion=4),
        ],
        density=0.95, # https://www.bpf.co.uk/plastipedia/polymers/HDPE.aspx
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
            density=0.9982,
            color="blue",
            scattering="c_H_in_H2O",
        ),
        "Ammonia": Material(
            composition=[
                AtomProportion(atom=atoms["H"], proportion=3),
                AtomProportion(atom=atoms["N"], proportion=1),
            ],
            density=0.771,
            color="lightblue",
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
        "EUROFER97": Material(
            composition=[
                AtomProportion(atom=atoms["Fe"], proportion=88.8298),
                AtomProportion(atom=atoms["Cr"], proportion=9.3),
                AtomProportion(atom=atoms["W"], proportion=1.0),
                AtomProportion(atom=atoms["Mn"], proportion=0.40),
                AtomProportion(atom=atoms["V"], proportion=0.22),
                AtomProportion(atom=atoms["C"], proportion=0.11),
                AtomProportion(atom=atoms["Ta"], proportion=0.086),
                AtomProportion(atom=atoms["Si"], proportion=0.038),
                AtomProportion(atom=atoms["N"], proportion=0.011),
                AtomProportion(atom=atoms["P"], proportion=0.0023),
                AtomProportion(atom=atoms["S"], proportion=0.0029),
            ],
            density=7.8,
            color="gray",
        ),
        "Galinstan": Material(
            composition=[
                AtomProportion(atom=atoms["Ga"], proportion=1),
                AtomProportion(atom=atoms["In"], proportion=1),
                AtomProportion(atom=atoms["Sn"], proportion=1),
            ],
            density=6.2,
            color="lightblue",
        ),
        "Lithium Oxide": Material(
            composition=[
                AtomProportion(atom=atoms["Li"], proportion=2),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=1.76, # at 1250 celsius
            color="lightblue",
        ),
        "Lithium Fluoride": Material(
            composition=[
                AtomProportion(atom=atoms["Li"], proportion=1),
                AtomProportion(atom=atoms["F"], proportion=1),
            ],
            density=2.635,
            color="yellow",
        ),
        "Molten Lithium Fluoride": Material(
            composition=[
                AtomProportion(atom=atoms["Li"], proportion=1),
                AtomProportion(atom=atoms["F"], proportion=1),
            ],
            density=1.69, # at 1250 celsius
            color="yellow",
        ),
        "Beryllium Oxide": Material( 
            composition=[
                AtomProportion(atom=atoms["Be"], proportion=1),
                AtomProportion(atom=atoms["O"], proportion=1),
            ],
            density=2.92, # at 1250 celsius https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=116
            color="lightblue",
            # scattering="c_B_in_BeO",
        ),
        "Zirconium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Zr"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=1.6),
            ],
            density=5.6,
            color="gray",
        ),
        "Yttrium Hydride": Material(
            composition=[
                AtomProportion(atom=atoms["Y"], proportion=1),
                AtomProportion(atom=atoms["H"], proportion=1.9),
            ],
            density=5.0,
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
        "Cooling Tower Water": Material(
            composition=[
                AtomProportion(atom=atoms["H"],  proportion=2000.0),
                AtomProportion(atom=atoms["O"],  proportion=1000.87),

                # Major cations from hardness / TDS
                AtomProportion(atom=atoms["Na"], proportion=0.588),
                AtomProportion(atom=atoms["Ca"], proportion=0.135),
                AtomProportion(atom=atoms["Mg"], proportion=0.015),
                AtomProportion(atom=atoms["K"],  proportion=0.005),

                # Major anions & trace species
                AtomProportion(atom=atoms["Cl"], proportion=0.407),
                AtomProportion(atom=atoms["S"],  proportion=0.131),  # from SO4
                AtomProportion(atom=atoms["C"],  proportion=0.118),  # from HCO3
                AtomProportion(atom=atoms["Si"], proportion=0.024),  # from SiO2
                AtomProportion(atom=atoms["F"],  proportion=0.005),
            ],
            density=1.002,
            color="lightblue",
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
            density=3.77, # https://rdreview.jaea.go.jp/review_en/2006/pdf/e2006_3-12.pdf
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
            density=10.56 * 0.95, # Uranium Dioxide density at 1250 celsius with 5% porosity
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
        "Natural Graphite": natural_graphite,
        "Low Density Graphite": Material(
            composition=[AtomProportion(atom=atoms["C"])],
            density=2.26*0.1,
            color="lightgray",
            scattering="c_Graphite",
            graphite_like=True,
        ),
        "Graphite NO Scattering": Material(
            composition=[AtomProportion(atom=atoms["C"])],
            density=2.26,
            color="yellow",
            scattering=None,
            graphite_like=True,
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
        "High Density PolyEthylene": high_density_polyethylene,
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
        "InGaAs": Material(
            composition=[
                AtomProportion(atom=atoms["In"], proportion=0.53),
                AtomProportion(atom=atoms["Ga"], proportion=0.47),
                AtomProportion(atom=atoms["As"], proportion=1.0),
            ],
            density=5.50,
            color="lightblue",
        ),
    }

    material_mixed_def = {
        "Borotron": MixedMaterial(
            materials=["Boron", "High Density PolyEthylene"],
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

    _MATERIAL_SVG_COLORS.clear()
    _MATERIAL_SVG_COLORS.update(
        {name: _svg_color(materials_def, name) for name in materials_def}
    )
    _MATERIAL_SPECS.clear()
    _MATERIAL_SPECS.update(materials_def)
    _MATERIAL_MIXED.clear()
    _MATERIAL_MIXED.update(material_mixed_def)
    if _colors_only:
        return {}, {}, material_choice

    materials_dict = make_materials_dict(
        materials_def, material_mixed_def, material_choice, extra_names
    )

    updated_materials_dict, updated_material_choice = separate_duplicate_materials(
        material_choice, materials_dict
    )
    colors = {
        openmc_material: rgb_for_openmc_material_name(name)
        for name, openmc_material in updated_materials_dict.items()
    }
    return updated_materials_dict, colors, updated_material_choice
