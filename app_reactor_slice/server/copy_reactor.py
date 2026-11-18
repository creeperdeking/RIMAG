"""Build reactor cylinders and write Blender's viewport paste file.

Blender's 3D View paste (Ctrl+V) appends every object in copybuffer.blend.
"""

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
