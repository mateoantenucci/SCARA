# Evidencia del banco `scara-dev/1`

Ensayos hechos sobre el banco provisional `scara-dev/1`, movidos acá con `git mv` el 01/11/2026 sin cambiar sus bytes: los SHA-256 que citan los manifiestos siguen valiendo, pero las rutas que nombran son las de antes del movimiento (`validation/<archivo>`). No prueban el sistema nuevo (D16, D25).

| Evidencia | Qué era |
| --- | --- |
| `j4_experiment_*`, `j4_stops_*`, `j4_stop_probe.json`, `j4_diagnosis.json`, `j4_tests.json`, `j4_timestep_cost.json` | Diagnóstico del tope de J4 ([documento](../../../docs/historico/DIAGNOSTICO_TOPE_J4.md)) |
| `perdida_esfuerzo_20261026.json` | Pérdida por esfuerzo del banco viejo |
| `simulation_collisions.json`, `simulation.json`, `simulation_j4.json` | Comportamiento y colisiones en simulación con el banco viejo |
| `client_native.json`, `scara_banco.png` | Ensayo y captura de la interfaz web del banco viejo |
| `sesion2`, `sesion4`–`sesion7`, `sesion9` | Sesiones de integración, portabilidad (incluye `SCARA-ejecucion.zip`), demostración del banco y su consolidación |

Lo reemplaza la [campaña de validación](../../campana/INFORME.md) del sistema nuevo: homing, teach & play y fallas F1–F5.
