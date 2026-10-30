import importlib.util
import unittest

from tools.exportar_maestro import FUENTE, SALTO, a_html


@unittest.skipUnless(importlib.util.find_spec("mistune"), "requiere tools/requirements-docs.txt")
class ExportarMaestroTests(unittest.TestCase):
    def test_tablas_saltos_y_titulo(self):
        pagina = a_html(f"# Título\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n{SALTO}\n\n## Otra", "T<1>")
        self.assertIn("<table>", pagina)
        self.assertIn('<div class="salto"></div>', pagina)
        self.assertIn("<title>T&lt;1&gt;</title>", pagina)

    def test_el_maestro_v2_existe_y_convierte(self):
        pagina = a_html(FUENTE.read_text(encoding="utf-8"), "maestro")
        for propuesta in ("D9", "D10", "D11"):
            self.assertIn(propuesta, pagina)


if __name__ == "__main__":
    unittest.main()
