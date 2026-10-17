#!/usr/bin/env python3
"""Registra cachés de subensambles mediante piezas compartidas, sin resolver mates.

Solo produce propuestas y evidencia en un JSON separado. Una transformación
parcial no vuelve rígido a todo un ensamble. No modifica CAD, mundos ni masas.
"""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLOBAL = "0-EnsambleColision"
POSITION_TOLERANCE_M = 1e-7
ROTATION_ENTRY_TOLERANCE = 1e-6


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def multiply(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inverse(matrix):
    return [[matrix[j][i] if j < 3 else -sum(matrix[k][i]*matrix[k][3] for k in range(3))
             for j in range(4)] for i in range(3)] + [[0, 0, 0, 1]]


def difference(a, b):
    return {"translation_m": math.dist([a[i][3] for i in range(3)], [b[i][3] for i in range(3)]),
            "rotation_max_entry_difference": max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))}


def agrees(a, b):
    error = difference(a, b)
    return (error["translation_m"] <= POSITION_TOLERANCE_M
            and error["rotation_max_entry_difference"] <= ROTATION_ENTRY_TOLERANCE)


def cache_identity(instance):
    model, file = instance["model_attributes"], instance["file_attributes"]
    return (instance["basename"].casefold(), model.get("swConfigurationName"),
            model.get("swLastModifiedStamp"), file.get("swCreationTime"))


def comparable(source, target):
    return (cache_identity(source) == cache_identity(target)
            and source["local_sha256"] == target["local_sha256"]
            and max(abs(a-b) for a, b in zip(source["cached_local_bbox_m"],
                                            target["cached_local_bbox_m"])) <= POSITION_TOLERANCE_M)


def registration_candidates(source, reference):
    candidates = []
    for part in source:
        for anchor in reference:
            if not comparable(part, anchor):
                continue
            # p_reference = T_reference_part * inverse(T_source_part) * p_source.
            transform = multiply(anchor["transform_object_to_assembly_m"],
                                 inverse(part["transform_object_to_assembly_m"]))
            if any(agrees(transform, item["transform_source_to_reference_m"]) for item in candidates):
                continue
            controls = []
            for item in source:
                matches = [other for other in reference if other["basename"] == item["basename"]]
                if not matches:
                    continue
                predicted = multiply(transform, item["transform_object_to_assembly_m"])
                best = min(matches, key=lambda other: (
                    not comparable(item, other),
                    difference(predicted, other["transform_object_to_assembly_m"])["translation_m"],
                    difference(predicted, other["transform_object_to_assembly_m"])["rotation_max_entry_difference"]))
                same_cache = comparable(item, best)
                controls.append({"source_instance": item["instance_name"],
                    "reference_instance": best["instance_name"], "basename": item["basename"],
                    "source_cache_stamp": item["model_attributes"].get("swLastModifiedStamp"),
                    "reference_cache_stamp": best["model_attributes"].get("swLastModifiedStamp"),
                    "same_cached_identity": same_cache,
                    "consistent_pose": same_cache and agrees(predicted, best["transform_object_to_assembly_m"]),
                    "error": difference(predicted, best["transform_object_to_assembly_m"])})
            supports = [control for control in controls if control["consistent_pose"]]
            conflicts = [control for control in controls if control["same_cached_identity"] and not control["consistent_pose"]]
            candidates.append({"anchor_source_instance": part["instance_name"],
                "anchor_reference_instance": anchor["instance_name"],
                "transform_source_to_reference_m": transform,
                "support_instances": len(supports),
                "support_distinct_part_types": len({control["basename"] for control in supports}),
                "support_source_names": [control["source_instance"] for control in supports],
                "conflicting_shared_instances": len(conflicts),
                "all_comparable_shared_instances_consistent": not conflicts,
                "controls": controls})
    return sorted(candidates, key=lambda item: (-item["support_distinct_part_types"], -item["support_instances"]))


