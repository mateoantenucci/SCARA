# Alcance, decisiones y pendientes del SCARA

Este documento conserva los acuerdos del proyecto. La [guía de comprensión](PROCESO_Y_ARCHIVOS.md) explica cómo funciona; el [README](../README.md) explica cómo ejecutarlo; la [validación](VALIDACION_WEBOTS.md) identifica qué versiones se ensayaron.

## Requisitos y procedencia

La [consigna, revisión 13/10/2026](../CONSIGNA-TP-FINAL.pdf), páginas 1–2, exige un modelo físico Webots `.wbt`, controlador en C++, Java o Python, aplicación visual externa y mensajes de texto por TCP/IP. El rol cliente/servidor depende de la aplicación. La página 6 identifica al SCARA como no construido, sin protocolo ni programa externo desarrollados, y no completa objetivos específicos ni fecha de entrega.

El [documento maestro, versión 02/05/2026](../00-SCARA-Master.pdf), aporta mecánica, cadena R-R-R-P, transmisiones nominales y sensores previstos. Tiene datos incompletos y discrepancias con planos y piezas. El grupo informó que el profesor preparará el protocolo y solicitó dinámica y fallas; esos detalles no constituyen todavía un contrato técnico entregado.

El objetivo acordado es simular el diseño para docencia y una posible construcción futura, con geometría, cinemática, propiedades físicas con procedencia, comunicación y fallas reproducibles. No existe hardware disponible para calibrarlo experimentalmente. Esta decisión y sus consecuencias están en [ADR 0001](adr/0001-simulacion-del-diseno-sin-hardware.md).

## Decisiones de comportamiento

| Tema | Decisión |
| --- | --- |
| Aplicación externa | Incluir una interfaz web mínima de referencia, sustituible por otra compatible. |
| Movimiento | Punto a punto con objetivo XYZ, velocidad relativa y orientación opcional. Primera demostración sin pinza. |
| Orientación omitida | Conservar el rumbo estimado del soporte respecto del mundo cuando lo permitan los límites. |
| Trayectoria | Interpolación articular suave. No se exige una línea recta cartesiana. |
| Entradas y recorridos inválidos | Rechazar antes de iniciar la nueva trayectoria. No buscar automáticamente un desvío. |
| Falla o desconexión reconocida | Cancelar la trayectoria y solicitar detención con la física activa. Exigir habilitación explícita; no repetir órdenes al reconectar. |
| Referencia perdida | No recuperarla usando en secreto la posición perfecta del simulador. El banco requiere recargar el ensayo; homing físico queda pendiente. |
| Fallas iniciales | Reducción/pérdida de esfuerzo, Hall fijo y cierre de conexión; carga ajustable para estudiar sobrecarga. |
| Protocolo | Usar `scara-dev/1` como banco provisional y adaptar al contrato oficial cuando se reciba. |
| Documentación | Conservar propósito, decisiones, método, evidencia, reproducción y límites; separar la coordinación de sesiones de la documentación técnica. |

Una detención ordenada no garantiza inmovilidad si el actuador carece de esfuerzo para sostener el mecanismo. Limpiar una falla no equivale a recuperar fuerza ni referencia. La sobrecarga actual se avisa a partir de la masa conocida del banco y del esfuerzo provisional, sin atribuirle al robot un sensor de peso.

## Fronteras de la implementación

- **Cálculo e intérprete:** matemática y reglas de estado independientes de Webots. En el banco actual el programa externo resuelve la inversa y envía consignas articulares. El reparto definitivo depende de si el protocolo oficial pide articulaciones o destinos cartesianos.
- **Geometría y física:** separar mallas visuales, formas de contacto y propiedades materiales. El precálculo CAD no asigna por sí solo masas a motores o piezas impresas.
- **Motores y articulaciones:** Webots acciona directamente los cuatro grados de libertad. Relación motor→articulación, acoplamiento M1/M2, pérdidas, electrónica y pasos requieren modelos explícitos si se incluyen en la entrega.
- **Observación y control:** distinguir ordenado, estimado ideal y físico simulado. La instrumentación interna verifica ensayos; no representa encoders del diseño.
- **Comunicación y tiempo:** el transporte no bloquea los pasos de Webots. Trayectorias y física usan tiempo simulado; conexiones y sus plazos usan tiempo de pared. Pausar Webots pausa la atención TCP.

## Qué está resuelto y qué falta

| Área | Disponible | Pendiente para cerrar fidelidad o entrega |
| --- | --- | --- |
| Referencia | Originales conservados, conversiones, colocaciones y ejes con procedencia | Revisión mecánica oficial que resuelva discrepancias. |
| Modelo articulado | Base fija, cuatro ejes y montaje CAD parcial | Componentes omitidos, fijaciones y transmisión completa. |
| Movimiento | Directa/inversa, límites, orientación y perfil suave | Referencias oficiales y criterios docentes de precisión y trayectorias. |
| Comunicación | Cliente web, transporte e intérprete provisionales | Protocolo oficial y ensayos de compatibilidad. |
| Dinámica | Esfuerzos finitos, gravedad y carga; precálculo geométrico | Materiales, impresión, componentes comerciales, masas/inercias y esfuerzos fundamentados. |
| Colisiones | Rechazo nominal frente al entorno y de herramienta/carga frente a base; auditorías seleccionadas | Otros pares internos, contactos más precisos y componentes omitidos. |
| Fallas | Inyecciones básicas y recuperación por recarga | Homing, pasos perdidos, atasco y desprendimiento según alcance que se acuerde. |
| Entrega | Instrucciones, fuentes, pruebas e informes | Copia limpia reproducida por otro integrante, ejecución nativa Windows/Linux y aceptación docente. |

La evidencia de cada resultado está en [Validación Webots](VALIDACION_WEBOTS.md); las cantidades de piezas y pruebas pertenecen a esas ejecuciones y no son criterios de fidelidad por sí mismas.

## Criterios de cierre

Una entrega defendible necesita que:

1. Las piezas y cuerpos incorporados tengan procedencia, unidades y colocaciones justificadas.
2. Los parámetros distingan valores confirmados, calculados y provisionales.
3. El intercambio de comandos, estados, rechazo, finalización y recuperación cumpla el protocolo acordado.
4. Cada escenario exigido tenga condición inicial, resultado esperado, tolerancia y ejecución registrada.
5. Los informes identifiquen las fuentes y el ejecutable ensayados, sin atribuir aprobaciones anteriores a cambios posteriores.
6. Otro integrante pueda abrir una copia completa y reproducir la demostración.

El orden de trabajo es revisar montaje y contactos, fundamentar la física, completar comportamiento/contrato y verificar la entrega. Las dependencias externas están en [Consultas para el profesor](historico/DATOS_PARA_EL_PROFESOR.md). Una duda externa limita la parte que depende de ella; no impide avanzar en las otras.

La reunión puede resolver solo parte de esas consultas. Registrar cada respuesta con su fuente y fecha, qué decisión confirma y qué sigue pendiente; la tabla de consultas identifica el trabajo que destraba cada una. Con esas respuestas, elegir una ronda acotada, comprobar sus dependencias y repetir solo los ensayos afectados. No hace falta esperar todas las respuestas para avanzar en un área ya definida, ni convertir una respuesta incompleta en un supuesto aprobado.
