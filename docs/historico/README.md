# Documentación histórica

Estos documentos describen el banco provisional `scara-dev/1` (Webots como servidor, cliente HTTP y puente Python) o revisiones fechadas de ese momento. Se conservan como historia del proceso, sin editar sus bytes: pueden contradecir el estado actual y sus enlaces internos apuntan a archivos que ya no existen. No se citan como prueba del sistema nuevo (D16, D25).

El 01/11/2026, con el retiro del banco (#17, PR #34) y la campaña de validación nueva (#18, PR #36), pasaron acá:

| Documento | Lo reemplaza |
| --- | --- |
| [PROTOCOLO_SCARA_DEV_1.md](PROTOCOLO_SCARA_DEV_1.md) | [Protocolo `scara/1`](../PROTOCOLO_SCARA_1.md) y [ADR 0003](../adr/0003-protocolo-en-unidades-articulares.md) |
| [DIAGNOSTICO_TOPE_J4.md](DIAGNOSTICO_TOPE_J4.md) | Planta nueva de Webots. Su conclusión sigue vigente: el paso de simulación de 2 ms (`simulation.basic_time_step_ms` en `config/scara.json`) |
| [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md) |
| [REVISION_PARA_EL_PROFESOR_2026-10-27.md](REVISION_PARA_EL_PROFESOR_2026-10-27.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md) |
| [FALLAS_Y_VALIDACION.md](FALLAS_Y_VALIDACION.md) | [Campaña de validación](../../validation/campana/INFORME.md) y sección 10 del [maestro v2](../maestro/SCARA-Master-v2.md) |
| [VALIDACION_WEBOTS.md](VALIDACION_WEBOTS.md) | Ídem. Sigue siendo el índice de la evidencia CAD de 15–17/10/2026, que los documentos CAD vigentes enlazan |
| [INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md), [registro de decisiones](../REGISTRO_DE_DECISIONES.md) y [ADR](../adr/) |

El PDF de la revisión del 27/10/2026 está en [`output/pdf/historico/`](../../output/pdf/historico/SCARA_revision_profesor_2026-10-27.pdf).

La evidencia de esos ensayos está en [validation/historico/banco_scara_dev_1](../../validation/historico/banco_scara_dev_1/README.md).

## Clasificación de `docs/` y `validation/` (issue #1)

**Vigentes:** `ENSAMBLE_CAD`, `FUENTES_CAD_WEBOTS`, `INTEGRACION_CAD_CRITERIOS`, `EVALUACION_CONVERSION_CAD`, `PROPIEDADES_GEOMETRICAS_CAD`, `RECUPERACION_GEOMETRIAS`, `MONTAJE_Y_AUTOCOLISIONES`, `PROTOCOLO_SCARA_1`, `UCI_WEBOTS`, `ARDUINO_UNO`, `REGISTRO_DE_DECISIONES`, `maestro/`, `adr/`, `agents/`; reescritos para el sistema nuevo: `README`, `PROCESO_Y_ARCHIVOS`, `PLAN_GEMELO_DIGITAL`.

**Vigentes con referencias a actualizar:** `COLISIONES_Y_RECORRIDOS` (lo usa el planificador de la URC, pero describe la comprobación del banco viejo) y `TRANSMISION` (los documentos CAD enlazan su evidencia al índice histórico `VALIDACION_WEBOTS`).

**Históricos:** los de la tabla de arriba.

**Evidencia vigente del sistema nuevo:** `validation/campana/`, `bala_trazadora/`, `protocolo/`, `transmision/`, `segmentos/`, `homing/`, `instrumentacion/`, `jog/`, `reproduccion/`, `perdida_pasos/`.

**Evidencia CAD y de geometría** (vigente mientras el modelo no cambie): `cad_*`, `pulley_*`, `mounting*`, `wrist_*`, `self_collisions*`, `collisions*`, `collision_tests.json`, `remaining_mounts*`, `transmission*`, `physics_sources.json`, las capturas `scara_cad_*.png` y `sesion8/` (precálculo geométrico). Los `cad_motion_*` y `collisions_native_*` se corrieron en Webots con el banco `scara-dev/1`: valen como evidencia de montaje y contactos, no del control.

**Evidencia histórica:** [`validation/historico/`](../../validation/historico/README.md), incluido el banco `scara-dev/1`.
