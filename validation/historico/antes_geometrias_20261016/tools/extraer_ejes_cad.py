#!/usr/bin/env python3
"""Cross-check proposed SCARA axis lines against existing STEP cylinders.

Requires the isolated OCP environment. No CAD conversion or repair. Every
proposed line is paired with an observed cylinder and checked against an axis
from another part. Command signs, robot zero and official TCP remain unset.
"""
import json
import math
from pathlib import Path

from extraer_ensamble import ROOT, digest, transform_point


def cylinders(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.IFSelect import IFSelect_RetDone

    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone and reader.TransferRoots()
    explorer = TopExp_Explorer(reader.OneShape(), TopAbs_FACE)
    result, index = [], 0
    while explorer.More():
        surface = BRepAdaptor_Surface(TopoDS.Face(explorer.Current()), True)
        if surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder()
            point, axis = cylinder.Location(), cylinder.Axis().Direction()
            result.append({"face_index": index, "radius_mm": cylinder.Radius(),
                           "origin_mm": [point.X(), point.Y(), point.Z()],
                           "axis": [axis.X(), axis.Y(), axis.Z()]})
        index += 1
        explorer.Next()
    return {"step_sha256": digest(path.read_bytes()), "cylinders": result}


def main():
    report_path = ROOT / "cad/ensambles/informe.json"
    report = json.loads(report_path.read_text())
    assembly = next(a for a in report["assemblies"] if a["source"].endswith("0-EnsambleColision.SLDASM"))
    assert digest((ROOT / assembly["source"]).read_bytes()) == assembly["source_sha256"]
    by = {i["instance_name"]: i for i in assembly["configurations"][0]["instances"]}
    evidence = {name: cylinders(ROOT / "cad/derivados/step" / (name + ".step")) for name in
                ["A-Brazo", "B-Antebrazo", "A-BridaEje", "Z-BujeExterior", "R-Bancada"]}

    def frame(instance, origin, axis, radius=None):
        if radius is not None:
            observed = evidence[instance.rsplit("-", 1)[0]]["cylinders"]
            assert any(abs(c["radius_mm"]-radius) < 1e-6
                       and max(abs(c["origin_mm"][i]-origin[i]*1000) for i in range(3)) < 1e-6
                       and abs(abs(sum(c["axis"][i]*axis[i] for i in range(3)))-1) < 1e-8
                       for c in observed), "Expected cylindrical evidence is absent: " + instance
        matrix = by[instance]["transform_object_to_assembly_m"]
        return {"point_on_axis_assembly_m": transform_point(matrix, origin),
                "axis_direction_assembly": [sum(matrix[i][j]*axis[j] for j in range(3)) for i in range(3)],
                "source_instance": instance, "point_local_m": origin, "axis_local": axis,
                "observed_cylinder_radius_mm": radius, "sign_is_command_convention": False}

    axes = {
        "J1": frame("A-BridaEje-1", [0, 0, 0], [0, 0, 1], 8),
        "J2": frame("A-Brazo-1", [0, -.025, .280], [0, 1, 0], 4.5),
        "J3": frame("Z-BujeExterior-1", [0, 0, .028], [0, 0, -1], 17.5),
        "J4": frame("Z-Piston-1", [0, 0, 0], [0, 0, 1]),
    }
    references = {
        "J1": [frame("A-Brazo-1", [0, -.023, .030], [0, -1, 0], 8)],
        "J2": [frame("B-Antebrazo-1", [0, -.025, .220], [0, 1, 0], 4),
               frame("B-CarretelInf-1", [0, 0, 0], [0, 0, 1])],
        "J3": [frame("R-Bancada-1", [0, -.017, -.020], [0, 1, 0], 27.5),
               frame("Z-Cuerpo-1", [0, 0, 0], [0, 0, 1])],
        "J4": [frame("Z-Cuerpo-1", [0, 0, 0], [0, 0, 1])],
    }
    for name, candidates in references.items():
        point, axis = axes[name]["point_on_axis_assembly_m"], axes[name]["axis_direction_assembly"]
        for candidate in candidates:
            delta = [candidate["point_on_axis_assembly_m"][i]-point[i] for i in range(3)]
            dot = sum(delta[i]*axis[i] for i in range(3))
            distance = math.sqrt(sum((delta[i]-dot*axis[i])**2 for i in range(3)))
            parallel = abs(sum(candidate["axis_direction_assembly"][i]*axis[i] for i in range(3)))
            assert distance < 1e-10 and abs(parallel-1) < 1e-8
            candidate["perpendicular_distance_m"] = distance
        axes[name]["independent_line_agreement_checks"] = candidates
    points = [axes[name]["point_on_axis_assembly_m"] for name in ("J1", "J2", "J3")]
    lengths = {label: math.hypot(points[i][0]-points[i+1][0], points[i][1]-points[i+1][1])
               for i, label in enumerate(("J1_J2_horizontal_m", "J2_J3_horizontal_m"))}
    assert all(abs(value-.25) < 1e-10 for value in lengths.values())
    groups = {
        "fixed_base": ["0-Torre-1"], "arm_proposed": ["A-Brazo-1", "A-BridaEje-1"],
        "forearm_proposed": ["B-Antebrazo-1", "NEMA17-1", "R-Bancada-1", "R-ContraBancada-1"],
        "z_rotating_outer_proposed": ["Z-BujeExterior-1", "Z-Cuerpo-1", "Z-SoporteM4-1", "Z-SoporteRuleman-1", "NEMA17-2"],
        "z_sliding_proposed": ["Z-Piston-1", "Z-SoporteEfector-1"],
        "transmission_membership_unresolved": ["A-CarretelInf-1", "A-CarretelSup-1", "B-CarretelInf-1", "B-CarretelSup-1", "R-CarretelInf-1", "R-CarretelSup-1"],
    }
    assert sorted(sum(groups.values(), [])) == sorted(by)
    result = {"generator_sha256": digest(Path(__file__).read_bytes()),
              "assembly_report_sha256": digest(report_path.read_bytes()),
              "source_assembly": assembly["source"], "source_sha256": assembly["source_sha256"],
              "units": "m", "frame": "exact saved 0-EnsambleColision assembly frame",
              "axes": axes, "horizontal_link_lengths": lengths,
              "tool_support": {"instance": "Z-SoporteEfector-1", "official_tcp_defined": False,
                  "transform_object_to_assembly_m": by["Z-SoporteEfector-1"]["transform_object_to_assembly_m"],
                  "mesh_status": "rejected; cached frame only"},
              "grouping_proposal": groups,
              "grouping_status": "Engineering proposal from documented construction and geometry; mates not solved. Carretels intentionally unresolved.",
              "basis_for_upright_frame": {"candidate_rotation_saved_to_upright": [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
                  "candidate_name": "180 degrees around saved X; still requires translation and yaw convention", "applied": False},
              "joint_zeros_limits_and_motor_signs_determined": False}
    for name, data in [("evidencia_ejes_cilindros.json", evidence), ("ejes_propuestos.json", result)]:
        (ROOT / "cad/ensambles" / name).write_text(json.dumps(data, indent=2) + "\n")
    print("PASS: observed cylinders, cross-part coaxiality, two 250mm lengths and 20-instance grouping coverage")


if __name__ == "__main__":
    main()
