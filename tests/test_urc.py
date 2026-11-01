"""URC por su borde hacia el robot: una UCI falsa se conecta por TCP y habla scara/1."""

import http.client
import json
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from urc.app import handler_for
from urc.protocol import ProtocolError
from urc.session import STOP_GUARD, Session


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("No se cumplió la condición esperada")


class FakeUci:
    """Extremo UCI: se conecta a la URC como lo hace Webots o socat."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.buffer = b""

    def send(self, line):
        self.sock.sendall(line.encode() + b"\n")

    def receive(self, ignore=("PING",)):
        while True:
            while b"\n" not in self.buffer:
                chunk = self.sock.recv(1024)
                if not chunk:
                    raise ConnectionError("La URC cerró la conexión")
                self.buffer += chunk
            line, self.buffer = self.buffer.split(b"\n", 1)
            text = line.decode()
            if text not in ignore:
                return text

    def silent(self, seconds=0.2, ignore=("PING",)):
        """Nada más que lo ignorado durante `seconds`."""
        deadline = time.monotonic() + seconds
        try:
            while (left := deadline - time.monotonic()) > 0:
                self.sock.settimeout(left)
                text = self.receive(ignore)
                raise AssertionError(f"La URC envió {text!r}")
        except socket.timeout:
            return True
        finally:
            self.sock.settimeout(3)

    def close(self):
        self.sock.close()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0, jog_hold=0.3)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)

    def test_greets_and_reads_boot_hi_and_status(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("BOOT scara/1 1")
        self.uci.send("HI scara/1 1")
        self.uci.send("S IDLE 15 450 -900 0 12000 0 16 0")
        state = wait_for(lambda: (s := self.session.snapshot())["status"] and s)
        self.assertTrue(state["connected"])
        self.assertEqual(state["firmware"], {"protocol": "scara/1", "version": 1})
        self.assertEqual(state["boots"], 1)
        self.assertEqual(state["status"]["mode"], "IDLE")
        self.assertEqual(state["status"]["homed"], 15)
        self.assertEqual(state["status"]["position"], [450, -900, 0, 12000])
        self.assertIn({"direction": "<", "line": "BOOT scara/1 1"}, state["traffic"])

    def test_pings_keep_the_watchdog_alive(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.assertEqual(self.uci.receive(ignore=()), "PING")
        self.assertEqual(self.uci.receive(ignore=()), "PING")

    def test_jog_is_sent_once_and_stops_when_not_refreshed(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        wait_for(lambda: self.session.snapshot()["connected"])
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")
        self.session.jog(1, "+")
        # Sin renovar, el jog vence y la URC lo frena.
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.session.jog(1, "-")
        self.assertEqual(self.uci.receive(), "JOG 1 - 500")
        self.session.jog_stop()
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.session.zero()
        self.assertEqual(self.uci.receive(), "ZERO")

    def test_motor_jog_is_a_different_jog(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        wait_for(lambda: self.session.snapshot()["connected"])
        self.session.jog(4, "-")
        self.assertEqual(self.uci.receive(), "JOG 4 - 500")
        # El mismo eje y sentido, pero por motor: es otra orden.
        self.session.jog(1, "+", motor=True)
        self.assertEqual(self.uci.receive(), "JOG M1 + 500")
        self.assertEqual(self.session.snapshot()["jog"],
                         {"mode": "articular", "joint": 1, "direction": "+", "motor": True, "slow": False})
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")

    def test_rejects_invalid_jog_and_orders_without_robot(self):
        with self.assertRaises(ValueError):
            self.session.jog(5, "+")
        with self.assertRaises(ValueError):
            self.session.jog(1, "x")
        with self.assertRaises(ValueError):
            self.session.jog(1, "+", motor="sí")
        self.uci.close()
        wait_for(lambda: not self.session.snapshot()["connected"])
        with self.assertRaises(ConnectionError):
            self.session.jog(1, "+")

    def test_bad_lines_are_reported_without_dropping_the_link(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.sock.sendall(b"\xff\xfe ruido de arranque\n" + b"x" * 200 + b"\n")
        self.uci.send("HI scara/2 1")
        self.uci.send("S IDLE 1_5 0 0 0 0 0 16 0")
        self.uci.send("HI scara/1 1")
        state = wait_for(lambda: (s := self.session.snapshot())["firmware"] and s)
        self.assertTrue(state["connected"])
        self.assertIsNone(state["status"])
        self.assertEqual(len(state["rejected"]), 4, state["rejected"])
        self.assertEqual(state["errors"], [])
        self.assertEqual(state["received"], 5)

    def test_orders_reach_the_uci(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        wait_for(lambda: self.session.snapshot()["connected"])
        self.session.enable()
        self.assertEqual(self.uci.receive(), "ENABLE")
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")
        # Frenar olvida el jog. Un pedido que estaba en camino no lo reanuda;
        # el próximo pedido de la página, sí.
        self.session.stop()
        self.assertEqual(self.uci.receive(), "STOP")
        self.session.jog(1, "+")
        self.assertTrue(self.uci.silent(0.1))
        time.sleep(STOP_GUARD)
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")
        self.session.halt()
        self.assertEqual(self.uci.receive(), "HALT")
        self.session.disable()
        self.assertEqual(self.uci.receive(), "DISABLE")
        self.session.order("STATUS")
        self.assertEqual(self.uci.receive(), "STATUS")
        self.assertIsNone(self.session.snapshot()["jog"])

    def test_malformed_orders_are_not_sent(self):
        wait_for(lambda: self.session.snapshot()["connected"])
        for line, code in (("MOVER 1", 1), ("JOG 1 + 1001", 2), ("ENABLE ya", 2), ("PING" + " " * 60, 3)):
            with self.subTest(line=line), self.assertRaises(ProtocolError) as caught:
                self.session.order(line)
            self.assertEqual(caught.exception.code, code)

    def test_unexpected_boot_marks_the_robot_unreferenced(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        # BOOT como primera línea: el UNO se reinicia cuando socat abre el USB.
        self.uci.send("BOOT scara/1 1")
        wait_for(lambda: self.session.snapshot()["boots"] == 1)
        self.assertIn("arrancó", self.session.snapshot()["message"])
        self.uci.send("S IDLE 15 450 0 0 12000 0 16 0")
        self.assertTrue(wait_for(lambda: self.session.snapshot()["referenced"]))
        # Con referencia, el jog es de segmentos que planifica la URC (D75).
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "SEG 1 20 470 0 0 12000")
        # A mitad de la conexión: la UCI se reinició sola (F5).
        self.uci.send("BOOT scara/1 1")
        state = wait_for(lambda: (s := self.session.snapshot())["boots"] == 2 and s)
        self.assertFalse(state["referenced"])
        self.assertIsNone(state["status"])
        self.assertIsNone(state["jog"])
        self.assertIn("F5", state["message"])
        # El jog se olvidó: si la página lo sigue pidiendo, la URC lo reenvía.
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")

    def test_uci_errors_are_decoded(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("ERR 4 watchdog")
        self.uci.send("ERR 99 nuevo")
        state = wait_for(lambda: len((s := self.session.snapshot())["errors"]) == 2 and s)
        self.assertEqual(state["errors"][0], "ERR 4 watchdog: más de 1 s sin mensajes de la URC: el robot frenó solo")
        self.assertIn("desconocido", state["errors"][1])
        self.assertEqual(state["rejected"], [])

    def test_reconnection_greets_again_and_discards_bad_lines(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("S IDLE 0 1 2")
        self.uci.send("ERR 1 comando")
        wait_for(lambda: self.session.snapshot()["errors"])
        self.assertEqual(len(self.session.snapshot()["rejected"]), 1)
        self.assertIsNone(self.session.snapshot()["status"])
        self.uci.close()
        second = FakeUci(self.session.port)
        self.addCleanup(second.close)
        self.assertEqual(second.receive(), "HELLO")
        second.send("S JOG 0 1 2 3 4 0 16 0")
        state = wait_for(lambda: (s := self.session.snapshot())["status"] and s)
        self.assertEqual(state["status"]["position"], [1, 2, 3, 4])


class JogTestCase(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)
        self.assertEqual(self.uci.receive(), "HELLO")

    def status(self, line):
        """Envía un S y espera a que la URC lo tenga."""
        fields = line.split()
        self.uci.send(line)
        wait_for(lambda: (s := self.session.snapshot()["status"]) and s["mode"] == fields[1]
                 and s["position"] == [int(v) for v in fields[3:7]] and s["last"] == int(fields[9]))


class MotorJogGuardTests(JogTestCase):
    """Con referencia, el jog por motor no pasa del recorrido ni entra en la zona de choque (D70)."""

    def test_motor_jog_stops_at_the_end_of_travel(self):
        # M1 mueve también J2, al revés.
        self.status("S IDLE 15 0 -13450 0 12000 0 16 0")
        with self.assertRaisesRegex(ValueError, "J2 llegó"):
            self.session.jog(1, "+", motor=True)
        self.session.jog(1, "-", motor=True)
        self.assertEqual(self.uci.receive(), "JOG M1 - 1000")
        self.session.jog_stop()
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.session.jog(1, "-", motor=True, slow=True)
        self.assertEqual(self.uci.receive(), "JOG M1 - 200")

    def test_a_running_motor_jog_stops_before_the_limit(self):
        self.status("S IDLE 15 0 0 0 11000 0 16 0")
        self.session.jog(4, "+", motor=True)
        self.assertEqual(self.uci.receive(), "JOG M4 + 1000")
        self.session.jog(4, "+", motor=True)
        self.status("S JOG 15 0 0 0 11950 0 16 0")
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.assertIn("J4 llegó al límite", self.session.snapshot()["message"])
        with self.assertRaisesRegex(ValueError, "J4 llegó"):
            self.session.jog(4, "+", motor=True)

    def test_motor_jog_stops_before_the_margin_of_an_obstacle(self):
        # Con J4 abajo, el soporte Z llega a la zona de margen del pedestal
        # desde J2 ≈ 107,4°: a 10 °/s, frena antes.
        self.status("S IDLE 15 0 10600 0 12000 0 16 0")
        with self.assertRaisesRegex(ValueError, "Z-SoporteEfector-1 tocaría pedestal_de_ensayo"):
            self.session.jog(2, "+", motor=True)
        # Para el otro lado, y aun dentro de la zona, puede salir.
        self.session.jog(2, "-", motor=True)
        self.assertEqual(self.uci.receive(), "JOG M2 - 1000")

    def test_without_reference_the_firmware_jogs_slowly(self):
        self.status("S IDLE 0 0 0 0 12050 0 16 0")
        # Solo lo frena el Hall (D58).
        self.session.jog(4, "+")
        self.assertEqual(self.uci.receive(), "JOG 4 + 500")
        self.session.jog(4, "+", slow=True)
        self.assertEqual(self.uci.receive(), "JOG 4 + 200")
        with self.assertRaisesRegex(ValueError, "cartesiano está deshabilitado"):
            self.session.jog(2, "+", mode="cartesiano")


class SegmentJogTests(JogTestCase):
    """Con referencia, la URC planifica el jog en segmentos verificados (D28, D75)."""

    def segments(self, until=None, count=None):
        """Recibe los SEG del jog hasta `count`, o hasta que la URC calla `until` segundos.

        Confirma cada uno y, como el firmware, informa con S cuántos terminó:
        uno cada 20 ms desde el primero.
        """
        received, quiet = [], time.monotonic() + (until or 3)
        while count is None or len(received) < count:
            left = quiet - time.monotonic()
            if left <= 0:
                if count is not None:
                    self.fail(f"Llegaron {len(received)} de {count} segmentos")
                break
            self.uci.sock.settimeout(left)
            try:
                fields = self.uci.receive(ignore=()).split()
            except socket.timeout:
                continue
            finally:
                self.uci.sock.settimeout(3)
            if fields == ["PING"]:
                continue
            self.assertEqual(fields[:3], ["SEG", fields[1], "20"], fields)
            number, units = int(fields[1]), [int(v) for v in fields[3:]]
            received.append((number, units, time.monotonic()))
            self.uci.send(f"OK {number}")
            first, began = received[0][0], received[0][2]
            done = min(number - 1, first - 1 + int((time.monotonic() - began) / 0.02))
            self.uci.send(f"S RUN 15 {' '.join(map(str, units))} 0 16 {max(0, done)}")
            quiet = time.monotonic() + (until or 3)
        return received

    def resting_at(self, sent):
        """S con el robot quieto en el último segmento recibido."""
        number, units, _ = sent[-1]
        self.status(f"S IDLE 15 {' '.join(map(str, units))} 0 16 {number}")

    def test_the_queue_holds_about_three_segments(self):
        self.status("S IDLE 15 0 -6000 0 6000 0 16 0")
        self.session.jog(1, "+")
        sent = self.segments(count=3)
        self.assertEqual([units for _, units, _ in sent],
                         [[20, -6000, 0, 6000], [40, -6000, 0, 6000], [60, -6000, 0, 6000]])
        # Después, uno cada 20 ms: lo que el robot ejecuta.
        start = time.monotonic()
        while time.monotonic() - start < 0.4:
            self.session.jog(1, "+")
            sent += self.segments(count=1)
        rate = (len(sent) - 3) / (sent[-1][2] - sent[2][2])
        self.assertAlmostEqual(rate, 50, delta=12)
        self.assertTrue(all(units[1:] == [-6000, 0, 6000] for _, units, _ in sent))

    def test_releasing_the_key_sends_nothing_more(self):
        self.status("S IDLE 15 0 -6000 0 6000 0 16 0")
        self.session.jog(3, "-", slow=True)
        sent = self.segments(count=3)
        self.assertEqual(sent[-1][1], [0, -6000, -12, 6000])
        self.session.jog_stop()
        # Ni otro SEG ni JOG STOP: el robot termina lo encolado y frena.
        self.assertTrue(self.uci.silent(0.15))
        self.assertIsNone(self.session.snapshot()["jog"])
        # Sin renovar, vence igual.
        self.resting_at(sent)
        self.session.jog(3, "+")
        self.assertTrue(self.segments(until=0.6))
        self.assertTrue(self.uci.silent(0.15))

    def test_a_new_jog_waits_until_the_robot_stops(self):
        self.status("S IDLE 15 0 -6000 0 6000 0 16 0")
        self.session.jog(2, "+")
        sent = self.segments(count=3)
        self.session.jog_stop()
        self.status(f"S RUN 15 0 -5980 0 6000 0 16 {sent[0][0]}")
        # El cambio de sentido espera: arrancar al revés sería el doble del salto sin rampa.
        self.session.jog(2, "-")
        self.assertTrue(self.uci.silent(0.15))
        with self.assertRaisesRegex(ValueError, "moviendo"):
            self.session.move_ptp((0, 0, 0, 6000))
        self.resting_at(sent)
        number, units, _ = self.segments(count=1)[0]
        self.assertEqual(number, sent[-1][0] + 1)
        self.assertEqual(units, [0, -5960, 0, 6000])

    def test_a_running_jog_stops_before_the_limit(self):
        self.status("S IDLE 15 0 0 0 12000 0 16 0")
        with self.assertRaisesRegex(ValueError, r"J4 llegó al límite de su recorrido \(120 mm\)"):
            self.session.jog(4, "+", mode="cartesiano")
        self.status("S IDLE 15 0 0 0 11900 0 16 0")
        self.session.jog(4, "+")
        sent = self.segments(until=0.3)
        self.assertEqual([units[3] for _, units, _ in sent], [11920, 11940, 11960, 11980, 12000])
        self.assertIn("J4 llegó al límite de su recorrido", self.session.snapshot()["message"])
        with self.assertRaisesRegex(ValueError, "J4 llegó"):
            self.session.jog(4, "+")
        # Hacia adentro, sí.
        self.resting_at(sent)
        self.session.jog(4, "-")
        self.assertEqual(self.segments(count=1)[0][1], [0, 0, 0, 11980])

    def test_a_running_jog_stops_before_the_margin_of_an_obstacle(self):
        # Con J4 abajo, el soporte Z llega a la zona de margen del pedestal
        # desde J2 ≈ 107,4°.
        self.status("S IDLE 15 0 10600 0 12000 0 16 0")
        self.session.jog(2, "+")
        sent = self.segments(until=0.3)
        self.assertLess(sent[-1][1][1], 10760)
        self.assertIn("Z-SoporteEfector-1 tocaría pedestal_de_ensayo", self.session.snapshot()["message"])
        with self.assertRaisesRegex(ValueError, "tocaría"):
            self.session.jog(2, "+")
        # Para el otro lado puede salir.
        self.resting_at(sent)
        self.session.jog(2, "-")
        self.assertLess(self.segments(count=1)[0][1][1], sent[-1][1][1])

    def test_cartesian_jog_keeps_the_elbow_and_the_heading(self):
        self.status("S IDLE 15 3000 -6000 1000 6000 0 16 0")
        state = self.session.snapshot()
        self.assertEqual(state["elbow"], "negativo")
        self.assertEqual(state["tool"]["heading"], -2000)
        x, y = state["tool"]["x"], state["tool"]["y"]
        self.session.jog(2, "+", mode="cartesiano")
        self.assertEqual(self.session.snapshot()["jog"],
                         {"mode": "cartesiano", "joint": 2, "direction": "+", "motor": False, "slow": False})
        sent = self.segments(count=10)
        for _, units, _ in sent:
            self.assertLess(units[1], 0)
            self.assertAlmostEqual(sum(units[:3]), -2000, delta=2)
            self.assertEqual(units[3], 6000)
        self.session.jog_stop()
        self.resting_at(sent)
        tool = self.session.snapshot()["tool"]
        self.assertGreater(tool["x"], x + 2)
        self.assertAlmostEqual(tool["y"], y, delta=0.1)
        with self.assertRaisesRegex(ValueError, "por motor es articular"):
            self.session.jog(1, "+", motor=True, mode="cartesiano")
        with self.assertRaises(ValueError):
            self.session.jog(1, "+", mode="polar")

    def test_from_the_rest_pose_the_cartesian_jog_takes_the_preferred_elbow(self):
        self.status("S IDLE 15 0 0 0 12000 0 16 0")
        self.assertEqual(self.session.snapshot()["elbow"], "estirado")
        with self.assertRaisesRegex(ValueError, "borde del alcance"):
            self.session.jog(2, "+", mode="cartesiano")
        self.session.jog(2, "-", mode="cartesiano")
        self.assertLess(self.segments(count=1)[0][1][1], 0)

    def test_releasing_a_rejected_jog_leaves_a_tramo_alone(self):
        self.status("S IDLE 15 0 0 0 12000 0 16 0")
        self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertTrue(self.uci.receive().startswith("SEG 1 "))
        with self.assertRaisesRegex(ValueError, "tramo"):
            self.session.jog(1, "+")
        self.session.jog_stop()
        self.uci.send("OK 1")
        self.assertTrue(self.uci.receive().startswith("SEG 2 "))
        self.assertIsNone(self.session.snapshot()["tramo"]["cancelled"])

    def test_an_err_after_releasing_does_not_leave_the_robot_busy(self):
        self.status("S IDLE 15 0 -6000 0 6000 0 16 0")
        self.session.jog(1, "+")
        sent = self.segments(count=3)
        self.session.jog_stop()
        self.uci.send("ERR 4 watchdog")
        self.status(f"S IDLE 15 20 -6000 0 6000 0 16 {sent[0][0]}")
        # El firmware descartó el resto: se puede mover de nuevo.
        self.session.move_ptp((0, -6000, 0, 6000), dry_run=True)
        self.session.jog(1, "-")
        self.assertEqual(self.segments(count=1)[0][1], [0, -6000, 0, 6000])

    def test_stop_and_errors_end_the_jog(self):
        self.status("S IDLE 15 0 -6000 0 6000 0 16 0")
        self.session.jog(1, "+")
        self.segments(count=2)
        self.session.stop()
        # El tercero ya podía estar en camino.
        while (line := self.uci.receive()) != "STOP":
            self.assertTrue(line.startswith("SEG 3 "), line)
        self.assertTrue(self.uci.silent(0.1))
        time.sleep(STOP_GUARD)
        self.status("S IDLE 15 30 -6000 0 6000 0 16 1")
        # El firmware vació la cola: el próximo jog no espera los descartados.
        self.session.jog(1, "+")
        self.assertEqual(self.segments(count=1)[0][1], [50, -6000, 0, 6000])
        self.uci.send("ERR 4 watchdog")
        wait_for(lambda: "ERR 4" in self.session.snapshot()["message"])
        self.assertIsNone(self.session.snapshot()["jog"])
        # Solo los que salieron antes de que llegara el ERR.
        last = self.session.next_segment - 1
        self.assertTrue(all(number <= last for number, _, _ in self.segments(until=0.15)))


class SegmentTests(unittest.TestCase):
    """Tramos PTP: un SEG por vez, el siguiente con el OK del anterior (D6)."""

    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("S IDLE 15 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])

    def segment(self):
        fields = self.uci.receive().split()
        self.assertEqual(fields[0], "SEG", fields)
        return int(fields[1]), [int(value) for value in fields[3:]]

    def test_the_urc_waits_for_each_ok(self):
        plan = self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertGreater(plan["segments"], 20)
        # Con la cola del firmware llena, el OK 17 se demora: la URC tiene
        # todo el tramo listo, pero no envía de más.
        for expected in range(1, 18):
            number, _ = self.segment()
            self.assertEqual(number, expected)
            self.assertTrue(self.uci.silent(0.05))
            if number < 17:
                self.uci.send(f"OK {number}")
        self.assertTrue(self.uci.silent(0.3))
        self.uci.send("OK 17")
        last = None
        for expected in range(18, plan["segments"] + 1):
            number, last = self.segment()
            self.assertEqual(number, expected)
            self.uci.send(f"OK {number}")
        self.assertEqual(last, [900, 0, 0, 12000])
        self.assertTrue(self.uci.silent(0.1))
        self.uci.send(f"S IDLE 15 900 0 0 12000 0 16 {plan['segments']}")
        state = wait_for(lambda: (s := self.session.snapshot())["status"]["last"] and s)
        self.assertEqual(state["tramo"]["done"], plan["segments"])
        self.assertIsNone(state["tramo"]["cancelled"])
        self.assertEqual(state["segments"], {"pending": 0, "in_flight": None, "last_ok": plan["segments"]})

    def test_stop_discards_the_rest_of_the_tramo(self):
        self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertEqual(self.segment()[0], 1)
        self.session.stop()
        self.assertEqual(self.uci.receive(), "STOP")
        # El OK que llega tarde no reanuda nada.
        self.uci.send("OK 1")
        self.assertTrue(self.uci.silent(0.2))
        state = self.session.snapshot()
        self.assertEqual(state["segments"]["pending"], 0)
        self.assertEqual(state["tramo"]["cancelled"], "frenado por el operador")
        # Los números no se repiten: un tramo nuevo sigue la cuenta.
        self.uci.send("S IDLE 15 50 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["status"]["position"][0] == 50)
        self.session.move_ptp((0, 0, 0, 12000), speed=1)
        self.assertGreater(self.segment()[0], 30)

    def test_stop_after_the_last_segment_was_sent_still_cancels(self):
        # La URC ya envió todo, pero el robot ejecuta los últimos de la cola.
        plan = self.session.move_ptp((900, 0, 0, 12000), speed=1)
        for _ in range(plan["segments"]):
            number, _ = self.segment()
            self.uci.send(f"OK {number}")
        self.uci.send(f"S RUN 15 400 0 0 12000 0 0 {plan['segments'] - 16}")
        wait_for(lambda: self.session.snapshot()["status"]["mode"] == "RUN")
        with self.assertRaisesRegex(ValueError, "tramo"):
            self.session.jog(1, "+")
        self.session.stop()
        self.assertEqual(self.uci.receive(), "STOP")
        self.assertEqual(self.session.snapshot()["tramo"]["cancelled"], "frenado por el operador")

    def test_a_robot_stopped_before_the_end_closes_the_tramo(self):
        # El firmware frenó por un ERR que la URC no pudo leer: S lo muestra
        # quieto antes del último segmento, y el jog vuelve a estar permitido.
        plan = self.session.move_ptp((900, 0, 0, 12000), speed=1)
        for _ in range(plan["segments"]):
            number, _ = self.segment()
            self.uci.send(f"OK {number}")
        self.uci.send("S IDLE 15 400 0 0 12000 0 16 20")
        state = wait_for(lambda: (s := self.session.snapshot())["tramo"]["cancelled"] and s)
        self.assertEqual(state["tramo"]["cancelled"], "el robot se detuvo antes de terminar")
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), f"SEG {plan['segments'] + 1} 20 420 0 0 12000")

    def test_an_err_cancels_the_tramo(self):
        self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertEqual(self.segment()[0], 1)
        self.uci.send("OK 1")
        self.assertEqual(self.segment()[0], 2)
        # Con segmentos, el firmware frena ante todo ERR; la URC no sigue.
        self.uci.send("ERR 4 watchdog")
        state = wait_for(lambda: (s := self.session.snapshot())["errors"] and s)
        self.assertIn("ERR 4", state["tramo"]["cancelled"])
        self.assertIn("cancelado", state["message"])
        self.uci.send("OK 2")
        self.assertTrue(self.uci.silent(0.2))

    def test_a_boot_cancels_the_tramo(self):
        self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertEqual(self.segment()[0], 1)
        self.uci.send("BOOT scara/1 1")
        wait_for(lambda: self.session.snapshot()["boots"] == 1)
        self.uci.send("OK 1")
        self.assertTrue(self.uci.silent(0.2))
        self.assertEqual(self.session.snapshot()["tramo"]["cancelled"], "la UCI se reinició")

    def test_ptp_needs_a_referenced_robot_at_rest(self):
        plan = self.session.move_ptp((900, 0, 0, 12000), speed=0.5, dry_run=True)
        self.assertEqual(plan["start"], [0, 0, 0, 12000])
        self.assertAlmostEqual(plan["duration_s"], plan["segments"] * 0.02)
        self.assertTrue(self.uci.silent(0.1))
        with self.assertRaisesRegex(ValueError, "J1 fuera"):
            self.session.move_ptp((14000, 0, 0, 12000))
        self.uci.send("S JOG 15 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["status"]["mode"] == "JOG")
        with self.assertRaisesRegex(ValueError, "moviendo"):
            self.session.move_ptp((900, 0, 0, 12000))
        self.uci.send("S IDLE 0 0 0 0 12000 0 16 0")
        wait_for(lambda: not self.session.snapshot()["referenced"])
        with self.assertRaisesRegex(ValueError, "referenciado"):
            self.session.move_ptp((900, 0, 0, 12000))

    def test_no_jog_during_a_tramo(self):
        self.session.move_ptp((900, 0, 0, 12000), speed=1)
        self.assertEqual(self.segment()[0], 1)
        with self.assertRaisesRegex(ValueError, "tramo"):
            self.session.jog(1, "+")


class HomingTests(unittest.TestCase):
    """Homing (D11) y estacionar: la URC sigue los EV HOMED y vuelve al reposo."""

    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("S IDLE 0 0 0 0 12000 8 16 0")
        wait_for(lambda: self.session.snapshot()["status"])

    def test_homing_follows_the_axes_and_parks(self):
        self.session.home()
        self.assertEqual(self.uci.receive(), "HOME")
        self.uci.send("S HOMING 0 0 0 0 11000 0 16 0")
        for joint in (4, 1, 2):
            self.uci.send(f"EV HOMED {joint}")
        state = wait_for(lambda: (s := self.session.snapshot())["homing"]["axes"] == [4, 1, 2] and s)
        self.assertEqual(state["homing"]["state"], "en curso")
        with self.assertRaisesRegex(ValueError, "homing"):
            self.session.jog(1, "+")
        self.uci.send("EV HOMED 3")
        self.uci.send("S IDLE 15 -12999 -12999 -14501 300 15 16 0")
        # Con los cuatro ejes, la URC vuelve sola al reposo con un PTP.
        fields = self.uci.receive().split()
        self.assertEqual(fields[:2], ["SEG", "1"])
        state = self.session.snapshot()
        self.assertEqual(state["homing"]["state"], "terminado")
        self.assertEqual(state["tramo"]["target"], [0, 0, 0, 12000])
        self.assertEqual(state["tramo"]["speed"], 1.0)

    def test_a_stuck_hall_aborts_without_parking(self):
        self.session.home()
        self.assertEqual(self.uci.receive(), "HOME")
        self.uci.send("EV HOMED 4")
        self.uci.send("ERR 12 trabado")
        state = wait_for(lambda: (s := self.session.snapshot())["homing"]["state"] != "en curso" and s)
        self.assertIn("ERR 12 trabado", state["homing"]["state"])
        self.uci.send("S IDLE 0 -500 0 0 300 9 16 0")
        self.assertTrue(self.uci.silent(0.3))

    def test_a_rejected_or_silent_end_closes_the_homing(self):
        # El firmware rechaza el HOME: S nunca muestra HOMING.
        self.session.home()
        self.assertEqual(self.uci.receive(), "HOME")
        with self.assertRaisesRegex(ValueError, "ya está en curso"):
            self.session.home()
        self.uci.send("ERR 5 ocupado")
        self.uci.send("S IDLE 0 0 0 0 12000 8 16 0")
        self.assertEqual(self.session.snapshot()["homing"]["state"], "en curso")
        time.sleep(1.1)
        self.uci.send("S IDLE 0 0 0 0 12000 8 16 0")
        wait_for(lambda: "no empezó" in self.session.snapshot()["homing"]["state"])
        # Empezó y el robot quedó quieto sin los cuatro ejes: un ERR que no llegó.
        self.uci.send("S IDLE 0 0 0 0 12000 8 16 0")
        self.session.home()
        self.assertEqual(self.uci.receive(), "HOME")
        self.uci.send("S HOMING 0 0 0 0 11000 0 16 0")
        self.uci.send("EV HOMED 4")
        self.uci.send("S IDLE 0 0 0 0 300 8 16 0")
        wait_for(lambda: "sin terminar" in self.session.snapshot()["homing"]["state"])

    def test_stop_aborts_the_homing(self):
        self.session.home()
        self.assertEqual(self.uci.receive(), "HOME")
        self.session.stop()
        self.assertEqual(self.uci.receive(), "STOP")
        self.assertIn("frenado", self.session.snapshot()["homing"]["state"])

    def test_homing_needs_power_and_a_still_robot(self):
        self.uci.send("S OFF 0 0 0 0 12000 8 16 0")
        wait_for(lambda: self.session.snapshot()["status"]["mode"] == "OFF")
        with self.assertRaisesRegex(ValueError, "sin corriente"):
            self.session.home()
        self.uci.send("S JOG 0 0 0 0 12000 8 16 0")
        wait_for(lambda: self.session.snapshot()["status"]["mode"] == "JOG")
        with self.assertRaisesRegex(ValueError, "moviendo"):
            self.session.home()

    def test_park_needs_a_referenced_robot(self):
        with self.assertRaisesRegex(ValueError, "referenciado"):
            self.session.park()
        self.uci.send("S IDLE 15 3000 -6000 2000 8000 0 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])
        plan = self.session.park()
        self.assertEqual(plan["target"], [0, 0, 0, 12000])
        self.assertTrue(self.uci.receive().startswith("SEG 1 20 "))


class LostStepsTests(unittest.TestCase):
    """F1 (D65): EV LOST deja la referencia dudosa hasta volver a referenciar."""

    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])

    def lose(self, line):
        self.uci.send(line)
        return wait_for(lambda: (s := self.session.snapshot())["doubtful"] and s)

    def test_lost_steps_make_the_reference_doubtful(self):
        state = self.lose("EV LOST 4 8")
        self.assertEqual(state["doubtful"], [{"joint": 4, "steps": 8}])
        # El firmware sigue referenciado: la URC avisa, no decide por él.
        self.assertTrue(state["referenced"])
        self.assertIn("dudosa", state["message"])
        self.uci.send("EV LOST 1 -4")
        state = wait_for(lambda: len((s := self.session.snapshot())["doubtful"]) == 2 and s)
        self.assertEqual(state["doubtful"][1], {"joint": 1, "steps": -4})

    def test_homing_the_axis_clears_its_doubt(self):
        self.lose("EV LOST 4 8")
        self.uci.send("EV LOST 1 -4")
        self.uci.send("EV HOMED 4")
        state = wait_for(lambda: len((s := self.session.snapshot())["doubtful"]) == 1 and s)
        self.assertEqual(state["doubtful"], [{"joint": 1, "steps": -4}])

    def test_only_homing_clears_the_doubt(self):
        self.lose("EV LOST 2 5")
        # La referencia manual es menos precisa que el homing, y el firmware
        # puede rechazarla: la duda sigue.
        self.session.zero()
        self.assertEqual(self.uci.receive(), "ZERO")
        self.assertEqual(self.session.snapshot()["doubtful"], [{"joint": 2, "steps": 5}])

    def test_each_axis_keeps_its_last_report(self):
        self.lose("EV LOST 4 8")
        self.uci.send("EV LOST 4 9")
        state = wait_for(lambda: (s := self.session.snapshot())["doubtful"][0]["steps"] == 9 and s)
        self.assertEqual(state["doubtful"], [{"joint": 4, "steps": 9}])
        # La lista de errores lo conserva aunque el mensaje cambie.
        self.assertTrue(state["errors"][-1].startswith("EV LOST 4 9"))

    def test_losing_the_reference_or_a_boot_clears_the_doubt(self):
        self.lose("EV LOST 4 8")
        # Sin referencia en J4 (DISABLE, HALT), ya no hay nada de qué dudar.
        self.uci.send("S OFF 7 0 0 0 12000 8 16 0")
        wait_for(lambda: not self.session.snapshot()["doubtful"])
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        self.lose("EV LOST 3 -2")
        self.uci.send("BOOT scara/1 1")
        wait_for(lambda: not self.session.snapshot()["doubtful"])

    def test_malformed_lost_events_are_rejected(self):
        for line in ("EV LOST 5 3", "EV LOST 4", "EV LOST 4 x", "EV LOST 4 0"):
            self.uci.send(line)
        state = wait_for(lambda: len((s := self.session.snapshot())["rejected"]) == 4 and s)
        self.assertEqual(state["doubtful"], [])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.session))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        headers = dict({"Content-Type": "application/json"} if data else {}, **(headers or {}))
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()

    def test_page_and_state(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"scara/1", page)
        status, body = self.request("GET", "/api/estado")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["connected"])

    def test_orders_need_a_robot_and_a_local_origin(self):
        status, body = self.request("POST", "/api/jog", {"joint": 1, "direction": "+"})
        self.assertEqual(status, 409, body)
        status, _ = self.request("POST", "/api/jog", {"joint": 1, "direction": "+"},
                                 {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/jog", {"joint": 9, "direction": "+"})
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/jog", {"joint": 1, "direction": "+", "motor": 1})
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/nada", {})
        self.assertEqual(status, 404)
        for path in ("/api/enable", "/api/disable", "/api/stop", "/api/halt", "/api/home", "/api/park"):
            with self.subTest(path=path):
                status, _ = self.request("POST", path, {})
                self.assertEqual(status, 409)

    def test_orders_reach_a_connected_uci(self):
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        wait_for(lambda: self.session.snapshot()["connected"])
        for path, line in (("/api/enable", "ENABLE"), ("/api/stop", "STOP"), ("/api/halt", "HALT"),
                           ("/api/disable", "DISABLE")):
            with self.subTest(path=path):
                status, body = self.request("POST", path, {})
                self.assertEqual(status, 202, body)
                self.assertEqual(uci.receive(), line)

    def test_jog_modes_through_the_page(self):
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        uci.send("S IDLE 0 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["status"])
        # Sin referencia: cartesiano deshabilitado, articular lento.
        status, body = self.request("POST", "/api/jog", {"joint": 2, "direction": "-", "mode": "cartesiano"})
        self.assertEqual(status, 400, body)
        self.assertIn("deshabilitado", json.loads(body)["error"])
        status, body = self.request("POST", "/api/jog", {"joint": 2, "direction": "-", "slow": True})
        self.assertEqual(status, 202, body)
        self.assertEqual(uci.receive(), "JOG 2 - 200")
        for request in ({"joint": 2, "direction": "-", "mode": "polar"}, {"joint": 2, "direction": "-", "slow": 1}):
            with self.subTest(request=request):
                self.assertEqual(self.request("POST", "/api/jog", request)[0], 400)
        self.assertEqual(self.request("POST", "/api/jog/stop", {})[0], 202)
        self.assertEqual(uci.receive(), "JOG STOP")
        # Con referencia, el cartesiano es de segmentos; el estado muestra el modo y el codo.
        uci.send("S IDLE 15 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])
        status, body = self.request("POST", "/api/jog", {"joint": 2, "direction": "-", "mode": "cartesiano"})
        self.assertEqual(status, 202, body)
        self.assertTrue(uci.receive().startswith("SEG 1 20 "))
        state = json.loads(self.request("GET", "/api/estado")[1])
        self.assertEqual(state["jog"]["mode"], "cartesiano")
        self.assertEqual(state["elbow"], "estirado")
        self.assertEqual(state["tool"], {"x": 500.0, "y": 0.0, "z": -25.33, "heading": 0})
        status, body = self.request("POST", "/api/jog", {"joint": 2, "direction": "+", "mode": "cartesiano"})
        self.assertEqual(status, 400, body)
        self.assertIn("borde del alcance", json.loads(body)["error"])

    def test_ptp_to_a_pose_written_by_hand(self):
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        uci.send("S IDLE 15 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])
        # Sin confirmar, solo planifica y no envía nada.
        status, body = self.request("POST", "/api/ptp", {"joints": [30, -60, 10, 60], "speed": 50})
        self.assertEqual(status, 200, body)
        plan = json.loads(body)
        self.assertEqual(plan["target"], [3000, -6000, 1000, 6000])
        self.assertEqual(plan["speed"], 0.5)
        self.assertGreater(plan["duration_s"], 1)
        self.assertTrue(uci.silent(0.1))
        # La misma pose en XYZ y rumbo, con el codo preferido.
        status, body = self.request("POST", "/api/ptp", {
            "pose": {"x": 433.0, "y": 0.0, "z": 34.7, "heading": -20}, "speed": 50})
        self.assertEqual(status, 200, body)
        for got, want in zip(json.loads(body)["target"], (3000, -6000, 1000, 6000)):
            self.assertAlmostEqual(got, want, delta=5)  # X, Y y Z redondeados a 0,1 mm
        status, body = self.request("POST", "/api/ptp", {"joints": [30, -60, 10, 60], "speed": 50, "confirm": True})
        self.assertEqual(status, 202, body)
        self.assertTrue(uci.receive().startswith("SEG 1 20 "))
        self.assertEqual(json.loads(self.request("GET", "/api/estado")[1])["tramo"]["segments"], plan["segments"])

    def test_ptp_rejects_bad_requests(self):
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        uci.send("S IDLE 15 0 0 0 12000 0 16 0")
        wait_for(lambda: self.session.snapshot()["referenced"])
        for request in ({"joints": [0, 0, 0]}, {"joints": [0, 0, 0, "x"]}, {"joints": [0, 0, 0, 120], "speed": 0},
                        {"joints": [0, 0, 0, 120], "speed": 101}, {}, {"pose": {"x": 900, "y": 0, "z": 0, "heading": 0}},
                        {"pose": {"x": 300, "y": 0, "z": 0, "heading": 0, "elbow": True}},
                        {"joints": [0, 140, 0, 120]}):
            with self.subTest(request=request):
                status, body = self.request("POST", "/api/ptp", request)
                self.assertEqual(status, 400, body)
        self.assertTrue(uci.silent(0.1))


if __name__ == "__main__":
    unittest.main()
