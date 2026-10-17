# Torre por cuerpos: derivado visual separado

Los tres STL de `stl/` representan individualmente los tres sólidos del STEP de `0-Torre`. Conservan origen y orientación de pieza. Las coordenadas están en **metros**; no aplicar otro factor de 0,001 al incorporarlas a Webots. Las tres mallas necesitan la misma colocación de la instancia de torre del ensamble.

| Cuerpo | Volumen BREP, mm³ | Triángulos crudos | Triángulos derivados | Error de volumen STL/BREP |
| --- | ---: | ---: | ---: | ---: |
| 01 | 9.457,636133 | 648 | 648 | 0,00768 % |
| 02 | 9.457,636133 | 648 | 648 | 0,00768 % |
| 03 | 373.897,663364 | 2.990 | 2.982 | 0,00564 % |

Los tres BREP son válidos para `BRepCheck_Analyzer`. Cada malla derivada pasa los controles individuales de aristas de borde/no manifold, volumen y caja envolvente. Esto permite usarlas como tres geometrías visuales dentro del mismo cuerpo estático; no demuestra que su unión sea una única malla manifold, ni valida materiales, masa, dinámica o colocación del ensamble.

`crudos/` conserva los STL directos de OCCT. En el cuerpo 03, ocho triángulos con área exactamente cero causaban autoaristas y lados contados más de dos veces en el control de malla. El filtro comprueba el producto vectorial con aritmética racional exacta de las coordenadas float32 guardadas: elimina exclusivamente esos ocho registros. Los cuerpos 01 y 02 no necesitan eliminar ninguno.

No se soldaron ni desplazaron vértices, no se cerraron huecos, no se añadieron caras y no se eliminó superficie de área positiva. Los registros restantes son idénticos byte a byte. La caja envolvente y el volumen orientado calculado del STL son idénticos antes/después en los tres cuerpos. El [informe individual](informe.json) registra índices de triángulos eliminados, versiones, fuentes, hashes y resultados.

Los archivos originales, el STEP y el informe principal permanecen intactos. El resultado del lote principal sigue siendo **44 STL aceptados y seis piezas rechazadas**, incluyendo el rechazo de la malla global de `0-Torre`. Este derivado no modifica ese resultado ni certifica equivalencia exacta contra SolidWorks.

Reproducir desde la raíz del proyecto con las dependencias de `tools/requirements-cad.txt`:

```sh
python -B tools/exportar_torre_cuerpos.py
```

Para una comprobación independiente sin reemplazar esta salida, agregar `--output /ruta/torre-prueba`. El programa no descarga archivos ni ejecuta de nuevo el conversor SLDPRT: comprueba los hashes del original y del STEP contra el informe existente. Dos ejecuciones con el entorno registrado produjeron los mismos hashes para los seis STL.
