# Canal de instrumentación y fallas F2–F5 en Webots (issue #14)

Ensayo del 31/10/2026, repetido el 01/11/2026 con la carga de D85, en Windows 11 Pro, Webots R2025a, con el controlador `scara_uci` compilado con el `g++` 14.2 de Webots y el microstepping por defecto, 1/8.

## Cómo se hizo

[`ensayo_webots.py`](ensayo_webots.py) corre contra el controlador, con Webots minimizado, sin vista, a tiempo real y arrancando justo en el reposo. Usa la sesión real de la URC (`scara/1`, puerto 9104) y el canal de instrumentación real (`urc/instrumentation.py`, `scara-sim/1`, puerto 9105).

Mira lo mismo que el panel «Banco de ensayo» de la página: la posición física simulada que manda el canal, leída de los sensores de posición de Webots, junto a la estimada por pasos que informa el firmware en `S`.

```sh
python validation/instrumentacion/ensayo_webots.py validation/instrumentacion/ensayo_webots.log
```

## Resultado

[`ensayo_webots.log`](ensayo_webots.log), en unidades de `scara/1` (centésimas de grado; J4 en centésimas de mm):

| Paso | Qué se hizo | Qué se vio |
| --- | --- | --- |
| 0 | Arranque, `ENABLE` y referencia manual | El canal se conecta solo (`SIM HELLO scara-sim/1`). Simulado y estimado coinciden: (0, 0, 0, 120 mm); los cuatro motores con corriente. |
| 1 | Carga de 500 g | `toolMass` del modelo pasa a 0,65 kg, la herramienta y la carga, y el canal informa 500 g (D85). |
| 2 | F2 con J4 en 60 mm | M4 queda sin corriente. J4 simulado **cae a 120 mm** y la estimada **sigue en 60 mm**: 60 mm de diferencia que el firmware no ve. Al quitar la falla, el motor retiene J4 donde quedó (D60). |
| 3 | F3: Hall de J4 trabado activo | El firmware lo ve activo a mitad de carrera. El homing aborta con `ERR 12 trabado`, sin referencia. |
| 4 | F4 en pleno jog de J1 | El estado `S` deja de llegar (2,6 s sin estado) y J1 simulado se queda quieto: el watchdog del firmware frenó solo. Al volver el enlace, el robot está en `IDLE`; el `ERR 4` salió con el enlace cortado y se perdió, como con un cable desenchufado. |
| 5 | F5 | La URC avisa «BOOT inesperado… (F5)» y marca el robot sin referencia. La UCI arranca sin corriente (D40): J1 sigue en 5,23° y J4, que quedó abajo después de F2, sigue en 120 mm. El aviso queda también en Errores (D87). |
| 6 | Recarga del mundo | Los dos canales se cortan y se vuelven a conectar solos. La UCI arranca de nuevo, sin referencia; el robot vuelve al reposo y la carga, a 0 g. |

Las pruebas automáticas cubren lo que no necesita Webots ([`tests/test_instrumentation.py`](../../tests/test_instrumentation.py)):

- **Sin canal, no hay banco:** la URC funciona igual, `/api/banco` responde `connected: false` y la página no muestra el panel.
- **Capturar y planificar no usan el canal:** la sesión, el planificador, la validación y el protocolo no importan `urc/instrumentation.py`. Con una posición simulada distinta de la estimada, el tramo PTP sale de la estimada.
- **Las órdenes del banco:** se validan antes de enviarse, y las líneas mal formadas del canal se descartan sin cortarlo.

## Qué mirar en la QA humana

El recorrido de la QA de la R6 se escribió en los PRs de los issues #14, #15 y #18. Al repetirlo con los límites de D76 aparecieron pasos mal escritos y tres arreglos (D85–D87); esta es la versión vigente de lo que toca el banco. Dónde se ve cada cosa en la página:

- **Mensaje de estado:** la línea debajo de los indicadores de arriba («UCI conectada», «Sin referencia», el modo). Cambia con cada orden.
- **Homing:** la línea «Homing:» de la sección «Referencia», con un ✓ por eje y el estado final.
- **Errores:** la sección «Errores», con los últimos 10 `ERR`, `EV LOST` y `BOOT` inesperados; no la pisa el mensaje siguiente.
- **Banco:** la tabla del banco de ensayo, la línea «Hall que ve el firmware» (bit 0 = J1, así que J1 activo es `0001`) y «Referencia dudosa (EV LOST)».

