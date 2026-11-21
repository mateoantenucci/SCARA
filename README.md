# SCARA · gemelo digital con teach & play en Webots

Trabajo final de **Gemelos digitales** (Seminario I, Ingeniería en Informática, UNSTA, 2026).
**Equipo Alan Turing:** Albarracin Ignacio · Antenucci Mateo · Grosso Luciano · Villalobo Evaristo.

> **Para revisar el trabajo, empezá por el informe, [`INFORME-SCARA.pdf`](INFORME-SCARA.pdf).** Se entrega junto con este zip; en el repositorio está en la raíz. Sigue las secciones de la consigna, y el aporte central es la sección 3: el protocolo `scara/1`. Este README sirve para ejecutar el sistema y ubicarse en el código.

## Qué es

Es una simulación en Webots del brazo SCARA diseñado por la cátedra (cuatro ejes: J1, J2 y J3 giran, J4 sube y baja), manejada desde un programa externo. Con el programa externo se mueve el robot con el teclado (jog), se capturan puntos y se arman trayectorias que después se reproducen con tramos rectos (LIN) o de menor recorrido (PTP). Antes de operar, el robot busca su referencia con sensores Hall (homing). Además, se pueden inyectar fallas para ver cómo responde.

```text
 Navegador ──HTTP 8766──▶ URC (Python, urc/) ──TCP 9000, scara/1──▶ UCI: firmware C++ (firmware/)
                                    │                                  dentro del controlador de Webots
                                    └──TCP 9001, scara-sim/1──────▶ banco de ensayo (solo simulación)
```

- **URC** (`urc/`): el programa externo. Sirve la página web, resuelve la cinemática, planifica los tramos, valida límites y choques, y guarda y reproduce las trayectorias.
- **UCI** (`firmware/`): el firmware del robot. Es un único código C++ que corre dentro del controlador de Webots y compila sin cambios para el Arduino UNO del robot real (decisión D3).
- **`scara/1`**: el protocolo de texto entre las dos partes. Solo lleva lo que un Arduino real podría saber. Lo que existe solo en la simulación (posición física real, fallas, carga) va por un canal aparte, `scara-sim/1` (D2).

El SCARA no está construido, así que no hay un robot real con el que comparar: se simula el *diseño*, y cada parámetro declara de dónde sale (D0).

## Requisitos

- **Webots R2025a.** Es la versión con la que se validó, en macOS y en Windows 11.
- **Python 3**, solo con la biblioteca estándar: no hay que instalar paquetes.
- **Un compilador de C++** para el controlador. En Windows alcanza con el que trae Webots. En macOS, con las Command Line Tools (`xcode-select --install`).
- Un navegador.

No hacen falta SolidWorks ni herramientas de CAD: Webots usa las mallas ya convertidas de `cad/derivados/`.

## Ejecutarlo

Todos los comandos se corren desde la carpeta raíz del proyecto. En Windows, usá `python` en lugar de `python3`.

**1. Compilar el controlador** (una sola vez):

- macOS:

  ```sh
  WEBOTS_HOME=/Applications/Webots.app make -C webots/controllers/scara_uci
  ```

- Windows (PowerShell, con el `g++` y el `make` que trae Webots):

  ```powershell
  & "C:\Program Files\Webots\msys64\usr\bin\bash.exe" -lc "export PATH=/mingw64/bin:/mingw64/bin/cpp:/usr/bin WEBOTS_HOME='C:/Program Files/Webots'; make -C webots/controllers/scara_uci"
  ```

- Desde Webots, en cualquier sistema: abrí el mundo, hacé clic derecho sobre el robot → *Edit Controller*, apretá **Build** (F7) y después **Reload World**.

**2. Levantar la URC** y dejar esa terminal abierta:

```sh
python3 -m urc.app
```

**3. Abrir la página** en <http://127.0.0.1:8766>.

**4. Abrir el robot en Webots:** *File → Open World* → `webots/worlds/scara_uci.wbt`, en modo **Real-time** (a 1× o menos). La consola de Webots muestra `UCI: conectada a la URC`. No importa si abrís primero Webots o la URC.

## Recorrido de demostración (5 minutos)

1. **Habilitar motores** y después **Homing…**. El robot busca un sensor Hall por eje y vuelve a la pose de reposo.
2. **Jog:** con la página enfocada, mantené **A/D** (J1), **W/S** (J2), **Q/E** (J3) o **R/F** (J4). Para mover el extremo en X, Y, Z, cambiá el jog a modo cartesiano: las teclas son las mismas.
3. **Reproducir una demostración:** en el panel de trayectorias, cargá `demo-pick-and-place` (o `demo-cuadrado-lin`, que hace rectas) y apretá **▶ Desde el principio**. Antes de mover, la URC valida la trayectoria entera. **Esc** o **Stop** frenan con rampa.
4. **Grabar una propia:** llevá el robot con el jog, capturá cada punto con **Espacio** y guardala con **Guardar como…**.
5. **Fallas:** el panel **Banco de ensayo (solo simulación)** inyecta pérdida de pasos, Hall trabado, corte del enlace, reinicio de la placa, carga y obstáculos.

