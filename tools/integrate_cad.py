"""Deriva marcos y colocaciones locales del CAD para la cadena R-R-R-P.

Con --update-config reemplaza solo geometría y cajas equivalentes derivadas;
conserva las masas y prestaciones provisionales. No modifica CAD originales.
"""

import argparse
import copy
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scara.frames import chain_frames, multiply, rigid_inverse, transform_point, z_pose
from scara.kinematics import load_config
from extraer_ensamble import transformed_bbox, union_bbox
from generate_cad_preview import digest, tower_body_meshes
from registrar_subensambles import comparable


BODY_DEFS = dict(base="BASE", arm="ARM", forearm="FOREARM", wrist="WRIST", tool="TOOL")


def close_matrix(a, b):
    return max(abs(x-y) for row_a, row_b in zip(a, b) for x, y in zip(row_a, row_b))


def derive(config=None):
    config = copy.deepcopy(config or load_config())
    spec_path = ROOT / "config/cad_integration.json"
    source_path = ROOT / "cad/ensambles/informe.json"
    spec, source = json.loads(spec_path.read_text()), json.loads(source_path.read_text())
    assembly = next(a for a in source["assemblies"] if Path(a["source"]).name == spec["source_assembly"])
    if digest(ROOT / assembly["source"]) != assembly["source_sha256"]:
        raise ValueError("El ensamble fuente cambió; repetir extracción antes de integrar")
    instances = {i["instance_name"]: i for i in assembly["configurations"][0]["instances"]
                 if i["xml_attributes"]["swSuppressed"] == "NO"}
    assigned = [name for group in spec["groups"].values() for name in group]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(instances):
        raise ValueError("Cada instancia activa debe pertenecer a exactamente un cuerpo")
    registration_path = ROOT / "cad/ensambles/registro_subensambles.json"
    registration = json.loads(registration_path.read_text())
    if (registration["assembly_report_sha256"] != digest(source_path) or
            registration["script_sha256"] != digest(ROOT / "tools/registrar_subensambles.py") or
            not registration["protected_inputs_unchanged"]):
        raise ValueError("El registro de subensambles está desactualizado")
    candidates = {p["proposed_occurrence"]: p for p in registration["proposed_additions"]}
    # Una selección explícita no vuelve compatibles las otras poses del caché.
    # La evidencia geométrica que justifica la elección permanece en su informe.
    for name, choice in spec.get("ambiguous_occurrence_choices", {}).items():
        if name in candidates or not choice.get("reason", "").strip():
            raise ValueError("Selección ambigua duplicada o sin motivo: " + name)
        withheld = next(p for p in registration["ambiguous_additions_withheld"]
                        if p["basename"] == choice["basename"])
        matches = [p for p in withheld["candidates"]
                   if p["source_assembly"] == choice["source_assembly"]
                   and p["source_instance"] == choice["source_instance"]]
        if len(matches) != 1:
            raise ValueError("La selección no identifica una pose retenida única: " + name)
        selected = matches[0]
        candidates[name] = dict(basename=selected["basename"],
            transform_part_to_global_m=selected["transform_part_to_global_m"],
            evidence=[selected])
    for group, names in spec.get("additional_occurrences", {}).items():
        for name in names:
            if name in instances:
                raise ValueError("Instancia adicional duplicada: " + name)
            candidate = candidates[name]
            evidence = candidate["evidence"][0]
            source_assembly = next(a for a in source["assemblies"]
                                   if Path(a["source"]).stem == evidence["source_assembly"])
            if digest(ROOT/source_assembly["source"]) != source_assembly["source_sha256"]:
                raise ValueError("Subensamble original modificado")
            instance = copy.deepcopy(next(i for i in source_assembly["configurations"][0]["instances"]
                                     if i["instance_name"] == evidence["source_instance"]))
            if not evidence["current_bbox_agrees_with_cached"]:
                raise ValueError("Incorporación con revisión de geometría discrepante")
            instance["instance_name"] = name
            instance["transform_object_to_assembly_m"] = candidate["transform_part_to_global_m"]
            instance["registration_evidence"] = candidate["evidence"]
            instances[name] = instance
            spec["groups"][group].append(name)
    placement_sources = {}
    for name, correction in spec.get("placement_overrides", {}).items():
        source_assembly = next(a for a in source["assemblies"]
                               if Path(a["source"]).name == correction["assembly"])
        source_file = ROOT / source_assembly["source"]
        if digest(source_file) != source_assembly["source_sha256"]:
            raise ValueError("Ensamble de corrección modificado: " + str(source_file))
        if len(source_assembly["configurations"]) != 1:
            raise ValueError("La corrección requiere una configuración guardada unívoca")
        source_parts = {p["instance_name"]: p for p in source_assembly["configurations"][0]["instances"]
                        if p["xml_attributes"]["swSuppressed"] == "NO"}
        anchor = correction["anchor"]
        if not all(comparable(instances[n], source_parts[n]) for n in (name, anchor)):
            raise ValueError("Revisiones incompatibles en corrección de " + name)
        transform = multiply(instances[anchor]["transform_object_to_assembly_m"],
                             rigid_inverse(source_parts[anchor]["transform_object_to_assembly_m"]))
        instances[name]["placement_correction"] = dict(
            source_assembly=source_assembly["source"], source_sha256=source_assembly["source_sha256"],
            anchor_instance=anchor, reason=correction["reason"],
            original_saved_object_to_assembly=instances[name]["transform_object_to_assembly_m"],
            transform_source_to_saved_assembly_m=transform)
        instances[name]["transform_object_to_assembly_m"] = multiply(
            transform, source_parts[name]["transform_object_to_assembly_m"])
        placement_sources[source_assembly["source"]] = source_assembly["source_sha256"]
    axes = json.loads((ROOT / "cad/ensambles/ejes_propuestos.json").read_text())
    if axes["source_sha256"] != assembly["source_sha256"]:
        raise ValueError("Las líneas de eje no corresponden al ensamble actual")
    positions = {name: data["point_on_axis_assembly_m"] for name, data in axes["axes"].items()}
    delta = [b-a for a, b in zip(positions["J1"], positions["J2"])]
    yaw = -math.atan2(-delta[1], delta[0])
    flip = [[1,0,0,0], [0,-1,0,0], [0,0,-1,0], [0,0,0,1]]
    canonical = multiply(z_pose(angle=yaw), flip)
    j1 = transform_point(canonical, positions["J1"])
    tower = instances["0-Torre-1"]
    tower_bbox = transformed_bbox(multiply(canonical, tower["transform_object_to_assembly_m"]), tower["cached_local_bbox_m"])
    canonical[0][3], canonical[1][3], canonical[2][3] = -j1[0], -j1[1], -tower_bbox[2]

    def part_point(name, point):
        return transform_point(multiply(canonical, instances[name]["transform_object_to_assembly_m"]), point)

    shoulder = part_point("A-Brazo-1", spec["shoulder_center_local_m"])
    elbow = part_point("B-Antebrazo-1", spec["elbow_center_local_m"])
    wrist_axis = transform_point(canonical, positions["J3"])
    tcp = part_point("Z-SoporteEfector-1", spec["tool_point_local_m"])
    support = multiply(canonical, instances["Z-SoporteEfector-1"]["transform_object_to_assembly_m"])
    heading = [sum(support[i][j] * spec["tool_heading_local"][j] for j in range(3)) for i in range(3)]
    q1 = math.atan2(elbow[1]-shoulder[1], elbow[0]-shoulder[0])
    q2 = math.atan2(wrist_axis[1]-elbow[1], wrist_axis[0]-elbow[0]) - q1
    q3 = math.atan2(heading[1], heading[0]) - q1 - q2
    reference = [q1, q2, q3, spec["saved_slider_position_m"]]
    geometry = dict(l1=math.dist(shoulder[:2], elbow[:2]),
                    l2=math.dist(elbow[:2], wrist_axis[:2]), shoulder_z=shoulder[2],
                    elbow_z_offset=elbow[2]-shoulder[2],
                    tool_z_offset=tcp[2]-elbow[2]+reference[3])
    config["geometry"] = geometry
    frames = chain_frames(reference, config)
    if math.dist([frames["tool"][i][3] for i in range(3)], tcp) > 1e-8:
        raise ValueError("El TCP propuesto no pertenece al eje; hace falta una cinemática con offset XY")
    entries, boxes = [], {group: [] for group in frames}
    for group, names in spec["groups"].items():
        for name in names:
            instance = instances[name]
            if digest(ROOT / instance["local_source"]) != instance["local_sha256"]:
                raise ValueError("Pieza original modificada: " + name)
            saved = multiply(canonical, instance["transform_object_to_assembly_m"])
            local = multiply(rigid_inverse(frames[group]), saved)
            if close_matrix(multiply(frames[group], local), saved) > 1e-9:
                raise ValueError("La reconstrucción cambia la colocación de " + name)
            meshes, body_report = [], None
            if instance["basename"] == "0-Torre.SLDPRT":
                meshes, body_report = tower_body_meshes(instance)
                disposition = "validated_individual_bodies_zero_area_cleanup"
            elif instance.get("accepted_stl"):
                mesh = instance["accepted_stl"]
                if not instance["local_matches_geometry_report_source"] or digest(ROOT / mesh["path"]) != mesh["sha256"]:
                    raise ValueError("Malla no coincide con validación: " + name)
                meshes = [mesh]
                disposition = "accepted_mesh" if instance["current_brep_cached_bbox_agree_0_05mm"] else "accepted_mesh_cache_differs"
            else:
                disposition = "wire_bbox_only_rejected_mesh"
            bbox = instance["cached_local_bbox_m"]
            # Para colisión usar bbox de la malla actual si está disponible; no la revisión vieja del caché.
            if meshes:
                from convertir_cad import mesh_metrics
                mesh_boxes = [mesh_metrics(ROOT / mesh["path"])["bbox_m"] for mesh in meshes]
                bbox = union_bbox([sides[0] + sides[1] for sides in mesh_boxes])
            boxes[group].append(transformed_bbox(local, bbox))
            entries.append(dict(instance_name=name, basename=instance["basename"], group=group,
                def_name="CAD_" + re.sub(r"[^A-Za-z0-9_]", "_", name), disposition=disposition,
                attachment_status=("provisional_joint_side" if name in spec["provisional_attachments"] else
                                   "registered_mount_visual_only" if "registration_evidence" in instance else
                                   "structural_group_from_assembly"),
                source=instance["local_source"], source_sha256=instance["local_sha256"],
                saved_object_to_assembly=instance["transform_object_to_assembly_m"],
                canonical_object_pose=saved, body_from_piece=local, bbox_local_m=bbox,
                meshes=meshes, body_report=body_report,
                placement_correction=instance.get("placement_correction"),
                registration_evidence=instance.get("registration_evidence")))
    body_boxes = {group: dict(size=[bounds[i+3]-bounds[i] for i in range(3)],
                             center=[(bounds[i]+bounds[i+3])/2 for i in range(3)], bounds=bounds)
                  for group in boxes for bounds in [union_bbox(boxes[group])]}
    manifest = dict(status="articulated_visual_CAD_provisional_physics", units="m",
                    source_assembly=assembly["source"], source_sha256=assembly["source_sha256"],
                    canonical_from_saved=canonical, saved_joint_reference=reference,
                    reference_status=spec["reference_status"], body_defs=BODY_DEFS,
                    geometry=geometry, reference_body_frames=frames, body_boxes=body_boxes,
                    instances=entries, sources={"config/cad_integration.json": digest(spec_path),
                        "cad/ensambles/informe.json": digest(source_path),
                        "cad/ensambles/ejes_propuestos.json": digest(ROOT / "cad/ensambles/ejes_propuestos.json"),
                        "cad/ensambles/registro_subensambles.json": digest(registration_path),
                        "tools/registrar_subensambles.py": digest(ROOT/"tools/registrar_subensambles.py"),
                        "tools/integrate_cad.py": digest(__file__),
                        "scara/frames.py": digest(ROOT / "scara/frames.py"), **placement_sources})
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-config", action="store_true")
    args = parser.parse_args()
    report = derive()
    path = ROOT / "cad/ensambles/integracion_articulada.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.update_config:
        config = load_config()
        config["geometry"] = report["geometry"]
        for body, group in zip(config["body_properties"], ("arm", "forearm", "wrist", "tool")):
            for key in ("size", "center"):
                body[key] = report["body_boxes"][group][key]
        config["model_status"] = "CAD visual articulado parcial; masas, esfuerzo, colisiones y TCP provisionales"
        for key in report["geometry"]:
            config["provenance"]["geometry." + key] = "Derivado del ensamble guardado y convenciones explícitas de config/cad_integration.json; ver cad/ensambles/integracion_articulada.json"
        config["provenance"]["body_properties"] = "Masas exploratorias conservadas; COM e inercia de cajas envolventes equivalentes de los grupos CAD. No son propiedades materiales validadas"
        (ROOT / "config/scara.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(path.relative_to(ROOT)), "geometry": report["geometry"],
                      "saved_reference": report["saved_joint_reference"], "instances": len(report["instances"])}, indent=2))


if __name__ == "__main__":
    main()