**F1 · Pérdida de pasos (#15).** Arranca con homing y «Pasos perdidos» en 0 en los cuatro motores.

1. Carga 4850 g, «Aplicar»: con los 150 g de la herramienta son los 5 kg de D76, el máximo que acepta el banco (D85). Con jog, subir J4 (R) unos centímetros y bajarlo: «Pasos perdidos» sigue en 0.
2. Llevar J4 a ≈ 60 mm. F1: M4 al 50 %, «Aplicar». Mantener R unos segundos: en Webots el pistón **no sube** (cede unas décimas de mm por segundo); «Estimada» sube a 10 mm/s y «Simulado» casi no cambia. «Pasos perdidos» de M4 crece en múltiplos de 4, unos 250 por segundo simulado (ver abajo).
3. F1: M4 al 100 %. «Estacionar…»: al pasar por el Hall de abajo, el mensaje de estado dice «Pérdida de pasos en J4: +N pasos completos…»; el banco, «Referencia dudosa (EV LOST): J4 +N pasos», y Errores, `EV LOST 4 N`, con N cerca de lo que marca «Pasos perdidos» de M4. «▶ Desde el principio», con cualquier trayectoria cargada, se rechaza debajo de los botones de reproducción: «No se puede reproducir: la referencia de J4 es dudosa por pérdida de pasos; hacé homing». El botón no se deshabilita: lo bloquea la URC (D68).
4. F1: M1 al 20 %. Mantener A (jog de J1 hacia el negativo) hasta que frene en su imán, a −130°: «Pasos perdidos» de M1 marca 4 al arrancar y, al llegar al imán, aparece `EV LOST 1 4`.
5. M1 al 100 %, carga 0 g, «Homing…»: la referencia deja de ser dudosa y «Pasos perdidos» vuelve a 0 en los cuatro motores, porque cuenta desde el último homing de cada eje (D86).

**F3 · Hall trabado (#14, #18).** Con referencia y en el reposo.

6. J1 en «activo»: «Hall que ve el firmware» pasa a `1001` (J1 trabado y J4, que descansa en su imán de abajo). Como J1 está referenciado, el firmware lo toma como una entrada al imán lejos de donde contó, y enseguida aparecen «Pérdida de pasos en J1: +289…» y `EV LOST 1 289` en Errores (D65): sin encoders, no distingue un sensor que miente de un motor corrido.
7. «Homing…»: J4 se referencia (✓); J1, a 1 °/s, avanza unos 6° buscando salir del que cree que es el imán del otro extremo y retrocede unos 12° sin que el Hall se apague. A los ~45 s, la línea «Homing:» dice «abortado: ERR 12 trabado…», el mensaje de estado «Homing abortado, sin referencia: ERR 12 trabado: el Hall no se apagó, está trabado activo» (D87), Errores `ERR 12 trabado` y el indicador, «Sin referencia». J1 a «libre».

**F5 · Reinicio de la UCI (#14, #18).**

8. Robot quieto: «F5 · Reiniciar la UCI…» y confirmar. El mensaje de estado dice «BOOT inesperado: la UCI se reinició y perdió la referencia (F5)», y Errores lo repite, así que sigue a la vista después de la orden siguiente (D87). Los indicadores pasan a «Sin referencia» y «Motores sin corriente», «arranques vistos» suma uno y, en el banco, «Motor con corriente» queda en «no» en los cuatro: J4 cae; J1–J3 quedan donde estaban.

**Carga y recarga (#14).**

9. Carga 1000 g, «Aplicar»: el banco informa 1000 g. Carga 0 g, «Aplicar»: vuelve a 0 g, la herramienta sola (D85).
10. «Recargar el mundo…»: Webots se recarga, el panel desaparece un instante y vuelve; la UCI arranca sin referencia, cerca del reposo y con 0 g.

**Los números de «Pasos perdidos» con F1 por carga (paso 2).** El campo de M4 avanza a los 10 mm/s del jog (D75; D76 no cambió el jog): 1,25 vueltas por segundo, 250 pasos completos o 2000 micropasos con 1/8. Cada 20 ms la URC encola un segmento de 5 pasos completos. Con 5 kg y la mitad de la corriente, el rotor no sube: cada vez que el campo se le adelanta dos pasos completos, cae al equilibrio siguiente, un ciclo eléctrico más atrás, y se pierden 4 pasos completos, 32 micropasos (D64). El banco cuenta pasos completos, así que el número siempre es múltiplo de 4, pero crece a 250 por segundo simulado. El canal lo informa cada 50 ms simulados (12,5 pasos: suma 12 o 16) y la página refresca cada 250 ms del reloj de la PC; entre dos refrescos suman unos 60 si Webots va a tiempo real, y menos si va más lento. Con 20 o 24 por refresco, Webots corría a un tercio del tiempo real. El paso viejo decía «crece de a 4»: era el tamaño de cada pérdida, no lo que se ve entre refrescos.

Ensayado el 01/11/2026 con un guion que maneja la sesión y el canal reales: carga 0 g (antes quedaba en la carga anterior); F1 por carga con 4850 g, de a 12 o 16 por mensaje `SIM` y 640 pasos en 3,5 s, `EV LOST 4 642` al estacionar y la reproducción rechazada; F1 por aceleración, 4 en M1 que el homing vuelve a 0; F3 en J1, `EV LOST 1 289` y `ERR 12` a los 43 s con el mensaje nuevo; F5, el `BOOT` en Errores.
