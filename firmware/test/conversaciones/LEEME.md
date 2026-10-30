# Conversaciones de prueba del firmware

Cada `.txt` es una conversación `scara/1` entre una URC imaginaria y el firmware real, compilado para la PC con una capa de hardware falsa: reloj controlable y contadores de pasos por motor (los Hall a voluntad llegan con el homing, issue #8). Es el seam 1 de la spec #2. Más adelante, una UCI falsa en Python reproducirá las mismas conversaciones contra la URC, así los dos lados quedan obligados a entender igual el protocolo.

## Cómo se corren

Con la suite de Python, desde la raíz del repo:

```sh
python3 -m unittest tests.test_firmware -v
```

En Windows, `python` en lugar de `python3`. La prueba busca un compilador de C++ (`CXX`, `c++`, `g++`, `clang++` o el `g++` que trae Webots en `msys64`); sin compilador, se omite y lo avisa.

## Formato

El firmware arranca al empezar cada archivo (envía `BOOT`). El reloj empieza en 0 ms.

| Renglón | Significado |
| --- | --- |
| `# texto` | Comentario. |
| `> LÍNEA` | La URC envía `LÍNEA` (se agrega el LF). `\r` representa un CR real. |
| `< LÍNEA` | La UCI tiene que haber enviado `LÍNEA`. `*` acepta cualquier campo. |
| `+ N` | Avanza el reloj N ms, de a 1 ms, atendiendo al firmware en cada uno. |
| `= M1 a M2 b …` | Pasos netos emitidos a cada motor desde el arranque. |

Reglas de `<`: las líneas `S` periódicas que no se esperan se saltean; cualquier otra línea inesperada es un error, también si queda alguna al terminar el archivo. Toda línea que envía la UCI tiene que medir hasta 64 bytes.
