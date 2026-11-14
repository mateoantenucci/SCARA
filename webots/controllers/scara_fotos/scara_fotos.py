"""Saca las fotos del SCARA en Webots para el informe (webots/worlds/scara_fotos.wbt).

Lo corren dos robots del mundo con la misma lista de tomas. El SCARA se lleva a
la pose de cada toma con sus motores; el «fotógrafo», un robot sin física con
una cámara, se ubica mirando al objetivo y guarda la imagen cuando la pose ya
se asentó. Al terminar, cierra Webots.

    webots --batch --mode=fast --minimize webots/worlds/scara_fotos.wbt

Las imágenes van a docs/informe/img/ (o a SCARA_FOTOS_DIR, si está definida).
"""

import math
import os
from pathlib import Path

from controller import Supervisor

ROOT = Path(__file__).resolve().parents[3]
DESTINO = Path(os.environ.get("SCARA_FOTOS_DIR", ROOT / "docs" / "informe" / "img"))
DURACION = 4.0  # s por toma: el SCARA llega a la pose y se asienta antes de la foto

# Nombre, pose (J1–J3 en grados, J4 en mm), cámara y punto al que mira (m).
TOMAS = [
    ("webots-general", (40, -50, 10, 40), (1.05, -0.95, 0.9), (0.2, 0.12, 0.2)),
    ("webots-reposo", (0, 0, 0, 120), (0.3, -1.35, 0.55), (0.26, 0.0, 0.25)),
    ("webots-hall-j1", (110, 70, 0, 60), (-0.17, -0.13, 0.31), (-0.035, 0.0, 0.243)),
    ("webots-hall-j2", (0, 120, 0, 60), (0.17, -0.17, 0.26), (0.215, 0.0, 0.249)),
    ("webots-hall-j3", (0, 0, -120, 60), (0.37, -0.15, 0.34), (0.465, 0.0, 0.258)),
    ("webots-hall-j4", (0, 0, 0, 60), (0.6, -0.11, 0.15), (0.51, -0.005, 0.168)),
]


def orientacion(desde, hacia):
    """Rotación (eje y ángulo) de una cámara en `desde` que mira a `hacia` con z arriba."""
    f = [h - d for d, h in zip(desde, hacia)]
    n = math.sqrt(sum(v * v for v in f))
    f = [v / n for v in f]
    izq = [-f[1], f[0], 0.0]
    n = math.hypot(izq[0], izq[1])
    izq = [v / n for v in izq]
    arriba = [f[1] * izq[2] - f[2] * izq[1], f[2] * izq[0] - f[0] * izq[2], f[0] * izq[1] - f[1] * izq[0]]
    m = [[f[0], izq[0], arriba[0]], [f[1], izq[1], arriba[1]], [f[2], izq[2], arriba[2]]]
    angulo = math.acos(max(-1.0, min(1.0, (m[0][0] + m[1][1] + m[2][2] - 1) / 2)))
    if angulo < 1e-9:
        return [0, 0, 1, 0]
    eje = [m[2][1] - m[1][2], m[0][2] - m[2][0], m[1][0] - m[0][1]]
    n = math.sqrt(sum(v * v for v in eje))
    if n < 1e-9:  # media vuelta: el eje sale de la diagonal
        eje = [math.sqrt(max(0.0, (m[i][i] + 1) / 2)) for i in range(3)]
        n = 1.0
    return [v / n for v in eje] + [angulo]


def main():
    robot = Supervisor()
    paso = int(robot.getBasicTimeStep())
    fotografo = robot.getName() == "fotografo"
    if fotografo:
        camara = robot.getDevice("camara")
        camara.enable(paso)
        yo = robot.getSelf()
        DESTINO.mkdir(parents=True, exist_ok=True)
    else:
        motores = [robot.getDevice(f"j{i}_motor") for i in range(1, 5)]
    hecha = -1
    while robot.step(paso) != -1:
        toma = int(robot.getTime() / DURACION)
        if toma >= len(TOMAS):
            if fotografo:
                robot.simulationQuit(0)
            continue
        nombre, pose, desde, hacia = TOMAS[toma]
        if not fotografo:
            for motor, valor in zip(motores[:3], pose[:3]):
                motor.setPosition(math.radians(valor))
            motores[3].setPosition(pose[3] / 1000)
            continue
        yo.getField("translation").setSFVec3f(list(desde))
        yo.getField("rotation").setSFRotation(orientacion(desde, hacia))
        if toma != hecha and robot.getTime() >= (toma + 1) * DURACION - 0.1:
            camara.saveImage(str(DESTINO / f"{nombre}.png"), 100)
            print(f"foto: {DESTINO / nombre}.png")
            hecha = toma


main()
