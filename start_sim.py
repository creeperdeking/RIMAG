#!/usr/bin/env python3
"""Look up NSM material and conical pitch from a simulation spreadsheet."""

import argparse
import ast
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import get_args

from common_lib.runlib import RunMode

RUN_MODE_CHOICES = get_args(RunMode.__value__ if hasattr(RunMode, "__value__") else RunMode)

SIM_FILENAME_RE = re.compile(r"^simpaper_(\d+)_([\d.]+)\.json$", re.IGNORECASE)
SIM_PATTERN_RE = re.compile(r"^simpaper_(\d+)_\[NSM thickness\]\.json$", re.IGNORECASE)

TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
CALCEXT_NS = "urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0"
NS = {"table": TABLE_NS, "text": TEXT_NS}

SCRIPT_DIR = Path(__file__).resolve().parent
SIMULATION_SCRIPT = SCRIPT_DIR / "simulation_paper.py"
MATERIALS_PY = SCRIPT_DIR / "common_lib" / "materials.py"
RESULTSIM_JSON = SCRIPT_DIR / "resultsim.json"


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


def _format_thickness_for_filename(nsm_thickness: float) -> str:
    if abs(nsm_thickness - round(nsm_thickness)) < 1e-9:
        return str(int(round(nsm_thickness)))
    return format(nsm_thickness, "g")


def _sim_json_path(sim_index: int, nsm_thickness: float) -> Path:
    thickness_part = _format_thickness_for_filename(nsm_thickness)
    return SCRIPT_DIR / f"simpaper_{sim_index}_{thickness_part}.json"


def get_sim_block(ods_path: str | Path, sim_index: int) -> dict[str, object]:
    ods_file = Path(ods_path)
    sim_blocks: dict[int, dict[str, object]] = {}
    for sheet_name, rows in _load_sheet_rows(ods_file).items():
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

    return block


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
    block = get_sim_block(ods_file, sim_index)
    column_index = _thickness_column_index(block["thicknesses"], nsm_thickness)

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
    run_mode: RunMode | None = None,
) -> None:
    payload = {
        "nsm_material": _resolve_nsm_material(str(params["nsm"])),
        "nsm_thickness": params["nsm_thickness"],
        "conical_pitch": params["pitch"],
        "n_batches": n_batches,
    }
    if run_mode is not None:
        payload["run_mode"] = run_mode
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


def _cell_text(cell: ET.Element) -> str:
    return "".join(text.text or "" for text in cell.findall(".//text:p", NS))


def _logical_row_values(row: ET.Element) -> list[str]:
    values: list[str] = []
    for cell in row.findall("table:table-cell", NS):
        repeated = int(cell.get(f"{{{TABLE_NS}}}number-columns-repeated", 1))
        if repeated > 100 and _cell_text(cell) == "":
            break
        values.extend([_cell_text(cell)] * repeated)
    return values


def _row_label(row: ET.Element) -> str:
    values = _logical_row_values(row)
    return values[0] if values else ""


def _capture_data_columns(row: ET.Element) -> list[dict[str, str | None]]:
    columns: list[dict[str, str | None]] = []
    for cell in row.findall("table:table-cell", NS)[1:]:
        repeated = int(cell.get(f"{{{TABLE_NS}}}number-columns-repeated", 1))
        if repeated > 100 and _cell_text(cell) == "":
            break
        cell_info = {
            "style": cell.get(f"{{{TABLE_NS}}}style-name", "ce1"),
            "value_type": cell.get(f"{{{OFFICE_NS}}}value-type", "string"),
            "office_value": cell.get(f"{{{OFFICE_NS}}}value"),
            "text": _cell_text(cell),
        }
        columns.extend([cell_info.copy() for _ in range(repeated)])

    while len(columns) < 5:
        columns.append(
            {
                "style": "ce1",
                "value_type": "string",
                "office_value": None,
                "text": "",
            }
        )
    return columns[:5]


def _format_office_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return format(value, ".15g")


def _make_ods_cell(
    style_name: str,
    display_text: str,
    value_type: str,
    office_value: str | None = None,
) -> ET.Element:
    cell = ET.Element(f"{{{TABLE_NS}}}table-cell")
    cell.set(f"{{{TABLE_NS}}}style-name", style_name)
    cell.set(f"{{{OFFICE_NS}}}value-type", value_type)
    cell.set(f"{{{CALCEXT_NS}}}value-type", value_type)
    if office_value is not None:
        cell.set(f"{{{OFFICE_NS}}}value", office_value)

    paragraph = ET.SubElement(cell, f"{{{TEXT_NS}}}p")
    paragraph.text = display_text
    return cell


