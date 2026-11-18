"""Material library lookups for colors, compositions, and densities."""

from __future__ import annotations

import sys
from pathlib import Path


def _project_root():
    return Path(__file__).resolve().parents[2]


def material_library(enrichment_pct: float):
    """Compositions, densities, and colors from common_lib.materials."""
    import sys

    root = str(_project_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from common_lib.materials import material_definitions
    except ModuleNotFoundError:
        return {}, {}
    return material_definitions(enrichment_pct)


def _library_entry(name: str, specs: dict, mixed: dict):
    if name in specs:
        return specs[name], None
    base, separator, suffix = name.rpartition(" ")
    if separator and suffix.isdigit() and base in specs:
        return specs[base], None
    mix = mixed.get(name)
    if mix is None and separator and suffix.isdigit():
        mix = mixed.get(base)
    return None, mix


def _composition_text(spec) -> str:
    parts = []
    for part in spec.composition:
        proportion = part.proportion
        amount = "" if proportion in (None, 1) else f" {proportion:.4g}"
        enrichment = ""
        if part.enrichment is not None:
            enrichment = f" ({part.enrichment:.4g}% enriched)"
        parts.append(f"{part.atom.name}{amount}{enrichment}")
    return ", ".join(parts)


def material_fact(name: str, specs: dict, mixed: dict) -> dict | None:
    """Color, composition, and density for one library material. Disk is not in the library."""
    spec, mix = _library_entry(name, specs, mixed)
    if spec is not None:
        return {
            "color": spec.color or "orange",
            "composition": _composition_text(spec),
            "density": spec.density,
        }
    if mix is None:
        return {"color": "black", "composition": "", "density": None} if name == "Disk" else None
    weights = [w for w in mix.proportions if w > 0]
    if not weights:
        return None
    volume = 0.0
    described = []
    color = "orange"
    for component, proportion in zip(mix.materials, mix.proportions):
        component_spec = specs.get(component)
        if component_spec is None or proportion <= 0:
            return None
        if component == mix.materials[0] and component_spec.color:
            color = component_spec.color
        volume += proportion / component_spec.density
        described.append(f"{proportion:.4g} {component}")
    total = sum(mix.proportions)
    return {
        "color": color,
        "composition": " + ".join(described),
        "density": total / volume if volume else None,
    }


def material_lines(rows: list[dict], specs: dict, mixed: dict) -> list[str]:
    lines = []
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        fact = material_fact(name, specs, mixed)
        if fact is None or not fact["composition"]:
            continue
        density = fact["density"]
        density_text = f" · {density:.4g} g/cm³" if density is not None else ""
        lines.append(f"{name}: {fact['composition']}{density_text}")
    return lines