def select(candidates, required):
    choices = [item for item in candidates if set(required) <= set(item["support_source_names"])]
    if len(choices) != 1:
        raise ValueError(f"Registro no unívoco para controles {required}: {len(choices)}")
    return choices[0]


def classify_candidate_instances(placements, global_instances):
    proposed, excluded = [], []
    for placement in placements:
        for item in placement["instances"]:
            matrix = multiply(placement["transform_source_to_global_m"], item["transform_object_to_assembly_m"])
            shared = [target for target in global_instances if target["basename"] == item["basename"]]
            base = {"source_assembly": placement["source_assembly"], "source_instance": item["instance_name"],
                    "basename": item["basename"], "source_cache_stamp": item["model_attributes"].get("swLastModifiedStamp"),
                    "cached_identity": list(cache_identity(item)),
                    "transform_part_to_global_m": matrix, "registration_route": placement["route"],
                    "local_source": item["local_source"], "local_sha256": item["local_sha256"],
                    "accepted_stl": item.get("accepted_stl"),
                    "current_bbox_agrees_with_cached": item.get("current_brep_cached_bbox_agree_0_05mm", False)}
            if shared:
                matches = [target["instance_name"] for target in shared
                           if comparable(item, target) and agrees(matrix, target["transform_object_to_assembly_m"])]
                base.update(status="already_global_same_pose" if matches else "shared_part_pose_or_revision_conflict",
                            matched_global_instances=matches)
                excluded.append(base)
            elif not item.get("accepted_stl") or not base["current_bbox_agrees_with_cached"]:
                base["status"] = "mesh_or_current_cache_revision_not_accepted"
                excluded.append(base)
            else:
                proposed.append(base)
    # Repeated parts within one assembly remain distinct. Across assemblies,
    # require the complete set of placed occurrences to agree; never add both
    # conflicting cached poses of the same physical part merely by basename.
    grouped = defaultdict(list)
    for item in proposed:
        grouped[item["basename"]].append(item)
    additions, ambiguous = [], []
    for basename, items in sorted(grouped.items()):
        if len({tuple(item["cached_identity"]) for item in items}) != 1:
            ambiguous.append({"basename": basename, "reason": "different_cached_revisions_across_registered_assemblies",
                              "candidates": items})
            continue
        clusters = []
        for item in items:
            cluster = next((cluster for cluster in clusters
                            if agrees(cluster[0]["transform_part_to_global_m"], item["transform_part_to_global_m"])), None)
            if cluster is None:
                clusters.append([item])
            else:
                cluster.append(item)
        coverage = {source: {index for index, cluster in enumerate(clusters)
                             if any(item["source_assembly"] == source for item in cluster)}
                    for source in {item["source_assembly"] for item in items}}
        if len({tuple(sorted(indices)) for indices in coverage.values()}) != 1:
            ambiguous.append({"basename": basename, "reason": "different_placed_occurrences_across_registered_caches",
                              "candidates": items})
            continue
        for index, cluster in enumerate(clusters, 1):
            additions.append({"proposed_occurrence": f"{Path(basename).stem}-registro-{index}",
                "basename": basename, "transform_part_to_global_m": cluster[0]["transform_part_to_global_m"],
                "accepted_stl": cluster[0]["accepted_stl"], "evidence": cluster,
                "status": "pose_candidate_not_rigid_body_assignment", "rigid_body": None,
                "fresh_cad_rebuild": False})
    return additions, ambiguous, excluded


