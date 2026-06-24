#!/usr/bin/env python3
"""Look up NSM material and conical pitch from a simulation spreadsheet."""

import ast
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

SIM_FILENAME_RE = re.compile(r"^simpaper_(\d+)_([\d.]+)\.json$", re.IGNORECASE)
SIM_PATTERN_RE = re.compile(r"^simpaper_(\d+)_\[NSM thickness\]\.json$", re.IGNORECASE)

TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS = {"table": TABLE_NS, "text": TEXT_NS}

SCRIPT_DIR = Path(__file__).resolve().parent
SIMULATION_SCRIPT = SCRIPT_DIR / "simulation_frustum.py"
MATERIALS_PY = SCRIPT_DIR / "common_lib" / "materials.py"


def _row_cells(row: ET.Element) -> list[str]:
    cells: list[str] = []
    for cell in row.findall("table:table-cell", NS):
        repeated = int(cell.get(f"{{{TABLE_NS}}}number-columns-repeated", 1))
        value = "".join(text.text or "" for text in cell.findall(".//text:p", NS))
        cells.extend([value] * repeated)
    return cells


def _load_sheet_rows(ods_path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(ods_path) as archive:
        root = ET.fromstring(archive.read("content.xml"))

    sheets: dict[str, list[list[str]]] = {}
    for sheet in root.findall(".//table:table", NS):
        name = sheet.get(f"{{{TABLE_NS}}}name")
        if not name:
            continue
        rows = [_row_cells(row) for row in sheet.findall("table:table-row", NS)]
        sheets[name] = rows
    return sheets


def _trim_row(values: list[str]) -> list[str]:
    trimmed = list(values)
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


def _parse_sim_blocks(rows: list[list[str]]) -> dict[int, dict[str, object]]:
    blocks: dict[int, dict[str, object]] = {}

    for index, cells in enumerate(rows):
        if len(cells) < 2 or cells[0] != "Sim file name":
            continue

        pattern_match = SIM_PATTERN_RE.match(cells[1])
        if not pattern_match:
            continue

        sim_index = int(pattern_match.group(1))
        nsm = ""
        pitch = ""
        thicknesses: list[float] = []
        ddd_values: list[str] = []
        batch_values: list[str] = []
        uncertainty_values: list[str] = []

        for follow_up in rows[index + 1 :]:
            if len(follow_up) >= 2 and follow_up[0] == "Sim file name":
                break
            if len(follow_up) < 2:
                continue
            label = follow_up[0].strip()
            row_values = _trim_row(follow_up[1:])
            if label == "NSM:":
                nsm = follow_up[1].strip()
            elif label == "Pitch":
                pitch = follow_up[1].strip()
            elif label == "NSM thickness (cm)":
                thicknesses = [float(value) for value in row_values]
            elif label.startswith("DDD 10"):
                ddd_values = row_values
            elif label == "Number of batches":
                batch_values = row_values
            elif label == "Uncertainty":
                uncertainty_values = row_values

        blocks[sim_index] = {
            "nsm": nsm,
            "pitch": pitch,
            "thicknesses": thicknesses,
            "ddd_10_years": ddd_values,
            "n_batches": batch_values,
            "uncertainty": uncertainty_values,
        }

    return blocks


def _thickness_column_index(thicknesses: list[float], nsm_thickness: float) -> int:
    for index, thickness in enumerate(thicknesses):
        if abs(thickness - nsm_thickness) < 1e-9:
            return index
    available = ", ".join(str(thickness) for thickness in thicknesses)
    raise ValueError(
        f"No column found for NSM thickness {nsm_thickness} cm. "
        f"Available thicknesses: {available}"
    )


def _value_at_column(values: list[str], column_index: int) -> str | None:
    if column_index >= len(values):
        return None
    return values[column_index].strip()


def _is_todo(value: str | None) -> bool:
    return value is None or value.lower() == "#todo"


def lookup_sim_parameters(ods_path: str | Path, sim_json_name: str | Path) -> dict[str, str | float | int]:
    ods_file = Path(ods_path)
    sim_name = Path(sim_json_name).name

    filename_match = SIM_FILENAME_RE.match(sim_name)
    if not filename_match:
        raise ValueError(
            f"Invalid simulation file name '{sim_name}'. "
            "Expected format: simpaper_<sim index>_<NSM thickness>.json"
        )

    sim_index = int(filename_match.group(1))
    nsm_thickness = float(filename_match.group(2))

    sheets = _load_sheet_rows(ods_file)
    sim_blocks: dict[int, dict[str, str]] = {}
    for sheet_name, rows in sheets.items():
        if sheet_name == "General simulation settings":
            continue
        sim_blocks.update(_parse_sim_blocks(rows))

    if sim_index not in sim_blocks:
        known = ", ".join(str(index) for index in sorted(sim_blocks))
        raise ValueError(
            f"No simulation block found for index {sim_index} in '{ods_file}'. "
            f"Known indices: {known}"
        )

    block = sim_blocks[sim_index]
    if not block["nsm"] or not block["pitch"]:
        raise ValueError(
            f"Incomplete data for simulation index {sim_index} in '{ods_file}'."
        )

    thicknesses = block["thicknesses"]
    if not thicknesses:
        raise ValueError(
            f"No NSM thickness columns found for simulation index {sim_index}."
        )

    column_index = _thickness_column_index(thicknesses, nsm_thickness)

    return {
        "sim_index": sim_index,
        "nsm_thickness": nsm_thickness,
        "nsm": block["nsm"],
        "pitch": float(block["pitch"]),
        "ddd_10_years": _value_at_column(block["ddd_10_years"], column_index),
        "n_batches": _value_at_column(block["n_batches"], column_index),
        "uncertainty": _value_at_column(block["uncertainty"], column_index),
    }


def _format_metric(label: str, value: str | None) -> str:
    if _is_todo(value):
        return f"{label}: value needs to be calculated"
    return f"{label}: {value}"


@lru_cache(maxsize=1)
def _get_material_names() -> frozenset[str]:
    module = ast.parse(MATERIALS_PY.read_text(encoding="utf-8"))
    names: set[str] = set()

    def add_dict_keys(dict_node: ast.Dict) -> None:
        for key in dict_node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                names.add(key.value)

    for node in ast.walk(module):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in {"materials_def", "material_mixed_def"} and isinstance(
                node.value, ast.Dict
            ):
                add_dict_keys(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id in {"materials_def", "material_mixed_def"}
                    and isinstance(node.value, ast.Dict)
                ):
                    add_dict_keys(node.value)

    if not names:
        raise RuntimeError(f"Could not extract material names from '{MATERIALS_PY}'.")

    return frozenset(names)


def _resolve_nsm_material(spreadsheet_nsm: str) -> str:
    material_name = spreadsheet_nsm.strip()
    material_names = _get_material_names()
    if material_name not in material_names:
        known = ", ".join(sorted(material_names))
        raise ValueError(
            f"Unknown NSM material '{material_name}'. "
            f"It must exactly match a material name defined in materials.py. "
            f"Known materials: {known}"
        )
    return material_name


def write_sim_json(
    sim_json_path: Path,
    params: dict[str, str | float | int],
    n_batches: int,
) -> None:
    payload = {
        "nsm_material": _resolve_nsm_material(str(params["nsm"])),
        "nsm_thickness": params["nsm_thickness"],
        "conical_pitch": params["pitch"],
        "n_batches": n_batches,
    }
    with sim_json_path.open("w", encoding="utf-8") as json_file:
        json.dump(payload, json_file, indent=4)
        json_file.write("\n")


def run_simulation(sim_json_path: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(SIMULATION_SCRIPT), str(sim_json_path)],
        cwd=SCRIPT_DIR,
        check=False,
    )
    return result.returncode


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print(
            "Usage: python start_sim.py <simulation_data.ods> "
            "<simpaper_<index>_<NSM thickness>.json> [n_batches]",
            file=sys.stderr,
        )
        sys.exit(1)

    sim_json_path = Path(sys.argv[2])
    n_batches_arg = sys.argv[3] if len(sys.argv) == 4 else None

    try:
        params = lookup_sim_parameters(sys.argv[1], sim_json_path)
    except (ValueError, FileNotFoundError, zipfile.BadZipFile, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"NSM: {params['nsm']}")
    print(f"Pitch: {params['pitch']}")
    print(_format_metric("Number of batches", params["n_batches"]))
    print(_format_metric("Uncertainty", params["uncertainty"]))
    print(_format_metric("DDD 10 years (MeV/g)", params["ddd_10_years"]))

    if n_batches_arg is None:
        return

    try:
        n_batches = int(n_batches_arg)
        if n_batches <= 0:
            raise ValueError
    except ValueError:
        print(
            f"Error: Invalid number of batches '{n_batches_arg}'. Expected a positive integer.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        write_sim_json(sim_json_path, params, n_batches)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote simulation parameters to '{sim_json_path}'", flush=True)
    sys.stdout.flush()
    sys.exit(run_simulation(sim_json_path))


if __name__ == "__main__":
    main()
