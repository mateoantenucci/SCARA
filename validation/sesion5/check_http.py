"""Smoke HTTP de la copia real: arranca client.app en un proceso separado."""

import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    root = Path(sys.argv[1]).resolve()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    # Puerto no atendido para probar el inicio sin controlador Webots.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        webots_port = listener.getsockname()[1]
    command = [sys.executable, '-S', '-B', '-m', 'client.app', '--port', str(port),
               '--webots-port', str(webots_port)]
    child = subprocess.Popen(command, cwd=str(root), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONPATH=''))
    base = 'http://127.0.0.1:{}'.format(port)
    checks = []

    def get(path):
        with urlopen(base + path, timeout=2) as response:
            return response.status, response.read(), response.headers

    def post(path, data):
        request = Request(base + path, data=json.dumps(data).encode('utf-8'),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as response:
            return response.code, json.loads(response.read())

    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                status, html, headers = get('/')
                break
            except (OSError, URLError):
                assert child.poll() is None, 'client.app terminó antes de atender HTTP'
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        assert status == 200 and html == (root / 'client/index.html').read_bytes()
        assert headers['Content-Type'] == 'text/html; charset=utf-8'
        checks.append('GET / sirve exactamente index.html UTF-8 de la copia')
        status, raw, _ = get('/api/state')
        state = json.loads(raw)
        assert status == 200 and state['protocol'] == 'scara-dev/1'
        assert state['connected'] is False and len(state['initial_pose']) == 4
        checks.append('GET /api/state inicia sin conexión y devuelve configuración de la copia')
        status, result = post('/api/command', {'command': 'rearm'})
        assert status == 409 and 'no se guardó' in result['error']
        checks.append('POST de movimiento sin Webots se rechaza y no se guarda')
        for enabled in (False, True):
            status, _ = post('/api/connection', {'connect': enabled})
            assert status == 200
            _, raw, _ = get('/api/state')
            assert json.loads(raw)['connection_enabled'] is enabled
        checks.append('Desconectar/reconectar HTTP funciona sin habilitar movimiento')
        try:
            get('/no-existe')
            raise AssertionError('Ruta inexistente servida')
        except HTTPError as response:
            assert response.code == 404
        checks.append('Ruta desconocida devuelve 404')
    finally:
        child.send_signal(signal.SIGINT)
        try:
            output = child.communicate(timeout=5)[0].decode('utf-8')
        except subprocess.TimeoutExpired:
            child.kill()
            output = child.communicate()[0].decode('utf-8')
    assert child.returncode == 0, output
    print(json.dumps(dict(status='passed', platform=platform.platform(), python=sys.version,
                          executable=sys.executable, cwd=str(root), command=command,
                          no_site_packages=True, checks=checks, output=output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
