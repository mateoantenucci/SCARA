# Sesión 8 · precálculo geométrico de 39 instancias

Resultado del 17/10/2026: **50 tipos examinados, 49 calculados, 51 sólidos y 39/39 instancias calculadas**. La única exclusión sigue siendo `B-ExtensorM3`, por BREP global inválido y fuera de las instancias seleccionadas. No se modificaron ni repararon originales; no hubo reconversión, asignación de material/densidad ni cambios en física, configuración, PROTO, mundo o ZIP.

La copia aislada se contrastó antes y después contra los **680 archivos** de `baseline_rondaA.json`, sin diferencias. Incluye los 152 archivos bajo `Modelos3D` y las demás fuentes/evidencias de la base. El propio calculador verificó además sus **217 entradas protegidas**, conservadas. Los informes de 38 permanecen intactos y el candidato agrega archivos con sufijo `_39`; no los reemplaza.

## Fuentes y ejecución

- Base: `baseline_rondaA.json`, copia exacta del registro privado del director; identidad de las fuentes en `contraste.json`, el JSON generado y el manifiesto candidato.
- Productor existente: `tools/calcular_propiedades_cad.py`, SHA-256 `c3dea02608b263f267c7de401a5ab5d851f173652d47402b036bf6be1786df8a`.
- Entorno reutilizado: macOS 27.0.1 arm64, Python 3.12.14; `cadquery-ocp-novtk` y `cadquery-ocp-proxy` **8.0.1.1.0**. No se instaló otra dependencia.
- Cálculo en copia limpia: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/scara-cad-piloto-20261014/venv/bin/python tools/calcular_propiedades_cad.py --output /private/tmp/scara-rondaA-20261017-01/sesion8/recalculo39`. Terminó con código 0; salida completa en `calculo.log`.
- Contraste nuevo: `verificar_sesion8.py`, ejecutado con ese Python, desde la copia de proyecto, con `--new /private/tmp/scara-rondaA-20261017-01/sesion8/recalculo39/propiedades_geometricas.json`. Terminó con código 0; resultados en `contraste.json` y `contraste.log`.

El script acepta `--root`, `--new` y `--output` para repetir la comprobación contra una **copia de la misma base**, conservando el registro candidato. El CSV contiguo al JSON debe tener el mismo nombre base. El baseline incluido fija toda la versión; cambios documentales posteriores de la integración requieren usar la copia base preservada para repetir ese control completo.

## Contraste de 38 a 39

Las fuentes SHA-256, estados, advertencias y etiquetas materiales de los 50 tipos coinciden con el informe del **17/10/2026 18:49:01 UTC**. Las propiedades de sus 49 tipos calculados y 51 sólidos coinciden exactamente. Las 38 ocurrencias anteriores mantienen fuente, grupo, colocación, disposición y propiedades. No se retiró ninguna.

La única alta es **`2GT_80Teet_40Bore-registro-R`**, en `wrist`, proveniente de `Modelos3D/2GT_80Teet_40Bore.SLDPRT` y su STEP ya existente. Su incorporación visual estaba aceptada y registrada desde el ensamble R; este trabajo solo completa la cobertura del informe. Hay una ocurrencia en JSON, una fila `instance` en CSV y una inclusión en la suma de muñeca.

| Magnitud de muñeca | Informe 38 | Informe 39 |
| --- | ---: | ---: |
| Instancias calculadas/seleccionadas | 6/6 | 7/7 |
| Suma aditiva, cm³ | 197,036449908 | 206,203101556 |
| Centroide en cuerpo, mm | (0,013789950; −0,009364398; 145,970814589) | (0,013176925; −0,008948109; 139,415010916) |

El delta de volumen es **9,166651648 cm³**, igual al volumen de la única polea añadida. El JSON conserva los tensores centrales completos. Su diferencia no representa por sí sola el tensor de la polea: cambia el centroide de referencia y corresponde aplicar ejes paralelos. Base (10/10), brazo (9/9), antebrazo (11/11) y herramienta (2/2) conservan exactamente volumen, centroide y tensor.

## Comprobación independiente afectada

Se releyeron los STEP de las seis y siete instancias de muñeca, se transformó cada BREP mediante `gp_Trsf`, se formaron compuestos de copias y se integraron directamente con `BRepGProp.VolumeProperties(OnlyClosed=True, SkipShared=True, UseTriangulation=False)`. Este camino no importa ni llama `combine`, `placed` ni `read_part` del productor.

Se reutilizaron las tolerancias ya documentadas en `validation/cad_properties.json`: error relativo de volumen ≤10⁻⁹, distancia de centroides ≤10⁻¹⁰ m y error máximo de tensor normalizado por su máximo elemento ≤10⁻⁹. Para metadatos/colocaciones, absoluto/relativo 10⁻¹² como documenta el método del precálculo.

| Compuesto de muñeca | Error relativo de volumen | Distancia de centroides, m | Error relativo máximo de tensor |
| --- | ---: | ---: | ---: |
| Seis instancias históricas | 2,22×10⁻¹⁶ | 2,73×10⁻¹⁸ | 2,40×10⁻¹⁵ |
| Siete instancias actuales | 2,22×10⁻¹⁶ | 1,67×10⁻¹⁶ | 4,37×10⁻¹⁵ |

Todos los controles pasaron. No se repitió la suite de software ni Webots: no cambió código ni contenido entregado por el ZIP. La comprobación BREP afectada es nueva y no se presenta como revisión independiente de otro agente; esa revisión corresponde a sesión 9 antes de integrar.

## Límites y entrega

Son integrales del CAD convertido y sumas **aditivas**, sin unión booleana ni auditoría de solapamientos. Comparten kernel y STEP con el productor; no certifican equivalencia con SolidWorks, masa real, material, distribución interna comercial o relleno impreso. Los campos de masa/densidad siguen sin asignar. No prueban montaje completo, QA física ni materiales efectivos; la física activa sigue provisional.

El candidato propone `cad/propiedades/propiedades_geometricas_39.{json,csv}` y la evidencia en `validation/sesion8/`. El director mantiene la única escritura del proyecto común y solo integrará después de la revisión separada. `recomendacion_documental.md` propone ajustes mínimos para el documento dueño y Validación; no se editó documentación común. La copia aislada y la corrida cruda se conservan para la revisión de sesión 9.
