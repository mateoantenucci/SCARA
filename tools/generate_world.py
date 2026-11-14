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


# Carcasas que tapan las poleas: el campo housingTransparency del PROTO las
# vuelve transparentes para verlas girar (solo visual).
HOUSINGS = {'0-Torre-1', '0-PlatinaSuperior-registro-1', 'A-Brazo-1', 'B-Antebrazo-1',
            'B-SoporteM3-registro-1', 'R-Bancada-1', 'R-ContraBancada-1'}


def numbers(values):
    return " ".join(f"{v:.15g}" for v in values)


# Sensores Hall (D10, D56): un KY-003 por articulación, en la pieza fija, y dos
# imanes en la que se mueve, centrados en los extremos del recorrido. En
# Webots, el imán es un Emitter con su alcance y el KY-003 un Receiver del
# mismo canal: el Hall se activa cuando el imán está a menos del alcance, así
# que la activación sale de la geometría, no de leer la posición de las
# articulaciones. Webots no entrega paquetes dentro de un mismo robot: la
# distancia la mide la planta (scara_uci.cpp, D57).
# Montaje (D93): en J1–J3 los imanes van pegados por fuera de la pared del
# carretel que gira con la pieza (radio 35 mm, pared de 2 mm) y el KY-003, en
# una escuadra atornillada a la pieza fija, mira a esa pared desde 180°. En J4
# el único cuerpo que recorre los 120 mm frente a un punto fijo es el pistón:
# los imanes van por dentro de su pared, porque por fuera rozarían el cuerpo Z
# en el que corre, y el KY-003 cuelga del buje exterior con una abrazadera.
# El flanco del lado negativo es HALL_EDGE en firmware/config.h
# (tests/test_hall.py lo verifica).
HALL_HALF_WIDTH = (math.radians(5), math.radians(5), math.radians(5), 0.003)
MAGNET = (0.004, 0.003)  # imán de neodimio de Ø8 × 3 mm, con el eje hacia el sensor
HALL_GAP = 0.0015  # del imán (o de la cara del pistón) a la cara del sensor
REEL_RADIUS = 0.035  # cara exterior de los carreteles
# Altura del medio de la pared del carretel que gira, en el marco de la pieza
# que se mueve: A-CarretelSup, B-CarretelInf y R-CarretelSup.
HALL_HEIGHT = (-0.048, 0.034, 0.045)
# Cara de la pieza fija donde se atornilla la escuadra, en su marco: tapa de la
# torre, cara de abajo del brazo y cara de arriba del antebrazo.
HALL_MOUNT_Z = (0.2216, -0.025, 0.025)
# J4: cara y pared del pistón (tubo de 20 mm) y altura del sensor en el cuerpo
# Z, justo debajo del buje exterior (que termina en -38 mm).
PISTON_FACE, PISTON_WALL, HALL4_Z = 0.010, 0.0012, -0.0475
# Collar de la escuadra de J4 alrededor del buje exterior (radio 17,5 mm); baja
# 0,4 mm más que el buje y tapa su borde.
COLLAR_RADIUS, COLLAR_Z, COLLAR_HEIGHT = 0.0215, -0.0344, 0.008
# Modelo CAD del KY-003: placa de 15 × 27,5 mm con el TO-92 en la punta. Su
# punto sensible es la cabeza del TO-92, 1 mm detrás de la cara que mira al imán.
KY003_TIP = (0, 0.012, 0.004)
KY003_DEPTH = 0.001
BRACKET_COLOR = '0.16 0.16 0.17'  # PLA negro


def hall_layout(joint):
    """Distancia al eje del punto sensible y del centro de los imanes, y su altura."""
    if joint == 3:
        return PISTON_FACE + HALL_GAP + KY003_DEPTH, PISTON_FACE - PISTON_WALL - MAGNET[1] / 2, HALL4_Z
    return REEL_RADIUS + MAGNET[1] + HALL_GAP + KY003_DEPTH, REEL_RADIUS + MAGNET[1] / 2, HALL_HEIGHT[joint]


def hall_range(joint):
    """Alcance del imán para que la zona activa mida ±HALL_HALF_WIDTH."""
    sensor, magnet, _ = hall_layout(joint)
    if joint == 3:
        return math.hypot(sensor - magnet, HALL_HALF_WIDTH[3])  # el imán pasa de largo frente al sensor
    return math.sqrt(sensor ** 2 + magnet ** 2 - 2 * sensor * magnet * math.cos(HALL_HALF_WIDTH[joint]))


