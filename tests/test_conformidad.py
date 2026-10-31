"""Conformidad de la URC: las mismas conversaciones que prueban el firmware
(firmware/test/conversaciones) se reproducen contra la URC real, con una UCI
falsa conectada por TCP (seam 2 de la spec #2).

Cada renglón se lee desde el lado de la URC:

- `> LÍNEA`: la URC tiene que poder enviarla, y la UCI falsa la recibe tal
  cual. Si el firmware la rechaza por su forma (ERR 1, 2 o 3), la URC tiene
  que negarse a enviarla, con el mismo código. Los SEG siguen el control de
  flujo: la URC envía uno y espera su OK. Un SEG que el firmware rechaza con
  ERR 9 (cola) es uno que la URC no envía, porque todavía espera el OK del
  anterior: no envía de más.
- `< LÍNEA`: la UCI falsa la envía (`*` vale 0) y la URC tiene que entenderla:
  un `S` actualiza el estado, un `BOOT` deja el robot sin referencia, un `OK`
  confirma el segmento, un `EV LOST` deja la referencia dudosa y un `ERR`
  queda registrado con su código.
- `+`, `=` y `!` son del reloj, los motores y el reinicio de la UCI: la URC
  no los ve.
"""

from pathlib import Path
import unittest

from tests.test_urc import FakeUci, wait_for
from urc.protocol import ProtocolError, parse_message
from urc.session import Session


ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = sorted((ROOT / "firmware" / "test" / "conversaciones").glob("*.txt"))
GRAMMAR_ERRORS = (1, 2, 3)
QUEUE_ERROR = 9


def read_conversation(path):
    """Renglones (número, tipo, cuerpo), sin comentarios ni vacíos."""
    items = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line and line[0] != "#":
            items.append((number, line[0], line[2:]))
    return items


def firmware_answer(items, index):
    """Primera respuesta de la UCI después de la orden items[index], o None."""
    for _, kind, body in items[index + 1:]:
        if kind == ">":
            return None
        if kind == "<":
            return body
    return None


class ConformanceTests(unittest.TestCase):
    def test_conversations_against_the_urc(self):
        self.assertTrue(CONVERSATIONS, "No hay conversaciones de ejemplo")
        for path in CONVERSATIONS:
            with self.subTest(conversacion=path.name):
                self.play(path)

    def play(self, path):
        # jog_hold largo: aquí nadie renueva un jog desde una página.
        session = Session(port=0, jog_hold=60)
        self.addCleanup(session.close)
        uci = FakeUci(session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        wait_for(lambda: session.snapshot()["connected"])
        items, sent = read_conversation(path), 0
        for index, (number, kind, body) in enumerate(items):
            where = f"{path.name}:{number}"
            if kind == ">":
                self.order(session, uci, body.replace("\\r", "\r"), firmware_answer(items, index), where)
            elif kind == "<":
                line = " ".join("0" if field == "*" else field for field in body.split())
                uci.send(line)
                sent += 1
                wait_for(lambda: session.snapshot()["received"] == sent)
                self.check_understood(session.snapshot(), parse_message(line), where)
        self.assertEqual(session.snapshot()["rejected"], [], path.name)

    def order(self, session, uci, text, answer, where):
        if not text.strip():
            return  # una línea vacía no es un mensaje: no hay nada que enviar
        code = int(answer.split()[1]) if answer and answer.startswith("ERR ") else None
        if code in GRAMMAR_ERRORS:
            with self.assertRaises(ProtocolError, msg=where) as caught:
                session.order(text)
            self.assertEqual(caught.exception.code, code, where)
            return
        session.order(text)
        if code == QUEUE_ERROR:
            self.assertTrue(uci.silent(), where)
            return
        expected = text.replace("\r", "")
        received = uci.receive(ignore=() if expected == "PING" else ("PING",))
        self.assertEqual(received.split(), expected.split(), where)

    def check_understood(self, state, message, where):
        kind = message.pop("kind")
        if kind == "S":
            status = {key: value for key, value in state["status"].items() if key != "age_s"}
            self.assertEqual(status, message, where)
            self.assertEqual(state["referenced"], message["homed"] == 15, where)
        elif kind == "BOOT":
            self.assertFalse(state["referenced"], where)
            self.assertIsNone(state["status"], where)
        elif kind == "HI":
            self.assertEqual(state["firmware"], message, where)
        elif kind == "OK":
            self.assertEqual(state["segments"]["last_ok"], message["number"], where)
            self.assertIsNone(state["segments"]["in_flight"], where)
        elif kind == "EV" and message["event"] == "LOST":
            self.assertEqual(state["doubtful"][-1], {"joint": message["joint"], "steps": message["steps"]}, where)
        elif kind == "ERR":
            self.assertTrue(state["errors"][-1].startswith(f"ERR {message['code']} {message['word']}:"), where)
            # Ante un ERR, lo que faltaba del tramo ya no se envía.
            self.assertEqual(state["segments"]["pending"], 0, where)
            self.assertIsNone(state["segments"]["in_flight"], where)


if __name__ == "__main__":
    unittest.main()
