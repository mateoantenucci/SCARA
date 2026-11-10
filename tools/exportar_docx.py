"""Exporta el informe en Markdown a Word (.docx).

Entiende el subconjunto de Markdown y HTML que usa docs/informe/INFORME-SCARA.md:
carátula, títulos, párrafos, listas, citas, tablas, bloques de código, figuras y
saltos de página. Las figuras SVG se pasan a PNG con Chrome sin interfaz.

    python3 tools/exportar_docx.py --fuente docs/informe/INFORME-SCARA.md \
        --destino output/docx/SCARA-Informe-Gemelos-Digitales.docx

Requiere python-docx y, si hay figuras SVG, Google Chrome.
"""

import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FUENTE = "Calibri"
MONO = "Consolas"
AZUL = RGBColor(0x1F, 0x3A, 0x5F)
GRIS = RGBColor(0x55, 0x55, 0x55)
ANCHO_UTIL = 16.0  # cm, A4 con márgenes de 2,5 cm


# --- Texto con formato en línea -------------------------------------------------

_TOKEN = re.compile(r"(`[^`]+`|\*\*|\*|<[^>]+>)")


def add_inline(par, text, size=None, bold=False, italic=False, color=None):
    """Agrega a par el texto con **negrita**, *cursiva*, `código` y etiquetas HTML simples."""
    state = {"b": bold, "i": italic, "c": False}
    for piece in _TOKEN.split(text):
        if not piece:
            continue
        if piece.startswith("`") and piece.endswith("`") and len(piece) > 1:
            _run(par, piece[1:-1], state["b"], state["i"], True, size, color)
        elif piece == "**":
            state["b"] = not state["b"]
        elif piece == "*":
            state["i"] = not state["i"]
        elif piece.startswith("<"):
            tag = piece.strip("<>/ ").split()[0].lower() if piece.strip("<>/ ") else ""
            closing = piece.startswith("</")
            if tag in ("strong", "b"):
                state["b"] = not closing
            elif tag == "em":
                state["i"] = not closing
            elif tag == "code":
                state["c"] = not closing
            elif tag == "br":
                par.add_run().add_break()
        else:
            _run(par, html.unescape(piece), state["b"], state["i"], state["c"], size, color)


def _run(par, text, bold, italic, code, size, color):
    run = par.add_run(text)
    run.bold = bold or None
    run.italic = italic or None
    if code:
        _font(run, MONO)
        run.font.size = Pt((size or 11) - 1.5)
        run.font.color.rgb = RGBColor(0x8A, 0x1C, 0x3B)
    else:
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = color
    return run


def _font(run, name):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), name)


def _shade(element_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element_pr.append(shd)


def _spacing(par, before=0, after=6, line=None):
    fmt = par.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    if line:
        fmt.line_spacing = line


# --- Imágenes -------------------------------------------------------------------

class Imagenes:
    def __init__(self, base):
        self.base = base
        self.tmp = Path(tempfile.mkdtemp(prefix="informe-docx-"))

    def ruta(self, src):
        path = (self.base / src).resolve()
        if path.suffix.lower() != ".svg":
            return path
        png = self.tmp / (path.stem + ".png")
        if not png.exists():
            box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', path.read_text(encoding="utf-8"))
            w, h = (int(float(v)) for v in box.groups())
            page = self.tmp / (path.stem + ".html")
            page.write_text(
                f'<html><body style="margin:0;background:#fff">'
                f'<img src="{path.as_uri()}" style="width:{w}px;height:{h}px;display:block"></body></html>',
                encoding="utf-8")
            subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={w},{h}", "--force-device-scale-factor=3",
                            f"--screenshot={png}", page.as_uri()],
                           check=True, capture_output=True, timeout=60)
        return png


# --- Bloques --------------------------------------------------------------------

def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def heading(doc, text, level):
    par = doc.add_heading(level=level)
    add_inline(par, text)
    return par


def paragraph(doc, text, style=None):
    par = doc.add_paragraph(style=style)
    add_inline(par, text)
    _spacing(par, after=6, line=1.15)
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return par


def code_block(doc, lines):
    for i, line in enumerate(lines):
        par = doc.add_paragraph()
        run = par.add_run(line if line else " ")
        # Sin esto Word junta los espacios y desarma los diagramas en texto.
        for t in run._r.iter(qn("w:t")):
            t.set(qn("xml:space"), "preserve")
        _font(run, MONO)
        run.font.size = Pt(8)
        _shade(par._p.get_or_add_pPr(), "F3F4F6")
        _spacing(par, before=4 if i == 0 else 0, after=4 if i == len(lines) - 1 else 0, line=1.0)
        par.paragraph_format.left_indent = Cm(0.2)
        par.paragraph_format.keep_with_next = i < len(lines) - 1


