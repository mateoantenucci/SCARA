"""Observador del ensayo de transmisión: lee la posición física simulada.

Controlador de Webots para un robot supervisor aparte, que el ensayo agrega a
un mundo temporal. No toca al SCARA: mide las orientaciones relativas de sus
cuerpos y la separación del pistón respecto de la muñeca. Usa la geometría
del robot, sin capturar un origen antes de que arranque la UCI (el orden de
arranque de los controladores no está garantizado). El antiguo argumento
"absoluto" sigue aceptado; las medidas ahora siempre son absolutas.
Escribe cada 10 ms, en el archivo que recibe como primer argumento, J1–J4
en unidades de scara/1 (floats) y el rumbo.
"""

import json
import math
import os
from pathlib import Path
import sys

from controller import Supervisor

BODIES = ("ARM", "FOREARM", "WRIST", "TOOL")


def relative_rotation(parent, child):
    """parentᵀ · child con matrices de 3 × 3 en listas de 9."""
    return [sum(parent[3 * k + i] * child[3 * k + j] for k in range(3))
            for i in range(3) for j in range(3)]


def heading(parent, child):
    """Giro alrededor del eje local Z entre cuerpos, en centésimas de grado."""
    turn = relative_rotation(parent, child)
    return math.degrees(math.atan2(turn[3], turn[0])) * 100


def wrapped(angle):
    """Ángulo en centésimas de grado, llevado a [−18000, 18000)."""
    return (angle + 18000) % 36000 - 18000


robot = Supervisor()
step = int(robot.getBasicTimeStep())
scara = robot.getFromDef("SCARA")
nodes = [scara.getFromProtoDef(name) for name in BODIES]
# El ensayo copia este controlador bajo webots/controllers/; la configuración
# es la misma fuente geométrica con la que se generó el PROTO.
root = Path(__file__).resolve().parents[3]
tool_offset = json.loads((root / "config/scara.json").read_text())["geometry"]["tool_z_offset"]
path = sys.argv[1]
count = 0
while robot.step(step) != -1:
    count += 1
    if count % max(1, 10 // step):
        continue
    orientations = [scara.getOrientation(), *(node.getOrientation() for node in nodes[:3])]
    arm, elbow, wrist = (heading(orientations[i], orientations[i + 1]) for i in range(3))
    offset = [a - b for a, b in zip(nodes[3].getPosition(), nodes[2].getPosition())]
    tool_z = sum(offset[i] * orientations[3][3 * i + 2] for i in range(3))
    # J4 es positivo hacia abajo; 1 m son 100000 centésimas de mm.
    j4 = (tool_offset - tool_z) * 100000
    # Los rumbos dan la vuelta en ±180°; cada articulación cabe en ±180°.
    sample = {"t": robot.getTime(), "joints": [arm, wrapped(elbow), wrapped(wrist), j4],
              "heading": wrapped(arm + elbow + wrist)}
    with open(path + ".tmp", "w", encoding="utf-8") as file:
        json.dump(sample, file)
    try:
        os.replace(path + ".tmp", path)
    except PermissionError:
        pass  # Windows: el ensayo lo está leyendo; va la próxima muestra
