"""Regenera el modelo exploratorio a partir de config/scara.json."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scara.dynamics import box_with_payload
from scara.kinematics import load_config


def numbers(values):
    return " ".join(f"{v:.12g}" for v in values)


def box(size, center, color):
    return f"""Pose {{
      translation {numbers(center)}
      children [ Shape {{
        appearance PBRAppearance {{ baseColor {color} roughness 0.6 metalness 0.2 }}
        geometry Box {{ size {numbers(size)} }}
      }} ]
    }}"""


def physics(body):
    mass, center, inertia = box_with_payload(body)
    return f"""Physics {{ density -1 mass {mass:.12g}
      centerOfMass [ {numbers(center)} ]
      inertiaMatrix [ {numbers(inertia[:3])}, {numbers(inertia[3:])} ]
    }}"""


def build():
    c = load_config()
    g, q = c["geometry"], c["initial_positions"]
    bodies = c["body_properties"]
    tool = f"""DEF TOOL Solid {{
      translation 0 0 {g['tool_z_offset'] - q[3]:.12g}
      name "piston_y_soporte"
      children [
        {box(bodies[3]['size'], bodies[3]['center'], '0.2 0.38 0.75')}
        {box([0.06, 0.06, 0.006], [0, 0, 0], '0.25 0.45 0.8')}
        Shape {{ appearance PBRAppearance {{ baseColor 0.1 0.9 0.3 roughness 0.5 metalness 0 }}
          geometry Sphere {{ radius 0.008 }} }}
      ]
      boundingObject Pose {{ translation {numbers(bodies[3]['center'])}
        children [ Box {{ size {numbers(bodies[3]['size'])} }} ] }}
      physics Physics {{ density -1 mass IS toolMass
        centerOfMass IS toolCenterOfMass inertiaMatrix IS toolInertiaMatrix }}
    }}"""
    slider = f"""SliderJoint {{
      jointParameters JointParameters {{ axis 0 0 -1 position {q[3]:.12g}
        minStop {c['limits'][3][0]} maxStop {c['limits'][3][1]} dampingConstant 0.2 }}
      device [ LinearMotor {{ name "j4_motor" minPosition {c['limits'][3][0]} maxPosition {c['limits'][3][1]}
        maxVelocity {c['max_velocity'][3]} acceleration {c['max_acceleration'][3]} maxForce {c['max_effort'][3]} }}
        PositionSensor {{ name "j4_sensor" }} ]
      endPoint {tool}
    }}"""
    endpoint = f"""Solid {{
      translation {g['l2']} 0 0 rotation 0 0 1 {q[2]:.12g}
      name "conjunto_z"
      children [ {box(bodies[2]['size'], bodies[2]['center'], '0.65 0.67 0.7')} {slider} ]
      boundingObject Pose {{ translation {numbers(bodies[2]['center'])}
        children [ Box {{ size {numbers(bodies[2]['size'])} }} ] }}
      physics {physics(bodies[2])}
    }}"""
    anchors = [[0, 0, g['shoulder_z']], [g['l1'], 0, g['elbow_z_offset']], [g['l2'], 0, 0]]
    for axis in (2, 1, 0):
        joint = f"""HingeJoint {{
          jointParameters HingeJointParameters {{ axis 0 0 1 anchor {numbers(anchors[axis])}
            position {q[axis]:.12g} minStop {c['limits'][axis][0]} maxStop {c['limits'][axis][1]}
            dampingConstant 0.01 }}
          device [ RotationalMotor {{ name "j{axis+1}_motor" minPosition {c['limits'][axis][0]}
            maxPosition {c['limits'][axis][1]} maxVelocity {c['max_velocity'][axis]}
            acceleration {c['max_acceleration'][axis]} maxTorque {c['max_effort'][axis]} }}
            PositionSensor {{ name "j{axis+1}_sensor" }} ]
          endPoint {endpoint}
        }}"""
        if axis:
            body = bodies[axis-1]
            endpoint = f"""Solid {{
              translation {numbers(anchors[axis-1])} rotation 0 0 1 {q[axis-1]:.12g}
              name "{'antebrazo' if axis == 2 else 'brazo'}"
              children [ {box(body['size'], body['center'], '0.65 0.23 0.2')} {joint} ]
              boundingObject Pose {{ translation {numbers(body['center'])}
                children [ Box {{ size {numbers(body['size'])} }} ] }}
              physics {physics(body)}
            }}"""
    tool_mass, tool_center, tool_inertia = box_with_payload(bodies[3])
    proto = f"""#VRML_SIM R2025a utf8
# Generado por tools/generate_world.py. Modelo exploratorio, NO montaje CAD validado.
PROTO SCARA [
  field SFVec3f translation 0 0 0
  field SFRotation rotation 0 0 1 0
  field SFString controller "scara_bridge"
  field SFFloat toolMass {tool_mass:.12g}
  field MFVec3f toolCenterOfMass [ {numbers(tool_center)} ]
  field MFVec3f toolInertiaMatrix [ {numbers(tool_inertia[:3])}, {numbers(tool_inertia[3:])} ]
] {{
  Robot {{
    translation IS translation rotation IS rotation
    name "SCARA" model "SCARA exploratorio; parametros provisionales"
    supervisor TRUE controller IS controller selfCollision FALSE
    children [
      {box([0.28, 0.28, 0.025], [0, 0, 0.0125], '0.4 0.42 0.45')}
      {box([0.12, 0.12, 0.16], [0, 0, 0.105], '0.58 0.56 0.5')}
      {joint}
    ]
    boundingObject Group {{ children [
      Pose {{ translation 0 0 0.0125 children [ Box {{ size 0.28 0.28 0.025 }} ] }}
      Pose {{ translation 0 0 0.105 children [ Box {{ size 0.12 0.12 0.16 }} ] }}
    ] }}
  }}
}}
"""
    world = """#VRML_SIM R2025a utf8
EXTERNPROTO "../protos/SCARA.proto"
WorldInfo { basicTimeStep 16 }
Viewpoint { orientation -0.247320324917239 0.12594159147589 0.960713990956388 2.23162100538708 position 0.95 -0.95 0.85 }
Background { skyColor [ 0.9 0.93 0.97 ] }
DirectionalLight { direction -0.4 0.5 -1 intensity 1 castShadows TRUE }
DirectionalLight { direction 0.5 -0.5 -1 intensity 0.5 }
Solid {
  name "suelo_de_ensayo"
  translation 0 0 -0.205
  children [ Shape {
    appearance PBRAppearance { baseColor 0.78 0.8 0.83 roughness 0.9 metalness 0 }
    geometry Box { size 2 2 0.01 }
  } ]
  boundingObject Box { size 2 2 0.01 }
}
Solid {
  name "pedestal_de_ensayo"
  translation 0 0 -0.1
  children [ Shape {
    appearance PBRAppearance { baseColor 0.45 0.48 0.52 roughness 0.9 metalness 0 }
    geometry Box { size 0.32 0.32 0.2 }
  } ]
  boundingObject Box { size 0.32 0.32 0.2 }
}
DEF SCARA SCARA { }
"""
    for path, content in ((ROOT / "webots/protos/SCARA.proto", proto),
                          (ROOT / "webots/worlds/scara.wbt", world)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    build()