def split_row(line):
    cells, cur, i = [], "", 0
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if line[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += line[i]
        i += 1
    cells.append(cur.strip())
    return cells


def table(doc, rows):
    header, body = rows[0], rows[2:]
    t = doc.add_table(rows=1 + len(body), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r, cells in enumerate([header] + body):
        for c, text in enumerate(cells[:len(header)]):
            cell = t.cell(r, c)
            par = cell.paragraphs[0]
            add_inline(par, text, size=9, bold=(r == 0))
            _spacing(par, before=1, after=1, line=1.0)
            if r == 0:
                _shade(cell._tc.get_or_add_tcPr(), "DCE3EC")
    # La fila de encabezado se repite si la tabla cambia de página.
    trpr = t.rows[0]._tr.get_or_add_trPr()
    rep = OxmlElement("w:tblHeader")
    rep.set(qn("w:val"), "true")
    trpr.append(rep)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figure(doc, imgs, src, caption, width_cm, container=None):
    target = container if container is not None else doc
    par = target.add_paragraph() if container is None else container.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(imgs.ruta(src)), width=Cm(width_cm))
    par.paragraph_format.keep_with_next = True
    if caption:
        cap = target.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(cap, caption, size=9, italic=True, color=GRIS)
        _spacing(cap, before=2, after=10, line=1.0)


_FIG = re.compile(r'<figure(?:\s+class="([^"]*)")?>(.*?)</figure>', re.S)
_IMG = re.compile(r'<img\s+src="([^"]+)"')
_CAP = re.compile(r"<figcaption>(.*?)</figcaption>", re.S)


def parse_figures(block):
    out = []
    for cls, inner in _FIG.findall(block):
        img = _IMG.search(inner)
        cap = _CAP.search(inner)
        out.append((cls or "", img.group(1) if img else None, cap.group(1).strip() if cap else ""))
    return out


def figures(doc, imgs, block):
    figs = parse_figures(block)
    if block.lstrip().startswith('<div class="fotos">') and len(figs) > 1:
        t = doc.add_table(rows=1, cols=len(figs))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        width = ANCHO_UTIL / len(figs) - 0.6
        for i, (_, src, cap) in enumerate(figs):
            figure(doc, imgs, src, cap, width, container=t.cell(0, i))
        doc.add_paragraph().paragraph_format.space_after = Pt(0)
        return
    for cls, src, cap in figs:
        if src is None:
            continue
        width = 5.0 if "retrato" in src or "turing" in src else ANCHO_UTIL if cls in ("ancha", "captura") else 12.0
        figure(doc, imgs, src, cap, width)


def caratula(doc, block):
    for _ in range(3):
        doc.add_paragraph()
    for tag, cls, text in re.findall(r'<(p|h1)(?:\s+class="([^"]*)")?>(.*?)</\1>', block, re.S):
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if tag == "h1":
            add_inline(par, text, size=30, bold=True, color=AZUL)
            _spacing(par, before=0, after=18)
        elif cls == "rotulo":
            add_inline(par, text.upper(), size=9, bold=True, color=GRIS)
            _spacing(par, before=10, after=0)
        else:
            add_inline(par, text, size=13)
            _spacing(par, before=0, after=2)


# --- Documento ------------------------------------------------------------------

def setup(doc):
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.5))
    normal = doc.styles["Normal"]
    normal.font.name = FUENTE
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FUENTE)
    for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12), ("Title", 26)):
        st = doc.styles[name]
        st.font.name = FUENTE
        st.font.size = Pt(size)
        st.font.color.rgb = AZUL
        st.font.bold = True
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(attr), FUENTE)
        for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            fonts.attrib.pop(qn(theme), None)
        st.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
        st.paragraph_format.space_after = Pt(6)
    # Número de página centrado en el pie.
    foot = sec.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = foot.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            run._r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = text
            run._r.append(instr)
    run.font.size = Pt(9)
    sec.different_first_page_header_footer = True


def convert(source, dest):
    text = source.read_text(encoding="utf-8")
    doc = Document()
    setup(doc)
    imgs = Imagenes(source.parent)
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s == "<!-- SALTO DE PAGINA -->":
            page_break(doc)
            i += 1
            continue
        if s.startswith("<!--"):
            while "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if s.startswith("<div") or s.startswith("<figure"):
            end_tag = "</div>" if s.startswith("<div") else "</figure>"
            block = []
            while True:
                block.append(lines[i])
                if lines[i].strip().endswith(end_tag):
                    break
                i += 1
            i += 1
            block = "\n".join(block)
            if 'class="caratula"' in block:
                caratula(doc, block)
            else:
                figures(doc, imgs, block)
            continue
        if s.startswith("```"):
            i += 1
            code = []
            while not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            code_block(doc, code)
            continue
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            level = len(m.group(1))
            heading(doc, m.group(2), 1 if level <= 2 else 2)
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            table(doc, rows)
            continue
        if s.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            for para in "\n".join(quote).split("\n\n"):
                par = paragraph(doc, " ".join(para.split("\n")))
                par.paragraph_format.left_indent = Cm(1)
                par.paragraph_format.right_indent = Cm(1)
                for run in par.runs:
                    run.italic = True
            continue
        if re.match(r"(-|\d+\.)\s", s):
            ordered = s[0].isdigit()
            while i < len(lines) and re.match(r"(-|\d+\.)\s", lines[i].strip()):
                item = re.sub(r"^(-|\d+\.)\s+", "", lines[i].strip())
                i += 1
                while i < len(lines) and lines[i].startswith("   ") and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                par = paragraph(doc, item, style="List Number" if ordered else "List Bullet")
                par.alignment = WD_ALIGN_PARAGRAPH.LEFT
                _spacing(par, after=3, line=1.1)
            continue
        para = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||```|<|>|-\s|\d+\.\s)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        paragraph(doc, " ".join(para))
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fuente", type=Path, required=True)
    ap.add_argument("--destino", type=Path, required=True)
    args = ap.parse_args()
    convert(args.fuente, args.destino)
    print(args.destino)


if __name__ == "__main__":
    main()
