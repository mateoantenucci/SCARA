"""Estado del banco de demostración. No llama APIs de Webots ni conoce TCP."""

import math

from .kinematics import interpolate, load_config, trajectory_duration, validate_joints
from .collisions import CollisionChecker


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: usar un numero")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name}: fuera de rango") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name}: usar un numero finito")
    return number


class Runtime:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.commanded = list(self.config["initial_positions"])
        self.estimated = list(self.commanded)
        self.mode = "STOPPED"
        self.motion = None
        self.faults = {}
        self.payload_mass = 0.0
        self.reference_valid = True
        self.drive_factors = [1.0] * 4
        self.collisions = CollisionChecker(self.config)

    def advance(self, now):
        if self.motion is None:
            return []
        start, target, began, duration, request_id = self.motion
        self.commanded = interpolate(start, target, now - began, duration)
        # Baseline: referencia ideal. NO es un encoder ni un modelo de microstepping.
        self.estimated = list(self.commanded)
        if now - began >= duration:
            self.motion = None
            self.mode = "IDLE"
            return [{"event": "completed", "id": request_id,
                     "message": "Finalizaron las consignas; comprobar llegada en instrumentacion"}]
        return []

    def stop(self):
        self.motion = None
        self.commanded = list(self.estimated)
        self.mode = "FAULT" if self.faults else "STOPPED"

    def effort_factors(self):
        return list(self.drive_factors)

    def hall_output(self, nominal):
        delivered = list(nominal)
        for fault in self.faults.values():
            if fault["kind"] == "hall_stuck":
                delivered[fault["axis"]-1] = bool(fault["factor"])
        return delivered

    def handle(self, request, now):
        request_id = request.get("id") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict):
                raise ValueError("Se necesita un objeto JSON")
            if request_id is not None and (not isinstance(request_id, str) or len(request_id) > 80):
                raise ValueError("id debe ser texto de hasta 80 caracteres")
            command = request.get("command")
            if command == "move_joints":
                if self.mode not in ("IDLE",):
                    raise ValueError("Para mover: resolver fallas y habilitar; esperar si ya hay movimiento")
                target = validate_joints(request.get("positions"), self.config)
                duration = trajectory_duration(self.estimated, target, request.get("speed", 0.5), self.config)
                self.collisions.validate_path(self.estimated, target, self.payload_mass)
                self.motion = (list(self.estimated), target, now, duration, request_id)
                self.mode = "MOVING"
            elif command == "stop":
                self.stop()
            elif command == "rearm":
                if self.faults:
                    raise ValueError("Primero quitar las fallas inyectadas")
                if not self.reference_valid:
                    raise ValueError("Referencia no confirmada tras perder esfuerzo: reiniciar ensayo. No hay encoders reales")
                if self.mode == "MOVING":
                    raise ValueError("Detener antes de habilitar nuevamente")
                self.mode = "IDLE"
                self.drive_factors = [1.0] * 4
            elif command == "fault":
                kind, axis = request.get("kind"), request.get("axis")
                if kind not in ("effort_loss", "hall_stuck") or type(axis) is not int or not 1 <= axis <= 4:
                    raise ValueError("Falla o eje no admitido")
                factor = finite_number(request.get("factor", 0), "Factor")
                if not 0 <= factor <= 1 or (kind == "hall_stuck" and factor not in (0, 1)):
                    raise ValueError("Factor invalido para la falla")
                self.faults[f"{kind}:J{axis}"] = {"kind": kind, "axis": axis, "factor": factor}
                if kind == "effort_loss" and factor < 1:
                    self.drive_factors[axis-1] = min(factor, self.drive_factors[axis-1])
                    self.reference_valid = False
                self.stop()
            elif command == "clear_faults":
                if self.mode == "MOVING":
                    raise ValueError("Detener antes de quitar fallas")
                self.faults.clear()
                self.mode = "STOPPED"
            elif command == "payload":
                mass = finite_number(request.get("mass"), "Carga")
                if not 0 <= mass <= 2:
                    raise ValueError("Carga de ensayo entre 0 y 2 kg")
                if self.mode == "MOVING":
                    raise ValueError("Cambiar la carga con el movimiento detenido")
                if not self.reference_valid and mass != self.payload_mass:
                    raise ValueError("Referencia no confirmada: reiniciar ensayo antes de cambiar la carga")
                if self.reference_valid and mass != self.payload_mass:
                    self.collisions.validate_path(self.estimated,self.estimated,mass)
                self.payload_mass = mass
                weight = (self.config["body_properties"][-1]["mass"] + mass) * 9.81
                if weight > self.config["max_effort"][3]:
                    # Aviso por carga conocida del banco; no diagnóstico con un encoder oculto.
                    self.faults["overload:J4"] = {
                        "kind": "overload", "axis": 4, "weight_N": weight,
                        "message": "La carga conocida excede la capacidad estatica provisional de J4",
                    }
                    self.reference_valid = False
                    self.stop()
            elif command != "status":
                raise ValueError("Comando desconocido del banco provisional scara-dev/1")
            return {"event": "accepted", "id": request_id, "mode": self.mode}
        except (ValueError, TypeError, OverflowError) as exc:
            safe_id = request_id if isinstance(request_id, str) and len(request_id) <= 80 else None
            return {"event": "rejected", "id": safe_id, "message": str(exc)}
