"""Registro de eventos de la URC (D78): qué pasó, numerado y con la hora.

Lo llevan la sesión con la UCI (lo que informa la UCI y lo que decide la URC),
el servidor HTTP (las órdenes del operador, aceptadas o rechazadas) y el
canal de instrumentación (los cambios del banco de ensayo). La página lo
muestra como historial y saca de él los avisos emergentes.

Cada evento tiene un número que no se repite, la hora de la PC, un nivel
(info, ok, aviso o error), quién lo produjo y el texto. Uno igual al último
dentro de REPEAT segundos no es un evento nuevo: suma una repetición, así el
jog que se renueva contra un límite no tapa el resto.
"""

from collections import deque
import threading
import time


LEVELS = ("info", "ok", "aviso", "error")
SIZE = 200                   # eventos que se conservan
REPEAT = 3.0                 # s entre dos iguales para contarlos como uno


class EventLog:
    def __init__(self, size=SIZE, clock=time.time):
        self.lock = threading.Lock()
        self.items = deque(maxlen=size)
        self.count = 0
        # Sube con cada evento nuevo y con cada repetición: la página pide lo
        # que cambió desde la última versión que vio.
        self.version = 0
        self.clock = clock

    def add(self, level, source, text, detail=None, rejected=False):
        """Anota un evento y devuelve su número.

        source es quién lo produjo: «UCI», «URC», «Banco» o la orden del
        operador («Homing»). rejected marca una orden que la URC rechazó.
        """
        if level not in LEVELS:
            raise ValueError(f"Nivel de evento desconocido: {level}")
        now = self.clock()
        with self.lock:
            self.version += 1
            last = self.items[-1] if self.items else None
            if last and (last["text"], last["detail"]) == (text, detail) and now - last["last"] <= REPEAT:
                last.update(repeats=last["repeats"] + 1, last=now, version=self.version)
                return last["n"]
            self.count += 1
            self.items.append({"n": self.count, "time": now, "last": now, "repeats": 1, "level": level,
                               "source": source, "text": text, "detail": detail, "rejected": rejected,
                               "version": self.version})
            return self.count

    def since(self, version=0):
        """Los eventos nuevos o repetidos después de version, del más viejo al más nuevo."""
        with self.lock:
            return {"version": self.version,
                    "events": [dict(item) for item in self.items if item["version"] > version]}