def build(output):
    source_path = ROOT / "cad/ensambles/informe.json"
    report = json.loads(source_path.read_text())
    assemblies = {}
    protected = {source_path: digest(source_path), ROOT / "cad/derivados/informe.json": digest(ROOT / "cad/derivados/informe.json")}
    if report["geometry_report_sha256"] != protected[ROOT / "cad/derivados/informe.json"]:
        raise ValueError("El informe geométrico cambió desde la extracción de ensambles")
    for assembly in report["assemblies"]:
        if len(assembly["configurations"]) != 1:
            raise ValueError("Se necesita una configuración guardada unívoca")
        path = ROOT / assembly["source"]
        if digest(path) != assembly["source_sha256"]:
            raise ValueError(f"Ensamble cambiado: {path}")
        protected[path] = digest(path)
        active = [item for item in assembly["configurations"][0]["instances"]
                  if item["xml_attributes"].get("swSuppressed") == "NO"]
        for item in active:
            path = ROOT / item["local_source"]
            if digest(path) != item["local_sha256"]:
                raise ValueError(f"Pieza cambiada: {path}")
            protected[path] = digest(path)
            if item.get("accepted_stl"):
                mesh = ROOT / item["accepted_stl"]["path"]
                if digest(mesh) != item["accepted_stl"]["sha256"]:
                    raise ValueError(f"Malla cambiada: {mesh}")
        assemblies[Path(assembly["source"]).stem] = active
    pairs = {(name, GLOBAL) for name in assemblies if name != GLOBAL}
    pairs.update({("0-EnsambleBase", "0-EnsambleTorre"),
                  ("Z-EnsambleM4", "Z-EnsambleEfector"),
                  ("A-EnsambleBrazo", "0-EnsambleBase"),
                  ("B-EnsambleAntebrazo", "R-EnsambleRotacion")})
    registrations = {f"{a} -> {b}": registration_candidates(assemblies[a], assemblies[b]) for a, b in sorted(pairs)}
    chosen = []
    for name, anchors in [("0-EnsambleTorre", ["0-Torre-1"]),
                          ("A-EnsambleBrazo", ["A-Brazo-1", "A-BridaEje-1"]),
                          ("B-EnsambleAntebrazo", ["B-Antebrazo-1", "R-Bancada-1"]),
                          ("R-EnsambleRotacion", ["Z-BujeExterior-1", "Z-Cuerpo-1"])]:
        selected = select(registrations[f"{name} -> {GLOBAL}"], anchors)
        chosen.append({"source_assembly": name, "instances": assemblies[name],
                       "transform_source_to_global_m": selected["transform_source_to_reference_m"],
                       "route": [f"{name} -> {GLOBAL}"],
                       "registration_evidence": selected,
                       "global_registration_independent_shared_controls": selected["support_instances"]-1})
    base_tower = select(registrations["0-EnsambleBase -> 0-EnsambleTorre"],
                        ["0-Bancada-1", "0-SoporteMotores-1", "NEMA23-1", "NEMA23-3"])
    tower = next(item for item in chosen if item["source_assembly"] == "0-EnsambleTorre")
    chosen.append({"source_assembly": "0-EnsambleBase", "instances": assemblies["0-EnsambleBase"],
        "transform_source_to_global_m": multiply(tower["transform_source_to_global_m"], base_tower["transform_source_to_reference_m"]),
        "route": ["0-EnsambleBase -> 0-EnsambleTorre", f"0-EnsambleTorre -> {GLOBAL}"],
        "registration_evidence": base_tower,
        "global_registration_independent_shared_controls": 0,
        "warning": "La ruta global depende de la única ancla 0-Torre; A-BridaEje no es ancla de base fija"})
    additions, ambiguous, excluded = classify_candidate_instances(chosen, assemblies[GLOBAL])
    for item in chosen:
        item.pop("instances")
    direct_base = registrations[f"0-EnsambleBase -> {GLOBAL}"][0]["transform_source_to_reference_m"]
    base_via_tower = next(item for item in chosen if item["source_assembly"] == "0-EnsambleBase")["transform_source_to_global_m"]
    result = {"script_sha256": digest(__file__), "assembly_report_sha256": protected[source_path],
        "reference_assembly": GLOBAL, "matrix_convention": "p_global = T_global_source * T_source_part * p_part; metres; row lists",
        "position_tolerance_m": POSITION_TOLERANCE_M, "rotation_entry_tolerance": ROTATION_ENTRY_TOLERANCE,
        "method": "T_reference_source = T_reference_shared_part * inverse(T_source_shared_part)",
        "registration_requires_equal_cached_identity": ["basename", "configuration", "modification_stamp", "creation_time", "local_source_sha256", "cached_bbox"],
        "notes": ["Cache matches do not prove a fresh rebuild or equality to current CAD features.",
                  "Partial registration aligns a subset; articulated/shared conflicts exclude whole-assembly rigid merging.",
                  "Single-part registration of tower to global is explicit and lacks an independent global shared-part check.",
                  "Each additional pose still requires assignment to a moving/fixed body; no mass is assigned here.",
                  "No symmetry-based rotation equivalence or axis-only registration is assumed.",
                  "Z-EnsambleEfector and Z-EnsambleM4 are not bridged to global across different cache stamps."],
        "registrations": registrations, "selected_partial_routes": chosen,
        "base_route_comparison": {"via": "0-Torre", "alternative_anchor": "A-BridaEje",
                                  "difference": difference(base_via_tower, direct_base),
                                  "compatible": agrees(base_via_tower, direct_base),
                                  "decision": "do_not_use_moving_flange_as_fixed_base_anchor"},
        "proposed_additions": additions, "ambiguous_additions_withheld": ambiguous,
        "shared_or_unaccepted_instances_excluded": excluded,
        "not_globally_registered": ["Z-EnsambleEfector", "Z-EnsambleM4"],
        "world_generator_or_config_modified": False,
        "protected_inputs_unchanged": all(digest(path) == value for path, value in protected.items())}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "pose_candidates": len(additions),
                      "ambiguous_part_types_withheld": [item["basename"] for item in ambiguous]}, ensure_ascii=False))