def _make_ods_cell_from_info(cell_info: dict[str, str | None]) -> ET.Element:
    return _make_ods_cell(
        str(cell_info["style"]),
        str(cell_info["text"]),
        str(cell_info["value_type"]),
        cell_info["office_value"],
    )


def _set_row_data_value(
    row: ET.Element,
    column_index: int,
    display_text: str,
    value_type: str,
    office_value: float | None = None,
) -> None:
    cells = row.findall("table:table-cell", NS)
    if not cells:
        return

    data_columns = _capture_data_columns(row)
    data_columns[column_index] = {
        "style": data_columns[column_index]["style"],
        "value_type": value_type,
        "office_value": None if office_value is None else _format_office_number(office_value),
        "text": display_text,
    }

    trailing_repeat = "1018"
    if len(cells) > 1:
        last_cell = cells[-1]
        repeat = last_cell.get(f"{{{TABLE_NS}}}number-columns-repeated")
        if repeat and int(repeat) > 100 and _cell_text(last_cell) == "":
            trailing_repeat = repeat

    for cell in cells[1:]:
        row.remove(cell)

    for cell_info in data_columns:
        row.append(_make_ods_cell_from_info(cell_info))

    trailing_cell = ET.SubElement(row, f"{{{TABLE_NS}}}table-cell")
    trailing_cell.set(f"{{{TABLE_NS}}}number-columns-repeated", trailing_repeat)


def _find_sim_block_rows(sheet: ET.Element, sim_index: int) -> dict[str, ET.Element]:
    target_name = f"simpaper_{sim_index}_[NSM thickness].json"
    rows = sheet.findall("table:table-row", NS)
    block_rows: dict[str, ET.Element] = {}
    in_block = False

    for row in rows:
        label = _row_label(row)
        if label == "Sim file name":
            logical_values = _logical_row_values(row)
            if len(logical_values) > 1 and logical_values[1] == target_name:
                in_block = True
                continue
            if in_block:
                break
            continue

        if not in_block or not label:
            continue

        block_rows[label] = row

    if not block_rows:
        raise ValueError(f"Could not locate simulation block for index {sim_index} in ODS content.")

    return block_rows


def _format_ddd_value(ddd: float) -> str:
    return f"{ddd:.2E}"


def _format_uncertainty_value(ddd_ci95p: float | None) -> str:
    if ddd_ci95p is None:
        return "#todo"
    return f"{ddd_ci95p * 100:.2f}%"


def load_resultsim(path: Path = RESULTSIM_JSON) -> dict[str, float | int | None]:
    if not path.is_file():
        raise FileNotFoundError(f"Simulation result file '{path}' was not found.")

    with path.open(encoding="utf-8") as result_file:
        payload = json.load(result_file)

    if "ddd" not in payload or not payload["ddd"]:
        raise ValueError(f"Simulation result file '{path}' does not contain a DDD value.")

    return {
        "ddd": float(payload["ddd"][0]),
        "ddd_ci95p": None if payload.get("ddd_ci95p") is None else float(payload["ddd_ci95p"]),
        "n_batches": int(payload["n_batches"]),
    }


def update_ods_with_results(
    ods_path: str | Path,
    sim_index: int,
    nsm_thickness: float,
    results: dict[str, float | int | None],
) -> None:
    ods_file = Path(ods_path)
    with zipfile.ZipFile(ods_file, "r") as archive:
        content_xml = archive.read("content.xml")
        other_files = [
            (info, archive.read(info.filename))
            for info in archive.infolist()
            if info.filename != "content.xml"
        ]

    root = ET.fromstring(content_xml)
    block_rows = None
    column_index = None

    for sheet in root.findall(".//table:table", NS):
        sheet_name = sheet.get(f"{{{TABLE_NS}}}name")
        if sheet_name == "General simulation settings":
            continue
        try:
            candidate_rows = _find_sim_block_rows(sheet, sim_index)
            thickness_row = candidate_rows["NSM thickness (cm)"]
            thicknesses = [float(value) for value in _logical_row_values(thickness_row)[1:6]]
            column_index = _thickness_column_index(thicknesses, nsm_thickness)
            block_rows = candidate_rows
            break
        except ValueError:
            continue

    if block_rows is None or column_index is None:
        raise ValueError(
            f"Could not locate ODS rows to update for simulation index {sim_index} "
            f"and NSM thickness {nsm_thickness} cm."
        )

    ddd_value = float(results["ddd"])
    n_batches_value = int(results["n_batches"])
    ddd_ci95p = None if results["ddd_ci95p"] is None else float(results["ddd_ci95p"])

    row_updates = {
        next(label for label in block_rows if label.startswith("DDD 10")): (
            _format_ddd_value(ddd_value),
            "float",
            ddd_value,
        ),
        "Number of batches": (
            str(n_batches_value),
            "float",
            float(n_batches_value),
        ),
        "Uncertainty": (
            _format_uncertainty_value(ddd_ci95p),
            "percentage" if ddd_ci95p is not None else "string",
            ddd_ci95p,
        ),
    }

    for label, (display_text, value_type, office_value) in row_updates.items():
        if label not in block_rows:
            raise ValueError(f"Missing '{label}' row for simulation index {sim_index} in ODS.")
        _set_row_data_value(
            block_rows[label],
            column_index,
            display_text,
            value_type,
            office_value,
        )

    updated_content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    temp_path = ods_file.with_suffix(".ods.tmp")
    with zipfile.ZipFile(temp_path, "w") as archive:
        archive.writestr("content.xml", updated_content)
        for info, data in other_files:
            archive.writestr(info, data)
    temp_path.replace(ods_file)