def hall_sensor(joint, anchor):
    """KY-003 de Jj+1 en su escuadra, en el marco de la pieza fija; anchor es el eje de la articulación.

    Los hijos se dibujan en el marco del sensor: x se aleja del imán, z hacia arriba.
    """
    radius, _, height = hall_layout(joint)
    mm = 0.001
    origin = [KY003_TIP[2], -KY003_TIP[1], -KY003_TIP[0]]  # del modelo, con su cara de componentes hacia el imán
    board = (-13.5 * mm - KY003_TIP[1], 14 * mm - KY003_TIP[1])  # largo de la placa, a lo ancho del sensor
    back = 4 * mm  # dorso de la placa, detrás del punto sensible
    edge = 4.5 * mm  # la escuadra cubre 9 de los 15 mm de la placa: se ve el KY-003
    parts = [box([3 * mm, board[1] - board[0], 2 * edge], [back + 1.5 * mm, sum(board) / 2, 0], BRACKET_COLOR)]
    if joint == 3:
        position, turn = [radius, 0, height], 0
        # Pata hasta el collar, que abraza el buje exterior.
        leg_top = COLLAR_Z - COLLAR_HEIGHT / 2 - height
        parts.append(box([3 * mm, 8 * mm, leg_top - edge], [back + 1.5 * mm, -2 * mm, (leg_top + edge) / 2],
                         BRACKET_COLOR))
        parts.append(f"""Pose {{ translation {numbers([-radius, 0, COLLAR_Z - height])} children [ Shape {{
          appearance PBRAppearance {{ baseColor {BRACKET_COLOR} roughness 0.7 metalness 0.1 }}
          geometry Cylinder {{ radius {COLLAR_RADIUS} height {COLLAR_HEIGHT} }} }} ] }}""")
    else:
        position, turn = [anchor[0] - radius, anchor[1], anchor[2] + height], math.pi
        # Pata hasta la cara de la pieza fija y pie de 12 mm atornillado a ella.
        mount = HALL_MOUNT_Z[joint] - position[2]
        edge = edge if mount > 0 else -edge
        foot = mount - 1.5 * mm if mount > 0 else mount + 1.5 * mm
        middle = sum(board) / 2
        parts.append(box([3 * mm, 12 * mm, abs(mount - edge)], [back + 1.5 * mm, middle, (mount + edge) / 2],
                         BRACKET_COLOR))
        parts.append(box([12 * mm, 12 * mm, 3 * mm], [back + 6 * mm, middle, foot], BRACKET_COLOR))
    return f"""Receiver {{ translation {numbers(position)} name "hall{joint+1}"
      type "radio" channel {joint+1} rotation 0 0 1 {turn:.15g}
      children [ Pose {{ translation {numbers(origin)} rotation 0 1 0 {-math.pi / 2:.15g} children [ Shape {{
          appearance PBRAppearance {{ baseColor 0.15 0.35 0.75 roughness 0.6 metalness 0 }}
          geometry Mesh {{ url [ "../../cad/derivados/stl/KY-003.stl" ] }} }} ] }}
        {' '.join(parts)} ] }}"""


