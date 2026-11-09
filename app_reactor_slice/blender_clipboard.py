"""Copy reactor columns onto Blender's object clipboard.

Blender's 3D View paste (Ctrl+V) does not read the system clipboard. It appends
every object saved in ``copybuffer.blend`` in Blender's temporary directory.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

SIDES = 64

_BLENDER_SCRIPT = r"""
import json
import math
import os
import sys
import traceback

import bpy
import bmesh


def arguments():
    if "--" not in sys.argv:
        raise RuntimeError("missing cylinder arguments")
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 2:
        raise RuntimeError("expected a spec path and a result path")
    return args[0], args[1]


def copybuffer_destination():
    # Same place as Blender's viewport paste: {temp base}/copybuffer.blend.
    # A custom preference wins. Otherwise the base is the parent of the
    # per-session folder bpy.app.tempdir (named blender_<id>).
    preference = ""
    try:
        preference = bpy.context.preferences.filepaths.temporary_directory or ""
    except AttributeError:
        preference = ""
    if preference.strip():
        base = bpy.path.abspath(preference)
        if os.path.isdir(base):
            return os.path.join(os.path.normpath(base), "copybuffer.blend")
    session = os.path.normpath(bpy.app.tempdir)
    name = os.path.basename(session)
    base = os.path.dirname(session) if name.startswith("blender_") else session
    return os.path.join(base, "copybuffer.blend")


def build_cylinder(name, radius, height, center, sides):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=sides,
        radius1=radius,
        radius2=radius,
        depth=height,
    )
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    # Mesh is centered, so this origin sits at mid-height and the base is on z = 0.
    obj.location = (float(center[0]), float(center[1]), height / 2.0)
    return obj


def measure(obj, radius, height, sides):
    mesh = obj.data
    quads = sum(1 for poly in mesh.polygons if len(poly.vertices) == 4)
    caps = sum(1 for poly in mesh.polygons if len(poly.vertices) != 4)
    radial = max(math.hypot(vertex.co.x, vertex.co.y) for vertex in mesh.vertices)
    zs = [vertex.co.z for vertex in mesh.vertices]
    extent = max(zs) - min(zs)
    if quads != sides or caps != 2:
        raise RuntimeError(f"{obj.name} has {quads} side faces and {caps} caps")
    if abs(radial - radius) > 1e-4 or abs(extent - height) > 1e-4:
        raise RuntimeError(
            f"{obj.name} measures {radial * 2:.6g} m across and {extent:.6g} m tall"
        )
    location = (obj.location.x, obj.location.y, obj.location.z)
    return {
        "name": obj.name,
        "location": [location[0], location[1], location[2]],
        "side_faces": quads,
        "diameter": radial * 2.0,
        "height": extent,
    }


def column_order(obj):
    parts = obj.name.split()
    if len(parts) == 1:
        return 0
    return int(parts[-1])


def main():
    spec_path, result_path = arguments()
    with open(spec_path, encoding="utf-8") as handle:
        spec = json.load(handle)
    radius = float(spec["radius"])
    height = float(spec["height"])
    centers = spec["centers"]
    sides = int(spec["sides"])
    if radius <= 0 or height <= 0 or not centers or sides < 3:
        raise RuntimeError("cylinder size is invalid")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = []
    for index, center in enumerate(centers, start=1):
        name = "Reactor" if len(centers) == 1 else f"Column {index}"
        objects.append(build_cylinder(name, radius, height, center, sides))

    dest = copybuffer_destination()
    staging = dest + ".rimag-staging.blend"
    try:
        datablocks = set()
        for obj in objects:
            datablocks.add(obj)
            datablocks.add(obj.data)
        bpy.data.libraries.write(
            staging,
            datablocks,
            path_remap="NONE",
            fake_user=True,
            compress=False,
        )

        bpy.ops.wm.read_factory_settings(use_empty=True)
        with bpy.data.libraries.load(staging) as (data_from, data_to):
            data_to.objects = list(data_from.objects)
        loaded = []
        for obj in data_to.objects:
            if obj is None:
                continue
            bpy.context.scene.collection.objects.link(obj)
            loaded.append(obj)
        if len(loaded) != len(centers):
            raise RuntimeError(f"clipboard file has {len(loaded)} objects, expected {len(centers)}")
        loaded.sort(key=column_order)
        report = []
        for obj, center in zip(loaded, centers):
            item = measure(obj, radius, height, sides)
            x, y, z = item["location"]
            if abs(x - float(center[0])) > 1e-4 or abs(y - float(center[1])) > 1e-4:
                raise RuntimeError(f"{obj.name} is in the wrong place")
            if abs(z - height / 2.0) > 1e-4:
                raise RuntimeError(f"{obj.name} is not sitting on the ground plane")
            report.append(item)
        os.replace(staging, dest)
    finally:
        if os.path.exists(staging):
            os.remove(staging)

    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump({"path": dest, "columns": report}, handle)
    print("COPIED", dest)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
