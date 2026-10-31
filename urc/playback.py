"""Reproducción de trayectorias desde el gestor (D29, D32, D33, D68–D70).

Antes de mover nada, la URC planifica y valida todos los tramos que se van a
ejecutar (D55): el de aproximación, desde donde está el robot hasta el punto
de partida, cada tramo de la trayectoria y, con loop, la vuelta del último
punto al primero. Cada tramo se encola entero, con su espera como segmentos
sin movimiento, y el siguiente entra antes de que se acabe el anterior: el
robot los encadena con su reloj y los tiempos son los de la planificación.

La pausa es el STOP con rampa del firmware (D52). Al reanudar, la URC
recalcula lo que faltaba del tramo desde la pose en la que quedó, con el
mismo tipo: un LIN sigue sobre la misma recta y un PTP sobre la misma recta
en articulaciones.
"""

from collections import deque
from dataclasses import dataclass, replace
import threading
import time

from urc import validation
from urc.planner import SEGMENT_MS
from urc.trajectories import robot_pose


APPROACH_SPEED = 0.25        # tramo de aproximación, × la velocidad global (D33)
SPEEDS = range(10, 101)      # velocidad global, % entero (D22)
# Menos de un paso por articulación (D33, D68): con 1/8, un paso es 5,6
# centésimas de grado en J1–J3 y 0,5 de mm en J4, redondeado hacia arriba.
AT_POINT = (6, 6, 6, 1)
WAIT_MS = 1000               # una espera son segmentos sin movimiento de hasta 1 s (D50)
AHEAD = 50                   # con menos segmentos por enviar (1 s), se encola el tramo siguiente
TICK = 0.02                  # s
ACTIVE = ("reproduciendo", "pausando", "pausada")


@dataclass
class Tramo:
    """Cómo se llega a un punto: lo que la reproducción encola de una vez."""
    point: int               # índice del punto al que llega
    label: str               # "0" (aproximación), "2", "3"… o "vuelta"
    kind: str
    speed: float             # fracción, ya multiplicada por la velocidad global
    target: tuple
    motion: list             # segmentos del movimiento; None: se recalcula al reanudar
    wait_ms: int
    cycle: int = 1
    first: int = None        # números de SEG, una vez encolado
    last: int = None

    def segments(self):
        waits, left = [], self.wait_ms
        while left > 0:
            waits.append((min(left, WAIT_MS), self.target))
            left -= WAIT_MS
        return self.motion + waits

    def rejection_label(self):
        return {"0": 0, "vuelta": "de vuelta"}.get(self.label, self.label)