def hall_magnets(joint, limits, offset=0):
    """Imanes de Jj+1 en el marco de la pieza que se mueve, con su origen en el eje.

    offset es la altura del sensor sobre el origen de la pieza que se mueve con
    J = 0, si no es la de HALL_HEIGHT (J4: el pistón cuelga del cuerpo Z).
    """
    _, radius, height = hall_layout(joint)
    nodes = []
    for name, center in (("inicio", limits[0]), ("fin", limits[1])):
        if joint == 3:
            # J4 baja cuando crece: el imán queda alineado con el sensor con J4 = center.
            position, rotation = [radius, 0, height + offset + center], [0, 1, 0, math.pi / 2]
        else:
            angle = math.pi - center  # el sensor está a 180°: con J = center, el imán queda frente a él
            position = [radius * math.cos(angle), radius * math.sin(angle), height]
            rotation = [-math.sin(angle), math.cos(angle), 0, math.pi / 2]  # eje del imán hacia afuera
        nodes.append(f"""Emitter {{ translation {numbers(position)} name "iman{joint+1}_{name}"
      type "radio" range {hall_range(joint):.15g} maxRange {hall_range(joint):.15g} channel {joint+1}
      rotation {numbers(rotation)}
      children [ Shape {{ appearance PBRAppearance {{ baseColor 0.75 0.75 0.78 roughness 0.3 metalness 0.8 }}
        geometry Cylinder {{ radius {MAGNET[0]} height {MAGNET[1]} }} }} ] }}""")
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
    rotating = set(json.loads((ROOT/'config/cad_integration.json').read_text()).get('rotating_occurrences', []))
    spin_fields = []
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
            clear = ' transparency IS housingTransparency' if entry['instance_name'] in HOUSINGS else ''
            for mesh in entry['meshes']:
                url = os.path.relpath(ROOT/mesh['path'], ROOT/'webots/protos').replace(os.sep, '/')
                shapes.append(f"""Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 0.55 metalness 0.15{clear} }}
                  geometry Mesh {{ url [ {json.dumps(url)} ] }} castShadows FALSE }}""")
            if not shapes:
                shapes.append(wire_box(entry['bbox_local_m']))
            if entry['instance_name'] in rotating:
                # Polea que gira sobre su eje, solo visual: la planta le pone el
                # ángulo (PULLEYS en scara_uci.cpp) por un campo del PROTO, porque
                # los internos son de solo lectura. El eje apunta a +Z del cuerpo,
                # así un ángulo positivo es el giro positivo de su motor.
                axis = 1 if entry['body_from_piece'][2][2] > 0 else -1
                field = 'spin_' + entry['def_name'].removeprefix('CAD_')
                spin_fields.append(f"field SFRotation {field} 0 0 {axis} 0")
                # Las mallas de las poleas son lisas: sin una marca, el giro no se
                # ve. Franja en la llanta; no es geometría del CAD.
                box = entry['bbox_local_m']
                mark = f"""Pose {{ translation {numbers([box[3], 0, (box[2]+box[5])/2])} children [ Shape {{
                    appearance PBRAppearance {{ baseColor 1 0.85 0 roughness 0.5 metalness 0 }}
                    geometry Box {{ size {numbers([0.002, 0.004, box[5]-box[2]+0.001])} }} }} ] }}"""
                shapes = [f"""Pose {{ rotation IS {field}
                  children [ {' '.join(shapes)} {mark} ] }}"""]
            poses.append(f"""# {entry['instance_name']} | {entry['disposition']} | {entry['attachment_status']}
              DEF {entry['def_name']} Pose {{ translation {numbers([matrix[i][3] for i in range(3)])}
                rotation {numbers(axis_angle(matrix))} children [ {' '.join(shapes)} ] }}""")
        return '\n'.join(poses)

    tool = f"""DEF TOOL Solid {{
      translation 0 0 {g['tool_z_offset']-q[3]:.15g} name "piston_y_soporte"
      children [ {visual('tool')} {hall_magnets(3, c['limits'][3], -g['tool_z_offset'])}
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
      children [ {visual('wrist')} {hall_magnets(2, c['limits'][2])}
        {hall_sensor(3, [0, 0, 0])} {slider} ]
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
              children [ {visual(group)} {hall_magnets(axis-1, c['limits'][axis-1])}
                {hall_sensor(axis, anchors[axis])} {joint} ]
              boundingObject {collision(cad,group)}
              physics {physics(bodies[axis-1])} }}"""
    tool_mass, tool_center, tool_inertia = box_with_payload(bodies[3])
    base = visual('base')  # antes del encabezado: completa spin_fields
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
  # Solo visual: transparencia de las carcasas que tapan las poleas (0 a 1) y
  # giro de las poleas de motor y del eje interior, que lo pone la planta.
  field SFFloat housingTransparency 0
  {chr(10).join('  ' + f for f in spin_fields).lstrip()}
] {{
  DEF BASE Robot {{ translation IS translation rotation IS rotation
    name "SCARA" model "SCARA con CAD articulado parcial; parametros fisicos provisionales"
    supervisor TRUE controller IS controller controllerArgs IS controllerArgs selfCollision FALSE
    children [ {base} {hall_sensor(0, anchors[0])}
      # Un Solid físico bajo la base estática queda soldado al entorno por
      # Webots. Da a J1 un cuerpo padre para medir su esfuerzo sin liberar la base.
      DEF J1_MOUNT Solid {{ name "soporte_j1_fijo"
        children [ {joint} ]
        # Masa e inercia numéricas del soporte inmóvil; no agregan geometría.
        physics Physics {{ density -1 mass 1 centerOfMass [ 0 0 0 ]
          inertiaMatrix [ 0.01 0.01 0.01, 0 0 0 ] }} }} ]
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
