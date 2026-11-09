"""Save and load reactor-slice configurations as JSON files."""

from __future__ import annotations

import json
import re
from pathlib import Path

SAVE_DIR = Path(__file__).resolve().parent / "save"

# key -> (low, high, step, default). Matches the numeric controls.
NUMERIC_FIELDS = {
    "a": (1.0, 4.0, 0.1, 2.0),
    "abs": (0.01, 0.5, 0.01, 0.01),
    "refl": (0.1, 1.0, 0.1, 0.5),
    "b_pct": (1.0, 100.0, 1.0, 100.0),
    "w": (0.3, 3.0, 0.1, 1.0),
    "ratio_pct": (10.0, 50.0, 1.0, 30.0),
    "tpv_density": (0.01, 3.0, 0.01, 0.89),
    "enrichment_pct": (0.1, 20.0, 0.1, 5.0),
    "tpv_eff_pct": (10.0, 50.0, 1.0, 33.0),
    "stack_m": (0.1, 20.0, 0.1, 1.0),
    "columns": (1.0, 3.0, 1.0, 1.0),
}

RELOAD_FRACTIONS = ("1/2", "1/3", "1/4", "1/5")

LAYER_IDS = ("disk", "fuel", "reflector", "shield_moderator", "shield_absorber", "tpv")
LAYER_TITLES = {
    "disk": "Disk layer",
    "fuel": "Fuel layer",
    "reflector": "Reflector layer",
    "shield_moderator": "Shield moderator",
    "shield_absorber": "Shield absorber",
    "tpv": "TPV layer",
}
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE)


class ConfigurationError(ValueError):
    """A configuration name or file cannot be used."""


def snap(value: float, low: float, high: float, step: float) -> float:
    """Clamp onto a slider range and its step size."""
    value = min(high, max(low, value))
    if step <= 0:
        return value
    snapped = low + round((value - low) / step) * step
    return min(high, max(low, round(snapped, 10)))


def configuration_stem(name: str) -> str:
    """File stem for a user-typed name, with no path separators."""
    stem = name.strip()
    if not stem:
        raise ConfigurationError("Enter a configuration name.")
    if stem.lower().endswith(".json"):
        stem = stem[:-5].strip()
    stem = stem.rstrip(" .")
    if (
        not stem
        or stem in {".", ".."}
        or ".." in stem
        or any(char in stem for char in '/\\:*?"<>|')
        or _RESERVED.match(stem)
    ):
        raise ConfigurationError("Use a name without folders or special characters.")
    return stem


def configuration_path(name: str) -> Path:
    """JSON path inside the save folder."""
    stem = configuration_stem(name)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = (SAVE_DIR / f"{stem}.json").resolve()
    if path.parent != SAVE_DIR.resolve():
        raise ConfigurationError("Use a name without folders or special characters.")
    return path


def list_configurations() -> list[str]:
    """Saved configuration names, without the .json suffix."""
    if not SAVE_DIR.is_dir():
        return []
    names = [path.stem for path in SAVE_DIR.glob("*.json") if path.is_file()]
    return sorted(names, key=str.lower)


def normalize(data: object) -> dict:
    """Slider values and layer stacks clamped onto the controls."""
    if not isinstance(data, dict):
        raise ConfigurationError("That file is not a configuration.")
    values: dict = {}
    for key, (low, high, step, default) in NUMERIC_FIELDS.items():
        raw = data.get(key, default)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            number = default
        # Earlier files stored this density in kW/m². 1 W/cm² = 10 kW/m².
        if key == "tpv_density" and number > high:
            number /= 10
        values[key] = snap(number, low, high, step)
    reload = data.get("reload_fraction", "1/4")
    values["reload_fraction"] = reload if reload in RELOAD_FRACTIONS else "1/4"
    dims = data.get("dims", True)
    if isinstance(dims, str):
        values["dims"] = dims.strip().lower() in {"1", "true", "yes"}
    else:
        values["dims"] = bool(dims)
    values["layers"] = _layers(data.get("layers"))
    return values


def _layers(raw: object) -> dict[str, list[dict]]:
    source = raw if isinstance(raw, dict) else {}
    layers: dict[str, list[dict]] = {}
    for group_id in LAYER_IDS:
        parsed = []
        rows = source.get(group_id) or []
        if isinstance(rows, list):
            for item in rows:
                if not isinstance(item, dict):
                    continue
                try:
                    cm = float(item.get("cm"))
                except (TypeError, ValueError):
                    continue
                name = item.get("name", item.get("n", ""))
                parsed.append(
                    {
                        "name": str(name).strip() or LAYER_TITLES[group_id],
                        "cm": round(min(20.0, max(0.01, cm)), 4),
                    }
                )
        layers[group_id] = parsed or [{"name": LAYER_TITLES[group_id], "cm": 1.0}]
    return layers


def save_configuration(name: str, data: dict) -> Path:
    """Write a configuration, replacing an existing file of the same name."""
    path = configuration_path(name)
    payload = normalize(data)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def delete_configuration(name: str) -> str:
    """Remove a configuration file. Returns the deleted name."""
    path = configuration_path(name)
    if not path.is_file():
        raise ConfigurationError(f"There is no saved configuration named {path.stem}.")
    path.unlink()
    return path.stem


def load_configuration(name: str) -> dict:
    """Read a configuration from the save folder."""
    path = configuration_path(name)
    if not path.is_file():
        raise ConfigurationError(f"There is no saved configuration named {path.stem}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError("That file is not a configuration.") from error
    return normalize(data)
