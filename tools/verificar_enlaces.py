"""Verifica que los enlaces internos de los Markdown del repo apunten a algo.

Revisa enlaces `[texto](ruta)`, `![img](ruta)` y `src`/`href` HTML. Ignora
URLs externas, anclas sueltas, bloques de código y las carpetas `historico/`,
cuyos bytes no se editan (la evidencia se identifica por SHA-256).
Uso: python tools/verificar_enlaces.py  (sale con 1 si hay rotos).
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EXCLUIDAS = {".git", ".claude", "historico", "node_modules", "output"}
BLOQUE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
CODIGO = re.compile(r"`[^`\n]*`")
ENLACE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)")
HTML = re.compile(r"""(?:src|href)=["']([^"']+)["']""")
EXTERNO = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def destinos(texto):
    texto = CODIGO.sub("", BLOQUE.sub("", texto))
    for patron in (ENLACE, HTML):
        for coincidencia in patron.finditer(texto):
            yield coincidencia.group(1).strip("<>")


def enlaces_rotos(raiz):
    rotos = []
    for archivo in sorted(raiz.rglob("*.md")):
        relativo = archivo.relative_to(raiz)
        if EXCLUIDAS.intersection(relativo.parts[:-1]):
            continue
        for destino in destinos(archivo.read_text(encoding="utf-8")):
            ruta = unquote(destino.split("#", 1)[0])
            if not ruta or EXTERNO.match(destino) or destino.startswith("//"):
                continue
            # `../blob/main/...` es la forma de enlazar al repo desde issues de GitHub.
            if "/blob/" in ruta or "/tree/" in ruta:
                continue
            if not (archivo.parent / ruta).exists():
                rotos.append((relativo.as_posix(), destino))
    return rotos


def main():
    rotos = enlaces_rotos(ROOT)
    for archivo, destino in rotos:
        print(f"{archivo}: {destino}")
    print(f"{len(rotos)} enlaces rotos")
    return 1 if rotos else 0


if __name__ == "__main__":
    sys.exit(main())
