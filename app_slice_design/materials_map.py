"""Map calculator layer names onto a MaterialChoice for make_materials."""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

from common_lib.materials import MaterialChoice

from app_slice_design.setup import AppSliceSetup, LayerRow

# Labels used in the web UI that are not OpenMC material catalog names.
MATERIAL_ALIASES = {
    "Disk": "Graphite",
    "disk": "Graphite",
}


def resolve_material_name(name: str) -> str:
    trimmed = (name or "").strip()
    if not trimmed:
        return "Void"
    return MATERIAL_ALIASES.get(trimmed, trimmed)


def _first_name(rows: List[LayerRow], *preferred: str) -> str | None:
    resolved = [resolve_material_name(row.name) for row in rows]
    for want in preferred:
        for name in resolved:
            if name == want:
                return name
    for name in resolved:
        if name != "Void":
            return name
    return None


def same_material_names(left: List[LayerRow], right: List[LayerRow]) -> bool:
    names_left = [resolve_material_name(row.name) for row in left]
    names_right = [resolve_material_name(row.name) for row in right]
    return bool(names_left) and names_left == names_right


def collect_material_names(setup: AppSliceSetup, nsm_material: str) -> Set[str]:
    names: Set[str] = {resolve_material_name(nsm_material), "Void", "Graphite", "InGaAs"}
    for rows in setup.layers.values():
        for row in rows:
            names.add(resolve_material_name(row.name))
    return names


def material_choice_from_setup(setup: AppSliceSetup, nsm_material: str) -> MaterialChoice:
    layers = setup.layers
    fuel_name = _first_name(layers.get("fuel", []), "Uranium Dioxide") or "Uranium Dioxide"
    clad_name = _first_name(layers.get("fuel", []), "Graphite") or "Graphite"
    if clad_name == fuel_name:
        clad_name = "Graphite"
    reflector_name = _first_name(layers.get("reflector", []), "Graphite") or "Graphite"
    absorber_name = _first_name(layers.get("shield_absorber", []), "Boron Carbide") or "Boron Carbide"
    tpv_name = _first_name(layers.get("tpv", []), "InGaAs") or "InGaAs"
    disk_name = _first_name(layers.get("disk", []), "Graphite") or "Graphite"
    nsm = resolve_material_name(nsm_material)

    return MaterialChoice(
        moderator=reflector_name,
        moderator_cladding=reflector_name,
        neutron_absorber=absorber_name,
        neutron_reflector=reflector_name,
        bottom_reflector=reflector_name,
        rotary_axle=disk_name,
        fuel=fuel_name,
        fuel_cladding=clad_name,
        emitter=disk_name,
        photovoltaic=tpv_name,
        coolant="Void",
        coolant_cladding="Graphite",
        shaft_shield_moderator=nsm,
        outer_cold_shield_moderator=nsm,
        neutron_shield_moderator=nsm,
        shield_moderator_cladding=nsm,
        gamma_shield="Void",
        outer_empty_zone="Void",
        void="Void",
    )


def stack_with_disk(zone_rows: List[LayerRow], disk_rows: List[LayerRow]) -> List[LayerRow]:
    """Disk layers sit on every stack; total thickness is zone + disk."""
    return [LayerRow(name=row.name, cm=row.cm) for row in zone_rows] + [
        LayerRow(name=row.name, cm=row.cm) for row in disk_rows
    ]


def shared_stack_thickness_cm(setup: AppSliceSetup) -> float:
    disk = setup.layers.get("disk", [])
    disk_cm = sum(row.cm for row in disk)
    totals = []
    for key in ("fuel", "reflector", "shield_moderator", "shield_absorber", "tpv"):
        totals.append(sum(row.cm for row in setup.layers.get(key, [])) + disk_cm)
    rounded = {round(value, 2) for value in totals}
    if len(rounded) != 1:
        detail = ", ".join(f"{t:.4f}" for t in totals)
        raise ValueError(f"Layer stacks plus disk must share one thickness; got [{detail}] cm")
    return totals[0]


def fuel_and_tpv_thickness_cm(setup: AppSliceSetup) -> tuple[float, float]:
    """
    Thicknesses used as volume/thickness → face area in core characteristics.

    Fuel: total UO2 thickness (usually one slab; emissive area then ×2 for both faces).
    TPV: thickness of a *single* InGaAs sheet. Both faces are separate cells whose
    volumes are summed; dividing by the summed sheet thickness would under-count
    area by ~2× vs the website's ``2 * density * TPV_area``.
    """
    fuel_cm = 0.0
    for row in setup.layers.get("fuel", []):
        if resolve_material_name(row.name) == "Uranium Dioxide":
            fuel_cm += row.cm
    if fuel_cm <= 0:
        fuel_cm = setup.cylinder_diameter_mm / 10.0
    tpv_sheets = [
        row.cm
        for row in setup.layers.get("tpv", [])
        if resolve_material_name(row.name) == "InGaAs" and row.cm > 0
    ]
    if not tpv_sheets:
        tpv_cm = 0.02
    elif max(tpv_sheets) - min(tpv_sheets) > 1e-6:
        # Differing sheet thicknesses: use volume-weighted mean so
        # sum(V_i) / t_mean ≈ sum(V_i / t_i) when areas are similar.
        tpv_cm = sum(tpv_sheets) / len(tpv_sheets)
    else:
        tpv_cm = tpv_sheets[0]
    return fuel_cm, tpv_cm


def ensure_materials_available(
    materials_dict: Dict[str, object],
    names: Iterable[str],
) -> None:
    missing = sorted({resolve_material_name(name) for name in names} - set(materials_dict))
    if missing:
        raise ValueError(f"Materials missing from OpenMC catalog after make_materials: {missing}")
