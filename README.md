# SCARA · simulación en Webots

Simulación del diseño SCARA entregado por la cátedra, para estudiar movimiento, comunicación y fallas. **Todavía no existe un robot físico con el que comparar el modelo.** Usamos sus archivos CAD y planos como referencia.

El robot tiene cuatro articulaciones y se controla desde el navegador. Reutiliza geometrías CAD y colocaciones recuperadas de los archivos de la cátedra. El montaje es parcial, las propiedades físicas siguen siendo provisionales y los originales permanecen intactos. La [validación](docs/VALIDACION_WEBOTS.md) identifica la última revisión ensayada y sus resultados.

**Camino nuevo, en construcción:** la URC con el protocolo `scara/1` y el firmware C++ compartido entre Arduino y Webots ya mueven J1 por jog. Cómo compilarlo y usarlo: [UCI en Webots](docs/UCI_WEBOTS.md). Lo que sigue describe el banco provisional `scara-dev/1`, que funciona igual que antes.

Para entender el proyecto desde cero, leé la [guía desde cero](docs/PROCESO_Y_ARCHIVOS.md): explica qué recibimos, qué desarrollamos, cómo funciona una orden y qué archivo resuelve cada parte. Este README es el manual de ejecución; no hace falta leer primero los informes técnicos.

## Qué podés abrir

| Mundo | Uso |
| --- | --- |
| [scara.wbt](webots/worlds/scara.wbt) | Robot móvil, control desde el navegador, carga de ensayo y fallas. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista fija de colocaciones CAD recuperadas. No tiene motores ni física. |

J1 mueve el brazo, J2 el antebrazo, J3 gira la muñeca y J4 desplaza el conjunto vertical. La interfaz usa **milímetros y grados**. Aumentar J4 baja el extremo; aumentar la coordenada Z lo sube.

## Requisitos

- **Python 3.9 o posterior**, Webots y un navegador. Para usar esta versión no hace falta instalar paquetes de Python, OCP, SolidWorks ni herramientas CAD.
- Webots está disponible para [Windows, macOS y Linux](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/installation-procedure.md). Consultá los [requisitos de la versión elegida](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/system-requirements.md).
- Los ensayos guardados usan **Webots R2025b nightly en macOS 27**, por un problema de arranque con R2025a. La [validación](docs/VALIDACION_WEBOTS.md) identifica el ejecutable ensayado. Al compartir el proyecto, registrar la compilación que se usa y comprobarla en cada equipo.
- La ejecución completa en Windows y Linux sigue pendiente de validación. Conviene que el grupo use la misma compilación de Webots y anote cuál es.

## Copia para ejecutar

El [paquete SCARA-ejecucion.zip](validation/sesion5/SCARA-ejecucion.zip) incluye el banco, las mallas y un `LEEME.txt` con el arranque. Extraé completa su carpeta `SCARA`; se puede usar una ruta con espacios. No incluye fuentes CAD originales, tests ni herramientas de regeneración: para editar o recalcular se conserva el proyecto fuente completo. La [validación por entorno](docs/VALIDACION_WEBOTS.md) identifica lo efectivamente probado.

### Repositorio y colaboración

