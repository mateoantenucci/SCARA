"""TCP local no bloqueante del banco PROVISIONAL scara-dev/1, JSON por linea."""

import json
import math
import socket


MAX_FRAME = 16 * 1024


class Server:
    def __init__(self, host="127.0.0.1", port=9000):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.client = None
        self.received = bytearray()
        self.outgoing = bytearray()
        self.lost = False

    def disconnect(self):
        if self.client is not None:
            self.client.close()
            self.lost = True
        self.client = None
        self.received.clear()
        self.outgoing.clear()

    def send(self, event):
        if self.client is None:
            return
        data = json.dumps(event, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(data) > MAX_FRAME or len(self.outgoing) + len(data) > 256 * 1024:
            self.disconnect()
        else:
            self.outgoing.extend(data)

    def poll(self):
        messages = []
        if self.client is None:
            try:
                self.client, _ = self.listener.accept()
                self.client.setblocking(False)
            except BlockingIOError:
                return messages
        for _ in range(8):
            try:
                chunk = self.client.recv(4096)
            except BlockingIOError:
                break
            except OSError:
                self.disconnect()
                return messages
            if not chunk:
                self.disconnect()
                return []
            self.received.extend(chunk)
            if len(self.received) > MAX_FRAME and b"\n" not in self.received:
                self.disconnect()
                return []
        for _ in range(16):
            if b"\n" not in self.received:
                break
            frame, _, tail = self.received.partition(b"\n")
            self.received = bytearray(tail)
            if len(frame) > MAX_FRAME:
                self.disconnect()
                return []
            try:
                request = json.loads(frame.decode("utf-8"), parse_constant=self._invalid_constant,
                                     parse_float=self._finite_float)
                messages.append(request)
            except (ValueError, UnicodeError, RecursionError):
                self.send({"event": "rejected", "id": None, "message": "JSON invalido"})
        if len(self.received) > MAX_FRAME:
            self.disconnect()
            return []
        if self.client is not None and self.outgoing:
            try:
                count = self.client.send(self.outgoing)
                if count == 0:
                    self.disconnect()
                    return []
                del self.outgoing[:count]
            except BlockingIOError:
                pass
            except OSError:
                self.disconnect()
                return []
        return messages if self.client is not None else []

    @staticmethod
    def _invalid_constant(value):
        raise ValueError(value)

    @staticmethod
    def _finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Numero fuera de rango")
        return number

    def close(self):
        self.disconnect()
        self.listener.close()
