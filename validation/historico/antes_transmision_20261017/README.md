# SCARA · simulación en Webots

Simulación del diseño SCARA entregado por la cátedra, para estudiar movimiento, comunicación y fallas. **Todavía no existe un robot físico con el que comparar el modelo.** Usamos sus archivos CAD y planos como referencia.

El montaje actual reúne **36 piezas colocadas**, incluidos seis rodamientos representados de forma simplificada en base, brazo y muñeca. Tiene cuatro articulaciones y se controla desde el navegador. El montaje es parcial y las propiedades físicas siguen siendo provisionales. Los archivos originales permanecen intactos.

Para entender el proyecto desde cero, leé la [guía breve de proceso y archivos](docs/PROCESO_Y_ARCHIVOS.md). El detalle de esta revisión está en [Montaje y autocolisiones](docs/MONTAJE_Y_AUTOCOLISIONES.md).

## Qué podés abrir

| Mundo | Uso |
| --- | --- |
| [scara.wbt](webots/worlds/scara.wbt) | Robot móvil, control desde el navegador, carga de ensayo y fallas. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista fija de colocaciones CAD recuperadas. No tiene motores ni física. |

J1 mueve el brazo, J2 el antebrazo, J3 gira la muñeca y J4 desplaza el conjunto vertical. La interfaz usa **milímetros y grados**. Aumentar J4 baja el extremo; aumentar la coordenada Z lo sube.

## Requisitos

