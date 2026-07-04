#!/usr/bin/env python3
"""Build pitch and materials curve CSVs from a RIMAEL simulation spreadsheet."""

import argparse
import ast
import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

SHEET_GENERAL = "General simulation settings"
SHEET_PITCH = "Different conical pitches simulations"
SHEET_MATERIALS = "Different NSM simulations"

PITCH_CSV = SCRIPT_DIR / "pitch_sim_curve.csv"
MATERIALS_CSV = SCRIPT_DIR / "materials_sim_curve.csv"

X_COLUMN = "Neutron Shield Moderator thickness (cm)"
OUTPUT_THICKNESSES = [0.5, 25, 50, 75, 100, 125]

SIM_PATTERN_RE = re.compile(r"^simpaper_(\d+)_\[NSM thickness\]\.json$", re.IGNORECASE)

TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS = {"table": TABLE_NS, "text": TEXT_NS}

MATERIAL_TO_CSV = {
    "Graphite": "Graphite",
    "Beryllium Oxide": "BeO",
    "High Density PolyEthylene": "HDPE",
    "Titanium Hydride": "TiH2",
    "Water": "Water",
    "Light Water": "Water",
}


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
                thicknesses = [
                    _parse_thickness_value(value)
                    for value in row_values
                    if value.strip()
                ]
            elif label.startswith("DDD 10"):
                ddd_values = row_values
            elif label == "Uncertainty":
                uncertainty_values = row_values

        blocks[sim_index] = {
            "nsm": nsm,
            "pitch": pitch,
            "thicknesses": thicknesses,
            "ddd_10_years": ddd_values,
            "uncertainty": uncertainty_values,
        }

    return blocks


def _format_ddd_value(ddd: float) -> str:
    return f"{ddd:.2E}"


