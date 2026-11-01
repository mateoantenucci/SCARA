# SCARA · simulación en Webots

Simulación del diseño SCARA entregado por la cátedra, para estudiar movimiento, comunicación y fallas. **Todavía no existe un robot físico con el que comparar el modelo.** Usamos sus archivos CAD y planos como referencia.

El robot tiene cuatro articulaciones y se controla desde el navegador. Reutiliza geometrías CAD y colocaciones recuperadas de los archivos de la cátedra. El montaje es parcial, las propiedades físicas siguen siendo provisionales y los originales permanecen intactos. La [validación](docs/VALIDACION_WEBOTS.md) identifica la última revisión ensayada y sus resultados.

El sistema es la URC (`urc/`, Python, en la PC) que habla el protocolo `scara/1` con un único firmware C++ (`firmware/`), compartido entre el Arduino UNO y el controlador `scara_uci` de Webots. Cómo compilarlo y usarlo: [UCI en Webots](docs/UCI_WEBOTS.md). Para el robot real, el mismo firmware compila para el Arduino UNO y se conecta a la URC con socat: [UCI en el Arduino UNO](docs/ARDUINO_UNO.md).

Para entender el proyecto desde cero, leé la [guía desde cero](docs/PROCESO_Y_ARCHIVOS.md). Este README es el manual de ejecución.

## Qué podés abrir

| Mundo | Uso |
| --- | --- |
| [scara_uci.wbt](webots/worlds/scara_uci.wbt) | Robot móvil con el controlador `scara_uci`, manejado desde la página de la URC. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista fija de colocaciones CAD recuperadas. No tiene motores ni física. |

J1 mueve el brazo, J2 el antebrazo, J3 gira la muñeca y J4 desplaza el conjunto vertical. La interfaz usa **milímetros y grados**. Aumentar J4 baja el extremo; aumentar la coordenada Z lo sube.

## Requisitos

- **Python 3.9 o posterior**, Webots y un navegador. Para usar esta versión no hace falta instalar paquetes de Python, OCP, SolidWorks ni herramientas CAD.
- Webots está disponible para [Windows, macOS y Linux](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/installation-procedure.md). Consultá los [requisitos de la versión elegida](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/system-requirements.md).
- Los ensayos guardados usan **Webots R2025b nightly en macOS 27**, por un problema de arranque con R2025a. La [validación](docs/VALIDACION_WEBOTS.md) identifica el ejecutable ensayado. Al compartir el proyecto, registrar la compilación que se usa y comprobarla en cada equipo.
- La ejecución completa en Windows y Linux sigue pendiente de validación. Conviene que el grupo use la misma compilación de Webots y anote cuál es.

## Copia del proyecto

### Repositorio y colaboración

El [repositorio privado](https://github.com/mateoantenucci/SCARA) conserva código, originales CAD, derivados, documentación y evidencia. Para acceder, cada integrante debe aceptar la invitación con su cuenta de GitHub. Con Git instalado y acceso a la cuenta, descargar el proyecto completo con:

```sh
git clone https://github.com/mateoantenucci/SCARA.git
cd SCARA
```

Trabajar en una rama propia y proponer los cambios mediante un pull request. Antes de editar, actualizar `main` con `git pull --ff-only` y crear la rama con `git switch -c nombre-del-cambio`. No subir credenciales, entornos de Python ni archivos de sesión; los originales y los informes históricos se conservan. No convertir los saltos de línea de archivos existentes: sus bytes identifican la evidencia mediante SHA-256.

## Primera ejecución, paso a paso

1. Compilá el controlador `scara_uci` una vez (y de nuevo cada vez que cambie el firmware): [Compilar el controlador](docs/UCI_WEBOTS.md#compilar-el-controlador).
2. Desde la raíz del proyecto, levantá la URC: `python3 -m urc.app` (Windows: `python -m urc.app`). Dejá esa terminal abierta.
3. Abrí [la página de la URC](http://127.0.0.1:8766) en el navegador.
4. En Webots, elegí **File → Open World**, abrí [webots/worlds/scara_uci.wbt](webots/worlds/scara_uci.wbt) y pulsá reproducción. El controlador se conecta a la URC por TCP 9000.
5. Seguí [Usarlo](docs/UCI_WEBOTS.md#usarlo): habilitar motores, homing, jog, trayectorias, fallas y carga por el canal de instrumentación.

## Qué se revisa y qué falta

Se han probado geometría, colocaciones, movimiento, comunicación y fallas. Consultá la [validación](docs/VALIDACION_WEBOTS.md) para conocer la revisión, evidencia y límites de cada ejecución; una prueba anterior no valida automáticamente una versión nueva.

Antes de mover se comprueba el recorrido nominal contra pedestal y piso, y la herramienta y carga frente a la base fija. Son controles con formas simplificadas; **la comprobación continua general de autocolisiones sigue pendiente**. No se buscan caminos alternativos ni se cubren piezas omitidas u obstáculos nuevos.

También faltan:

- Confirmar revisión mecánica, ceros, sentidos, topes, herramienta y sensores.
- Sustituir masas, inercias y esfuerzos provisionales por datos de materiales, impresión, componentes comerciales y transmisiones.
- Completar la ejecución y validación en Windows y Linux.

Las [consultas para el profesor](docs/historico/DATOS_PARA_EL_PROFESOR.md) reúnen esas preguntas. Los ensayos del simulador no certifican prestaciones del diseño físico.

## Pruebas y lectura adicional

Para comprobar el software, desde la raíz del proyecto:

```sh
python3 -m unittest discover -v
```

En Windows usá `python` en lugar de `python3`. No requiere Webots ni Internet. Las pruebas de geometría que necesitan el entorno CAD se omiten cuando ese entorno no está instalado.

| Tema | Guía |
| --- | --- |
| Entender el proyecto y sus carpetas | [Proceso y archivos](docs/PROCESO_Y_ARCHIVOS.md) |
| Montaje e interferencias internas | [Montaje y autocolisiones](docs/MONTAJE_Y_AUTOCOLISIONES.md) |
| Colisiones con el entorno | [Colisiones y recorridos](docs/COLISIONES_Y_RECORRIDOS.md) |
| Geometrías recuperadas | [Recuperación de geometrías](docs/RECUPERACION_GEOMETRIAS.md) |
| Colocaciones y agrupación de piezas | [Ensamble CAD](docs/ENSAMBLE_CAD.md) y [criterios de integración](docs/INTEGRACION_CAD_CRITERIOS.md) |
| Propiedades calculadas y datos físicos faltantes | [Propiedades geométricas CAD](docs/PROPIEDADES_GEOMETRICAS_CAD.md) |
| Ensayos en Webots y eje vertical | [Validación](docs/VALIDACION_WEBOTS.md) y [diagnóstico de J4](docs/historico/DIAGNOSTICO_TOPE_J4.md) |
| Acuerdos y próximos pasos | [Plan](docs/PLAN_GEMELO_DIGITAL.md) y [glosario](GLOSSARY.md) |

Para cambiar el modelo se editan sus fuentes, se regeneran las salidas y se repiten las comprobaciones correspondientes. Las etapas anteriores se conservan en `validation/historico/` como evidencia, fuera de la ruta de lectura. El [mapa de documentos](docs/PROCESO_Y_ARCHIVOS.md#9-mapa-de-archivos-para-explorar) orienta la exploración.
