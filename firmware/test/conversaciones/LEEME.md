# Conversaciones de conformidad

Cada `.txt` es una conversación `scara/1` entre la URC y la UCI. Son la definición ejecutable del [protocolo](../../../docs/PROTOCOLO_SCARA_1.md) y se corren contra los dos lados (D39, D42), así los dos quedan obligados a entender igual el protocolo:

- **Firmware** (seam 1 de la spec #2): el núcleo real, compilado para la PC con una capa de hardware falsa: reloj controlable, contadores de pasos por motor y corriente de los drivers (los Hall a voluntad llegan con el homing, issue #8).
- **URC** (seam 2): una UCI falsa en Python se conecta por TCP a la URC real. Envía las líneas `<` y comprueba que la URC pueda enviar cada `>`. Si el firmware rechaza una orden por su forma (`ERR 1`, `2` o `3`), la URC tiene que negarse a enviarla con el mismo código. `+`, `=` y `!` no los ve la URC.

Los `SEG` siguen el control de flujo (D50): en el archivo, cada `> SEG` va después del `< OK` del anterior, porque la URC no envía uno nuevo sin ese `OK`. Un `SEG` que el firmware rechaza con `ERR 9 cola` es uno que una URC correcta no envía: la prueba de la URC comprueba que lo retenga.

## Cómo se corren

Con la suite de Python, desde la raíz del repo:

```sh
python3 -m unittest tests.test_firmware tests.test_conformidad -v
```

En Windows, `python` en lugar de `python3`. La prueba del firmware busca un compilador de C++ (`CXX`, `c++`, `g++`, `clang++` o el `g++` que trae Webots en `msys64`); sin compilador, se omite y lo avisa.

## Formato

El firmware arranca al empezar cada archivo (envía `BOOT`). El reloj empieza en 0 ms. Los pasos de las líneas `=` están escritos para el microstepping por defecto, 1/8 (`firmware/config.h`, D44); la conversión con los demás valores la prueba [`transmision.cpp`](../transmision.cpp).

| Renglón | Significado |
| --- | --- |
| `# texto` | Comentario. |
| `> LÍNEA` | La URC envía `LÍNEA` (se agrega el LF). `\r` representa un CR real. |
| `< LÍNEA` | La UCI tiene que haber enviado `LÍNEA`. `*` acepta cualquier campo. |
| `+ N` | Avanza el reloj N ms, de a 1 ms, atendiendo al firmware en cada uno. |
| `= M1 a M2 b … EN e` | Pasos netos emitidos a cada motor desde el arranque; `EN 1` o `EN 0`, drivers con corriente o sin ella. Se puede nombrar cualquier subconjunto. |
| `! reinicio` | La UCI se reinicia sin cortar el enlace (falla F5): el firmware vuelve a arrancar y envía `BOOT`. Los motores conservan los pasos dados. |

Reglas de `<`: las líneas `S` periódicas que no se esperan se saltean; cualquier otra línea inesperada es un error, también si queda alguna al terminar el archivo. Toda línea que envía la UCI tiene que medir hasta 64 bytes.
