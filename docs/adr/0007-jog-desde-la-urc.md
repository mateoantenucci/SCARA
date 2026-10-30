---
status: accepted
---

# El jog se maneja con el teclado de la URC, no con la ventana de Webots

El profesor sugirió mover las articulaciones con teclas en Webots. Decidimos leer el teclado en la página de la URC, con dos modos y las mismas teclas: cartesiano (W/A/S/D, R/F, Q/E) y articular. Hay tres motivos:

1. El robot real no tendrá botonera, así que el jog desde la URC funciona igual con el robot real y con la simulación.
2. El jog cartesiano necesita la cinemática inversa, que corre en la URC.
3. La lista de puntos queda a la vista mientras se captura.

Decidido el 29/10/2026.

## Considered Options

- **Teclas en la ventana de Webots** (descartado como vía principal): solo existiría en la simulación, permitiría únicamente jog articular y exige hacer clic en la vista 3D para darle el foco. Si el profesor lo pide, se puede agregar sin cambiar el firmware.

## Consequences

- La referencia manual es un botón con confirmación, no la tecla Z: queda pegada a la A y se dispararía sin querer.
