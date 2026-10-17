# SCARA · simulación del diseño en Webots

**Punto 3 completado, 16/10:** se recuperaron `B-CarretelInf`, `B-CarretelSup` y `Z-SoporteEfector` ajustando el refinamiento de curvas del conversor. Hay **47 STL aceptados, 49 tipos con propiedades geométricas y 30/30 instancias representadas**. Aprobaron 30 pruebas Python, 15 comprobaciones de recuperación, la auditoría de 22 sólidos móviles y las regresiones nativas de CAD y colisiones. La configuración física se conservó. Ver [diagnóstico, evidencia y exportación de contraste](docs/RECUPERACION_GEOMETRIAS.md). El montaje mecánico completo y las autocolisiones internas siguen pendientes.

Proyecto de Robótica para construir una simulación reutilizable del SCARA entregado por la cátedra. **No existe un robot físico con el que calibrar el modelo.** La referencia actual son sus archivos CAD, planos y documento maestro.

Hoy el robot de Webots incorpora **CAD articulado parcial: 30 instancias de piezas, todas con geometría**. Tiene cuatro articulaciones, una interfaz web externa y comunicación TCP/IP. Se comprobaron colocación, movimiento y fallas dentro del simulador. Las masas, inercias, colisiones, esfuerzos y algunas convenciones siguen siendo provisionales; los ensayos no certifican prestaciones físicas del diseño.

**Si empezás desde cero, leé [Proceso y archivos](docs/PROCESO_Y_ARCHIVOS.md)**: explica qué hicimos, para qué sirve cada archivo, cuáles se editan y cómo usar este trabajo como base del informe final.

**Avance del 15/10/2026:** se calcularon volumen, centroide y tensor por densidad de **46 tipos de pieza (48 sólidos)** y de **27/30 instancias**. La [guía de propiedades CAD](docs/PROPIEDADES_GEOMETRICAS_CAD.md) explica el método, las tablas, cómo reproducirlo y qué datos faltan para reemplazar la física provisional. El precálculo todavía no se aplica al robot.

**Punto 2:** se reprodujeron invasiones del pedestal, se cambiaron las cinco cajas globales por **30 cajas de pieza** y se agregó rechazo previo de recorridos contra pedestal/piso, con margen de 1 mm. La [guía de colisiones y recorridos](docs/COLISIONES_Y_RECORRIDOS.md) explica los casos, la comprobación continua y sus límites. La sesión que estaba abierta no fue recargada; reiniciar el cliente y recargar el mundo para usar esta revisión.

**Actualización 16/10:** se diagnosticó el sostén de J4 en el tope exacto. Al reducir el paso físico de **16 a 2 ms**, la amplitud observada bajó de **10,997 a 0,174 mm**, conservando carrera, masas y esfuerzo. Aprobaron 15 casos medidos en cada paso físico, además de las regresiones anteriores. El [diagnóstico de J4](docs/DIAGNOSTICO_TOPE_J4.md) conserva el fallo, los experimentos, el costo de ejecución y los límites del resultado.

| Mundo | Para qué sirve |
| --- | --- |
| [scara.wbt](webots/worlds/scara.wbt) | Robot con CAD articulado parcial, física provisional, interfaz, movimiento y fallas. |
| [scara_cad_inspeccion.wbt](webots/worlds/scara_cad_inspeccion.wbt) | Vista estática de colocaciones CAD recuperadas: 20 instancias con geometría. No tiene motores ni física. Conserva la pose guardada, con la torre arriba; no es el cero del robot. |

La [recuperación del ensamble](docs/ENSAMBLE_CAD.md) explica los colores, las revisiones distintas y los datos verificados. [Captura CAD](validation/scara_cad_inspeccion.png) · [captura del CAD articulado](validation/scara_cad_articulado.png).

## Qué hace cada parte

```text
Navegador → programa externo Python → TCP local → controlador Webots → robot simulado
         ← estado y respuestas      ←           ← instrumentación del simulador
```

La interfaz recibe un destino X,Y,Z. El programa externo calcula las posiciones necesarias de las articulaciones —cinemática inversa— y las manda al controlador. Webots aplica las consignas con límites de esfuerzo y calcula la respuesta física del modelo.

