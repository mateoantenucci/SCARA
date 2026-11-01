# Alcance, decisiones y pendientes del SCARA

Este documento conserva los acuerdos del proyecto. La [guía de comprensión](PROCESO_Y_ARCHIVOS.md) explica cómo funciona; el [README](../README.md) explica cómo ejecutarlo; la [campaña de validación](../validation/campana/INFORME.md) identifica qué versión se ensayó.

## Requisitos y procedencia

La [consigna, revisión 13/10/2026](../CONSIGNA-TP-FINAL.pdf), páginas 1–2, exige un modelo físico Webots `.wbt`, controlador en C++, Java o Python, aplicación visual externa y mensajes de texto por TCP/IP. El rol cliente/servidor depende de la aplicación. La página 6 identifica al SCARA como no construido, sin protocolo ni programa externo desarrollados, y no completa objetivos específicos ni fecha de entrega.

El [documento maestro, versión 02/05/2026](../00-SCARA-Master.pdf), aporta mecánica, cadena R-R-R-P, transmisiones nominales y sensores previstos. Tiene datos incompletos y discrepancias con planos y piezas. En la clase del 27/10/2026 el profesor pidió teach & play y fijó que los SolidWorks son la fuente de verdad; el protocolo lo define el grupo (`scara/1`). El [maestro v2](maestro/SCARA-Master-v2.md) reemplaza al v1 donde difieren.

El objetivo acordado es simular el diseño para docencia y una posible construcción futura, con geometría, cinemática, propiedades físicas con procedencia, comunicación y fallas reproducibles. No existe hardware disponible para calibrarlo experimentalmente. Esta decisión y sus consecuencias están en [ADR 0001](adr/0001-simulacion-del-diseno-sin-hardware.md).

## Arquitectura vigente

| Tema | Decisión | Fuente |
| --- | --- | --- |
| Partes | URC en la PC (Python) y UCI con un único firmware C++, el mismo en el Arduino UNO y en el controlador de Webots | D3, D6, [ADR 0002](adr/0002-firmware-compartido-robot-real-y-simulacion.md) |
| Protocolo | `scara/1`: texto por línea, enteros en unidades articulares, la URC escucha y la UCI se conecta | D1, D4, D5, [ADR 0003](adr/0003-protocolo-en-unidades-articulares.md) |
| Reparto | La URC planifica (inversa, rectas, perfil, colisiones) y manda segmentos con duración; el firmware los ejecuta | D6, [ADR 0005](adr/0005-la-urc-planifica-el-firmware-ejecuta.md) |
| Simulación | Canal de instrumentación aparte (`scara-sim/1`) para posición física, fallas y carga | D2, [ADR 0004](adr/0004-canal-de-instrumentacion-separado.md) |
| Motores | Pasos y transmisión con acople M1/M2 (N1); par limitado y pérdida de pasos (N2) | D8, D44, D64, [ADR 0006](adr/0006-modelo-de-motores-pasos-y-perdida-de-pasos.md) |
| Referencia | Homing con un Hall por eje (J4, J1, J2, J3) desde la pose de reposo; sin referencia, solo jog lento | D11, D21, D30, D56, D58, D72 |
| Operación | Jog desde la URC, gestor de trayectorias, tramos PTP y LIN, reproducción con loop, pausa y stop | D12–D14, D28–D34, D62–D63, D68–D69, D75, [ADR 0007](adr/0007-jog-desde-la-urc.md) |
| Fallas | F1 pérdida de pasos, F2 driver sin corriente, F3 Hall trabado, F4 enlace cortado, F5 reinicio de la UCI | D23 |
| Validación | Campaña en Webots con versión ensayada identificada; lo del banco `scara-dev/1` no se cita como prueba | D25, D73 |

El detalle de cada parte está en el [maestro v2](maestro/SCARA-Master-v2.md) y cada porqué, en el [registro de decisiones](REGISTRO_DE_DECISIONES.md).

## Qué está resuelto y qué falta

| Área | Disponible | Pendiente |
| --- | --- | --- |
| Mecánica | Originales conservados, conversiones, colocaciones y ejes con procedencia | Discrepancias entre maestro, planos y CAD ([revisión del 27/10/2026](historico/REVISION_PARA_EL_PROFESOR_2026-10-27.md)) |
| Electrónica | Firmware que compila para el UNO; camino serie probado con puerto virtual y socat | Prueba con la placa real (D49) |
| Propuestas | P1 microstepping 1/8 (D9) y P2 ubicación de los Hall (D10, D11) | Revisión del profesor |
| Motores | Modelo N2 con la familia de motor más cercana y supuestos declarados | Hojas de datos exactas; N3 no se simula |
| Validación | Campaña en Windows 11 con Webots R2025a | macOS (D19) |
| Fallas | F1–F5 ensayadas | F6 (correa) no se implementó |

## Criterios de cierre

Una entrega defendible necesita que:

1. Las piezas y cuerpos incorporados tengan procedencia, unidades y colocaciones justificadas.
2. Los parámetros distingan valores confirmados, calculados y provisionales.
3. El intercambio de comandos, estados, rechazo, finalización y recuperación cumpla el protocolo acordado.
4. Cada escenario exigido tenga condición inicial, resultado esperado, tolerancia y ejecución registrada.
5. Los informes identifiquen las fuentes y el ejecutable ensayados, sin atribuir aprobaciones anteriores a cambios posteriores.
6. Otro integrante pueda abrir una copia completa y reproducir la demostración.

Las consultas que dependen del profesor están en la sección 1 del [maestro v2](maestro/SCARA-Master-v2.md#1-propuestas-para-revisar-en-clase). Registrar cada respuesta con su fuente y fecha, y qué decisión confirma.
