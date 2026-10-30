# Protocolo `scara/1`

Contrato de mensajes entre la URC y el firmware de la UCI. Reemplaza al banco provisional [`scara-dev/1`](PROTOCOLO_SCARA_DEV_1.md), que sigue funcionando al lado hasta su retiro (issue #17).

**Estado:** subconjunto de la bala trazadora (issue #5). El protocolo completo (`ENABLE`, `HOME`, `SEG`, `STOP`, `HALT`, `OK`, `EV`…) llega con el issue #6 y puede ajustar lo que sigue. Las decisiones están en el [registro](REGISTRO_DE_DECISIONES.md) (D4, D5, D24, D27 y D35–D39).

## Transporte y formato

- La URC escucha en TCP 9000 y la UCI se conecta (D1, D24). Con el robot real, socat puentea el USB del Arduino a ese puerto.
- ASCII, una línea por mensaje terminada en LF; el CR se ignora. Hasta 64 bytes con el LF; una línea más larga se descarta entera y la UCI responde `ERR 3 largo`.
- Campos separados por espacios. Los números son enteros: centésimas de grado para J1–J3 y centésimas de mm para J4 (ADR 0003).
- Se puede hablar a mano (D4): `nc -l 9000` hace de URC frente a Webots, y el monitor serie del IDE de Arduino, frente a la UCI real.

## URC → UCI

| Mensaje | Efecto | Respuesta |
| --- | --- | --- |
| `HELLO` | Saludo. La URC lo envía al aceptar cada conexión. | `HI scara/1 <versión de firmware>` |
| `PING` | Renueva el watchdog. La URC lo envía cada 250 ms. | — |
| `STATUS` | Pide el estado ya. | `S …` |
| `JOG j ± vel` | Jog articular de `j` (1–4) a `vel` centésimas por segundo (1–1000). Reemplaza al jog anterior. | — |
| `JOG STOP` | Frena el jog. | — |
| `ZERO` | Declara que el robot está en la pose de reposo (D30) y deja los cuatro ejes referenciados. Es la referencia manual. | `ERR 5 ocupado` si hay jog |

## UCI → URC

| Mensaje | Cuándo |
| --- | --- |
| `BOOT scara/1 <versión>` | Una vez, al arrancar el firmware. Toda referencia anterior se perdió. |
| `HI scara/1 <versión>` | En respuesta a `HELLO`. |
| `S modo ref J1 J2 J3 J4 hall libres último` | 20 veces por segundo y ante `STATUS`. |
| `ERR código texto` | Ante un mensaje inválido o un evento que frena. |

Campos de `S`:

| Campo | Significado |
| --- | --- |
| `modo` | `IDLE` (quieto) o `JOG`. |
| `ref` | Máscara de ejes referenciados: bit 0 = J1 … bit 3 = J4; 15 = todos. |
| `J1`–`J4` | Posición estimada por pasos. Sin referencia, cuenta desde el arranque. |
| `hall` | Bits de los Hall (bit 0 = J1). Siempre 0 hasta el issue #8. |
| `libres` | Lugares libres en la cola de segmentos. Siempre 16 hasta el issue #9. |
| `último` | Último segmento terminado. Siempre 0 hasta el issue #9. |

Códigos de `ERR`:

| Código | Texto | Causa |
| --- | --- | --- |
| 1 | `comando` | Comando desconocido. |
| 2 | `argumentos` | Faltan, sobran o están fuera de rango. |
| 3 | `largo` | Línea de más de 64 bytes. |
| 4 | `watchdog` | Más de 1 s sin mensajes de la URC: el jog se frenó solo. |
| 5 | `ocupado` | La orden no se acepta mientras hay movimiento. |

## Ejemplo: jog de J1

```text
UCI → BOOT scara/1 1
URC → HELLO
UCI → HI scara/1 1
URC → JOG 1 + 450        (4,5 °/s)
UCI → S JOG 0 225 0 0 0 0 16 0
URC → PING
URC → JOG STOP
UCI → S IDLE 0 450 0 0 0 0 16 0
```

J1 avanza 4,5° y J2 relativo no cambia, porque el firmware mueve M1 y M2 juntos (J2 = (θM2 − θM1)/4). Las conversaciones completas, que son también las pruebas del firmware, están en [`firmware/test/conversaciones`](../firmware/test/conversaciones/).
