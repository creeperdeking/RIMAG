"""Rasterize runs/default OpenMC geometry to a PNG (plot mode, no transport)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import openmc

from app_slice_design.plot_defaults import (
    PLOT_DEFAULTS_NAME,
    view_size_for_basis,
)
from common_lib.materials import rgb_for_openmc_material_name

# Avoid 1-pixel-tall images when Z span << XY span (xz / yz slices).
MIN_AXIS_PIXELS = 48


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--basis",
        choices=("xy", "xz", "yz"),
        default="xy",
        help="Plot plane (default: xy)",
    )
    parser.add_argument(
        "--origin",
        nargs=3,
        type=float,
        default=None,
        metavar=("X", "Y", "Z"),
        help="Plot origin in cm (default: bbox center from plot_defaults.json)",
    )
    parser.add_argument(
        "--width",
        type=float,
        default=None,
        help="Horizontal plot width in cm (default: auto from bbox)",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=None,
        help="Vertical plot height in cm (default: auto from bbox)",
    )
    parser.add_argument(
        "--pixels",
        type=int,
        default=600,
        help="Max pixels on the longer side (default: 600, cap: 1000)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="plot_slice.png",
        help="Output PNG filename in the working directory",
    )
    return parser.parse_args(argv)


def _material_colors(materials: openmc.Materials) -> dict:
    colors = {}
    for mat in materials:
        name = mat.name or f"material_{mat.id}"
        colors[mat] = rgb_for_openmc_material_name(name)
    return colors


def _load_plot_defaults(work: Path) -> dict | None:
    path = work / PLOT_DEFAULTS_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ll = data.get("ll")
    ur = data.get("ur")
    if (
        not isinstance(ll, list)
        or not isinstance(ur, list)
        or len(ll) != 3
        or len(ur) != 3
    ):
        return None
    return data


def _pixel_shape(width: float, height: float, pixels: int) -> tuple[int, int]:
    """Map physical aspect to pixels; keep a usable minimum on the short axis."""
    long_side = max(width, height)
    scale = pixels / long_side
    px_w = max(MIN_AXIS_PIXELS, int(round(width * scale)))
    px_h = max(MIN_AXIS_PIXELS, int(round(height * scale)))
    # Cap the long side back to `pixels` after applying the minimum.
    if px_w >= px_h and px_w > pixels:
        px_h = max(MIN_AXIS_PIXELS, int(round(px_h * pixels / px_w)))
        px_w = pixels
    elif px_h > pixels:
        px_w = max(MIN_AXIS_PIXELS, int(round(px_w * pixels / px_h)))
        px_h = pixels
    return px_w, px_h


def _stage_plot_dir(work: Path) -> Path:
    """OpenMC plot mode writes plots.xml and summary.h5 in the process cwd.

    Keep that off the live run directory so a plot can run during transport.
    """
    stage = work / ".plot_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in ("geometry.xml", "materials.xml", "settings.xml", PLOT_DEFAULTS_NAME):
        src = work / name
        if src.is_file():
            shutil.copyfile(src, stage / name)
    return stage


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    work = Path.cwd()
    geom_path = work / "geometry.xml"
    mats_path = work / "materials.xml"
    if not geom_path.is_file() or not mats_path.is_file():
        print(
            "Missing geometry.xml and/or materials.xml in the working directory. "
            "Run a simulation (or render) first.",
            file=sys.stderr,
        )
        return 2

    defaults = _load_plot_defaults(work)
    if defaults is None:
        print(
            f"Missing {PLOT_DEFAULTS_NAME}; width/height/origin must be provided "
            "or regenerate geometry with a simulation run.",
            file=sys.stderr,
        )
        if args.width is None or args.origin is None:
            return 2

    if defaults is not None and (args.width is None or args.height is None or args.origin is None):
        auto_w, auto_h, auto_origin = view_size_for_basis(
            defaults["ll"],
            defaults["ur"],
            args.basis,
            pad=float(defaults.get("pad", 1.05)),
        )
    else:
        auto_w = auto_h = 0.0
        auto_origin = (0.0, 0.0, 0.0)

    origin = tuple(args.origin) if args.origin is not None else auto_origin
    width = float(args.width) if args.width is not None else float(auto_w)
    height = (
        float(args.height)
        if args.height is not None
        else (float(auto_h) if defaults is not None else width)
    )
    if width <= 0 or height <= 0:
        print("width and height must be positive", file=sys.stderr)
        return 2

    pixels = max(16, min(1000, int(args.pixels)))
    px = _pixel_shape(width, height, pixels)

    print(
        f"Plotting basis={args.basis} origin={origin} "
        f"width={width} height={height} pixels={px} -> {args.out}",
        flush=True,
    )

    stage = _stage_plot_dir(work)
    os.chdir(stage)
    materials = openmc.Materials.from_xml(str(stage / "materials.xml"))
    openmc.Geometry.from_xml(str(stage / "geometry.xml"), materials)

    plot = openmc.Plot()
    plot.filename = Path(args.out).stem
    plot.basis = args.basis
    plot.origin = origin
    plot.width = [width, height]
    plot.pixels = list(px)
    plot.color_by = "material"
    plot.colors = _material_colors(materials)
    plot.show_overlaps = True
    plot.overlap_color = (255, 0, 0)

    openmc.Plots([plot]).export_to_xml()
    openmc.plot_geometry(output=False)

    out_path = stage / f"{plot.filename}.png"
    wanted = work / args.out
    if out_path.is_file():
        shutil.copyfile(out_path, wanted)
    shutil.rmtree(stage, ignore_errors=True)
    if not wanted.is_file():
        print(f"Expected plot file missing: {wanted}", file=sys.stderr)
        return 1

    print(f"Wrote {wanted}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
