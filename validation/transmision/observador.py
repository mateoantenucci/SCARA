"""Observador del ensayo de transmisión: lee la posición física simulada.

Controlador de Webots para un robot supervisor aparte, que el ensayo agrega a
un mundo temporal. No toca al SCARA: mide la orientación de sus cuerpos (el
canal de instrumentación llega con el issue #14). El mundo arranca en la pose
de reposo (D38), así que el giro de cada cuerpo desde el arranque es la
posición de su articulación. Escribe cada 10 ms, en el archivo que recibe
como argumento, J1–J4 en unidades de scara/1 (floats) y el rumbo.
"""

import json
import math
import os
import sys

from controller import Supervisor

BODIES = ("ARM", "FOREARM", "WRIST", "TOOL")
REST_J4 = 12000.0  # centésimas de mm: J4 abajo


def product_transposed(a, b):
    """a · bᵀ con matrices de 3 × 3 en listas de 9."""
    return [sum(a[3 * i + k] * b[3 * j + k] for k in range(3)) for i in range(3) for j in range(3)]


def heading(start, now):
    """Giro alrededor de la vertical entre dos orientaciones, en centésimas de grado."""
    turn = product_transposed(now, start)
    return math.degrees(math.atan2(turn[3], turn[0])) * 100


robot = Supervisor()
step = int(robot.getBasicTimeStep())
scara = robot.getFromDef("SCARA")
nodes = [scara.getFromProtoDef(name) for name in BODIES]
start = [node.getOrientation() for node in nodes]
start_z = nodes[3].getPosition()[2]
path = sys.argv[1]
count = 0
while robot.step(step) != -1:
    count += 1
    if count % max(1, 10 // step):
        continue
    arm, forearm, wrist = (heading(start[i], nodes[i].getOrientation()) for i in range(3))
    # J4 es positivo hacia abajo; 1 m son 100000 centésimas de mm.
    j4 = REST_J4 + (start_z - nodes[3].getPosition()[2]) * 100000
    sample = {"t": robot.getTime(), "joints": [arm, forearm - arm, wrist - forearm, j4], "heading": wrist}
    with open(path + ".tmp", "w", encoding="utf-8") as file:
        json.dump(sample, file)
    try:
        os.replace(path + ".tmp", path)
    except PermissionError:
        pass  # Windows: el ensayo lo está leyendo; va la próxima muestra