class Player:
    def __init__(self, session, manager, approach_speed=APPROACH_SPEED):
        self.session, self.manager = session, manager
        self.approach_speed = approach_speed
        self.lock = threading.Lock()
        self.state, self.message = "inactiva", "Sin reproducción"
        self.cancelled = False       # Stop mientras se validaba
        self.options = {"speed": None, "loops": None, "start": None}
        self.summary = {"approach": None, "tramos": [], "duration_s": None}
        self._clear()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-reproduccion", daemon=True)
        self.thread.start()

    def _clear(self):
        self.points = None           # la trayectoria que se reproduce, copiada al dar play
        self.cycle_plan = []         # una vuelta completa del loop: la vuelta y los tramos 2…n
        self.cycles_left = 0         # vueltas que faltan encolar; None: sin fin
        self.cycle = 0
        self.pending = deque()       # tramos por encolar
        self.queued = deque()        # tramos encolados y todavía no terminados
        self.movement = None         # primer número del movimiento en la sesión
        self.pose = None             # de dónde arranca el próximo movimiento
        self.paused_at = None

    # --- Órdenes desde la interfaz ---------------------------------------

    def play(self, request):
        """Valida todo y arranca desde el punto `start` (0: el primero), a `speed` % y `loops` vueltas."""
        start, speed, loops = _options(request)
        with self.lock:
            if self.state in ACTIVE or self.state == "validando":
                raise ValueError("Ya hay una reproducción en curso: frenala con Stop")
            previous, self.state = (self.state, self.message), "validando"
            self.cancelled = False
        try:
            prepared = self._prepare(start, speed, loops)
        except BaseException:
            with self.lock:
                self.state, self.message = previous
            raise
        with self.lock:
            if self.cancelled:
                # Stop o Esc mientras se validaba: no arranca.
                self.state, self.message = "detenida", "Reproducción cancelada con Stop antes de arrancar"
                raise ValueError(self.message)
            self._clear()
            self.points, self.pose, self.cycle_plan, approach, first = prepared
            self.pending.extend(([approach] if approach else []) + first)
            self.cycles_left = None if loops is None else loops - 1
            self.cycle = 1
            self.options = {"speed": speed, "loops": loops, "start": start}
            self.summary = _summary(self.points, approach, start, first, self.cycle_plan, loops)
            self.state, self.message = "reproduciendo", "Reproducción en curso"
            try:
                self._feed(0)
            except BaseException:
                self._clear()
                self.state, self.message = previous
                raise
        return self.snapshot()

    def pause(self, request):
        """Frena con la rampa del firmware; el tramo se completa al reanudar."""
        with self.lock:
            if self.state != "reproduciendo":
                raise ValueError("No hay una reproducción en curso para pausar")
            self.state, self.message = "pausando", "Frenando para la pausa…"
            self.paused_at = time.monotonic()
        self.session.stop()
        return self.snapshot()

    def resume(self, request):
        """Recalcula lo que faltaba del tramo desde la pose de la pausa y sigue."""
        with self.lock:
            if self.state != "pausada":
                raise ValueError("No hay una reproducción en pausa para reanudar")
            state = self.session.snapshot()
            pose = robot_pose(state, "reanudar")
            _require_sure(state, "reanudar")
            if pose != self.pose:
                raise ValueError("El robot se movió durante la pausa: frená con Stop y reproducí de nuevo")
            with self.manager.lock:
                if [dict(p) for p in self.manager.points] != self.points:
                    raise ValueError("La trayectoria cambió durante la pausa: frená con Stop y reproducí de nuevo")
            if self.pending and self.pending[0].motion is None:
                tramo = self.pending[0]
                plan = self._check(tramo.kind, pose, tramo.target, tramo.speed, tramo.rejection_label())
                self.pending[0] = replace(tramo, motion=plan.segments)
            self.state, self.message = "reproduciendo", "Reproducción en curso"
            try:
                self._feed(0)
            except BaseException:
                self.state = "pausada"
                raise
            if self.movement is None:
                # Frenó justo en el destino del último tramo: no quedaba nada.
                self._end("terminada", "Reproducción terminada")
        return self.snapshot()

    def stop(self, request=None):
        """Frena y descarta lo pendiente. Esc y el Stop general también pasan por acá."""
        with self.lock:
            if self.state in ACTIVE:
                self._end("detenida", "Reproducción detenida por el operador")
            elif self.state == "validando":
                self.cancelled = True
        self.session.stop()
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            current = None
            if self.state == "pausada" and self.pending:
                current = _describe(self.pending[0], waiting=self.pending[0].motion == [])
            elif self.state in ("reproduciendo", "pausando") and self.queued:
                status = self.session.snapshot()["status"]
                current = self._current(-1 if status is None else status["last"])
            return {"state": self.state, "message": self.message, **self.options, **self.summary,
                    "cycle": self.cycle, "current": current}

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)

    # --- Planificación ------------------------------------------------------

    def _prepare(self, start, speed, loops):
        """Valida todos los tramos que se van a ejecutar; sin lock, puede tardar segundos (D55)."""
        state = self.session.snapshot()
        pose = robot_pose(state, "reproducir")
        _require_sure(state, "reproducir")
        with self.manager.lock:
            points = [dict(p) for p in self.manager.points]
        if not points:
            raise ValueError("La trayectoria no tiene puntos: capturá o agregá alguno antes de reproducir")
        if not start < len(points):
            raise ValueError(f"start tiene que ser un punto de la trayectoria (hay {len(points)})")
        scale = speed / 100
        target = points[start]["joints"]
        approach = None
        if any(abs(a - b) > step for a, b, step in zip(pose, target, AT_POINT)):
            plan = self._check("PTP", pose, target, self.approach_speed * scale, 0)
            approach = Tramo(start, "0", "PTP", self.approach_speed * scale, target, plan.segments, 0)
        arrivals = range(1, len(points)) if loops != 1 else range(start + 1, len(points))
        tramos = {index: self._tramo(points, index, index - 1, str(index + 1), scale) for index in arrivals}
        if loops != 1:
            # La vuelta del loop usa los parámetros del punto 1 (D32).
            tramos[0] = self._tramo(points, 0, len(points) - 1, "vuelta", scale)
        # Copias: _feed anota en cada tramo sus números de SEG.
        first = [replace(tramos[index]) for index in range(start + 1, len(points))]
        cycle = [tramos[index] for index in sorted(tramos)] if loops != 1 else []
        if loops != 1 and not any(t.segments() for t in cycle):
            raise ValueError("La trayectoria no se mueve ni espera: no hay nada que repetir en el loop")
        if not any(t.segments() for t in ([approach] if approach else []) + first) and loops == 1:
            raise ValueError("Nada que reproducir: el robot ya está en el único punto")
        return points, pose, cycle, approach, first

    def _tramo(self, points, index, previous, label, scale):
        point = points[index]
        speed = point["speed"] / 100 * scale
        tramo = Tramo(index, label, point["kind"], speed, point["joints"], None, round(point["wait"] * 1000))
        plan = self._check(point["kind"], points[previous]["joints"], point["joints"], speed, tramo.rejection_label())
        return replace(tramo, motion=plan.segments)

    def _check(self, kind, start, target, speed, label):
        return validation.check_tramo(kind, tuple(start), tuple(target), speed, label, self.session.limits,
                                      self.session.config, self.session.checker)

    # --- Seguimiento (con self.lock tomado) ----------------------------------

    def _run(self):
        while not self.closed.wait(TICK):
            with self.lock:
                if self.state not in ("reproduciendo", "pausando"):
                    continue
                try:
                    self._follow()
                except (ValueError, ConnectionError) as exc:
                    self._end("detenida", f"Reproducción detenida: {exc}")

    def _follow(self):
        state = self.session.snapshot()
        tramo, status = state["tramo"], state["status"]
        if tramo is None or tramo["first"] != self.movement:
            self._end("detenida", "Reproducción detenida: otro movimiento la reemplazó")
            return
        if self.state == "pausando":
            # Quieto según un estado que llegó después de la orden de pausa.
            if (status is not None and status["mode"] == "IDLE"
                    and time.monotonic() - status["age_s"] >= self.paused_at):
                self._paused(status)
            elif not state["connected"] or status is None:
                self._end("detenida", "Reproducción detenida: se perdió la UCI durante la pausa")
            return
        if tramo["cancelled"]:
            self._end("detenida", f"Reproducción detenida: {tramo['cancelled']}")
            return
        if state["doubtful"]:
            # F1 en plena reproducción (D65): la URC decide frenar.
            self._end("detenida", "Reproducción detenida: " + _doubt(state["doubtful"]))
            self.session.stop()
            return
        self._feed(state["segments"]["pending"])
        if status is not None:
            while len(self.queued) > 1 and self.queued[0].last <= status["last"]:
                self.queued.popleft()
        if (not self.pending and self.cycles_left == 0 and status is not None and status["mode"] == "IDLE"
                and status["last"] >= self.queued[-1].last):
            loops = self.options["loops"]
            self._end("terminada", "Reproducción terminada" + (f": {loops} vueltas" if loops > 1 else ""))

    def _feed(self, waiting):
        """Encola tramos mientras haya menos de AHEAD segmentos por enviar."""
        while waiting < AHEAD:
            if not self.pending:
                if self.cycles_left == 0:
                    return
                if self.cycles_left is not None:
                    self.cycles_left -= 1
                self.cycle += 1
                self.pending.extend(replace(t, cycle=self.cycle) for t in self.cycle_plan)
            tramo = self.pending.popleft()
            segments = tramo.segments()
            if not segments:
                continue
            if self.movement is None:
                tramo.first, tramo.last = self.session.run_segments(segments, start=self.pose, kind="reproducción")
                self.movement = tramo.first
            else:
                tramo.first, tramo.last = self.session.run_segments(segments, follows=self.movement)
            self.queued.append(tramo)
            waiting += len(segments)

    def _paused(self, status):
        """El robot frenó: lo que faltaba vuelve adelante de lo pendiente.

        El tramo interrumpido se recalcula al reanudar desde la pose de la
        pausa; si ya había llegado, queda lo que faltaba de su espera.
        """
        executing = status["last"] + 1
        unfinished = [t for t in self.queued if t.last >= executing]
        if unfinished:
            current, rest = unfinished[0], unfinished[1:]
            done = max(0, executing - current.first)
            if done < len(current.motion):
                current = replace(current, motion=None)
            else:
                current = replace(current, motion=[], wait_ms=sum(ms for ms, _ in current.segments()[done:]))
            self.pending.extendleft(reversed([current] + [replace(t, first=None, last=None) for t in rest]))
        self.queued.clear()
        self.movement = None
        self.pose = tuple(status["position"])
        self.state, self.message = "pausada", "En pausa: Reanudar sigue desde acá, sobre el mismo tramo"

    def _current(self, last):
        executing = last + 1
        tramo = next((t for t in self.queued if t.last >= executing), self.queued[-1])
        return _describe(tramo, waiting=executing - tramo.first >= len(tramo.motion))

    def _end(self, state, message):
        self._clear()
        self.state, self.message = state, message


