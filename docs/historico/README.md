# Documentación histórica

Estos documentos describen el banco provisional `scara-dev/1` (Webots como servidor, cliente HTTP y puente Python) o revisiones fechadas de ese momento. Se conservan como historia del proceso, sin editar sus bytes: pueden contradecir el estado actual y sus enlaces internos apuntan a archivos que ya no existen. No se citan como prueba del sistema nuevo (D16, D25).

El 01/11/2026, con el retiro del banco (#17, PR #34) y la campaña de validación nueva (#18, PR #36), pasaron acá:

| Documento | Lo reemplaza |
| --- | --- |
| [PROTOCOLO_SCARA_DEV_1.md](PROTOCOLO_SCARA_DEV_1.md) | [Protocolo `scara/1`](../PROTOCOLO_SCARA_1.md) y [ADR 0003](../adr/0003-protocolo-en-unidades-articulares.md) |
| [DIAGNOSTICO_TOPE_J4.md](DIAGNOSTICO_TOPE_J4.md) | Planta nueva de Webots. Su conclusión sigue vigente: el paso de simulación de 2 ms (`simulation.basic_time_step_ms` en `config/scara.json`) |
| [DATOS_PARA_EL_PROFESOR.md](DATOS_PARA_EL_PROFESOR.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md) |
| [REVISION_PARA_EL_PROFESOR_2026-10-27.md](REVISION_PARA_EL_PROFESOR_2026-10-27.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md) |
| [INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md](INVESTIGACION_TEACH_AND_PLAY_2026-10-29.md) | [Documento maestro v2](../maestro/SCARA-Master-v2.md), [registro de decisiones](../REGISTRO_DE_DECISIONES.md) y [ADR](../adr/) |

La evidencia de esos ensayos está en [validation/historico/banco_scara_dev_1](../../validation/historico/banco_scara_dev_1/README.md).