| Eje | Movimiento | Unidad interna |
| --- | --- | --- |
| J1 | Giro del brazo | radianes |
| J2 | Giro del antebrazo | radianes |
| J3 | Giro de la muñeca | radianes |
| J4 | Desplazamiento vertical, positivo hacia abajo | metros |

La interfaz muestra **milímetros y grados**. El programa convierte esos valores una vez a metros y radianes. El eje Z de las coordenadas apunta hacia arriba; por eso aumentar J4 baja el extremo.

## Requisitos

- **Python 3.9 o posterior**, un navegador y Webots. Cliente, cálculos y controlador usan solo la biblioteca estándar de Python: no hace falta ejecutar `pip install` para probar esta versión.
- Webots tiene [instaladores para Windows, macOS y Linux](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/installation-procedure.md). El proyecto se abrió en un Mac Apple Silicon; la ejecución completa en Windows y Linux todavía debe comprobarse. Consultar los [requisitos oficiales de la versión elegida](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/system-requirements.md).
- El entorno de uso confirmado por el usuario el 15/10/2026 es **Webots R2025b nightly sobre macOS 27**, porque R2025a le daba problemas. La compilación exacta actual no se inspeccionó en el precálculo CAD. Los ensayos previos usaron una copia oficial nightly del 13/10/2026 que contiene la [corrección](https://github.com/cyberbotics/webots/pull/7032) del [error de arranque](https://github.com/cyberbotics/webots/issues/6976). Su instalación temporal y build histórica están en el [checkpoint](docs/CHECKPOINT_CONTINUAR.md#webots-en-este-mac); esas rutas pueden caducar.
- SolidWorks, Onshape, Blender y las herramientas de conversión **no son necesarios para ejecutar** el banco actual. Reconstruir las exportaciones CAD es un trabajo separado, con dependencias explicadas en la [evaluación CAD](docs/EVALUACION_CONVERSION_CAD.md).

Los archivos `.wbt` y `.proto` llevan encabezado R2025a. Conviene que todo el grupo use la misma compilación de Webots para comparar ensayos; registrar cuál se utilizó.

## Primera ejecución, paso a paso

1. Conservar la carpeta completa del proyecto. El archivo `.wbt` depende del `.proto`, del controlador y de los parámetros: copiar solo el mundo no alcanza.
2. Abrir una terminal dentro de la carpeta `SCARA`, donde están este README y las carpetas `client`, `scara` y `webots`.
3. Comprobar Python y ejecutar la interfaz:

   **macOS o Linux**

   ```sh
   python3 --version
   python3 -m client.app
   ```

   **Windows**, desde PowerShell o CMD, si el intérprete instalado se llama `python`:

   ```powershell
   python --version
   python -m client.app
   ```

   Mantener esa terminal abierta. Debe anunciar `http://127.0.0.1:8765`.
4. Abrir [la interfaz local](http://127.0.0.1:8765) en el navegador. Al principio puede mostrar «Sin conexión TCP»: todavía falta iniciar el mundo.
5. En Webots, abrir [webots/worlds/scara.wbt](webots/worlds/scara.wbt) mediante **File → Open World**. Usar la copia corregida si se presenta el problema de macOS descrito arriba.
6. Ejecutar la simulación con el botón de reproducción. En la consola de Webots debe aparecer `banco provisional scara-dev/1 en TCP 127.0.0.1:9000`. El programa Python del controlador se inicia desde Webots; no hay que abrirlo con un segundo comando de terminal.
7. Esperar «TCP conectado» y datos de estado en la interfaz. Pulsar **Habilitar movimiento**: una conexión nueva por sí sola no habilita ni repite movimientos.

Si Webots informa que no encuentra Python, seleccionar el intérprete que funciona en la terminal en **Preferences → General → Python command**, según la [configuración oficial de Python](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/using-python.md). No instalar con `pip` un paquete llamado `controller`: ese módulo lo proporciona Webots a sus controladores.

Los puertos 8765 y 9000 son locales a esa computadora. Ejecutar una sola instancia del cliente y una del mundo. Para cerrar, usar **Detener movimiento**, cerrar Webots y finalizar la terminal del cliente con `Ctrl+C`.

## Primera prueba de movimiento

Con una recarga limpia, la configuración inicial estimada es J1=0°, J2=90°, J3=−90°, J4=60 mm. El extremo estimado está en **X=250, Y=250, Z≈34,67 mm**, con orientación 0°. Es la referencia del banco actual, no una posición calibrada del robot físico.

1. Habilitar y dejar la carga en 0 kg.
2. Introducir **X=240, Y=250, Z=35 mm**, velocidad 30 % y orientación vacía. Enviar el destino.
3. Observar las columnas y las respuestas. La orientación vacía conserva el rumbo estimado del extremo cuando existe una solución dentro de los límites; no significa fijar únicamente J3.
4. Esperar «Secuencia de consignas terminada». Comparar la pose estimada con la del simulador: ese mensaje **no confirma llegada física**.
5. Probar un destino fuera de alcance, por ejemplo X=1000 mm. Debe rechazarse sin comenzar una trayectoria hacia ese destino.

El movimiento es suave en las articulaciones, pero **no garantiza una línea recta del extremo**. Si ya hay un movimiento aceptado, el banco rechaza otro destino hasta terminar o detenerlo. No incluye pinza ni agarre de objetos.

Además de alcance y límites articulares, se comprueba **todo el recorrido nominal** de las envolventes de piezas contra pedestal y piso configurados, con margen de 1 mm. Una orden conflictiva se rechaza antes de cambiar consignas; también se reserva el cubo de carga de ensayo cuando corresponde. No hay búsqueda de caminos alternativos ni comprobación de autocolisiones (`selfCollision FALSE`), piezas omitidas u obstáculos nuevos. La garantía geométrica se limita a esas envolventes y a la referencia ideal; no asegura seguimiento físico bajo fallas.

### Cómo leer las columnas

| Dato | Qué representa |
| --- | --- |
| Ordenado | La consigna articular que el programa está aplicando. |
| Estimado | La referencia ideal que conoce el control en esta primera versión; aún no modela conteo de pasos ni microstepping. |
| Simulador | La posición física obtenida con instrumentación interna de Webots. El diseño documentado **no tiene encoders**; esta columna sirve para evaluar ensayos. |
| Hall | Una señal lógica nominal o la lectura fija inyectada; las regiones de activación todavía son provisionales. |

Los valores visibles no sustituyen mediciones reales. El feedback de esfuerzo de J1 no está disponible con esta base fija y se publica como `null`; los restantes feedbacks son aproximaciones del actuador, no sensores de carga externa.

Los campos TCP `tcp_world_yaw`, `tcp_world` y `tool_physics` permiten comprobar orientación, posición y propiedades efectivas del cuerpo en ensayos. Son instrumentación interna y no entradas de sensores físicos.

## Fallas y recuperación

Inyectar una sola falla por ensayo y comenzar cada comparación desde una recarga limpia. La falla es conocida por el banco; no se está demostrando que un controlador sin sensores adecuados pueda detectarla por sí solo.

| Ensayo | Cómo probarlo | Cómo continuar |
| --- | --- | --- |
| Corte de conexión | Durante un movimiento, pulsar **Desconectar**. El servidor cancela las consignas cuando reconoce el cierre. | Pulsar **Reconectar**, revisar el estado y **Habilitar movimiento**. Emitir un destino nuevo; no se reanuda el anterior. |
| Hall atascado | Elegir eje, **Sensor Hall atascado**, lectura activa o inactiva y **Aplicar falla**. | **Limpiar fallas** y luego **Habilitar movimiento**. El homing físico todavía no existe. |
| Pérdida de esfuerzo | Elegir eje y porcentaje disponible. 0 % deja ese motor sin fuerza; J4 es el eje apropiado para estudiar una posible caída por gravedad. | La referencia se marca inválida. **Limpiar fallas no devuelve fuerza ni referencia**. Usar **Reiniciar ensayo** y después habilitar. |
| Carga de ensayo | Con el movimiento detenido, establecer 0–2 kg. Repetir condiciones equivalentes con distinta carga. Si el peso conjunto del soporte y carga supera los 8 N provisionales de J4, se aplica la masa, se notifica sobrecarga y se invalida la referencia. El esfuerzo disponible sigue siendo 8 N. | **Reiniciar ensayo** vuelve a la condición inicial sin carga. Tras perder referencia se rechaza cambiar la masa: retirarla con una consigna antigua podría provocar un ascenso. La masa añadida tiene un modelo de inercia explícito, pero provisional. |

**Detener movimiento** cancela la secuencia y mantiene una consigna fija; no es un freno mecánico ni desactiva la física. Un motor sin fuerza puede seguir moviéndose por gravedad. **Reiniciar ensayo** recarga el mundo y restaura su estado inicial; no representa una búsqueda física de referencia ni una reparación real. La conexión se recupera automáticamente, sin repetir órdenes, y hace falta habilitar otra vez.

El aviso de sobrecarga usa una masa de ensayo conocida y el límite estático declarado; no un encoder ni un sensor de peso existente. En el banco actual la masa móvil inicial es 0,15 kg y el límite vertical 8 N; por encima de aproximadamente 0,665 kg de carga añadida ya se supera ese sostén estático. Esto no representa la capacidad de carga certificada del SCARA diseñado, ni un detector dinámico general.

Retirar un brazo, romper una unión y trabar físicamente una articulación son escenarios distintos que **todavía no están implementados**. No se fingen ocultando piezas. El [catálogo de fallas](docs/FALLAS_Y_VALIDACION.md) define lo que habría que construir y verificar.

## Qué está comprobado y qué falta

Pasaron **30 pruebas Python**: 16 del banco, cinco de propiedades geométricas y nueve de colisiones. Con el Python CAD/OCP se ejecutan las 30; el Python del banco ejecuta 27 y omite tres de kernel. La [evidencia vigente](validation/cad_recovery.json) registra resultados y hashes; `collision_tests.json` conserva la revisión anterior. El [análisis CAD de colisiones vigente](validation/collisions_recovery.json) contrasta once poses y un recorrido con extremos libres e invasión intermedia.

Se probó además el recorrido completo desde el navegador hasta Webots: habilitar, mover a (240, 250, 35) mm, regresar cerca de la pose inicial y reiniciar a STOPPED. La vuelta del ensayo CAD fue a (250, 250, 34,67) mm. La [evidencia de interfaz contra el simulador](validation/client_native.json) conserva respuestas y posición nativa; el aviso superior actualiza el resultado de la orden.

El ensayo nativo en Webots **R2025b nightly del 13/10/2026**, ejecutado en macOS 27.0.1 Apple Silicon, aprobó nueve comprobaciones. El [informe reproducible](validation/simulation.json) guarda parámetros, hashes, órdenes, estados y tolerancias; la [explicación de validación](docs/VALIDACION_WEBOTS.md) detalla su alcance.

- Movimiento nominal y conservación del rumbo: error final del punto de herramienta de aproximadamente **0,0248 mm dentro del simulador** y error máximo de rumbo de 6,68×10⁻⁷ rad. Es coherencia de este banco, no precisión del robot que pudiera construirse.
- Masa, centro de masa e inercia efectivos leídos y contrastados. Con 0,4 kg móviles, la fuerza de sostén fue aproximadamente 3,924 N.
- Caída de J4 de aproximadamente 60 mm al quitar esfuerzo; con 1 kg de carga añadida también cedió aproximadamente 60 mm, manteniendo el límite de 8 N.
- Rechazo previo, Hall atascado, rearme explícito, desconexión sin repetición y reinicio del ensayo comprobados.

Además, la [comprobación nativa del montaje CAD](validation/cad_motion.json) verificó 30 colocaciones en once estados (**330 comparaciones**), seis llegadas articulares, reconstrucción de la pose guardada y movimiento independiente de cada eje. Los cuerpos anteriores al eje que se mueve permanecieron en su sitio.

Estos resultados usan instrumentación interna, CAD visual parcial, colisiones de cajas e inercias de cajas equivalentes con masas provisionales. No validan anticolisión, todo el espacio de trabajo, transmisiones, hardware ni materiales reales. Las tolerancias del ensayo son criterios del banco, no prestaciones del diseño.

Las conversiones CAD dieron **50 STEP, 47 STL aceptados y tres piezas rechazadas explícitamente**; 21 de las aceptadas tienen advertencias. De esas piezas se seleccionaron las instancias con colocación y cuerpo móvil sustentados para integrarlas al robot dinámico; no se incorporaron ciegamente las 50. Se recuperaron del XML guardado las colocaciones de **106 instancias en los 10 ensambles**, con su [informe de procedencia](cad/ensambles/informe.json). Ese caché no resuelve restricciones ni reconstruye el CAD actual; el manifiesto de integración conserva qué colocación corresponde a cada cuerpo y qué decisiones siguen siendo provisionales. La aceptación topológica no prueba equivalencia exacta con SolidWorks. Los originales permanecen intactos. Ver [resultados CAD y pendientes](docs/EVALUACION_CONVERSION_CAD.md).

La torre tiene una recuperación adicional [por sus tres cuerpos](cad/derivados/torre_por_cuerpos/README.md), usada en ambas vistas: se eliminaron únicamente ocho triángulos de área exactamente cero y se verificó cada malla individual. El lote actual es 47 + 3 y conserva el informe anterior en su historial; la recuperación de la torre no certifica la unión global de sus cuerpos.

Antes de llamar al resultado «gemelo fiel» faltan, entre otras cosas:

- Confirmar una revisión coherente del ensamble, revisar autocolisiones internas y resolver las piezas restantes y la transmisión. Las 30 instancias actuales ya siguen cuerpos articulados; la asignación de seis carreteles es una hipótesis visual reversible.
- Confirmar ceros, sentidos, topes, punto de herramienta y offsets verticales. Hay cotas contradictorias entre maestro y planos.
- Sustituir las masas e inercias de cajas equivalentes por propiedades sustentadas en geometría y materiales. El [precálculo geométrico](docs/PROPIEDADES_GEOMETRICAS_CAD.md) ya está disponible; faltan materiales, impresión, propiedades comerciales, geometría excluida y componentes omitidos.
- Confirmar transmisiones, acoplamientos y esfuerzo disponible. Los valores actuales de velocidad, aceleración y fuerza/torque son de demostración, no prestaciones verificadas.
- Definir la ubicación y lógica Hall, homing y recuperación de referencia.
- Integrar el protocolo TCP del profesor y sus criterios docentes. **`scara-dev/1` es un contrato provisional de desarrollo**, no el protocolo de la cátedra.

La evidencia anterior del banco de cajas y sus fuentes se conserva en [validation/historico/banco_cajas/](validation/historico/banco_cajas/). Los reportes de la raíz corresponden ahora al CAD articulado.

Los informes `simulation.json`, `cad_motion.json`, `client_native.json` y `cad_properties.json` conservan su revisión anterior a las colisiones nuevas. Sus fuentes modificadas y resultados quedaron además en [el snapshot previo al punto 2](validation/historico/antes_colisiones_20261015/). La evidencia de colisiones del 15/10 usa sufijo `collisions` y `collisions_native.json`; la del ajuste temporal de J4 del 16/10 usa [simulation_j4.json](validation/simulation_j4.json), [cad_motion_j4.json](validation/cad_motion_j4.json) y [collisions_native_j4.json](validation/collisions_native_j4.json). El [resumen del ajuste J4](validation/j4_diagnosis.json) verifica las fuentes de aquella revisión. La [recuperación posterior de geometrías](validation/cad_recovery.json) identifica los derivados actuales y sus nuevas comprobaciones; no repite los ensayos de esfuerzo que mantienen configuración idéntica. La oscilación grande del tope quedó corregida dentro del criterio declarado; subsiste un residuo numérico de hasta 0,174 mm en los casos medidos.

Sobre la revisión final de colisiones aprobaron los [cinco casos nuevos](validation/collisions_native.json), los [nueve escenarios de dinámica/fallas](validation/simulation_collisions.json) y las [330 comparaciones de colocación CAD](validation/cad_motion_collisions.json), en una copia aislada de Webots R2025b nightly, sin mover la sesión de trabajo del usuario.

Las [consultas para el profesor](docs/DATOS_PARA_EL_PROFESOR.md) reúnen los datos ausentes o contradictorios; son un borrador, no se enviaron.

## Pruebas y cambios de parámetros

Desde la raíz, con Webots cerrado, ejecutar:

```sh
python3 -m unittest discover -v
```

En Windows sustituir `python3` por `python` si corresponde. Los tests TCP usan conexiones de loopback y puertos efímeros; no necesitan Internet, Webots ni hardware.

Para repetir los ensayos integrados, abrir **el mundo dinámico `webots/worlds/scara.wbt` y dejarlo en reproducción**. Puede usarse modo Fast para reducir la espera: el paso físico actual es **2 ms** de tiempo simulado, declarado en `config/scara.json`. Cerrar el programa `client.app` con `Ctrl+C`: el ensayo necesita ser el único cliente TCP. No ejecutarlo contra una vista CAD estática ni un dispositivo real. Para conservar una sesión de trabajo, usar una [copia aislada de ensayo](docs/DIAGNOSTICO_TOPE_J4.md#6-cómo-repetir-sin-afectar-la-sesión-de-trabajo).

```sh
python3 tools/check_simulation.py --webots-version "R2025b nightly_13_10_2026" --output validation/simulation-local.json
python3 tools/check_cad_motion.py --webots-version "R2025b nightly_13_10_2026" --output validation/cad-motion-local.json
```

Sustituir la versión por la compilación que realmente esté ejecutándose. Estos comandos mueven el robot y **recargan el mundo entre escenarios**; el ensayo de simulación también inyecta fallas. No conservan una sesión de trabajo. Al completar satisfactoriamente deja el ensayo inicial en `STOPPED`, sin habilitar movimiento. El informe local permite comparar resultados sin sobrescribir la evidencia guardada. Después se puede volver a iniciar `client.app` y habilitar explícitamente.

La fuente de parámetros es [config/scara.json](config/scara.json), que incluye unidades y procedencia. La agrupación y las convenciones CAD están en [config/cad_integration.json](config/cad_integration.json). Para reconstruir la integración a partir de ellas y regenerar el mundo/PROTO, con Webots cerrado:

```sh
python3 tools/integrate_cad.py --update-config
python3 tools/generate_world.py
```

El primer comando recalcula geometría y cajas desde el CAD, conservando masas, esfuerzos y límites declarados. Si solo se cambian esos parámetros físicos, basta ejecutar el segundo comando. Los cambios requieren repetir las comprobaciones pertinentes.

Esto sobrescribe los archivos generados. Cambiar también esos archivos a mano produciría dos versiones de los mismos parámetros; editar el generador o la configuración y regenerar. Reiniciar el cliente para que cargue la nueva configuración.

## Dónde seguir leyendo

| Archivo o carpeta | Contenido |
| --- | --- |
| [docs/PROCESO_Y_ARCHIVOS.md](docs/PROCESO_Y_ARCHIVOS.md) | Explicación desde cero, mapa de archivos y base para el informe. |
| [docs/PROPIEDADES_GEOMETRICAS_CAD.md](docs/PROPIEDADES_GEOMETRICAS_CAD.md) | Cálculo de 49 tipos/51 sólidos, tablas explorables, unidades, transformaciones y datos físicos pendientes. |
| [docs/COLISIONES_Y_RECORRIDOS.md](docs/COLISIONES_Y_RECORRIDOS.md) | Invasiones de pedestal, nuevas envolventes, rechazo del recorrido completo y evidencia de verificación. |
| [docs/DIAGNOSTICO_TOPE_J4.md](docs/DIAGNOSTICO_TOPE_J4.md) | Fallo de sostén en 120 mm, experimentos, paso de 2 ms y regresión en cada paso físico. |
| [docs/INTEGRACION_CAD_CRITERIOS.md](docs/INTEGRACION_CAD_CRITERIOS.md) | Evidencia geométrica y decisiones de agrupación. |
| [docs/PLAN_GEMELO_DIGITAL.md](docs/PLAN_GEMELO_DIGITAL.md) | Decisiones aceptadas, hitos y criterios. |
| [GLOSSARY.md](GLOSSARY.md) | Vocabulario desde cero. |
| [docs/FALLAS_Y_VALIDACION.md](docs/FALLAS_Y_VALIDACION.md) | Qué modifica cada falla y cómo evaluarla. |
| `Modelos3D/`, PDF originales | Archivos del profesor, conservados como referencia. |
| `cad/derivados/` | STEP, STL, informes y vistas de conversiones. |
| `cad/propiedades/` | JSON trazable y CSV de propiedades geométricas; generados, sin materiales asignados. |
| `scara/` | Cinemática, transformaciones entre cuerpos, dinámica equivalente, estados y transporte. |
| `webots/` | Mundo, PROTO y controlador del banco. |
| `client/` | Interfaz web local y su conexión TCP. |
