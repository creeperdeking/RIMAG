"""Persist a finite plot bounding box next to exported OpenMC XMLs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence, Tuple

Vec3 = Tuple[float, float, float]
BBox = Tuple[Vec3, Vec3]

PLOT_DEFAULTS_NAME = "plot_defaults.json"
PAD = 1.05


def _finite(values: Iterable[float]) -> bool:
    return all(abs(v) < 1e100 for v in values)


def write_plot_defaults(
    bounding_box: BBox,
    path: str | Path = PLOT_DEFAULTS_NAME,
    origin: Sequence[float] | None = None,
) -> Path:
    ll, ur = bounding_box
    if len(ll) != 3 or len(ur) != 3:
        raise ValueError("bounding_box must be two length-3 corners")
    if not _finite([*ll, *ur]):
        raise ValueError("bounding_box has non-finite coordinates")
    center = (
        0.5 * (ll[0] + ur[0]),
        0.5 * (ll[1] + ur[1]),
        0.5 * (ll[2] + ur[2]),
    )
    payload = {
        "ll": [float(ll[0]), float(ll[1]), float(ll[2])],
        "ur": [float(ur[0]), float(ur[1]), float(ur[2])],
        "origin": [float(origin[0]), float(origin[1]), float(origin[2])]
        if origin is not None
        else list(center),
        "pad": PAD,
    }
    target = Path(path)
    target.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    return target


def view_size_for_basis(
    ll: Sequence[float],
    ur: Sequence[float],
    basis: str,
    pad: float = PAD,
) -> tuple[float, float, Vec3]:
    """Return (width, height, origin) in cm that envelopes the bbox for one basis."""
    spans = (
        max(1e-6, (ur[0] - ll[0]) * pad),
        max(1e-6, (ur[1] - ll[1]) * pad),
        max(1e-6, (ur[2] - ll[2]) * pad),
    )
    origin: Vec3 = (
        0.5 * (ll[0] + ur[0]),
        0.5 * (ll[1] + ur[1]),
        0.5 * (ll[2] + ur[2]),
    )
    if basis == "xy":
        return spans[0], spans[1], origin
    if basis == "xz":
        return spans[0], spans[2], origin
    if basis == "yz":
        return spans[1], spans[2], origin
    raise ValueError(f"unknown basis {basis!r}")