- **Python 3.9 o posterior**, Webots y un navegador. Para usar esta versión no hace falta instalar paquetes de Python, OCP, SolidWorks ni herramientas CAD.
- Webots está disponible para [Windows, macOS y Linux](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/installation-procedure.md). Consultá los [requisitos de la versión elegida](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/system-requirements.md).
- En este Mac con macOS 27 se usa **Webots R2025b nightly**, porque R2025a presentaba un problema de arranque. El [detalle de compatibilidad](docs/CHECKPOINT_CONTINUAR.md#webots-en-este-mac) conserva la referencia utilizada; las rutas temporales pueden caducar.
- La ejecución completa en Windows y Linux sigue pendiente de validación. Conviene que el grupo use la misma compilación de Webots y anote cuál es.

## Primera ejecución, paso a paso

1. Conservá la carpeta completa de SCARA. Copiar solo el mundo no alcanza.
2. Abrí una terminal en esa carpeta, donde están este README y las carpetas `client`, `scara` y `webots`.
3. Comprobá Python e iniciá la interfaz con los comandos de tu sistema:

   **macOS o Linux**

   ```sh
   python3 --version
   python3 -m client.app
   ```

   **Windows**, desde PowerShell o CMD:

   ```powershell
   python --version
   python -m client.app
   ```

   Dejá esa terminal abierta. Debe anunciar `http://127.0.0.1:8765`.
4. Abrí [la interfaz local](http://127.0.0.1:8765) en el navegador. Al principio puede mostrar «Sin conexión TCP».
5. En Webots, elegí **File → Open World** y abrí [webots/worlds/scara.wbt](webots/worlds/scara.wbt).
6. Pulsá el botón de reproducción. Webots inicia el controlador automáticamente. Su consola debe anunciar `banco provisional scara-dev/1 en TCP 127.0.0.1:9000`.
7. Esperá «TCP conectado» en el navegador y pulsá **Habilitar movimiento**. Conectarse por sí solo no habilita ni repite movimientos.

Si Webots no encuentra Python, indicá el intérprete que funciona en tu terminal en **Preferences → General → Python command**. Ver [configuración oficial](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/using-python.md). El módulo `controller` lo aporta Webots: no lo instales con `pip`.

Usá una sola instancia del cliente y una del mundo. Pausar Webots también pausa la atención de órdenes. Para cerrar: **Detener movimiento**, cerrar Webots y finalizar la terminal con `Ctrl+C`.

## Primera prueba de movimiento

Empezá con una recarga limpia. El extremo inicial estimado está cerca de **X=250, Y=250, Z=34,67 mm**. Es la referencia del banco, todavía sin calibración física.

1. Pulsá **Habilitar movimiento** y dejá la carga en **0 kg**.
2. Introducí **X=240, Y=250, Z=35 mm**, velocidad **30 %** y orientación vacía. Enviá el destino.
3. Observá el movimiento y las columnas. La orientación vacía conserva el rumbo estimado del extremo cuando los límites lo permiten.
4. Esperá «Secuencia de consignas terminada» y compará los valores estimados con los del simulador. **Ese mensaje confirma el fin de las consignas, no la llegada física.**
5. Probá un destino fuera de alcance, por ejemplo **X=1000 mm**: debe rechazarse antes de moverse hacia él.

El extremo no tiene por qué seguir una línea recta. Durante un movimiento se rechaza otro destino hasta terminar o detenerlo. No hay pinza ni agarre de objetos.

### Qué significa cada columna

| Columna | Qué muestra |
| --- | --- |
| Ordenado | Posición que el control está pidiendo a cada articulación. |
| Estimado | Posición ideal que conoce el control; todavía no representa pasos perdidos. |
| Simulador | Posición física que Webots calcula, usada para revisar ensayos. El diseño documentado **no tiene encoders**. |
| Hall | Señal lógica de ensayo, con regiones de activación provisionales; puede fijarse mediante una falla. |

Son datos del banco de simulación. La lectura de esfuerzo tampoco equivale a un sensor de peso; en J1 no está disponible.

## Fallas y reinicio

Probá **una falla por vez**, empezando desde una recarga limpia. El banco conoce la falla inyectada; eso no demuestra que un robot real pueda detectarla automáticamente.

| Prueba | Acción y recuperación |
| --- | --- |
| Desconexión | Pulsá **Desconectar**. Cuando el servidor reconoce el cierre, cancela las consignas. **Reconectar**, revisar y **Habilitar movimiento**; el destino anterior no se repite. |
| Hall atascado | Elegí eje y lectura, aplicá la falla. Para seguir: **Limpiar fallas** y **Habilitar movimiento**. |
| Pérdida de esfuerzo | Elegí eje y porcentaje; 0 % lo deja sin fuerza. J4 puede caer por gravedad. **Reiniciar ensayo** y habilitar: limpiar fallas solo no devuelve fuerza ni referencia. |
| Carga de ensayo | Con el robot detenido, elegí 0–2 kg. Puede declararse sobrecarga con los límites provisionales. **Reiniciar ensayo** restaura la condición inicial sin carga. |

**Detener movimiento** mantiene una consigna fija: no es un freno mecánico ni apaga la física. **Reiniciar ensayo** recarga el mundo: no hace homing ni representa una reparación real. Después del reinicio hay que habilitar de nuevo.

Tras perder la referencia, el banco rechaza movimientos y cambios de carga hasta reiniciar. Las condiciones y límites de cada caso están en [Fallas y validación](docs/FALLAS_Y_VALIDACION.md).

## Qué se revisa y qué falta

Se han hecho pruebas de geometría, colocaciones, movimiento, comunicación y fallas. Consultá los **informes actuales** y su alcance en [Montaje y autocolisiones](docs/MONTAJE_Y_AUTOCOLISIONES.md) y [Validación Webots](docs/VALIDACION_WEBOTS.md); una prueba anterior no valida automáticamente una versión nueva.

Antes de mover se comprueba el recorrido nominal contra pedestal y piso, y la herramienta y carga frente a la base fija. Son controles con formas simplificadas; **la comprobación continua general de autocolisiones sigue pendiente**. No se buscan caminos alternativos ni se cubren piezas omitidas u obstáculos nuevos.

También faltan:

- Confirmar revisión mecánica, ceros, sentidos, topes, herramienta y sensores.
- Sustituir masas, inercias y esfuerzos provisionales por datos de materiales, impresión, componentes comerciales y transmisiones.
- Definir homing, otras fallas docentes y recuperación de referencia.
- Adaptar la comunicación al profesor: **`scara-dev/1` es un protocolo provisional de desarrollo**.
- Completar la ejecución y validación en Windows y Linux.

Las [consultas para el profesor](docs/DATOS_PARA_EL_PROFESOR.md) reúnen esas preguntas. Los ensayos del simulador no certifican prestaciones del diseño físico.

## Pruebas y lectura adicional

Para comprobar el software, desde la carpeta SCARA:

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
| Ensayos en Webots y eje vertical | [Validación](docs/VALIDACION_WEBOTS.md) y [diagnóstico de J4](docs/DIAGNOSTICO_TOPE_J4.md) |
| Acuerdos y próximos pasos | [Plan](docs/PLAN_GEMELO_DIGITAL.md) y [glosario](GLOSSARY.md) |

La [versión anterior del README](validation/historico/antes_montaje_20261016/README.md) conserva el detalle histórico. Para cambiar el modelo se editan sus fuentes, se regeneran las salidas y se repiten las comprobaciones correspondientes.
