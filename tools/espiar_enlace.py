"""Registra el diálogo real entre la UCI y la URC, línea por línea.

Se interpone entre los dos lados sin cambiar nada: escucha donde la UCI se
conecta (9000 para scara/1, 9001 para scara-sim/1) y reenvía cada byte a la
URC, levantada en otro puerto. Cada línea se anota con su hora relativa y su
sentido. Se usó para las transcripciones del informe (docs/informe/).

    python3 -m urc.app --uci-port 9010 --sim-port 9011
    python3 tools/espiar_enlace.py --registro /tmp/dialogo.log

Webots se abre como siempre: su controlador se conecta a 9000 y 9001.
"""

import argparse
import socket
import threading
import time


def relay(origen, destino, sentido, canal, registro, inicio, lock):
    """Copia los bytes de origen a destino y anota cada línea completa."""
    resto = b""
    try:
        while True:
            datos = origen.recv(4096)
            if not datos:
                break
            destino.sendall(datos)
            resto += datos
            *lineas, resto = resto.split(b"\n")
            with lock:
                for linea in lineas:
                    texto = linea.decode("ascii", "replace").rstrip("\r")
                    registro.write(f"{time.monotonic() - inicio:9.3f} {canal:<11} {sentido} {texto}\n")
                registro.flush()
    except OSError:
        pass
    finally:
        for extremo in (origen, destino):
            try:
                extremo.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def escuchar(puerto, puerto_urc, canal, registro, inicio, lock):
    servidor = socket.socket()
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("127.0.0.1", puerto))
    servidor.listen(1)
    while True:
        uci, _ = servidor.accept()
        urc = socket.create_connection(("127.0.0.1", puerto_urc))
        with lock:
            registro.write(f"{time.monotonic() - inicio:9.3f} {canal:<11} · conexión TCP\n")
        for args in ((uci, urc, "UCI → URC"), (urc, uci, "URC → UCI")):
            threading.Thread(target=relay, args=(*args, canal, registro, inicio, lock), daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registro", required=True)
    parser.add_argument("--uci", type=int, default=9000, help="Puerto al que se conecta la UCI (scara/1)")
    parser.add_argument("--urc", type=int, default=9010, help="Puerto donde escucha la URC (scara/1)")
    parser.add_argument("--sim", type=int, default=9001, help="Puerto al que se conecta la UCI (scara-sim/1)")
    parser.add_argument("--urc-sim", type=int, default=9011, help="Puerto donde escucha la URC (scara-sim/1)")
    args = parser.parse_args()
    inicio, lock = time.monotonic(), threading.Lock()
    with open(args.registro, "w", encoding="utf-8") as registro:
        for puerto, destino, canal in ((args.uci, args.urc, "scara/1"), (args.sim, args.urc_sim, "scara-sim/1")):
            threading.Thread(target=escuchar, args=(puerto, destino, canal, registro, inicio, lock),
                             daemon=True).start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
