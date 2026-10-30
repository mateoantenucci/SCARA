"""Exporta el documento maestro v2 de Markdown a PDF.

Convierte el Markdown a HTML con mistune (tools/requirements-docs.txt) y lo
imprime a PDF con Edge o Chrome sin interfaz. No toca 00-SCARA-Master.pdf.
`<!-- SALTO DE PAGINA -->` en el Markdown fuerza un salto de página.
"""

import argparse
import html
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FUENTE = ROOT / "docs/maestro/SCARA-Master-v2.md"
DESTINO = ROOT / "output/pdf/SCARA-Master-v2.pdf"
SALTO = "<!-- SALTO DE PAGINA -->"

NAVEGADORES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

ESTILO = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.42; color: #1a1a1a; }
h1 { font-size: 21pt; margin: 0 0 6pt; }
h2 { font-size: 15pt; border-bottom: 1.5pt solid #335; padding-bottom: 2pt; margin-top: 18pt; }
h3 { font-size: 12pt; margin-top: 14pt; }
h2, h3 { break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9.5pt; }
th, td { border: 0.6pt solid #999; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #e8ebf2; }
tr { break-inside: avoid; }
code { font-family: Consolas, Menlo, monospace; font-size: 9pt; background: #f2f2f2;
       padding: 0 2pt; }
pre { background: #f2f2f2; padding: 6pt 8pt; font-size: 9pt; break-inside: avoid;
      white-space: pre-wrap; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3pt solid #c90; margin: 8pt 0; padding: 2pt 10pt; background: #fff8e6; }
a { color: #1f4e9c; text-decoration: none; }
.salto { break-after: page; }
"""


def a_html(texto, titulo):
    import mistune

    convertir = mistune.create_markdown(plugins=["table", "strikethrough"], escape=False)
    partes = [convertir(parte) for parte in texto.split(SALTO)]
    cuerpo = '\n<div class="salto"></div>\n'.join(partes)
    return (
        '<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
        f"<title>{html.escape(titulo)}</title><style>{ESTILO}</style></head>"
        f"<body>\n{cuerpo}\n</body></html>\n"
    )


def buscar_navegador():
    elegido = os.environ.get("SCARA_NAVEGADOR")
    if elegido:
        return elegido
    for ruta in NAVEGADORES:
        if Path(ruta).exists():
            return ruta
    for nombre in ("msedge", "google-chrome", "chromium", "chromium-browser"):
        if shutil.which(nombre):
            return shutil.which(nombre)
    raise SystemExit("No se encontró Edge ni Chrome; indicá uno con SCARA_NAVEGADOR.")


def imprimir(pagina, destino, navegador):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as carpeta:
        fuente = Path(carpeta) / "maestro.html"
        fuente.write_text(pagina, encoding="utf-8")
        subprocess.run(
            [
                navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--user-data-dir={Path(carpeta) / 'perfil'}",
                f"--print-to-pdf={destino}", fuente.as_uri(),
            ],
            check=True, capture_output=True, timeout=120,
        )
    if not destino.exists() or destino.stat().st_size == 0:
        raise SystemExit(f"El navegador no generó {destino}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", type=Path, default=FUENTE)
    parser.add_argument("--destino", type=Path, default=DESTINO)
    args = parser.parse_args(argv)
    texto = args.fuente.read_text(encoding="utf-8")
    titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), "SCARA")
    imprimir(a_html(texto, titulo), args.destino.resolve(), buscar_navegador())
    print(args.destino)


if __name__ == "__main__":
    sys.exit(main())
