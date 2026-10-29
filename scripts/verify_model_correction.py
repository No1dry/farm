"""Independent export guard for the correction; visual review remains mandatory.

Checks the delivered GLB bytes, not the Blender builder's success report. It
does not infer model quality from polygon counts or certify onsite dimensions.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
STYLE_SHA = "874531436ffa156b232ca89766c1acfdd1f715ef22b4b2eba473cb5702a7c1cd"
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def mul(a, b):
    return [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
            for col in range(4) for row in range(4)]


def transform(node):
    if "matrix" in node:
        return node["matrix"]
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = node.get("scale", [1, 1, 1])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    return [sx*(1-2*y*y-2*z*z), sx*(2*x*y+2*z*w), sx*(2*x*z-2*y*w), 0,
            sy*(2*x*y-2*z*w), sy*(1-2*x*x-2*z*z), sy*(2*y*z+2*x*w), 0,
            sz*(2*x*z+2*y*w), sz*(2*y*z-2*x*w), sz*(1-2*x*x-2*y*y), 0,
            tx, ty, tz, 1]


def inspect(path):
    raw = path.read_bytes()
    magic, version, declared = struct.unpack_from("<III", raw)
    if magic != 0x46546C67 or version != 2 or declared != len(raw):
        raise ValueError(f"Invalid GLB: {path}")
    size, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError("GLB JSON chunk missing")
    doc = json.loads(raw[20:20+size])
    issues = []
    materials = [m.get("name", "") for m in doc.get("materials", [])]
    images = [im.get("name", "") for im in doc.get("images", [])]
    forbidden_materials = [m for m in materials if any(token in m.lower()
        for token in ["satellite", "drawing reference", "source-projected"])]
    forbidden_images = [m for m in images if any(token in m.lower()
        for token in ["卫星", "landscape", "as-built", "drawing-reference"])]
    if forbidden_materials:
        issues.append({"source_image_materials": forbidden_materials})
    if forbidden_images:
        issues.append({"source_reference_images": forbidden_images})
    owners = {}
    visible_meshes = 0
    triangles = 0
    nodes = doc.get("nodes", [])

    def visit(index, parent, inherited=None):
        nonlocal visible_meshes, triangles
        node = nodes[index]
        world = mul(parent, transform(node))
        extra = node.get("extras", {})
        sid = extra.get("spatial_id") or extra.get("owner_spatial_id") or inherited
        if "mesh" in node:
            visible_meshes += 1
            if extra.get("layer") in {"satellite", "drawing_reference"}:
                issues.append({"exported_reference_mesh": node.get("name", index)})
            for primitive in doc["meshes"][node["mesh"]]["primitives"]:
                accessor = doc["accessors"][primitive["attributes"]["POSITION"]]
                if primitive.get("mode", 4) == 4:
                    triangles += doc["accessors"][primitive["indices"]]["count"] // 3 if "indices" in primitive else accessor["count"] // 3
                if sid and "min" in accessor and "max" in accessor:
                    record = owners.setdefault(sid, {"kind": extra.get("kind"), "minY": math.inf, "maxY": -math.inf})
                    if extra.get("kind"):
                        record["kind"] = extra["kind"]
                    lo, hi = accessor["min"], accessor["max"]
                    for x in [lo[0], hi[0]]:
                        for y in [lo[1], hi[1]]:
                            for z in [lo[2], hi[2]]:
                                height = world[1]*x + world[5]*y + world[9]*z + world[13]
                                record["minY"] = min(record["minY"], height)
                                record["maxY"] = max(record["maxY"], height)
        for child in node.get("children", []):
            visit(child, world, sid)

    for node in doc["scenes"][doc.get("scene", 0)].get("nodes", []):
        visit(node, IDENTITY)
    relief = {sid: round(o["maxY"]-o["minY"], 4) for sid, o in owners.items()
              if o["kind"] in {"field", "pond", "lake", "road", "channel"}}
    flat = [sid for sid, height in relief.items() if height < .1]
    if flat:
        issues.append({"flat_business_geometry": flat})
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "meshes": visible_meshes, "triangles": triangles,
            "source_images_absent": not forbidden_images and not forbidden_materials,
            "relief_scene_units": relief, "issues": issues}


def main():
    manifest = json.loads((ROOT / "public/models/manifest.json").read_text(encoding="utf-8"))
    paths = []
    for asset in manifest["assets"]:
        for key in ["url", "lod_url"]:
            if asset.get(key):
                paths.append(ROOT / "public" / asset[key].lstrip("/"))
    assets = [inspect(path) for path in paths]
    original_css = hashlib.sha256((ROOT / "src/focus/style.css").read_bytes()).hexdigest() == STYLE_SHA
    report = {"original_dashboard_stylesheet_unchanged": original_css,
              "assets": assets,
              "passed": original_css and all(not a["issues"] for a in assets),
              "limits": ["Geometry height is a visual parameter, not a surveyed elevation.",
                         "This guard cannot replace human low-angle, clay-render and dashboard-layout review."]}
    out = ROOT / "deliverables/verification/model-correction-guard.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "original_css": original_css,
                      "assets": [{"path": a["path"], "issues": a["issues"]} for a in assets]},
                     ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
