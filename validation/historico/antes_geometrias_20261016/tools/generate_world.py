"""Genera el SCARA articulado con visuales CAD y física equivalente provisional."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.dynamics import box_with_payload
from scara.collisions import piece_boxes
from scara.frames import transform_point
from scara.kinematics import load_config
from generate_cad_preview import axis_angle, wire_box
from integrate_cad import BODY_DEFS, derive


def numbers(values):
    return " ".join(f"{v:.15g}" for v in values)


def box(size, center, color):
    return f"""Pose {{ translation {numbers(center)} children [ Shape {{
      appearance PBRAppearance {{ baseColor {color} roughness 0.7 metalness 0.1 }}
      geometry Box {{ size {numbers(size)} }} }} ] }}"""


def physics(body):
    mass, center, inertia = box_with_payload(body)
    return f"""Physics {{ density -1 mass {mass:.15g}
      centerOfMass [ {numbers(center)} ]
      inertiaMatrix [ {numbers(inertia[:3])}, {numbers(inertia[3:])} ] }}"""


def collision(cad, group):
    boxes = []
    for part in piece_boxes(cad):
        if part['group'] != group:
            continue
        center = transform_point(part['pose'],part['center'])
        boxes.append(f"""# {part['name']} | {part['disposition']}
          Pose {{ translation {numbers(center)} rotation {numbers(axis_angle(part['pose']))}
            children [ Box {{ size {numbers(part['size'])} }} ] }}""")
    return 'Group { children [ ' + '\n'.join(boxes) + ' ] }'


def build():
    c = load_config()
    cad = derive(c)
    if any(abs(value-c['geometry'][key]) > 1e-9 for key,value in cad['geometry'].items()):
        raise ValueError("Geometría desactualizada: ejecutar tools/integrate_cad.py --update-config")
    g, q, bodies = c['geometry'], c['initial_positions'], c['body_properties']
    colors = dict(base='0.45 0.48 0.52', arm='0.72 0.30 0.23', forearm='0.22 0.48 0.7',
                  wrist='0.68 0.72 0.76', tool='0.22 0.62 0.48')

    def visual(group):
        poses = []
        for entry in cad['instances']:
            if entry['group'] != group:
                continue
            matrix = entry['body_from_piece']
            color = '0.9 0.5 0.12' if entry['disposition'] == 'accepted_mesh_cache_differs' else colors[group]
            shapes = []
            for mesh in entry['meshes']:
                url = os.path.relpath(ROOT/mesh['path'], ROOT/'webots/protos').replace(os.sep, '/')
                shapes.append(f"""Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 0.55 metalness 0.15 }}
                  geometry Mesh {{ url [ {json.dumps(url)} ] }} castShadows FALSE }}""")
            if not shapes:
                shapes.append(wire_box(entry['bbox_local_m']))
            poses.append(f"""# {entry['instance_name']} | {entry['disposition']} | {entry['attachment_status']}
              DEF {entry['def_name']} Pose {{ translation {numbers([matrix[i][3] for i in range(3)])}
                rotation {numbers(axis_angle(matrix))} children [ {' '.join(shapes)} ] }}""")
        return '\n'.join(poses)

    tool = f"""DEF TOOL Solid {{
      translation 0 0 {g['tool_z_offset']-q[3]:.15g} name "piston_y_soporte"
      children [ {visual('tool')}
        # Marcador del TCP provisional; no es geometría de una pinza.
        Shape {{ appearance PBRAppearance {{ baseColor 0.1 0.9 0.3 roughness 0.5 metalness 0 }}
          geometry Sphere {{ radius 0.004 }} }} ]
      boundingObject {collision(cad,'tool')}
      physics Physics {{ density -1 mass IS toolMass
        centerOfMass IS toolCenterOfMass inertiaMatrix IS toolInertiaMatrix }}
    }}"""
    slider = f"""SliderJoint {{
      jointParameters JointParameters {{ axis 0 0 -1 position {q[3]:.15g}
        minStop {c['limits'][3][0]} maxStop {c['limits'][3][1]} dampingConstant 0.2 }}
      device [ LinearMotor {{ name "j4_motor" minPosition {c['limits'][3][0]} maxPosition {c['limits'][3][1]}
        maxVelocity {c['max_velocity'][3]} acceleration {c['max_acceleration'][3]} maxForce {c['max_effort'][3]} }}
        PositionSensor {{ name "j4_sensor" }} ] endPoint {tool} }}"""
    endpoint = f"""DEF WRIST Solid {{
      translation {g['l2']:.15g} 0 0 rotation 0 0 1 {q[2]:.15g} name "conjunto_z"
      children [ {visual('wrist')} {slider} ]
      boundingObject {collision(cad,'wrist')}
      physics {physics(bodies[2])} }}"""
    anchors = [[0,0,g['shoulder_z']], [g['l1'],0,g['elbow_z_offset']], [g['l2'],0,0]]
    for axis in (2,1,0):
        joint = f"""HingeJoint {{
          jointParameters HingeJointParameters {{ axis 0 0 1 anchor {numbers(anchors[axis])}
            position {q[axis]:.15g} minStop {c['limits'][axis][0]} maxStop {c['limits'][axis][1]}
            dampingConstant 0.01 }}
          device [ RotationalMotor {{ name "j{axis+1}_motor" minPosition {c['limits'][axis][0]}
            maxPosition {c['limits'][axis][1]} maxVelocity {c['max_velocity'][axis]}
            acceleration {c['max_acceleration'][axis]} maxTorque {c['max_effort'][axis]} }}
            PositionSensor {{ name "j{axis+1}_sensor" }} ] endPoint {endpoint} }}"""
        if axis:
            group = 'forearm' if axis == 2 else 'arm'
            endpoint = f"""DEF {BODY_DEFS[group]} Solid {{
              translation {numbers(anchors[axis-1])} rotation 0 0 1 {q[axis-1]:.15g} name "{group}"
              children [ {visual(group)} {joint} ]
              boundingObject {collision(cad,group)}
              physics {physics(bodies[axis-1])} }}"""
    tool_mass, tool_center, tool_inertia = box_with_payload(bodies[3])
    proto = f"""#VRML_SIM R2025a utf8
