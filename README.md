# SCARA · teach & play simulado en Webots

> **Para revisar el trabajo, empezá por el informe, [`INFORME-SCARA.pdf`](INFORME-SCARA.pdf)**, que se entrega junto con este zip (en el repositorio está en la raíz). Sigue las secciones que pide la consigna: equipo a simular, programa externo, protocolo, interconexión, pila tecnológica y observaciones finales. Este README explica cómo ejecutarlo; lo demás de `docs/` es referencia técnica para quien quiera el detalle.

Simulación del diseño SCARA entregado por la cátedra: se mueve el robot con jog, se graban puntos, se arman trayectorias con nombre y se reproducen con tramos PTP y LIN, con homing por sensores Hall y fallas F1–F5. **No existe un robot físico con el que comparar el modelo** (D0): los parámetros son provisionales y declaran su procedencia.

El sistema tiene dos partes que hablan el protocolo de texto [`scara/1`](docs/PROTOCOLO_SCARA_1.md) por TCP:

- **URC** (`urc/`, Python, en la PC): la página web, la cinemática, el planificador de tramos y jog, el gestor de trayectorias y la reproducción.
- **UCI**: un único firmware C++ (`firmware/`) que corre en el controlador `scara_uci` de Webots y compila para el Arduino UNO, conectado a la URC por USB y socat (D3).

Lo que solo existe en la simulación (posición física, fallas, carga) va por un canal de instrumentación aparte (D2).

## Qué hay en cada carpeta

| Carpeta | Contenido |
| --- | --- |
| `urc/` | Programa externo (URC): servidor, página web, planificador y trayectorias. |
| `scara/` | Cinemática, dinámica y colisiones en Python, que usa la URC. |
| `firmware/` | Firmware C++ de la UCI, compartido por Webots y el Arduino UNO, con sus pruebas de conformidad del protocolo. |
| `webots/` | Mundos, proto del robot y controlador `scara_uci`. |
| `trayectorias/` | Trayectorias de demostración. |
| `config/` | Parámetros del robot (geometría, límites, motores). |
| `Modelos3D/` | Originales SolidWorks de la cátedra. Solo en el repositorio: el zip de la entrega no los incluye, igual que la consigna y el maestro v1. |
| `cad/` | Derivados del CAD: STEP, STL, ensambles y propiedades. |
| `tools/` | Scripts de conversión y auditoría del CAD y de exportación del informe. |
| `tests/` | Pruebas automáticas (`python3 -m unittest discover`). |
| `validation/` | Evidencia de los ensayos en Webots y de las auditorías del CAD. |
| `docs/` | Informe en Markdown y Word (solo en el repositorio), protocolo, guías de Webots y Arduino, transmisión, CAD, registro de decisiones y glosario. |
| `fotografias/` | Renders y fotos de referencia. |

## Qué podés abrir

| Mundo | Uso |
| --- | --- |
| [scara_uci.wbt](webots/worlds/scara_uci.wbt) | Robot con el controlador `scara_uci`, manejado desde la página de la URC. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista fija de colocaciones CAD recuperadas. No tiene motores ni física. |

J1 mueve el brazo, J2 el antebrazo, J3 gira la muñeca y J4 desplaza el conjunto vertical. La interfaz usa **milímetros y grados**. Aumentar J4 baja el extremo; aumentar la coordenada Z lo sube.

## Requisitos