La guía completa de la página está en [UCI en Webots](docs/UCI_WEBOTS.md#usarlo).

## Si algo no anda

| Síntoma | Causa y solución |
| --- | --- |
| El robot frena solo con `ERR 4 watchdog` | Webots está corriendo acelerado (modo Fast o más de 1×). Usá **Real-time**. |
| La página dice que la UCI no está conectada | El controlador no está compilado, o la URC no está corriendo. Compilá (paso 1) y recargá el mundo. |
| No aparece el banco de ensayo | El controlador es una versión vieja: compilalo de nuevo y recargá el mundo. |
| `Address already in use` al levantar la URC | Ya hay una URC abierta en los puertos 8766, 9000 o 9001. Cerrala. |

## Pruebas automáticas

```sh
python3 -m unittest discover -v
```

Prueban el firmware, la URC, la cinemática, el planificador y las 24 conversaciones de conformidad que definen `scara/1`. Corren en menos de dos minutos y no necesitan Webots ni Internet. Las que dependen de algo que no está instalado (`arduino-cli`, el entorno de CAD o los originales de SolidWorks, que no van en el zip) se omiten y avisan.

La evidencia de los ensayos dentro de Webots (homing, teach & play, fallas F1–F5 y pruebas físicas C1–C4) está en la [campaña de validación](validation/campana/INFORME.md).

## Qué hay en cada carpeta

| Carpeta | Contenido |
| --- | --- |
| `urc/` | Programa externo: servidor, página web, planificador y gestor de trayectorias. |
| `scara/` | Cinemática, dinámica y colisiones en Python, que usa la URC. |
| `firmware/` | Firmware C++ de la UCI: versión para Arduino UNO, pruebas y conversaciones de conformidad del protocolo. |
| `webots/` | Mundos, proto del robot y controlador `scara_uci`, con la planta simulada de motores y sensores. |
| `trayectorias/` | Las tres trayectorias de demostración. |
| `config/` | Parámetros del robot: geometría, límites, motores y transmisión. |
| `cad/` | Piezas del CAD convertidas: STEP, STL para Webots, ensambles y propiedades. |
| `tools/` | Scripts que convierten y auditan el CAD, generan el mundo y exportan el informe. |
| `tests/` | Pruebas automáticas. |
| `validation/` | Evidencia de los ensayos en Webots y de las auditorías del CAD. |
| `docs/` | Documentación técnica (ver abajo). |
| `fotografias/` | Renders y fotos de referencia. |

En el [repositorio](https://github.com/mateoantenucci/SCARA) están además los originales de la cátedra (`Modelos3D/`, consigna y maestro v1) y la fuente del informe (`docs/informe/`). El zip de la entrega no los incluye.

## Documentación técnica

| Tema | Documento |
| --- | --- |
| Protocolo | [`scara/1`](docs/PROTOCOLO_SCARA_1.md) y el canal de instrumentación [`scara-sim/1`](docs/PROTOCOLO_SCARA_SIM_1.md) |
| Webots y Arduino | [UCI en Webots](docs/UCI_WEBOTS.md) y [UCI en el Arduino UNO](docs/ARDUINO_UNO.md) |
| Motores y transmisión | [Transmisión](docs/TRANSMISION.md) |
| Del CAD a Webots | [Conversión e integración](docs/DEL_CAD_A_WEBOTS.md), [propiedades](docs/PROPIEDADES.md) y [montaje y colisiones](docs/MONTAJE_Y_COLISIONES.md) |
| Por qué se decidió cada cosa | [Registro de decisiones](docs/REGISTRO_DE_DECISIONES.md): el código cita estas decisiones como D0, D1, … |
| Vocabulario | [Glosario](docs/GLOSARIO.md) |

## Alcance

- El firmware compila para el Arduino UNO y su enlace serie se probó con un puerto virtual y socat, pero no con la placa real (D49).
- Los parámetros de motores, masas y límites son provisionales: salen del CAD, del maestro v1 o del catálogo de la familia de motor más cercana.
- El microstepping 1/8 (D9) y la ubicación de los sensores Hall (D10) son propuestas del grupo para revisar con el profesor.
- Lo que quedó pendiente y lo que se podría mejorar está en la sección 6 del informe.
