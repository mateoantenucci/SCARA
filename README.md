# SCARA · teach & play simulado en Webots

Simulación del diseño SCARA entregado por la cátedra: se mueve el robot con jog, se graban puntos, se arman trayectorias con nombre y se reproducen con tramos PTP y LIN, con homing por sensores Hall y fallas F1–F5. **No existe un robot físico con el que comparar el modelo** ([ADR 0001](docs/adr/0001-simulacion-del-diseno-sin-hardware.md)): los parámetros son provisionales y declaran su procedencia.

El sistema tiene dos partes que hablan el protocolo de texto [`scara/1`](docs/PROTOCOLO_SCARA_1.md) por TCP:

- **URC** (`urc/`, Python, en la PC): la página web, la cinemática, el planificador de tramos y jog, el gestor de trayectorias y la reproducción.
- **UCI**: un único firmware C++ (`firmware/`) que corre en el controlador `scara_uci` de Webots y compila para el Arduino UNO, conectado a la URC por USB y socat ([ADR 0002](docs/adr/0002-firmware-compartido-robot-real-y-simulacion.md)).

Lo que solo existe en la simulación (posición física, fallas, carga) va por un canal de instrumentación aparte ([ADR 0004](docs/adr/0004-canal-de-instrumentacion-separado.md)).

Para entender el proyecto desde cero, leé el [documento maestro v2](docs/maestro/SCARA-Master-v2.md) y la [guía de archivos](docs/PROCESO_Y_ARCHIVOS.md). Este README es el manual de ejecución.

## Qué podés abrir

| Mundo | Uso |
| --- | --- |
| [scara_uci.wbt](webots/worlds/scara_uci.wbt) | Robot con el controlador `scara_uci`, manejado desde la página de la URC. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista fija de colocaciones CAD recuperadas. No tiene motores ni física. |

J1 mueve el brazo, J2 el antebrazo, J3 gira la muñeca y J4 desplaza el conjunto vertical. La interfaz usa **milímetros y grados**. Aumentar J4 baja el extremo; aumentar la coordenada Z lo sube.

## Requisitos

- Python 3, Webots y un navegador. Para usarlo no hace falta OCP, SolidWorks ni herramientas CAD.
- Para compilar el controlador alcanza con el `g++` que trae Webots: [compilar el controlador](docs/UCI_WEBOTS.md#compilar-el-controlador).
- La campaña de validación se corrió en **Windows 11 con Webots R2025a** (D73). macOS queda pendiente (D19).

## Copia del proyecto

El [repositorio privado](https://github.com/mateoantenucci/SCARA) conserva código, originales CAD, derivados, documentación y evidencia. Para acceder, cada integrante acepta la invitación con su cuenta de GitHub:

```sh
git clone https://github.com/mateoantenucci/SCARA.git
cd SCARA
```

Trabajar en una rama propia y proponer los cambios con un pull request. No subir credenciales, entornos de Python ni archivos de sesión. No convertir los saltos de línea de archivos existentes: sus bytes identifican la evidencia mediante SHA-256.

## Primera ejecución, paso a paso

1. Compilá el controlador `scara_uci` una vez, y de nuevo cada vez que cambie el firmware: [compilar el controlador](docs/UCI_WEBOTS.md#compilar-el-controlador).
2. Desde la raíz del proyecto, levantá la URC: `python3 -m urc.app` (Windows: `python -m urc.app`). Dejá esa terminal abierta.
3. Abrí [la página de la URC](http://127.0.0.1:8766) en el navegador.
4. En Webots, elegí **File → Open World**, abrí [webots/worlds/scara_uci.wbt](webots/worlds/scara_uci.wbt) y pulsá reproducción. El controlador se conecta a la URC por TCP 9000.
5. Seguí [Usarlo](docs/UCI_WEBOTS.md#usarlo): habilitar motores, homing, jog, trayectorias, fallas y carga por el banco de ensayo.

Las tres trayectorias de demostración están en `trayectorias/`, la carpeta por defecto de la URC. Para el robot real, el mismo firmware compila para el UNO: [UCI en el Arduino UNO](docs/ARDUINO_UNO.md).

## Qué se validó y qué falta

La [campaña de validación](validation/campana/INFORME.md) ensaya en Webots el homing (H1, H2), teach & play (T1–T3) y las fallas F1–F5, con la versión ensayada identificada por commit y SHA-256. El resumen está en la [sección 10 del maestro](docs/maestro/SCARA-Master-v2.md#10-validación). Una prueba anterior no valida automáticamente una versión nueva.

Faltan, entre otras cosas (maestro, secciones 9 y 10):

- Probar el firmware con la placa real; solo se probó el camino serie con un puerto virtual y socat (D49).
- Validar en macOS (D19).
- Sustituir parámetros provisionales por datos de materiales, componentes y motores con hoja de datos.
- Las propuestas P1 (microstepping) y P2 (sensores Hall) esperan la revisión del profesor.

## Pruebas y lectura adicional

Para comprobar el software, desde la raíz del proyecto:

```sh
python3 -m unittest discover -v
```

En Windows usá `python` en lugar de `python3`. No requiere Webots ni Internet. La compilación para el UNO necesita `arduino-cli` (variable `ARDUINO_CLI`); las pruebas de propiedades CAD, el entorno con OCP. Si falta alguno, esas pruebas se omiten. `python tools/verificar_enlaces.py` comprueba que no haya enlaces internos rotos.

| Tema | Guía |
| --- | --- |
| Diseño, decisiones y validación | [Maestro v2](docs/maestro/SCARA-Master-v2.md), [registro de decisiones](docs/REGISTRO_DE_DECISIONES.md) y [ADR](docs/adr/) |
| Archivos del proyecto | [Proceso y archivos](docs/PROCESO_Y_ARCHIVOS.md) |
| Protocolo | [`scara/1`](docs/PROTOCOLO_SCARA_1.md) |
| Webots y Arduino | [UCI en Webots](docs/UCI_WEBOTS.md) y [UCI en el Arduino UNO](docs/ARDUINO_UNO.md) |
| Transmisión y motores | [Transmisión](docs/TRANSMISION.md) |
| Colisiones | [Colisiones y recorridos](docs/COLISIONES_Y_RECORRIDOS.md) y [montaje](docs/MONTAJE_Y_AUTOCOLISIONES.md) |
| Alcance y pendientes | [Plan](docs/PLAN_GEMELO_DIGITAL.md) y [glosario](GLOSSARY.md) |

La documentación y la evidencia del banco provisional `scara-dev/1`, que este sistema reemplazó, están en [`docs/historico/`](docs/historico/README.md) y [`validation/historico/`](validation/historico/README.md).