def self_check():
    # Known +90° about Z and translation. Source-to-reference composition must
    # map [2,0,0] to [1,4,3], not use the inverse or column-major convention.
    transform = [[0, -1, 0, 1], [1, 0, 0, 2], [0, 0, 1, 3], [0, 0, 0, 1]]
    part = [[1, 0, 0, 2], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    placed = multiply(transform, part)
    assert [placed[i][3] for i in range(3)] == [1, 4, 3]
    assert agrees(multiply(placed, inverse(part)), transform)
    assert agrees(multiply(transform, inverse(transform)), [[1 if i == j else 0 for j in range(4)] for i in range(4)])
    moved = [row[:] for row in placed]
    moved[0][3] += 0.001
    assert not agrees(moved, placed)
    def instance(name, matrix, stamp="1"):
        return {"basename": name + ".SLDPRT", "instance_name": name + "-1",
                "transform_object_to_assembly_m": matrix, "local_sha256": name,
                "cached_local_bbox_m": [0, 0, 0, 1, 1, 1],
                "model_attributes": {"swConfigurationName": "Default", "swLastModifiedStamp": stamp},
                "file_attributes": {"swCreationTime": "1"}}
    source = [instance("a", part), instance("b", placed)]
    reference = [instance(item["basename"].split(".")[0],
                          multiply(transform, item["transform_object_to_assembly_m"])) for item in source]
    selected = select(registration_candidates(source, reference), ["a-1", "b-1"])
    assert selected["support_instances"] == 2
    assert agrees(selected["transform_source_to_reference_m"], transform)
    assert not comparable(source[0], instance("a", part, stamp="2"))
    reference[1]["transform_object_to_assembly_m"][0][3] += 0.001
    assert max(item["support_instances"] for item in registration_candidates(source, reference)) == 1
    print("PASS: matrix convention, inverse, multi-anchor registration, revision rejection and 1 mm conflict")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "cad/ensambles/registro_subensambles.json")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        output = args.output.resolve()
        if output == ROOT / "cad/ensambles/informe.json" or output == ROOT / "cad/derivados/informe.json":
            parser.error("Usar salida separada de los informes originales")
        build(output)


if __name__ == "__main__":
    main()