"""


class BlenderClipboardError(RuntimeError):
    """The reactor model could not be placed on Blender's clipboard."""


def find_blender() -> Path | None:
    """Newest installed Blender, so the clipboard file matches that version."""
    candidates: list[Path] = []
    override = os.environ.get("BLENDER_EXECUTABLE")
    if override:
        candidates.append(Path(override))
    found = shutil.which("blender")
    if found:
        candidates.append(Path(found))
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(key)
        if not root:
            continue
        base = Path(root) / "Blender Foundation"
        if base.is_dir():
            candidates.extend(base.glob("*/blender.exe"))
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    return max(existing, key=_version_key)


def copy_columns_to_blender(
    radius: float,
    height: float,
    centers: Sequence[tuple[float, float]],
) -> Path:
    """Write one cylinder per column into the file Blender pastes with Ctrl+V.

    ``radius`` and ``height`` are meters. Each center is an ``(x, y)`` position
    in meters. The cylinder has ``SIDES`` faces around and stands on ``z = 0``.
    """
    if radius <= 0 or height <= 0 or not math.isfinite(radius) or not math.isfinite(height):
        raise BlenderClipboardError("Cylinder size must be positive.")
    points = [(float(x), float(y)) for x, y in centers]
    if not points or any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        raise BlenderClipboardError("Column positions must be finite.")

    blender = find_blender()
    if blender is None:
        raise BlenderClipboardError("Blender was not found. Install it, or add blender.exe to PATH.")

    with tempfile.TemporaryDirectory(prefix="rimag-reactor-") as folder:
        root = Path(folder)
        spec_path = root / "reactor.json"
        result_path = root / "result.json"
        script_path = root / "copy_reactor.py"
        spec_path.write_text(
            json.dumps(
                {
                    "radius": radius,
                    "height": height,
                    "sides": SIDES,
                    "centers": points,
                }
            ),
            encoding="utf-8",
        )
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        try:
            completed = subprocess.run(
                [
                    str(blender),
                    "--background",
                    "--python",
                    str(script_path),
                    "--",
                    str(spec_path),
                    str(result_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=120,
                creationflags=_no_window_flag(),
            )
        except subprocess.TimeoutExpired as error:
            raise BlenderClipboardError("Blender took too long to build the reactor.") from error
        if completed.returncode != 0 or not result_path.is_file():
            raise BlenderClipboardError(_failure_text(completed.stdout, completed.stderr))
        payload = json.loads(result_path.read_text(encoding="utf-8"))

    path = Path(payload["path"])
    _check_report(payload, radius, height, points)
    if not path.is_file() or path.read_bytes()[:7] != b"BLENDER":
        raise BlenderClipboardError("Blender did not write a model file.")
    return path


def _check_report(payload: dict, radius: float, height: float, centers: list[tuple[float, float]]) -> None:
    columns = payload.get("columns")
    if not isinstance(columns, list) or len(columns) != len(centers):
        raise BlenderClipboardError("Blender wrote the wrong number of cylinders.")
    for column, center in zip(columns, centers):
        if column.get("side_faces") != SIDES:
            raise BlenderClipboardError(f"The cylinder does not have {SIDES} side faces.")
        if abs(float(column["diameter"]) - 2 * radius) > 1e-3:
            raise BlenderClipboardError("Cylinder diameter does not match the reactor.")
        if abs(float(column["height"]) - height) > 1e-3:
            raise BlenderClipboardError("Cylinder height does not match the stack.")
        x, y, z = column["location"]
        if abs(float(x) - center[0]) > 1e-3 or abs(float(y) - center[1]) > 1e-3:
            raise BlenderClipboardError("A cylinder is in the wrong place.")
        if abs(float(z) - height / 2) > 1e-3:
            raise BlenderClipboardError("A cylinder is not standing on the ground plane.")


def _version_key(path: Path) -> tuple[int, ...]:
    numbers = []
    for part in path.parts:
        token = ""
        for char in part:
            if char.isdigit():
                token += char
            elif token:
                numbers.append(int(token))
                token = ""
        if token:
            numbers.append(int(token))
    return tuple(numbers) or (0,)


def _no_window_flag() -> int:
    if sys.platform != "win32":
        return 0
    return subprocess.CREATE_NO_WINDOW


def _failure_text(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in f"{stdout}\n{stderr}".splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith("Blender ")]
    if not lines:
        return "Blender could not build the reactor model."
    return "\n".join(lines[-8:])