# Generado por tools/generate_world.py. Visuales CAD parciales; física y referencias provisionales.
PROTO SCARA [
  field SFVec3f translation 0 0 0
  field SFRotation rotation 0 0 1 0
  field SFString controller "scara_bridge"
  field MFString controllerArgs [ ]
  field SFFloat toolMass {tool_mass:.15g}
  field MFVec3f toolCenterOfMass [ {numbers(tool_center)} ]
  field MFVec3f toolInertiaMatrix [ {numbers(tool_inertia[:3])}, {numbers(tool_inertia[3:])} ]
] {{
  DEF BASE Robot {{ translation IS translation rotation IS rotation
    name "SCARA" model "SCARA con CAD articulado parcial; parametros fisicos provisionales"
    supervisor TRUE controller IS controller controllerArgs IS controllerArgs selfCollision FALSE
    children [ {visual('base')} {joint} ]
    boundingObject {collision(cad,'base')}
  }}
}}
"""
    world = """#VRML_SIM R2025a utf8
EXTERNPROTO "../protos/SCARA.proto"
WorldInfo { basicTimeStep TIME_STEP_MS info [ "Visuales CAD articulados; propiedades materiales, transmisiones y TCP provisionales" ] }
Viewpoint { orientation -0.247320324917239 0.12594159147589 0.960713990956388 2.23162100538708 position 0.95 -0.95 0.85 }
Background { skyColor [ 0.9 0.93 0.97 ] }
DirectionalLight { direction -0.4 0.5 -1 intensity 1 castShadows TRUE }
DirectionalLight { direction 0.5 -0.5 -1 intensity 0.5 }
"""
    world = world.replace('TIME_STEP_MS',str(c['simulation']['basic_time_step_ms']))
    for obstacle in c['environment']:
        world += f"""DEF ENV_{obstacle['name']} Solid {{ name "{obstacle['name']}"
          translation {numbers(obstacle['center'])}
          children [ Shape {{ appearance PBRAppearance {{ baseColor {numbers(obstacle['color'])} roughness 0.9 metalness 0 }}
            geometry Box {{ size {numbers(obstacle['size'])} }} }} ]
          boundingObject Box {{ size {numbers(obstacle['size'])} }} }}
"""
    world += 'DEF SCARA SCARA { }\n'
    for path, content in ((ROOT/'webots/protos/SCARA.proto', proto), (ROOT/'webots/worlds/scara.wbt', world)):
        path.write_text(content, encoding='utf-8')
        print(path.relative_to(ROOT))
    (ROOT/'cad/ensambles/integracion_articulada.json').write_text(json.dumps(cad,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    build()
