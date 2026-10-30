# Documento maestro v2

- Fuente: [`SCARA-Master-v2.md`](SCARA-Master-v2.md). Se edita solo el Markdown.
- PDF exportado: [`output/pdf/SCARA-Master-v2.pdf`](../../output/pdf/SCARA-Master-v2.pdf).
- El maestro v1 (`00-SCARA-Master.pdf`) no se toca (D17).

## Regenerar el PDF

Hace falta Python 3 con `mistune` y Edge o Chrome instalados. En Windows, Edge viene con el sistema.

```bash
python -m pip install -r tools/requirements-docs.txt
```

```bash
python tools/exportar_maestro.py
```

El script convierte el Markdown a HTML y lo imprime a PDF con el navegador sin interfaz, en una carpeta temporal que se borra sola. Si el navegador está en otra ruta, se indica con la variable `SCARA_NAVEGADOR`. `--fuente` y `--destino` permiten exportar otro Markdown.

`<!-- SALTO DE PAGINA -->` en el Markdown fuerza un salto de página. Los enlaces relativos a otros documentos del repo funcionan en GitHub; en el PDF quedan como referencia de lectura.

Cada vez que cambia el Markdown, se regenera el PDF y se versionan los dos en el mismo commit.