def _options(request):
    start, speed, loops = request.get("start", 0), request.get("speed", 100), request.get("loops", 1)
    if type(start) is not int or start < 0:
        raise ValueError("start tiene que ser el índice de un punto de la trayectoria")
    if type(speed) is not int or speed not in SPEEDS:
        raise ValueError("La velocidad global es un porcentaje entero de 10 a 100")
    if loops is not None and (type(loops) is not int or loops < 1):
        raise ValueError("loops es la cantidad de vueltas, 1 o más, o null para repetir sin fin")
    return start, speed, loops


def _require_sure(state, action):
    if state["doubtful"]:
        raise ValueError(f"No se puede {action}: {_doubt(state['doubtful'])}")


def _doubt(doubtful):
    joints = ", ".join(f"J{item['joint']}" for item in doubtful)
    return f"la referencia de {joints} es dudosa por pérdida de pasos; hacé homing"


def _describe(tramo, waiting):
    return {"point": tramo.point, "label": tramo.label, "kind": tramo.kind, "approach": tramo.label == "0",
            "waiting": waiting, "cycle": tramo.cycle}


def _seconds(segments):
    return sum(ms for ms, _ in segments) / 1000


def _summary(points, approach, start, first, cycle, loops):
    """Lo que la página muestra antes y durante la reproducción, con las duraciones planificadas."""
    def row(t):
        return {"point": t.point, "label": t.label, "kind": t.kind, "speed": points[t.point]["speed"],
                "duration_s": round(len(t.motion) * SEGMENT_MS / 1000, 2), "wait_s": t.wait_ms / 1000}
    tramos = first + [t for t in cycle if t.label == "vuelta"]
    rows = [row(t) for t in tramos]
    total = _seconds(approach.segments()) if approach else 0
    total += sum(_seconds(t.segments()) for t in first)
    duration = None if loops is None else round(total + (loops - 1) * sum(_seconds(t.segments()) for t in cycle), 2)
    return {"approach": {"skipped": approach is None, "duration_s": round(_seconds(approach.segments()), 2) if approach else 0,
                         "point": start},
            "tramos": rows, "duration_s": duration}