El [repositorio privado](https://github.com/mateoantenucci/SCARA) conserva código, originales CAD, derivados, documentación y evidencia. Para acceder, cada integrante debe aceptar la invitación con su cuenta de GitHub. Con Git instalado y acceso a la cuenta, descargar el proyecto completo con:

```sh
git clone https://github.com/mateoantenucci/SCARA.git
cd SCARA
```

Trabajar en una rama propia y proponer los cambios mediante un pull request. Antes de editar, actualizar `main` con `git pull --ff-only` y crear la rama con `git switch -c nombre-del-cambio`. No subir credenciales, entornos de Python ni archivos de sesión; los originales y los informes históricos se conservan. No convertir los saltos de línea de archivos existentes: sus bytes identifican la evidencia mediante SHA-256.

La [versión de demo del 17/10/2026](https://github.com/mateoantenucci/SCARA/releases/tag/demo-2026-10-17) ofrece el ZIP de ejecución probado, sin necesidad de instalar Git. Requiere acceso al repositorio privado. La demo comprobada en Mac puede presentarse desde ese equipo; probar Windows aporta evidencia adicional de compatibilidad, no es un requisito para mostrarla desde Mac.

## Primera ejecución, paso a paso

1. Conservá la carpeta completa de SCARA. Copiar solo el mundo no alcanza.
2. Abrí una terminal en esa carpeta, donde están las carpetas `client`, `scara` y `webots`.
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

### Mostrar la pérdida de esfuerzo al profesor

«Aplicar falla» reduce el esfuerzo **y avisa al controlador**, que cancela la trayectoria y bloquea nuevos movimientos. Por eso no permite mover después de inyectar ni continúa una trayectoria cada vez más atrasada. La física sigue activa: una consigna detenida no impide que un eje sin fuerza caiga. El porcentaje es **esfuerzo disponible**, no velocidad ni porcentaje de pérdida.

1. Pulsá **Reiniciar ensayo**, esperá la reconexión y **Habilitar movimiento**. Conservá la pose inicial y carga **0 kg**; no hace falta enviar un destino.
2. Elegí **J4 · desplazamiento vertical**, **Pérdida de fuerza del motor** y **0 %** de esfuerzo disponible. Pulsá **Aplicar falla**.
3. Mostrá «Falla activa» y la fila J4: **Estimado queda en 60 mm** y **Simulador avanza hacia 120 mm**. J4 positivo baja la herramienta; la separación es de unos **60 mm** al llegar al tope. La referencia queda invalidada, aunque la estimación conserve su último valor.
4. Para repetir o recuperar movimiento, **Reiniciar ensayo** y habilitar de nuevo. Limpiar fallas no devuelve fuerza ni referencia.

Como comparación, repetí desde un reinicio limpio con J4 al **50 %** y carga **0 kg**. El control también se detiene, pero el eje puede sostenerse: conserva **4 N** frente a unos **1,47 N** de peso del cuerpo móvil provisional. Reducir esfuerzo no exige que haya un desvío. En J1–J3, tras cancelar la trayectoria, el desplazamiento por inercia puede ser muy pequeño.

La [repetición aislada del 26/10/2026](validation/perdida_esfuerzo_20261026.json) comprobó esos dos casos, la caída con carga de 0,25 kg y J4 al 25 %, y la cancelación durante un movimiento de J1. Para estudiar retraso o pérdida de pasos mientras el control sigue enviando consignas haría falta un ensayo de inyección sin aviso, separado del comportamiento actual. El banco todavía usa una estimación ideal de consignas; no modela pasos individuales ni detección autónoma de esa pérdida.

## Qué se revisa y qué falta

Se han probado geometría, colocaciones, movimiento, comunicación y fallas. Consultá la [validación](docs/VALIDACION_WEBOTS.md) para conocer la revisión, evidencia y límites de cada ejecución; una prueba anterior no valida automáticamente una versión nueva.

Antes de mover se comprueba el recorrido nominal contra pedestal y piso, y la herramienta y carga frente a la base fija. Son controles con formas simplificadas; **la comprobación continua general de autocolisiones sigue pendiente**. No se buscan caminos alternativos ni se cubren piezas omitidas u obstáculos nuevos.

También faltan:

- Confirmar revisión mecánica, ceros, sentidos, topes, herramienta y sensores.
- Sustituir masas, inercias y esfuerzos provisionales por datos de materiales, impresión, componentes comerciales y transmisiones.
- Definir homing, otras fallas docentes y recuperación de referencia.
- Adaptar la comunicación al profesor: **`scara-dev/1` es un protocolo provisional de desarrollo**.
- Completar la ejecución y validación en Windows y Linux.

Las [consultas para el profesor](docs/DATOS_PARA_EL_PROFESOR.md) reúnen esas preguntas. Los ensayos del simulador no certifican prestaciones del diseño físico.

## Pruebas y lectura adicional

Para comprobar el software, desde la raíz del **proyecto fuente completo**; el ZIP de ejecución no incluye tests:

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

Para cambiar el modelo se editan sus fuentes, se regeneran las salidas y se repiten las comprobaciones correspondientes. Las etapas anteriores se conservan en `validation/historico/` como evidencia, fuera de la ruta de lectura. El [mapa de documentos](docs/PROCESO_Y_ARCHIVOS.md#9-mapa-de-archivos-para-explorar) orienta la exploración.