def _parse_thickness_value(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("empty thickness value")
    try:
        return float(value)
    except ValueError:
        match = re.match(r"^([\d.]+)", value)
        if match:
            return float(match.group(1))
        raise ValueError(f"invalid thickness value: {value!r}") from None


def _parse_bracket_list(value: str) -> list:
    value = value.strip()
    if not value.startswith("[") or not value.endswith("]"):
        raise ValueError(f"Expected bracket list, got: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return [part.strip() for part in inner.split(",") if part.strip()]


def _find_cell_value(rows: list[list[str]], label: str) -> str | None:
    for row in rows:
        for index, cell in enumerate(row):
            if cell.strip() == label and index + 1 < len(row):
                return row[index + 1].strip()
    return None


def _read_sheet1_order(rows: list[list[str]]) -> tuple[list[float], list[str]]:
    pitch_raw = _find_cell_value(rows, "Conical pitch")
    materials_raw = _find_cell_value(rows, "Tested neutron moderator materials")

    if pitch_raw is None:
        raise ValueError(
            f"Could not find 'Conical pitch' list on '{SHEET_GENERAL}'."
        )
    if materials_raw is None:
        raise ValueError(
            f"Could not find 'Tested neutron moderator materials' list on "
            f"'{SHEET_GENERAL}'."
        )

    pitch_order = [float(value) for value in _parse_bracket_list(pitch_raw)]
    material_order = [str(value).strip() for value in _parse_bracket_list(materials_raw)]
    return pitch_order, material_order


def _is_todo(value: str) -> bool:
    return value.strip().lower() == "#todo"


def _format_ddd_cell(value: str, warnings: list[str], context: str) -> str:
    if _is_todo(value):
        warnings.append(f"{context}: DDD is #todo")
        return value.strip()
    try:
        return _format_ddd_value(float(value))
    except ValueError:
        warnings.append(f"{context}: invalid DDD value {value!r}")
        return value.strip()


def _format_uncertainty_cell(value: str, warnings: list[str], context: str) -> str:
    if _is_todo(value):
        warnings.append(f"{context}: uncertainty is #todo")
        return value.strip()

    text = value.strip()
    if text.endswith("%"):
        try:
            return f"{float(text[:-1]):.2f}%"
        except ValueError:
            warnings.append(f"{context}: invalid uncertainty {value!r}")
            return text

    try:
        return f"{float(text):.2f}%"
    except ValueError:
        warnings.append(f"{context}: invalid uncertainty {value!r}")
        return text


def _thickness_index(thicknesses: list[float], target: float) -> int | None:
    for index, thickness in enumerate(thicknesses):
        if thickness == target:
            return index
    return None


def _block_values_at_thickness(
    block: dict[str, object],
    thickness: float,
    warnings: list[str],
    context: str,
) -> tuple[str, str]:
    thicknesses = block["thicknesses"]
    index = _thickness_index(thicknesses, thickness)
    if index is None:
        warnings.append(f"{context}: thickness {thickness:g} cm not in sim block")
        return "#todo", "#todo"

    ddd_values = block["ddd_10_years"]
    uncertainty_values = block["uncertainty"]

    if index >= len(ddd_values) or index >= len(uncertainty_values):
        warnings.append(f"{context}: missing value at thickness {thickness:g} cm")
        return "#todo", "#todo"

    return (
        _format_ddd_cell(str(ddd_values[index]), warnings, context),
        _format_uncertainty_cell(str(uncertainty_values[index]), warnings, context),
    )


def _build_pitch_rows(
    pitch_order: list[float],
    blocks: dict[int, dict[str, object]],
    warnings: list[str],
) -> tuple[list[str], list[list[str]]]:
    by_pitch: dict[float, dict[str, object]] = {}
    for block in blocks.values():
        by_pitch[float(block["pitch"])] = block

    series: list[tuple[str, dict[str, object]]] = []
    for pitch in pitch_order:
        block = by_pitch.get(pitch)
        if block is None:
            warnings.append(f"Pitch {pitch:g}° is listed on sheet 1 but has no sim block.")
            continue
        label = format(pitch, "g")
        series.append((label, block))

    if not series:
        raise ValueError(f"No pitch simulation blocks found on '{SHEET_PITCH}'.")

    header = [X_COLUMN]
    for label, _ in series:
        header.extend([label, f"{label}%"])

    rows: list[list[str]] = []
    for thickness in OUTPUT_THICKNESSES:
        row = [format(thickness, "g")]
        for label, block in series:
            context = f"pitch {label}°, thickness {thickness:g} cm"
            ddd, uncertainty = _block_values_at_thickness(
                block, thickness, warnings, context
            )
            row.extend([ddd, uncertainty])
        rows.append(row)

    return header, rows


def _resolve_material_block(
    material_name: str,
    blocks_by_nsm: dict[str, dict[str, object]],
) -> dict[str, object] | None:
    if material_name in blocks_by_nsm:
        return blocks_by_nsm[material_name]

    if material_name == "Water":
        return blocks_by_nsm.get("Light Water")

    return None


def _build_material_rows(
    material_order: list[str],
    blocks: dict[int, dict[str, object]],
    warnings: list[str],
) -> tuple[list[str], list[list[str]]]:
    blocks_by_nsm = {str(block["nsm"]): block for block in blocks.values()}

    known_nsm = set(MATERIAL_TO_CSV)
    for nsm in blocks_by_nsm:
        if nsm not in known_nsm:
            warnings.append(f"Skipping unknown NSM material: {nsm}")

    series: list[tuple[str, dict[str, object]]] = []
    for material_name in material_order:
        block = _resolve_material_block(material_name, blocks_by_nsm)
        if block is None:
            warnings.append(
                f"Material {material_name!r} is listed on sheet 1 but has no sim block."
            )
            continue

        csv_label = MATERIAL_TO_CSV.get(material_name) or MATERIAL_TO_CSV.get(
            str(block["nsm"]), str(block["nsm"])
        )
        series.append((csv_label, block))

    if not series:
        raise ValueError(f"No material simulation blocks found on '{SHEET_MATERIALS}'.")

    header = [X_COLUMN]
    for label, _ in series:
        header.extend([label, f"{label}%"])

    rows: list[list[str]] = []
    for thickness in OUTPUT_THICKNESSES:
        row = [format(thickness, "g")]
        for label, block in series:
            context = f"material {label}, thickness {thickness:g} cm"
            ddd, uncertainty = _block_values_at_thickness(
                block, thickness, warnings, context
            )
            row.extend([ddd, uncertainty])
        rows.append(row)

    return header, rows


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def make_curve_csvs(ods_path: Path) -> None:
    if not ods_path.is_file():
        raise FileNotFoundError(f"ODS file not found: {ods_path}")

    sheets = _load_sheet_rows(ods_path)
    if SHEET_GENERAL not in sheets:
        raise ValueError(f"Missing sheet '{SHEET_GENERAL}' in '{ods_path}'.")
    if SHEET_PITCH not in sheets:
        raise ValueError(f"Missing sheet '{SHEET_PITCH}' in '{ods_path}'.")
    if SHEET_MATERIALS not in sheets:
        raise ValueError(f"Missing sheet '{SHEET_MATERIALS}' in '{ods_path}'.")

    pitch_order, material_order = _read_sheet1_order(sheets[SHEET_GENERAL])
    warnings: list[str] = []

    pitch_header, pitch_rows = _build_pitch_rows(
        pitch_order,
        _parse_sim_blocks(sheets[SHEET_PITCH]),
        warnings,
    )
    materials_header, materials_rows = _build_material_rows(
        material_order,
        _parse_sim_blocks(sheets[SHEET_MATERIALS]),
        warnings,
    )

    _write_csv(PITCH_CSV, pitch_header, pitch_rows)
    _write_csv(MATERIALS_CSV, materials_header, materials_rows)

    pitch_columns = (len(pitch_header) - 1) // 2
    material_columns = (len(materials_header) - 1) // 2

    print(f"Input: {ods_path}")
    print(f"Wrote {PITCH_CSV} ({pitch_columns} pitch columns, {len(pitch_rows)} rows)")
    print(
        f"Wrote {MATERIALS_CSV} "
        f"({material_columns} material columns, {len(materials_rows)} rows)"
    )

    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read a RIMAEL simulation spreadsheet (.ods) and write "
            "pitch_sim_curve.csv and materials_sim_curve.csv to scripts/."
        )
    )
    parser.add_argument("ods_path", type=Path, help="Path to the simulation spreadsheet")
    args = parser.parse_args()
    make_curve_csvs(args.ods_path.resolve())


if __name__ == "__main__":
    main()
