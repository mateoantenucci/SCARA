"""Genera el SCARA articulado con visuales CAD y física equivalente provisional."""

import json
import math
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


# Sensores Hall (D10, D56): un KY-003 por articulación, en la pieza fija, y dos
# imanes en la que se mueve, centrados en los extremos del recorrido. En
# Webots, el imán es un Emitter con su alcance y el KY-003 un Receiver del
# mismo canal: el Hall se activa cuando el imán está a menos del alcance, así
# que la activación sale de la geometría, no de leer la posición de las
# articulaciones. Webots no entrega paquetes dentro de un mismo robot: la
# distancia la mide la planta (scara_uci.cpp, D57).
# Por articulación: radio desde el eje (m), ángulo del sensor (rad), centros
# de los imanes (rad o m) y medio ancho de la zona activa. El flanco del lado
# negativo es HALL_EDGE en firmware/config.h (tests/test_hall.py lo verifica).
HALL_HALF_WIDTH = (math.radians(5), math.radians(5), math.radians(5), 0.003)
HALL_RADIUS = (0.06, 0.04, 0.03, 0.03)


def hall_range(joint):
    """Alcance del imán para que la zona activa mida ±HALL_HALF_WIDTH."""
    if joint == 3:
        return HALL_HALF_WIDTH[3]  # imán y sensor alineados: la distancia es el desplazamiento
    return 2 * HALL_RADIUS[joint] * math.sin(HALL_HALF_WIDTH[joint] / 2)


def hall_sensor(joint, origin, height):
    """KY-003 de Jj+1 en el marco de la pieza fija; origin es el eje de la articulación."""
    x = origin[0] + (HALL_RADIUS[joint] if joint == 3 else -HALL_RADIUS[joint])
    return f"""Receiver {{ translation {numbers([x, origin[1], height])} name "hall{joint+1}"
      type "radio" channel {joint+1}
      children [ Shape {{ appearance PBRAppearance {{ baseColor 0.1 0.25 0.6 roughness 0.6 metalness 0 }}
        geometry Box {{ size 0.008 0.008 0.004 }} }} ] }}"""


def hall_magnets(joint, limits, height):
    """Imanes de Jj+1 en el marco de la pieza que se mueve, con su origen en el eje."""
    nodes = []
    for name, center in (("inicio", limits[0]), ("fin", limits[1])):
        if joint == 3:
            # J4 baja cuando crece: el imán queda alineado con el sensor con J4 = center.
            position = [HALL_RADIUS[3], 0, height + center]
        else:
            angle = math.pi - center  # el sensor está a 180°: con J = center, el imán queda debajo
            position = [HALL_RADIUS[joint] * math.cos(angle), HALL_RADIUS[joint] * math.sin(angle), height]
        nodes.append(f"""Emitter {{ translation {numbers(position)} name "iman{joint+1}_{name}"
      type "radio" range {hall_range(joint):.15g} maxRange {hall_range(joint):.15g} channel {joint+1}
      children [ Shape {{ appearance PBRAppearance {{ baseColor 0.75 0.75 0.78 roughness 0.3 metalness 0.8 }}
        geometry Cylinder {{ radius 0.004 height 0.004 }} }} ] }}""")
    return ' '.join(nodes)


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
      children [ {visual('tool')} {hall_magnets(3, c['limits'][3], 0)}
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
        maxVelocity {c['max_velocity'][3]} acceleration {c['max_acceleration'][3]} maxForce IS j4MaxForce }}
        PositionSensor {{ name "j4_sensor" }} ] endPoint {tool} }}"""
    endpoint = f"""DEF WRIST Solid {{
      translation {g['l2']:.15g} 0 0 rotation 0 0 1 {q[2]:.15g} name "conjunto_z"
      children [ {visual('wrist')} {hall_magnets(2, c['limits'][2], 0)}
        {hall_sensor(3, [0, 0], g['tool_z_offset'])} {slider} ]
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
            acceleration {c['max_acceleration'][axis]} maxTorque IS j{axis+1}MaxTorque }}
            PositionSensor {{ name "j{axis+1}_sensor" }} ] endPoint {endpoint} }}"""
        if axis:
            group = 'forearm' if axis == 2 else 'arm'
            endpoint = f"""DEF {BODY_DEFS[group]} Solid {{
              translation {numbers(anchors[axis-1])} rotation 0 0 1 {q[axis-1]:.15g} name "{group}"
              children [ {visual(group)} {hall_magnets(axis-1, c['limits'][axis-1], 0)}
                {hall_sensor(axis, anchors[axis][:2], anchors[axis][2])} {joint} ]
              boundingObject {collision(cad,group)}
              physics {physics(bodies[axis-1])} }}"""
    tool_mass, tool_center, tool_inertia = box_with_payload(bodies[3])
    proto = f"""#VRML_SIM R2025a utf8
# Generado por tools/generate_world.py. Visuales CAD parciales; física y referencias provisionales.
PROTO SCARA [
  field SFVec3f translation 0 0 0
  field SFRotation rotation 0 0 1 0
  field SFString controller "scara_uci"
  field MFString controllerArgs [ ]
  field SFFloat toolMass {tool_mass:.15g}
  field MFVec3f toolCenterOfMass [ {numbers(tool_center)} ]
  field MFVec3f toolInertiaMatrix [ {numbers(tool_inertia[:3])}, {numbers(tool_inertia[3:])} ]
  # Esfuerzo máximo de cada articulación. El mundo de la UCI los sube: ahí el
  # límite lo pone el modelo de los motores de la planta (D64).
  field SFFloat j1MaxTorque {c['max_effort'][0]}
  field SFFloat j2MaxTorque {c['max_effort'][1]}
  field SFFloat j3MaxTorque {c['max_effort'][2]}
  field SFFloat j4MaxForce {c['max_effort'][3]}
] {{
  DEF BASE Robot {{ translation IS translation rotation IS rotation
    name "SCARA" model "SCARA con CAD articulado parcial; parametros fisicos provisionales"
    supervisor TRUE controller IS controller controllerArgs IS controllerArgs selfCollision FALSE
    children [ {visual('base')} {hall_sensor(0, [0, 0], g['shoulder_z'])} {joint} ]
    boundingObject {collision(cad,'base')}
  }}
}}
"""
    # El mundo (webots/worlds/scara_uci.wbt) se mantiene a mano; acá solo el PROTO.
    path = ROOT/'webots/protos/SCARA.proto'
    path.write_text(proto, encoding='utf-8')
    print(path.relative_to(ROOT))
    (ROOT/'cad/ensambles/integracion_articulada.json').write_text(json.dumps(cad,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    build()
