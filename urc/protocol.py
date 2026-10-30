"""Gramática de scara/1 del lado de la URC (docs/PROTOCOLO_SCARA_1.md).

check_order revisa una orden URC → UCI antes de enviarla: la URC nunca envía
lo que el firmware rechazaría por su forma, y lo rechaza con el mismo código.
parse_message interpreta un mensaje UCI → URC. Las conversaciones de
conformidad obligan a los dos lados a coincidir (tests/test_conformidad.py).
"""

import re


PROTOCOL = "scara/1"
LINE_MAX = 64                # bytes con el LF (D4)
JOG_SPEED_MAX = 1000         # centésimas por segundo
SEG_NUMBER_MAX = 999999999   # n de SEG: hasta 9 cifras, desde 1
SEG_MS_MAX = 1000            # duración máxima de un segmento
SEG_UNITS_MAX = 99999        # |q| máximo de un segmento, en centésimas
MODES = ("OFF", "IDLE", "JOG", "RUN")
# Órdenes sin argumentos.
SIMPLE_ORDERS = ("HELLO", "PING", "STATUS", "ENABLE", "DISABLE", "STOP", "HALT", "ZERO")
# Código: (palabra, causa). Son estables: se agregan, no se renumeran.
ERRORS = {
    1: ("comando", "comando desconocido o bytes fuera de ASCII imprimible"),
    2: ("argumentos", "faltan, sobran o están fuera de rango"),
    3: ("largo", "línea de más de 64 bytes"),
    4: ("watchdog", "más de 1 s sin mensajes de la URC: el robot frenó solo"),
    5: ("ocupado", "no se acepta mientras hay movimiento"),
    6: ("deshabilitado", "no se acepta con los drivers sin corriente"),
    7: ("referencia", "SEG sin el robot referenciado"),
    8: ("velocidad", "el segmento supera la velocidad de un motor"),
    9: ("cola", "SEG antes del OK del anterior, con la cola llena"),
}
INTEGER = re.compile(r"-?[0-9]+")
UNSIGNED = re.compile(r"[0-9]{1,9}")      # como parseUnsigned del firmware
SIGNED = re.compile(r"-?[0-9]{1,9}")      # como parseSigned del firmware
PRINTABLE = re.compile(r"[ -~]*")


class ProtocolError(ValueError):
    """Orden mal formada; code es el ERR con que la respondería el firmware."""

    def __init__(self, code, detail):
        super().__init__(f"ERR {code} {ERRORS[code][0]}: {detail}")
        self.code = code


def check_order(line):
    """Valida una orden URC → UCI y la devuelve sin CR, lista para enviar."""
    line = line.replace("\r", "")
    if len(line.encode()) + 1 > LINE_MAX:
        raise ProtocolError(3, "la orden no entra en 64 bytes con el LF")
    if not PRINTABLE.fullmatch(line):
        raise ProtocolError(1, "solo se admite ASCII imprimible")
    fields = line.split()  # solo quedan espacios: el resto ya se rechazó
    if not fields:
        raise ValueError("Una línea vacía no es una orden")
    command, arguments = fields[0], fields[1:]
    if command in SIMPLE_ORDERS:
        if arguments:
            raise ProtocolError(2, f"{command} no lleva argumentos")
    elif command == "JOG":
        if arguments != ["STOP"] and not _valid_jog(arguments):
            raise ProtocolError(2, "se espera JOG j ± vel, JOG Mm ± vel (j y m de 1 a 4, vel de 1 a 1000) "
                                   "o JOG STOP")
    elif command == "SEG":
        if not _valid_segment(arguments):
            raise ProtocolError(2, f"se espera SEG n ms q1 q2 q3 q4 (n de 1 a {SEG_NUMBER_MAX}, ms de 1 a "
                                   f"{SEG_MS_MAX}, q enteros de hasta ±{SEG_UNITS_MAX})")
    else:
        raise ProtocolError(1, f"{command} no es una orden de {PROTOCOL}")
    return line


def _valid_jog(arguments):
    if len(arguments) != 3:
        return False
    axis, sign, speed = arguments
    if axis.startswith("M"):     # jog por motor (D46)
        axis = axis[1:]
    return (UNSIGNED.fullmatch(axis) is not None and 1 <= int(axis) <= 4 and sign in ("+", "-")
            and UNSIGNED.fullmatch(speed) is not None and 1 <= int(speed) <= JOG_SPEED_MAX)


def _valid_segment(arguments):
    if len(arguments) != 6:
        return False
    number, ms, *units = arguments
    return (UNSIGNED.fullmatch(number) is not None and 1 <= int(number)
            and UNSIGNED.fullmatch(ms) is not None and 1 <= int(ms) <= SEG_MS_MAX
            and all(SIGNED.fullmatch(q) is not None and abs(int(q)) <= SEG_UNITS_MAX for q in units))


def segment_line(number, ms, units):
    """Orden SEG lista para enviar: n, duración en ms y J1–J4 en centésimas."""
    return check_order(f"SEG {number} {ms} {' '.join(str(q) for q in units)}")


def integer(text):
    """Entero del protocolo: solo cifras ASCII y un signo menos opcional."""
    if not INTEGER.fullmatch(text):
        raise ValueError(f"{text!r} no es un entero")
    return int(text)


def parse_message(line):
    """Interpreta un mensaje UCI → URC; ValueError si no respeta la forma."""
    fields = line.split()
    if not fields:
        raise ValueError("línea vacía")
    kind, rest = fields[0], fields[1:]
    if kind in ("BOOT", "HI"):
        if len(rest) != 2:
            raise ValueError(f"{kind} mal formado")
        if rest[0] != PROTOCOL:
            raise ValueError(f"la UCI habla {rest[0]}, no {PROTOCOL}")
        return {"kind": kind, "protocol": rest[0], "version": integer(rest[1])}
    if kind == "S":
        return dict(parse_status(rest), kind="S")
    if kind == "OK":
        if len(rest) != 1:
            raise ValueError("OK mal formado")
        return {"kind": "OK", "number": integer(rest[0])}
    if kind == "ERR":
        if len(rest) != 2:
            raise ValueError("ERR mal formado")
        code = integer(rest[0])
        # Un código nuevo de un firmware más moderno se muestra igual.
        cause = ERRORS[code][1] if code in ERRORS else "código desconocido para esta URC"
        return {"kind": "ERR", "code": code, "word": rest[1], "cause": cause}
    raise ValueError("mensaje desconocido")


def parse_status(fields):
    """S modo referenciados J1 J2 J3 J4 hall libres último."""
    if len(fields) != 9 or fields[0] not in MODES:
        raise ValueError("estado S mal formado")
    numbers = [integer(value) for value in fields[1:]]
    return {
        "mode": fields[0],
        "homed": numbers[0],
        "position": numbers[1:5],
        "hall": numbers[5],
        "free": numbers[6],
        "last": numbers[7],
    }
