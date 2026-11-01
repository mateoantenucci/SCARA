# Referencias técnicas del proyecto

Índice de las fuentes primarias usadas durante el desarrollo. Las decisiones particulares y su evidencia están en los documentos enlazados. Las referencias de Webots R2025a describen esa revisión; los ensayos nativos identifican por separado el ejecutable utilizado. Las comparativas comerciales de herramientas consultadas al inicio se retiraron de la lectura vigente.

## Modelo y simulación

- [Mesh](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/mesh.md): importación de geometría visual.
- [Solid](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/solid.md) y [Physics](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/physics.md): cuerpos, contacto y propiedades físicas.
- [HingeJointParameters](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/hingejointparameters.md) y [JointParameters](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/jointparameters.md): ejes, referencias y topes.
- [Motor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/motor.md), [PositionSensor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/positionsensor.md) y [Supervisor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md): actuadores e instrumentación.
- [Programación del controlador](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/controller-programming.md) e [interfaz TCP/IP](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/interfacing-webots-to-third-party-software-with-tcp-ip.md).
- [Python Socket HOWTO](https://docs.python.org/3/howto/sockets.html): flujo TCP, buffers y sockets no bloqueantes.

Aplicación en el proyecto: [criterios de integración](INTEGRACION_CAD_CRITERIOS.md), [fallas](historico/FALLAS_Y_VALIDACION.md) y [validación](historico/VALIDACION_WEBOTS.md). El [diagnóstico de J4](historico/DIAGNOSTICO_TOPE_J4.md) enlaza además el código de la build efectivamente analizada.

## Conversión y cálculo CAD

- [sldprt2step, revisión fijada](https://github.com/BlinkingSun/sldprt2step/tree/fa954124f4f126e0c465c8f96454978ac80b812e): conversión local de piezas; ver [evaluación y reproducción](EVALUACION_CONVERSION_CAD.md).
- [Paquete OCP sin VTK usado](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/): versiones fijadas en `tools/requirements-cad.txt`.
- [OCCT BRepGProp](https://www.occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html) y [GProp_GProps](https://www.occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html): integrales geométricas y composición; ver [propiedades](PROPIEDADES_GEOMETRICAS_CAD.md).
- [API SolidWorks de referencias externas](https://help.solidworks.com/2021/english/api/swdocmgrapi/SolidWorks.Interop.swdocumentmgr~SolidWorks.Interop.swdocumentmgr.ISwDMDocument27~GetExternalFeatureReferences3.html): referencia sobre datos guardados por el documento padre; ver [recuperación del ensamble](ENSAMBLE_CAD.md).

Las licencias y atribuciones del conversor están en [LICENSE](../tools/patches/LICENSE-sldprt2step.txt) y [NOTICE](../tools/patches/NOTICE-sldprt2step.txt).
