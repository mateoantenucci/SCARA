#!/usr/bin/env python3
"""Recover saved SolidWorks assembly instances from the embedded XML cache.

Read-only with respect to source CAD. Uses the reviewed CFB reader and explicit
MiniFAT adapter already used by convertir_cad.py. Does not solve mates, rebuild
assemblies, infer joints, or silently replace missing/changed part revisions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path, PureWindowsPath
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "http://www.solidworks.com/sw2003/schema"
TAG = "{" + NAMESPACE + "}"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def numbers(value, count):
    result = [float(v) for v in value.split()]
    if len(result) != count or not all(math.isfinite(v) for v in result):
        raise ValueError("Unexpected/nonfinite XML numeric field")
    return result


def transform_point(matrix, point):
    return [sum(matrix[i][j] * point[j] for j in range(3)) + matrix[i][3]
            for i in range(3)]


def transformed_bbox(matrix, bbox):
    corners = [transform_point(matrix, p) for p in itertools.product(
        *[(bbox[i], bbox[i + 3]) for i in range(3)])]
    return ([min(p[i] for p in corners) for i in range(3)] +
            [max(p[i] for p in corners) for i in range(3)])


def union_bbox(boxes):
    if not boxes:
        raise ValueError("No active instance bounding boxes")
    return ([min(b[i] for b in boxes) for i in range(3)] +
            [max(b[i + 3] for b in boxes) for i in range(3)])


def decode_xml(stream):
    # Header of these files: GUID, uint32 uncompressed size, uint32 compressed
    # size, then zlib data. Refuse another layout instead of scanning heuristics.
    if len(stream) < 26:
        raise ValueError("Truncated COMPINSTANCETREE header")
    expected_size, compressed_size = struct.unpack_from("<II", stream, 16)
    if (expected_size > 5_000_000 or compressed_size != len(stream) - 32
            or stream[-8:] != bytes(8)):
        raise ValueError("Unexpected COMPINSTANCETREE length header")
    decoder = zlib.decompressobj()
    data = decoder.decompress(stream[24:-8], 5_000_001)
    if (len(data) != expected_size or decoder.unconsumed_tail or decoder.unused_data
            or not decoder.eof):
        raise ValueError("COMPINSTANCETREE decompression/size mismatch")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML DTD/entities are not accepted")
    return data


def matrix_from_xml(raw):
    values = numbers(raw, 16)
    matrix = [[values[c * 4 + r] for c in range(4)] for r in range(4)]
    if any(abs(a-b) > 1e-10 for a, b in zip(matrix[3], [0, 0, 0, 1])):
        raise ValueError("Stored matrix is not an affine rigid transform")
    orthogonality = max(abs(sum(matrix[k][i] * matrix[k][j] for k in range(3))
                            - (1 if i == j else 0)) for i in range(3) for j in range(3))
    a, b, c = matrix[:3]
    determinant = (a[0] * (b[1]*c[2] - b[2]*c[1])
                   - a[1] * (b[0]*c[2] - b[2]*c[0])
                   + a[2] * (b[0]*c[1] - b[1]*c[0]))
    if orthogonality > 1e-8 or abs(determinant-1) > 1e-8:
        raise ValueError("Stored matrix rotation is not proper/orthonormal")
    return matrix, orthogonality, determinant


def extract(path, parser_class, source, geometry, output):
    raw = path.read_bytes()
    parser = parser_class(raw)
    stream = parser.extract_stream("COMPINSTANCETREE__ZLB")
    if stream is None:
        raise ValueError("No embedded component instance XML tree")
    xml_bytes = decode_xml(stream.data)
    tree = ET.fromstring(xml_bytes)
    if tree.tag != TAG + "swSolidWorks":
        raise ValueError("Unexpected SolidWorks XML namespace/root")
    files = {e.attrib["id"]: e for e in tree.findall(".//" + TAG + "swFile")}
    models = {e.attrib["id"]: e for e in tree.findall(".//" + TAG + "swModel")}
    configs = tree.findall(".//" + TAG + "swConfiguration")
    xml_path = output / "xml" / (path.stem + ".xml")
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_bytes(xml_bytes)
    result = {"source": str(path.relative_to(ROOT)), "source_sha256": digest(raw),
              "xml": {"path": str(xml_path.relative_to(output)),
                      "sha256": digest(xml_bytes), "stored_stream_sha256": digest(stream.data),
                      "stream": stream.stream_name, "compressed_offset": 24},
              "sw_version": tree.attrib.get("swVersion"), "configurations": []}
    preview = parser.extract_stream("PreviewPNG")
    if preview is not None and preview.data.startswith(b"\x89PNG\r\n\x1a\n"):
        preview_path = output / "previews" / (path.stem + ".png")
        preview_path.parent.mkdir(exist_ok=True)
        preview_path.write_bytes(preview.data)
        result["saved_preview"] = {"path": str(preview_path.relative_to(output)),
                                   "sha256": digest(preview.data), "rendered_by_pipeline": False}
    for cfg in configs:
        root_model = models[cfg.attrib["swModelRef"]]
        instances, active_boxes = [], []
        for ref in root_model.findall(TAG + "swReference"):
            attrs = dict(ref.attrib)
            model = models[attrs["swModelRef"]]
            file = files[model.attrib["swFileRef"]]
            basename = PureWindowsPath(file.attrib["swPath"]).name
            matches = [p for p in source.iterdir() if p.name.casefold() == basename.casefold()]
            local = matches[0] if len(matches) == 1 else None
            matrix, orthogonality, determinant = matrix_from_xml(attrs["swTransform"])
            cached_bbox = numbers(model.attrib["swBoundingBox"], 6)
            box = transformed_bbox(matrix, cached_bbox)
            if attrs.get("swSuppressed") == "NO":
                active_boxes.append(box)
            instance = {"instance_name": attrs["swName"] + "-" + attrs["swReferenceNumber"],
                        "xml_attributes": attrs, "model_attributes": dict(model.attrib),
                        "file_attributes": dict(file.attrib), "basename": basename,
                        "local_resolution": "unique_basename" if local else "missing_or_ambiguous",
                        "local_source": str(local.relative_to(ROOT)) if local else None,
                        "local_sha256": digest(local.read_bytes()) if local else None,
                        "transform_object_to_assembly_m": matrix,
                        "orthogonality_max_error": orthogonality,
                        "rotation_determinant": determinant,
                        "cached_local_bbox_m": cached_bbox,
                        "cached_placed_bbox_m": box,
                        "cache_is_rebuild_of_current_part": False}
            measured = geometry.get(basename.casefold(), {})
            instance["mesh_gate_status"] = measured.get("status", "not_converted")
            instance["local_matches_geometry_report_source"] = bool(
                measured and local and measured["source_sha256"] == instance["local_sha256"])
            if measured.get("stl"):
                mesh_path = ROOT / "cad/derivados" / measured["stl"]["path"]
                if digest(mesh_path.read_bytes()) != measured["stl"]["sha256"]:
                    raise ValueError("Accepted STL differs from geometry report SHA")
                instance["accepted_stl"] = {"path": str(mesh_path.relative_to(ROOT)),
                                            "sha256": measured["stl"]["sha256"]}
            if "geometry" in measured:
                current_bbox = sum(measured["geometry"]["bbox_mm"], [])
                delta = max(abs(a * .001-b) for a, b in zip(current_bbox, cached_bbox))
                instance["current_brep_vs_cached_bbox_max_delta_m"] = delta
                instance["current_brep_cached_bbox_agree_0_05mm"] = delta <= 0.00005
            instances.append(instance)
        stored_bbox = numbers(root_model.attrib["swBoundingBox"], 6)
        computed_bbox = union_bbox(active_boxes)
        discrepancy = max(abs(a-b) for a, b in zip(stored_bbox, computed_bbox))
        if discrepancy > 1e-8:
            raise ValueError("Transform interpretation does not reproduce assembly cached bbox")
        result["configurations"].append({
            "xml_attributes": dict(cfg.attrib), "root_model_attributes": dict(root_model.attrib),
            "instances": instances, "instance_count": len(instances),
            "all_references_resolved": all(i["local_resolution"] == "unique_basename" for i in instances),
            "cached_assembly_bbox_m": stored_bbox,
            "recomputed_from_cached_instances_bbox_m": computed_bbox,
            "bbox_union_max_error_m": discrepancy,
            "fresh_geometry_validation": False})
    if digest(path.read_bytes()) != result["source_sha256"]:
        raise ValueError("Source assembly changed while reading")
    return result


def self_check():
    matrix, error, determinant = matrix_from_xml(
        "0 1 0 0 -1 0 0 0 0 0 1 0 0.1 0.2 0.3 1")
    assert transform_point(matrix, [1, 0, 0]) == [0.1, 1.2, 0.3]
    assert error == 0 and determinant == 1
    box = transformed_bbox(matrix, [0, 0, 0, 2, 1, 1])
    assert max(abs(a-b) for a, b in zip(box, [-.9, .2, .3, .1, 2.2, 1.3])) < 1e-12
    payload = b'<swSolidWorks xmlns="' + NAMESPACE.encode() + b'" />'
    compressed = zlib.compress(payload)
    raw = bytes(16) + struct.pack("<II", len(payload), len(compressed)) + compressed + bytes(8)
    assert decode_xml(raw) == payload
    try:
        decode_xml(raw[:-1])
    except ValueError:
        pass
    else:
        raise AssertionError("Truncated cache was accepted")
    print("PASS: rigid transform, non-symmetric rotation/translation, bbox, bounded XML and truncation")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--converter-root", type=Path)
    cli.add_argument("--source", type=Path, default=ROOT / "Modelos3D")
    cli.add_argument("--output", type=Path, default=ROOT / "cad/ensambles")
    cli.add_argument("--self-check", action="store_true")
    args = cli.parse_args()
    if args.self_check:
        self_check()
        return
    if args.converter_root is None:
        cli.error("--converter-root must point to the pinned source used by convertir_cad.py")
    # Reuse the reviewed reader and enforce the same upstream source identity.
    import convertir_cad
    source_hashes = {p.relative_to(args.converter_root).as_posix(): digest(p.read_bytes())
                     for p in sorted(args.converter_root.rglob("*.py"))}
    tree_hash = digest(json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode())
    if tree_hash != convertir_cad.UPSTREAM_TREE_SHA256:
        cli.error("Converter source tree differs from the reviewed pinned revision")
    sys.path.insert(0, str(args.converter_root.resolve()))
    sys.path.insert(0, str(ROOT / "tools/patches"))
    from ole_ministreams import install
    install()
    from sldprt2step_lib.container.ole_cfb import OleContainerParser
    report = ROOT / "cad/derivados/informe.json"
    geometry = {Path(p["source"]).name.casefold(): p for p in json.loads(report.read_text())["parts"]}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(args.source.glob("*.SLDASM")):
        results.append(extract(path.resolve(), OleContainerParser, args.source.resolve(), geometry, output))
    manifest = {"tool_sha256": digest(Path(__file__).read_bytes()),
                "reader_upstream_tree_sha256": tree_hash,
                "minifat_patch_sha256": digest((ROOT / "tools/patches/ole_ministreams.py").read_bytes()),
                "geometry_report_sha256": digest(report.read_bytes()),
                "semantics": "Saved XML cache; no mate solving or CAD rebuild",
                "matrix_convention": "XML column-major 4x4; JSON row lists; p_assembly = R*p_part + t; m",
                "assemblies": results,
                "summary": {"assembly_count": len(results),
                            "saved_instance_count": sum(c["instance_count"] for a in results for c in a["configurations"])}}
    (output / "informe.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(manifest["summary"]))


if __name__ == "__main__":
    main()
