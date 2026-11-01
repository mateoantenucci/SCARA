import tempfile
import unittest
from pathlib import Path

from tools.verificar_enlaces import ROOT, enlaces_rotos


# El maestro lo edita #19 en paralelo; apunta a documentos que #1 pasó a docs/historico/.
PENDIENTES_19 = {
    ("docs/maestro/SCARA-Master-v2.md", f"../{nombre}.md")
    for nombre in (
        "REVISION_PARA_EL_PROFESOR_2026-10-27",
        "DATOS_PARA_EL_PROFESOR",
        "INVESTIGACION_TEACH_AND_PLAY_2026-10-29",
    )
}


class VerificarEnlacesTests(unittest.TestCase):
    def _repo(self, archivos):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        raiz = Path(carpeta.name)
        for nombre, texto in archivos.items():
            ruta = raiz / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(texto, encoding="utf-8")
        return raiz

    def test_detecta_rotos_e_ignora_externos_y_anclas(self):
        raiz = self._repo({
            "README.md": "[a](docs/A.md#x) [b](docs/FALTA.md) [w](https://x.org) [s](#arriba)",
            "docs/A.md": "[up](../README.md) <img src=\"falta.png\"> [c](<con espacio.md>)",
            "docs/con espacio.md": "",
        })
        rotos = enlaces_rotos(raiz)
        self.assertEqual(rotos, [("docs/A.md", "falta.png"), ("README.md", "docs/FALTA.md")])

    def test_ignora_codigo_y_carpetas_historicas(self):
        raiz = self._repo({
            "a.md": "```\n[x](no.md)\n```\n`[y](no.md)`",
            "docs/historico/b.md": "[z](no.md)",
            "validation/historico/c/d.md": "[z](no.md)",
        })
        self.assertEqual(enlaces_rotos(raiz), [])

    def test_el_repo_no_tiene_enlaces_rotos(self):
        rotos = [r for r in enlaces_rotos(ROOT) if r not in PENDIENTES_19]
        self.assertEqual(rotos, [])


if __name__ == "__main__":
    unittest.main()