def _parse_batches_value(batches_value: str | None) -> int | None:
    if _is_todo(batches_value):
        return None
    try:
        n_batches = int(str(batches_value).strip())
    except ValueError:
        return None
    if n_batches <= 0:
        return None
    return n_batches


def _pending_columns(block: dict[str, object]) -> tuple[list[tuple[float, int]], list[str]]:
    pending: list[tuple[float, int]] = []
    warnings: list[str] = []
    thicknesses = block["thicknesses"]

    for column_index, thickness in enumerate(thicknesses):
        batches_value = _value_at_column(block["n_batches"], column_index)
        ddd_value = _value_at_column(block["ddd_10_years"], column_index)
        uncertainty_value = _value_at_column(block["uncertainty"], column_index)
        n_batches = _parse_batches_value(batches_value)

        if n_batches is None:
            if _is_todo(batches_value):
                warnings.append(
                    f"Skipping NSM thickness {thickness} cm: missing number of batches."
                )
            else:
                warnings.append(
                    f"Skipping NSM thickness {thickness} cm: invalid number of batches "
                    f"('{batches_value}')."
                )
            continue

        if not _is_todo(ddd_value) and not _is_todo(uncertainty_value):
            continue

        pending.append((float(thickness), n_batches))

    return pending, warnings


def run_single_simulation(
    ods_path: str | Path,
    params: dict[str, str | float | int],
    n_batches: int,
    sim_json_path: Path | None = None,
    run_mode: RunMode | None = None,
) -> int:
    sim_index = int(params["sim_index"])
    nsm_thickness = float(params["nsm_thickness"])
    json_path = sim_json_path or _sim_json_path(sim_index, nsm_thickness)

    write_sim_json(json_path, params, n_batches, run_mode=run_mode)
    print(f"Wrote simulation parameters to '{json_path}'", flush=True)
    sys.stdout.flush()

    exit_code = run_simulation(json_path)
    if exit_code != 0:
        return exit_code

    results = load_resultsim()
    update_ods_with_results(ods_path, sim_index, nsm_thickness, results)
    print(
        f"Updated '{ods_path}' for NSM thickness {nsm_thickness} cm "
        f"with results from '{RESULTSIM_JSON.name}'."
    )
    return 0


