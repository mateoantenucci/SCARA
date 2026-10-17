"""Cinemática R-R-R-P; SI, Z vertical y J4 positivo hacia abajo."""

import itertools
import json
import math
from pathlib import Path


def load_config(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "config/scara.json"
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _numbers(values, count, name):
    if not isinstance(values, (list, tuple)) or len(values) != count:
        raise ValueError(f"{name}: se necesitan {count} valores")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError(f"{name}: usar numeros finitos")
    try:
        converted = [float(v) for v in values]
    except OverflowError as exc:
        raise ValueError(f"{name}: valor fuera de rango") from exc
    if not all(math.isfinite(v) for v in converted):
        raise ValueError(f"{name}: usar numeros finitos")
    return converted


def validate_joints(q, config=None):
    config = config or load_config()
    q = _numbers(q, 4, "Articulaciones")
    for i, (value, bounds) in enumerate(zip(q, config["limits"]), 1):
        if not bounds[0] - 1e-10 <= value <= bounds[1] + 1e-10:
            raise ValueError(f"J{i} fuera de su recorrido")
    return q


def forward(q, config=None):
    config = config or load_config()
    q1, q2, q3, q4 = _numbers(q, 4, "Articulaciones")
    g = config["geometry"]
    yaw = q1 + q2 + q3
    return [
        g["l1"] * math.cos(q1) + g["l2"] * math.cos(q1 + q2),
        g["l1"] * math.sin(q1) + g["l2"] * math.sin(q1 + q2),
        g["shoulder_z"] + g["elbow_z_offset"] + g["tool_z_offset"] - q4,
        math.atan2(math.sin(yaw), math.cos(yaw)),
    ]


def inverse(x, y, z, yaw=None, current=None, config=None):
    config = config or load_config()
    x, y, z = _numbers([x, y, z], 3, "Objetivo XYZ")
    current = validate_joints(current if current is not None else config["initial_positions"], config)
    preserve_heading = yaw is None
    if preserve_heading:
        # Conservar la suma sin envolver evita un giro completo durante el recorrido.
        yaw = sum(current[:3])
    else:
        yaw = _numbers([yaw], 1, "Orientacion")[0]
        yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    g = config["geometry"]
    l1, l2 = g["l1"], g["l2"]
    cosine = (x * x + y * y - l1 * l1 - l2 * l2) / (2 * l1 * l2)
    if abs(cosine) > 1 + 1e-10:
        raise ValueError("El objetivo queda fuera del alcance horizontal")
    if math.hypot(x, y) < 1e-10:
        raise ValueError("El origen es una configuracion singular; elegir otro objetivo")
    q4 = g["shoulder_z"] + g["elbow_z_offset"] + g["tool_z_offset"] - z
    elbow = math.acos(max(-1.0, min(1.0, cosine)))
    candidates = []
    for q2 in (elbow, -elbow):
        shoulder = math.atan2(y, x) - math.atan2(l2 * math.sin(q2), l1 + l2 * math.cos(q2))
        for turn1, turn3 in itertools.product((-1, 0, 1), (0,) if preserve_heading else (-1, 0, 1)):
            q1 = shoulder + turn1 * math.tau
            q3 = yaw - q1 - q2 + turn3 * math.tau
            try:
                candidates.append(validate_joints([q1, q2, q3, q4], config))
            except ValueError:
                continue
    if not candidates:
        if preserve_heading:
            raise ValueError("La pose no permite conservar la orientacion dentro de los limites; indicar otra orientacion")
        raise ValueError("La pose no cumple los limites articulares o la carrera vertical")
    return min(candidates, key=lambda q: sum(
        ((v - previous) / (bounds[1] - bounds[0])) ** 2
        for v, previous, bounds in zip(q, current, config["limits"])
    ))


def trajectory_duration(start, target, speed=0.5, config=None):
    config = config or load_config()
    start, target = validate_joints(start, config), validate_joints(target, config)
    speed = _numbers([speed], 1, "Velocidad relativa")[0]
    if not 0.1 <= speed <= 1:
        raise ValueError("La velocidad relativa debe estar entre 0.1 y 1")
    # Derivadas maximas del perfil quintico s(u)=10u^3-15u^4+6u^5.
    durations = [0.032]
    for delta, velocity, acceleration in zip(
        (abs(a - b) for a, b in zip(target, start)), config["max_velocity"], config["max_acceleration"]
    ):
        durations.extend((1.875 * delta / (velocity * speed),
                          math.sqrt((10 / math.sqrt(3)) * delta / (acceleration * speed))))
    return max(durations)


def interpolate(start, target, elapsed, duration):
    if elapsed <= 0:
        return list(start)
    if elapsed >= duration:
        return list(target)
    u = max(0.0, min(1.0, elapsed / duration))
    s = u ** 3 * (10 - 15 * u + 6 * u * u)
    return [a + (b - a) * s for a, b in zip(start, target)]
