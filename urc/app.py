"""URC: python -m urc.app. Escucha a la UCI por scara/1 y sirve la página local.

Solo usa la biblioteca estándar. Convive con el banco viejo (client.app,
scara-dev/1): usan otro puerto HTTP y no se ejecutan a la vez sobre el 9000.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urc.session import Session


MAX_BODY = 1024
# Órdenes sin parámetros de la página.
ORDERS = {
    "/api/jog/stop": Session.jog_stop,
    "/api/zero": Session.zero,
    "/api/enable": Session.enable,
    "/api/disable": Session.disable,
    "/api/stop": Session.stop,
    "/api/halt": Session.halt,
}


def handler_for(session):
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
            elif self.path == "/api/estado":
                self.reply(200, session.snapshot())
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
                    session.jog(request.get("joint"), request.get("direction"))
                elif self.path in ORDERS:
                    ORDERS[self.path](session)
                else:
                    self.reply(404, {"error": "Ruta desconocida"})
                    return
                self.reply(202, {"message": "Orden enviada a la UCI"})
            except ConnectionError as exc:
                self.reply(409, {"error": str(exc)})
            except (ValueError, RecursionError) as exc:
                self.reply(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8766, help="Puerto HTTP de la página")
    parser.add_argument("--uci-port", type=int, default=9000, help="Puerto TCP de scara/1 (D24)")
    args = parser.parse_args()
    session = Session(port=args.uci_port)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(session))
    print(f"URC scara/1: http://127.0.0.1:{args.port}", flush=True)
    print(f"Esperando a la UCI en TCP 127.0.0.1:{session.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        session.close()


if __name__ == "__main__":
    main()
