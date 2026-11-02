"""URC: python -m urc.app. Escucha a la UCI por scara/1 y sirve la página local.

Solo usa la biblioteca estándar.
"""

import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urc import planner, trajectories
from urc.instrumentation import Instrumentation
from urc.playback import APPROACH_SPEED, Player
from urc.session import Session
from urc.trajectories import Conflict, TrajectoryManager
from urc.validation import Rejection


MAX_BODY = 1024
# Órdenes sin parámetros de la página.
ORDERS = {
    "/api/jog/stop": Session.jog_stop,
    "/api/zero": Session.zero,
    "/api/enable": Session.enable,
    "/api/disable": Session.disable,
    "/api/halt": Session.halt,
    "/api/home": Session.home,
    "/api/park": Session.park,
}


def _number(value, name):
    # Acotado: un número enorme desbordaría al pasarlo a centésimas.
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or abs(value) > 1e6):
        raise ValueError(f"{name} tiene que ser un número de hasta un millón")
    return value


def ptp_order(request):
    """Destino y velocidad de un PTP pedido por la página.

    joints: J1–J3 en grados y J4 en mm. pose: X, Y, Z en mm, rumbo en grados y
    codo (−1, J2 negativo, el preferido; o 1). speed: porcentaje de 1 a 100.
    """
    speed = _number(request.get("speed", 25), "La velocidad")
    if not 1 <= speed <= 100:
        raise ValueError("La velocidad va de 1 % a 100 %")
    if "joints" in request:
        joints = request["joints"]
        if not isinstance(joints, list) or len(joints) != 4:
            raise ValueError("Se esperan J1–J4")
        target = tuple(round(_number(value, name) * 100) for value, name in zip(joints, planner.NAMES))
    elif isinstance(request.get("pose"), dict):
        pose = request["pose"]
        values = [_number(pose.get(key), key) for key in ("x", "y", "z", "heading")]
        target = planner.joints_from_pose(*values, elbow=pose.get("elbow", -1))
    else:
        raise ValueError("Se espera joints (J1–J4) o pose (X, Y, Z y rumbo)")
    return target, speed / 100


# Reproducción de la trayectoria abierta (D29).
PLAYBACK = {
    "/api/reproduccion/reproducir": Player.play,
    "/api/reproduccion/pausa": Player.pause,
    "/api/reproduccion/reanudar": Player.resume,
    "/api/reproduccion/stop": Player.stop,
}


def handler_for(session, bench=None, manager=None, player=None):
    """bench: el canal de instrumentación, que solo existe en la simulación (ADR 0004)."""
    manager = manager or TrajectoryManager(session)
    player = player or Player(session, manager)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, data, content_type="application/json; charset=utf-8"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.reply(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/trajectories.js":
                self.reply(200, Path(__file__).with_name("trajectories.js").read_bytes(),
                           "text/javascript; charset=utf-8")
            elif self.path == "/api/estado":
                self.reply(200, session.snapshot())
            elif self.path == "/api/banco":
                self.reply(200, bench.snapshot() if bench else {"connected": False})
            elif self.path == "/banco.js":
                self.reply(200, Path(__file__).with_name("banco.js").read_bytes(), "text/javascript; charset=utf-8")
            elif self.path == "/api/trayectoria":
                self.reply(200, manager.state())
            elif self.path == "/api/trayectorias":
                self.reply(200, manager.files())
            elif self.path == "/api/reproduccion":
                self.reply(200, player.snapshot())
            else:
                self.reply(404, {"error": "Ruta desconocida"})

        def do_POST(self):
            # La URC escucha solo en loopback. No aceptar órdenes desde otra página.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.reply(403, {"error": "Origen externo rechazado"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Se requiere application/json"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    raise ValueError("El cuerpo debe ocupar entre 1 byte y 1 KiB")
                request = json.loads(self.rfile.read(size))
                if not isinstance(request, dict):
                    raise ValueError("Se requiere un objeto JSON")
                if self.path == "/api/jog":
                    session.jog(request.get("joint"), request.get("direction"), request.get("motor", False),
                                request.get("mode", "articular"), request.get("slow", False))
                elif self.path == "/api/ptp":
                    # Sin confirm, solo planifica: la página muestra la duración y pregunta.
                    target, speed = ptp_order(request)
                    confirm = request.get("confirm", False) is True
                    plan = session.move_ptp(target, speed, dry_run=not confirm)
                    self.reply(202 if confirm else 200, plan)
                    return
                elif self.path == "/api/banco":
                    if bench is None:
                        raise ConnectionError("No hay canal de instrumentación: solo existe en la simulación")
                    bench.order(request)
                    self.reply(202, {"message": "Orden enviada al banco de ensayo"})
                    return
                elif self.path == "/api/stop":
                    # Esc: frena todo, también la reproducción en curso o en pausa.
                    player.stop()
                elif self.path in PLAYBACK:
                    self.reply(202, PLAYBACK[self.path](player, request))
                    return
                elif self.path in ORDERS:
                    ORDERS[self.path](session)
                elif (result := trajectories.route(manager, self.path, request)) is not None:
                    self.reply(*result)
                    return
                else:
                    self.reply(404, {"error": "Ruta desconocida"})
                    return
                self.reply(202, {"message": "Orden enviada a la UCI"})
            except (ConnectionError, Conflict) as exc:
                self.reply(409, {"error": str(exc)})
            except OSError as exc:
                self.reply(500, {"error": f"Error de archivo: {exc}"})
            except Rejection as exc:
                # Un tramo imposible: el mensaje corto y el porqué aparte (D77).
                self.reply(400, {"error": str(exc), "detail": exc.detail})
            except (ValueError, RecursionError) as exc:
                self.reply(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8766, help="Puerto HTTP de la página")
    parser.add_argument("--uci-port", type=int, default=9000, help="Puerto TCP de scara/1 (D24)")
    parser.add_argument("--trayectorias", type=Path, default=trajectories.DEFAULT_FOLDER,
                        help="Carpeta de los archivos de trayectoria")
    parser.add_argument("--sim-port", type=int, default=9001, help="Puerto TCP del canal de instrumentación (D24)")
    parser.add_argument("--aproximacion", type=int, default=round(APPROACH_SPEED * 100), choices=range(1, 101),
                        metavar="1-100", help="Velocidad del tramo de aproximación, %% de la máxima (D33)")
    args = parser.parse_args()
    session = Session(port=args.uci_port)
    bench = Instrumentation(port=args.sim_port)
    manager = TrajectoryManager(session, args.trayectorias)
    player = Player(session, manager, args.aproximacion / 100)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(session, bench, manager, player))
    print(f"URC scara/1: http://127.0.0.1:{args.port}", flush=True)
    print(f"Esperando a la UCI en TCP 127.0.0.1:{session.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        player.close()
        session.close()
        bench.close()


if __name__ == "__main__":
    main()