def run_pending_simulations(
    ods_path: str | Path,
    sim_index: int,
    run_mode: RunMode | None = None,
) -> tuple[int, int]:
    block = get_sim_block(ods_path, sim_index)
    pending, warnings = _pending_columns(block)

    print(f"NSM: {block['nsm']}")
    print(f"Pitch: {block['pitch']}")

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if not pending:
        print(f"No pending simulations for index {sim_index}.")
        return 0, 0

    print(f"Running {len(pending)} pending simulation(s) for index {sim_index}...")

    for nsm_thickness, n_batches in pending:
        params = {
            "sim_index": sim_index,
            "nsm_thickness": nsm_thickness,
            "nsm": block["nsm"],
            "pitch": float(block["pitch"]),
        }
        sim_json_path = _sim_json_path(sim_index, nsm_thickness)
        print(
            f"\nStarting {sim_json_path.name} with {n_batches} batches "
            f"(NSM thickness {nsm_thickness} cm)...",
            flush=True,
        )
        try:
            exit_code = run_single_simulation(
                ods_path, params, n_batches, sim_json_path, run_mode=run_mode
            )
        except (ValueError, FileNotFoundError, zipfile.BadZipFile, KeyError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1, 0

        if exit_code != 0:
            print(
                f"Simulation failed for {sim_json_path.name} with exit code {exit_code}.",
                file=sys.stderr,
            )
            return exit_code, 0

    print(f"\nFinished all pending simulations for index {sim_index}.")
    return 0, len(pending)


def _format_resultsim_for_notification(path: Path = RESULTSIM_JSON) -> str:
    if not path.is_file():
        return f"({path.name} not found)"
    return path.read_text(encoding="utf-8").strip()


def _completion_message_for_batch(sim_index: int, pending_count: int) -> str:
    if pending_count == 0:
        return f"No pending simulations were found for index {sim_index}."
    return (
        f"All {pending_count} pending simulation(s) for index {sim_index} have finished.\n\n"
        f"{RESULTSIM_JSON.name}:\n{_format_resultsim_for_notification()}"
    )


def _completion_message_for_single(sim_json_path: Path) -> str:
    return (
        f"Simulation {sim_json_path.name} has finished and the ODS file was updated.\n\n"
        f"{RESULTSIM_JSON.name}:\n{_format_resultsim_for_notification()}"
    )


def notify_completion(title: str, message: str) -> None:
    """Show a loud, visible popup when the script finishes successfully."""
    print("\a", end="", flush=True)

    notify_path = SCRIPT_DIR / ".notify_popup.json"
    notify_path.write_text(
        json.dumps({"title": title, "message": message}, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        win_path = subprocess.check_output(
            ["wslpath", "-w", str(notify_path.resolve())],
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        win_path = str(notify_path.resolve())

    win_path_escaped = win_path.replace("'", "''")
    powershell_command = (
        f"$data = Get-Content -LiteralPath '{win_path_escaped}' -Raw -Encoding UTF8 | ConvertFrom-Json; "
        "Add-Type @'"
        "\nusing System;"
        "\nusing System.Runtime.InteropServices;"
        "\npublic static class NativeMessageBox {"
        "\n    [DllImport(\"user32.dll\", CharSet = CharSet.Unicode)]"
        "\n    public static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);"
        "\n}"
        "\n'@;"
        "[System.Media.SystemSounds]::Exclamation.Play();"
        "Start-Sleep -Milliseconds 200;"
        "$flags = 0x00000040 -bor 0x00040000 -bor 0x00010000 -bor 0x00001000;"
        "[NativeMessageBox]::MessageBoxW([IntPtr]::Zero, $data.message, $data.title, $flags) | Out-Null"
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", powershell_command],
            check=False,
            timeout=120,
        )
        if result.returncode == 0:
            return
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    finally:
        notify_path.unlink(missing_ok=True)

    try:
        subprocess.run(
            ["notify-send", "-u", "critical", title, message],
            check=False,
        )
        return
    except FileNotFoundError:
        pass

    banner = "=" * 60
    print(f"\n{banner}\n{title}\n{message}\n{banner}\n", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Look up NSM material and conical pitch from a simulation spreadsheet."
    )
    parser.add_argument("ods_path", help="Path to the simulation spreadsheet (.ods)")
    parser.add_argument(
        "target",
        help="Simulation index (batch mode) or simpaper_<index>_<NSM thickness>.json path",
    )
    parser.add_argument(
        "n_batches",
        nargs="?",
        type=int,
        help="Number of batches (required when target is a JSON file)",
    )
    parser.add_argument(
        "--run-mode",
        choices=RUN_MODE_CHOICES,
        default=None,
        help="Override the simulation run mode (default: keff in simulation script)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    ods_path = args.ods_path
    run_mode: RunMode | None = args.run_mode

    if args.n_batches is None:
        try:
            sim_index = int(args.target)
            if sim_index <= 0:
                raise ValueError
        except ValueError:
            print(
                f"Error: Invalid simulation index '{args.target}'. Expected a positive integer.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            exit_code, pending_count = run_pending_simulations(
                ods_path, sim_index, run_mode=run_mode
            )
        except (ValueError, FileNotFoundError, zipfile.BadZipFile, KeyError) as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)

        if exit_code == 0:
            notify_completion(
                "RIMAEL simulations complete",
                _completion_message_for_batch(sim_index, pending_count),
            )
        sys.exit(exit_code)

    sim_json_path = Path(args.target)
    n_batches = args.n_batches

    try:
        params = lookup_sim_parameters(ods_path, sim_json_path)
    except (ValueError, FileNotFoundError, zipfile.BadZipFile, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"NSM: {params['nsm']}")
    print(f"Pitch: {params['pitch']}")
    print(_format_metric("Number of batches", params["n_batches"]))
    print(_format_metric("Uncertainty", params["uncertainty"]))
    print(_format_metric("DDD 10 years (MeV/g)", params["ddd_10_years"]))

    if n_batches <= 0:
        print(
            f"Error: Invalid number of batches '{n_batches}'. Expected a positive integer.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        exit_code = run_single_simulation(
            ods_path, params, n_batches, sim_json_path, run_mode=run_mode
        )
    except (ValueError, FileNotFoundError, zipfile.BadZipFile, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    if exit_code == 0:
        notify_completion(
            "RIMAEL simulation complete",
            _completion_message_for_single(sim_json_path),
        )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
