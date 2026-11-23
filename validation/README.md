# Evidencia de validación

Qué se ensayó, dónde está la evidencia y cómo repetirla. La evidencia vigente del sistema es la [campaña de validación](campana/INFORME.md): identifica la versión ensayada por commit y SHA-256, y su resumen está en la sección 6 del [informe](../docs/informe/INFORME-SCARA.md).

## Campaña en Webots

`python validation/campana/campana.py` corre los diez ensayos en Webots, uno detrás de otro, y deja [`campana.json`](campana/campana.json) y los registros en [`campana/registros/`](campana/registros/). Dura unos 20 minutos. Sin Webots, `python -m unittest discover` comprueba que la campaña registrada aprobó todos los escenarios.

| Ensayo | Escenarios | Qué valida |
| --- | --- | --- |
| [protocolo](protocolo/ensayo_webots.py) | P1, F4 | Protocolo `scara/1` con la UCI de Webots: corriente, paradas, watchdog, reinicio. |
| [transmision](transmision/INFORME.md) | P2 | Transmisión N1: acople M1/M2 y resolución por eje. |
| [segmentos](segmentos/INFORME.md) | P3 | Segmentos temporizados y tramo PTP. |
| [homing](homing/INFORME.md) | H1, H2 | Sensores Hall y homing desde el reposo. |
| [instrumentacion](instrumentacion/INFORME.md) | F2, F3a, F4, F5 | Canal de instrumentación y fallas inyectadas. |
| [perdida_pasos](perdida_pasos/INFORME.md) | F1 | Pérdida de pasos (N2) detectada con `EV LOST`. |
| [reproduccion](reproduccion/INFORME.md) | T2, F5 | Reproducción de trayectorias. |
| [campana](campana/ensayo_webots.py) | H2, T1, T3, F3b, F5 | Teach & play con puntos capturados, demos, Hall trabado inactivo, reinicio en plena reproducción. |
| [fisicas](fisicas/INFORME.md) | C1, C2, C3 | Contacto y perturbación física. |
| [movido_mano](movido_mano/INFORME.md) | C4 | Movimiento a mano sin corriente. |

Cada carpeta tiene su script, su informe y, en algunos casos, el registro de una corrida propia; los registros de la campaña vigente son los de `campana/registros/`.

## Otros ensayos del sistema

- [primer_jog](primer_jog/INFORME.md): primer jog de J1 de punta a punta con `scara/1`.
- [jog](jog/INFORME.md): jog cartesiano y jog verificado contra colisiones.

## Auditorías del CAD

[`cad/`](cad/) guarda los resultados vigentes de las herramientas de `tools/` que auditan el modelo: recuperación de geometrías, propiedades, colisiones, autocolisiones y montajes. Se explican en [Del CAD a Webots](../docs/DEL_CAD_A_WEBOTS.md), [propiedades](../docs/PROPIEDADES.md) y [montaje y colisiones](../docs/MONTAJE_Y_COLISIONES.md). [`cad/sesion8/`](cad/sesion8/INFORME.md) es el precálculo geométrico de las 39 instancias; su `verificar_sesion8.py` compara hashes de archivos que ya no están en el árbol y se reproduce desde el tag `pre-limpieza`.

## Línea base de la muñeca

[`historico/`](historico/README.md) conserva la línea base del diagnóstico de los rodamientos de muñeca.