- Python 3, Webots y un navegador. Para usarlo no hace falta OCP, SolidWorks ni herramientas CAD.
- Para compilar el controlador alcanza con el `g++` que trae Webots: [compilar el controlador](docs/UCI_WEBOTS.md#compilar-el-controlador).
- La campaña de validación vigente (con escenarios C1–C4) se corrió en **macOS con Webots R2025a** (D19, D73).

## Copia del proyecto

El [repositorio](https://github.com/mateoantenucci/SCARA) conserva código, originales CAD, derivados, documentación y evidencia:

```sh
git clone https://github.com/mateoantenucci/SCARA.git
cd SCARA
```

No conviertas los saltos de línea de los archivos: sus bytes identifican la evidencia mediante SHA-256.

## Primera ejecución, paso a paso

1. Compilá el controlador `scara_uci` una vez, y de nuevo cada vez que cambie el firmware: [compilar el controlador](docs/UCI_WEBOTS.md#compilar-el-controlador).
2. Desde la raíz del proyecto, levantá la URC: `python3 -m urc.app` (Windows: `python -m urc.app`). Dejá esa terminal abierta.
3. Abrí [la página de la URC](http://127.0.0.1:8766) en el navegador.
4. En Webots, elegí **File → Open World**, abrí [webots/worlds/scara_uci.wbt](webots/worlds/scara_uci.wbt) y ejecutá en **tiempo real** (botón Real-time, con el indicador de velocidad en ~1× o menos). No uses el modo Fast con la URC conectada: el watchdog del firmware y los pings de la URC requieren tiempo real ([UCI en Webots](docs/UCI_WEBOTS.md#cómo-funciona)). El controlador se conecta a la URC por TCP 9000.
5. Seguí [Usarlo](docs/UCI_WEBOTS.md#usarlo): habilitar motores, homing, jog, trayectorias, fallas y carga por el banco de ensayo.

Las tres trayectorias de demostración están en `trayectorias/`, la carpeta por defecto de la URC. Para el robot real, el mismo firmware compila para el UNO: [UCI en el Arduino UNO](docs/ARDUINO_UNO.md).

## Qué se validó y qué falta

La [campaña de validación](validation/campana/INFORME.md) ([mapa de la evidencia](validation/README.md)) ensaya en Webots el homing (H1, H2), teach & play (T1–T3) y las fallas F1–F5, con la versión ensayada identificada por commit y SHA-256. El resumen está en la sección 6 del informe. Una prueba no valida automáticamente una versión distinta.

Quedan fuera del alcance, entre otras cosas (informe, sección 6.2):

- Probar el firmware con la placa real; solo se probó el camino serie con un puerto virtual y socat (D49).
- Sustituir parámetros provisionales por datos de materiales, componentes y motores con hoja de datos.
- El microstepping 1/8 (D9) y la ubicación de los sensores Hall (D10) son propuestas del grupo que quedan para la revisión del profesor (informe, secciones 1.3 y 1.4).

## Pruebas y lectura adicional

Para comprobar el software, desde la raíz del proyecto:

```sh
python3 -m unittest discover -v
```

En Windows usá `python` en lugar de `python3`. No requiere Webots ni Internet. La compilación para el UNO necesita `arduino-cli` (variable `ARDUINO_CLI`); las pruebas de propiedades CAD, el entorno con OCP. Si falta alguno, esas pruebas se omiten. `python tools/verificar_enlaces.py` comprueba que no haya enlaces internos rotos.

| Tema | Guía |
| --- | --- |
| Decisiones de diseño (D0, D1, …) | [Registro de decisiones](docs/REGISTRO_DE_DECISIONES.md) |
| Protocolo | [`scara/1`](docs/PROTOCOLO_SCARA_1.md) y el canal de instrumentación [`scara-sim/1`](docs/PROTOCOLO_SCARA_SIM_1.md) |
| Informe del trabajo final (Gemelos digitales) | [PDF](INFORME-SCARA.pdf), con su fuente en [Markdown](docs/informe/INFORME-SCARA.md) y [Word](docs/informe/SCARA-Informe-Gemelos-Digitales.docx) |
| Webots y Arduino | [UCI en Webots](docs/UCI_WEBOTS.md) y [UCI en el Arduino UNO](docs/ARDUINO_UNO.md) |
| Transmisión y motores | [Transmisión](docs/TRANSMISION.md) |
| Del CAD a Webots | [Conversión, ensambles e integración](docs/DEL_CAD_A_WEBOTS.md), [propiedades](docs/PROPIEDADES.md) y [montaje y colisiones](docs/MONTAJE_Y_COLISIONES.md) |
| Alcance, pendientes y vocabulario | Sección 6 del informe y [glosario](docs/GLOSARIO.md) |
