# Protocolo `scara-sim/1`

Especificación del canal de instrumentación entre la URC y el controlador de Webots (D2, D59, [ADR 0004](adr/0004-canal-de-instrumentacion-separado.md)). Lleva lo que solo existe en la simulación: la posición física simulada, las fallas F1–F5, la carga, los obstáculos, el empujón, el movido a mano y la recarga del mundo. El robot real no lo tiene: sin este canal, la URC funciona igual y el banco de ensayo no aparece. El contrato con el robot es [`scara/1`](PROTOCOLO_SCARA_1.md).

Implementaciones: `Bench` en [`scara_uci.cpp`](../webots/controllers/scara_uci/scara_uci.cpp) y [`urc/instrumentation.py`](../urc/instrumentation.py).

## Transporte y formato

- La URC escucha en TCP 9001 (`--sim-port`) y el controlador de Webots se conecta (`--sim-port` en `controllerArgs`; 0 lo apaga). Una conexión nueva reemplaza a la anterior: Webots se recargó.
- Como `scara/1`: ASCII, una línea por mensaje terminada en LF (se ignora CR), campos separados por espacios. El controlador guarda hasta 64 caracteres por línea y descarta el resto.
- Unidades de `scara/1` para las articulaciones (centésimas de grado en J1–J3 y de mm en J4); mm para obstáculos, gramos para la carga.

## Controlador → URC

| Mensaje | Cuándo |
| --- | --- |
| `SIM HELLO scara-sim/1` | Al conectarse. |
| `SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga i1 i2 i3 i4 p1 p2 p3 p4` | Cada 50 ms del reloj simulado. |
| `SIM OBSTACULO tipo X Y altura` | Cada 50 ms. `tipo`: `ninguno`, `maceta` o `mesa`. |
| `SIM CONTACTO tipo cuerpo e1 e2 e3 e4 p1 p2 p3 p4 l1 l2 l3 l4` | Cada 50 ms. `cuerpo`: `ninguno`, `ARM`, `FOREARM`, `WRIST` o `TOOL`. `e`, `p` y `l`: esfuerzo actual, pico y límite provisional de J1–J4 (N·m en J1–J3; N en J4), con decimales (D89, D90). |
| `SIM MANO j posición` | Eco de un `MANO` aplicado. |
| `SIM EMPUJON fuerza_cN dirección duración_ms` | Eco de un `EMPUJON` aplicado. |
| `SIM ERR orden` · `SIM ERR corriente` · `SIM ERR posicion` | Orden desconocida o mal formada; `MANO` con algún driver con corriente; `MANO` fuera de los límites. |

Campos del estado `SIM` (19 campos):

| Campo | Significado |
| --- | --- |
| `J1`–`J4` | Posición física simulada, de los `PositionSensor` de Webots. |
| `hall` | Bits de los Hall como los ve el firmware, con F3 aplicada (bit 0 = J1). |
| `corriente` | Máscara de drivers con corriente (bit 0 = M1); 15 = todos. |
| `f2`, `f4` | F2 (driver de M4 sin corriente) y F4 (enlace `scara/1` cortado): 0 o 1. |
| `f3` | Un carácter por articulación: `-` libre, `A` trabado activo, `I` trabado inactivo. |
| `carga` | Gramos agregados a la herramienta, sin el pistón y su soporte (150 g): 0–4850 (D85). |
| `i1`–`i4` | Corriente de cada driver, en % de la nominal (F1). |
| `p1`–`p4` | Pasos completos que perdió cada motor desde el último homing de su eje o desde que recuperó la corriente (D64, D86). |

## URC → controlador

| Orden | Parámetros | Efecto |
| --- | --- | --- |
| `F1 m porcentaje` | Motor 1–4; 10–100 | Corriente del driver de `m`: con menos, el motor tiene menos par y puede perder pasos. |
| `F2 0\|1` | — | Driver de M4 sin corriente: J4 cae; la posición estimada no cambia (D60). |
| `F3 j estado` | 1–4; `activo`, `inactivo` o `libre` | Traba el Hall de `j` o lo devuelve a la geometría. |
| `F4 0\|1` | — | Corta `scara/1` sin cerrar la conexión: lo que llega se pierde y lo que sale no llega. Actúa el watchdog. |
| `F5` | — | Reinicia el firmware: `BOOT`, sin corriente ni referencia (D61). |
| `CARGA gramos` | 0–4850 | Masa agregada a la herramienta (`toolMass` del proto). |
| `RECARGA` | — | Recarga el mundo; los dos canales se vuelven a conectar. |
| `OBSTACULO ninguno` · `OBSTACULO maceta X Y` · `OBSTACULO mesa X Y altura` | X, Y: −1000 a 1000 mm; altura: −20 a 90 mm | Pone o saca el obstáculo de ensayo (C1, C2). |
| `EMPUJON fuerza_cN dirección duración_ms` | 1–5000 cN; −180 a 180°; 50–2000 ms | Fuerza horizontal breve en la punta y su par en los rotores (C3, D92). |
| `MANO j posición` | 1–4; centésimas dentro de los límites | Coloca la articulación con los cuatro drivers sin corriente, sin referenciar el firmware (C4, D91). |

Cada orden vale solo si ocupa la línea entera (`F2 1x` no es `F2 1`). No hay acuse: la URC confirma cada orden que cambia el estado (carga, F1–F4, obstáculo) cuando el estado `SIM` la muestra, y si no la ve en 2 s lo avisa en el registro de eventos (D79). `MANO` y `EMPUJON`, que no se ven en el estado, se confirman con su eco.

## Ejemplo

Tráfico real del 07/11/2026 ([registro](informe/dialogo/dialogo-2026-11-07.log)): apertura del canal y F1 con 5 kg; la carga y la corriente se ven en el `SIM` siguiente.

```text
SIM HELLO scara-sim/1
SIM 966 123 -228 12000 8 0 0 ---- 0 0 100 100 100 100 0 0 0 0
CARGA 4850                                                         (URC → controlador)
F1 4 50                                                            (URC → controlador)
SIM -2 -1 -3 6001 0 15 0 ---- 0 4850 100 100 100 50 0 0 0 0
```
