# UCI en el Arduino UNO: firmware, cableado y socat

El mismo firmware que corre en Webots, compilado para el Arduino UNO del robot real (D3, [ADR 0002](adr/0002-firmware-compartido-robot-real-y-simulacion.md)). Solo cambia la capa de hardware: pines, serie y timer. La URC no cambia: socat puentea el USB-serie del UNO al puerto TCP 9000 donde la URC escucha (D1, D18). No hay placa todavía: el firmware compila sin hardware y el camino serie + socat se ensaya con un puerto serie virtual (issue #16).

```text
navegador ──HTTP 8766──► URC ◄──TCP 9000── socat ◄──USB-serie 115200── Arduino UNO
                                                                        ├─ firmware/  (el mismo núcleo de Webots)
                                                                        └─ capa de hardware del UNO ──► 4 TB6600, 4 KY-003
```

## Archivos

| Archivo | Qué es |
| --- | --- |
| [`firmware/arduino/scara_uci/scara_uci.ino`](../firmware/arduino/scara_uci/scara_uci.ino) | Sketch: une el núcleo con la capa de hardware del UNO. |
| [`firmware/arduino/scara_uci/hal_uno.h`](../firmware/arduino/scara_uci/hal_uno.h) | Asignación de pines, baudios y tick del timer. |
| [`firmware/arduino/scara_uci/hal_uno.cpp`](../firmware/arduino/scara_uci/hal_uno.cpp) | Capa de hardware: pines, serie, Hall y la interrupción del Timer1. |
| [`firmware/arduino/scara_uci/pulsos.cpp`](../firmware/arduino/scara_uci/pulsos.cpp) | Generador de pulsos STEP/DIR, portable y probado en la PC. |
| [`firmware/pc/uci_serie.cpp`](../firmware/pc/uci_serie.cpp) | UCI de PC detrás de un puerto serie virtual, para ensayar socat sin la placa. |
| [`tests/test_uno.py`](../tests/test_uno.py) | Prueba del generador de pulsos y compilación para el UNO con su presupuesto. |
| [`tests/test_serie_socat.py`](../tests/test_serie_socat.py) | La URC real opera el firmware por puerto serie virtual + socat. |

## Pines (D47)

El presupuesto de D18: 13 pines de E/S más la serie, 15 de 20. La asignación deja libres D4 y D10–D13, los que usa un shield Ethernet, así que esa alternativa no obliga a recablear.

| Pin | Puerto | Uso | Conecta a |
| --- | --- | --- | --- |
| D0, D1 | PD0, PD1 | Serie (USB) a 115200 | Puente USB del UNO |
| D2 | PD2 | STEP M1 | PUL+ del TB6600 de M1 |
| D3 | PD3 | STEP M2 | PUL+ del TB6600 de M2 |
| D5 | PD5 | STEP M3 | PUL+ del TB6600 de M3 |
| D6 | PD6 | STEP M4 | PUL+ del TB6600 de M4 |
| A0 | PC0 | DIR M1 | DIR+ del TB6600 de M1 |
| A1 | PC1 | DIR M2 | DIR+ del TB6600 de M2 |
| A2 | PC2 | DIR M3 | DIR+ del TB6600 de M3 |
| A3 | PC3 | DIR M4 | DIR+ del TB6600 de M4 |
| D7 | PD7 | ENABLE común | ENA+ de los cuatro TB6600 |
| D8 | PB0 | Hall J1 | OUT del KY-003 de J1 |
| D9 | PB1 | Hall J2 | OUT del KY-003 de J2 |
| A4 | PC4 | Hall J3 | OUT del KY-003 de J3 |
| A5 | PC5 | Hall J4 | OUT del KY-003 de J4 |
| D4, D10–D13 | | Libres | Reservados para el shield Ethernet (SD CS, W5100 CS, SPI) |

Por qué así:

- **Los cuatro STEP en el mismo puerto (PORTD)**: la interrupción los escribe con un solo acceso. J1 mueve M1 y M2 juntos (acople de la cadena híbrida) y sus pulsos salen en el mismo instante.
- **Los cuatro DIR en otro puerto (PORTC)**, también de una vez. Si un motor quedó cableado al revés, se corrige con `DIR_INVERT` en `hal_uno.h`, sin tocar los cables ni el núcleo.
- **Los Hall** son entradas con el pull-up interno activado: el KY-003 tira a masa con el imán cerca, así que `LOW` es «activo». En `S`, el bit n del campo `hall` es el Hall de Jn+1.

## Cableado de los TB6600

Cátodo común: PUL−, DIR− y ENA− de los cuatro drivers a la masa del Arduino; PUL+, DIR+ y ENA+ a los pines de la tabla. El TB6600 acepta 5 V en sus entradas optoacopladas sin resistencias extra. Las llaves DIP de cada driver se ponen en la corriente de su motor y en el microstepping de `SCARA_MICROSTEPS`, el parámetro único de [`firmware/config.h`](../firmware/config.h) (D44): hoy 1/8, 1600 pulsos por vuelta (D9). Si cambia uno, tiene que cambiar el otro; el firmware no puede leer las llaves.

- **ENA+ en alto corta la corriente.** Con este cableado, el opto del ENABLE conduce con el pin en alto y el driver queda libre. Por eso `begin()` fija D7 en alto antes de hacerlo salida, y `ENABLE` lo baja.
- **Durante el reinicio, los drivers tienen corriente.** Mientras el UNO se reinicia (al abrir el puerto, D36), sus pines quedan en alta impedancia, el opto no conduce y los TB6600 sostienen a los motores. Dura lo que tarda el bootloader; después el firmware arranca y los deja sin corriente (D40). No se dan pasos en ese lapso: los STEP están en alta impedancia. Si hiciera falta asegurarlo contra ruido, una resistencia de 10 kΩ a masa en cada STEP lo resuelve.
- **Tiempos del TB6600**: pide DIR estable al menos 5 µs antes del flanco del pulso y pulsos de al menos 2,2 µs. El generador da 50 µs de cada uno.

Los KY-003 van a 5 V y masa del Arduino, con su salida al pin de la tabla. Los drivers se alimentan aparte, con 36 V (maestro v2, §5).

## Pasos por timer (D48)

El núcleo decide cuándo dar cada paso, con su reloj de milisegundos, y llama a `Hal::step`. La capa del UNO no saca el pulso en ese momento: lo deja pendiente y la interrupción del Timer1, a 20 kHz, lo convierte en un pulso con los tiempos del TB6600:

1. Si el sentido cambió, primero cambia DIR, y el pulso sale en el tick siguiente.
2. El pulso dura un tick (50 µs) en alto y al menos uno en bajo: hasta 10 000 pasos por segundo por motor. Con 1/8 y las velocidades máximas de `config.h` (D45), el que más pide es M4: 1350 °/s, 6000 pasos/s (J4 a 30 mm/s). Con un tick de 10 kHz no alcanzaría. Un `static_assert` en `hal_uno.h` lo comprueba al compilar: con 1/16, M4 pediría 12 000 pasos/s y el sketch no compila hasta subir `TICK_HZ`.
3. Si un motor junta 255 pasos pendientes, `step` espera a que la interrupción los saque. El núcleo se atrasa, pero ningún paso que contó se deja de dar: la posición estimada no se separa de la real por culpa del firmware. Mientras espera, el núcleo no lee la serie: el buffer de 64 bytes del UNO se llena en unos 5 ms. Solo pasa si el núcleo pide más de 10 000 pasos/s a un motor, y eso lo impiden los límites de velocidad de `config.h` (D45) y el `static_assert` de abajo.

Así el ancho del pulso no depende de cuánto tarde `poll()`, y la serie sigue atendida mientras salen los pasos.

**Costo.** Contando ciclos en el desensamblado: sin pasos pendientes, la interrupción sale en unos 75 ciclos sin tocar los puertos (≈ 9 % del procesador a 20 kHz); con los cuatro motores pulsando a la vez, unos 165 en promedio (≈ 20 %). La primera versión recorría los motores en cada tick y costaba unos 250 ciclos incluso quieta (≈ 30 %): por eso el generador lleva una máscara de motores con pasos pendientes, `tick()` avisa si cambió alguna salida y unas tablas de 16 entradas traducen cada máscara a los bits del puerto.

## Compilar sin placa

Hace falta [`arduino-cli`](https://arduino.github.io/arduino-cli/) con el core `arduino:avr`:

```sh
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno --library firmware firmware/arduino/scara_uci
```

Hay que correrlo desde la raíz del repo. `--library firmware` hace que el núcleo (`firmware/firmware.cpp`, `firmware.h`, `hal.h`) se compile tal cual, sin copias: Arduino lo trata como una biblioteca y no mira sus subcarpetas. Para grabar la placa se agrega `--upload -p PUERTO`.

`python -m unittest discover` lo compila y verifica el presupuesto si encuentra `arduino-cli` en el PATH o en la variable `ARDUINO_CLI`; si no, lo omite.

**Resultado (30/10/2026, Windows 11, arduino-cli 1.5.1, `arduino:avr` 1.8.8, avr-gcc 7.3.0, con el núcleo de la transmisión N1 de #7 y 1/8):**

| Recurso | Usado | Del UNO | |
| --- | --- | --- | --- |
| Flash | 6544 bytes | 32 256 (32 KB menos el bootloader) | 20 % |
| RAM global | 575 bytes | 2048 | 28 % |

Quedan 1473 bytes para la pila, que usa el núcleo para armar cada línea (`S` usa 96 bytes). La prueba exige que la RAM global no pase del 75 %, el umbral en el que Arduino avisa «poca memoria». Compila sin avisos en el código del proyecto con `--warnings all`; los únicos avisos son del core de Arduino.

En Windows, el instalador de winget (`ArduinoSA.CLI`) pide elevación; el zip oficial de [GitHub](https://github.com/arduino/arduino-cli/releases) no la necesita.

## socat con el robot real

La URC escucha en el 9000 (D1); socat abre el USB del UNO y se conecta a ella. Abrir el puerto reinicia el UNO, que envía `BOOT` (D36): la URC lo marca sin referencia (D43). El `HELLO` que la URC envía al conectarse llega mientras el UNO está en el bootloader y se pierde; no hace falta, porque `BOOT` ya trae el protocolo y la versión.

**macOS** (Homebrew: `brew install socat`). Usar `/dev/cu.*`, no `/dev/tty.*`, que espera la señal de portadora:

```sh
ls /dev/cu.usbmodem*
socat -d -d /dev/cu.usbmodem1101,b115200,rawer TCP:127.0.0.1:9000
```

**Linux** (`apt install socat`; el usuario tiene que estar en el grupo `dialout`):

```sh
socat -d -d /dev/ttyACM0,b115200,rawer TCP:127.0.0.1:9000
```

**Windows**: con el socat de MSYS2 (ver abajo), `COMn` es `/dev/ttyS(n−1)`; por ejemplo, COM3:

```sh
socat -d -d /dev/ttyS2,b115200,rawer TCP:127.0.0.1:9000
```

- Se levanta primero la URC (`python3 -m urc.app`). Para que socat espere a la URC en lugar de fallar, se agrega `,forever,interval=1` a la dirección TCP.
- socat termina si se corta el USB o la URC. Para que vuelva solo: `while true; do socat …; sleep 1; done`. Cada vuelta reinicia el UNO y la URC pide referencia de nuevo.
- `rawer` deja el puerto en modo crudo y sin eco. Un socat anterior a 1.7.4 no lo conoce: usar `raw,echo=0`.
- `-d -d` muestra en la terminal qué abrió y a qué se conectó. Para ver el tráfico, `-v`.

Con el robot real no se probó todavía: no hay placa. Lo que se probó es la misma receta contra un puerto serie virtual.

## Ensayo sin placa: puerto serie virtual + socat (D49)

`firmware/pc/uci_serie.cpp` es el núcleo con una capa de hardware POSIX que hace de UNO detrás de un puerto serie virtual (un PTY). Crea el puerto, informa su nombre y espera. socat lo abre con la misma receta que el USB del UNO; solo cambia el nombre del dispositivo. Como el UNO, abrir el puerto reinicia el firmware (`BOOT`, sin corriente) y cerrarlo lo apaga. No tiene planta: los pasos no mueven nada y los Hall no se activan.

**macOS o Linux:**

```sh
c++ -std=c++11 firmware/pc/uci_serie.cpp firmware/firmware.cpp -o /tmp/uci_serie
python3 -m urc.app &                     # página en http://127.0.0.1:8766
/tmp/uci_serie                           # anuncia «puerto serie en /dev/ttys004»
socat -d -d /dev/ttys004,b115200,rawer TCP:127.0.0.1:9000
```

**Windows:** hace falta [MSYS2](https://www.msys2.org/) con `socat` y `gcc`. Los programas nativos de Windows (el `g++` de Webots, Python) no ven los PTY de MSYS2: `uci_serie` se compila con el `g++` de MSYS2, y los dos corren en su `bash`. Sin permisos de administrador alcanza con extraer el `msys2-base-x86_64-*.sfx.exe` de los [releases oficiales](https://github.com/msys2/msys2-installer/releases) en `C:\msys64` e instalar los paquetes:

```powershell
& C:\msys64\usr\bin\bash.exe -lc "pacman -S --noconfirm socat gcc"
```

Después, con la URC levantada en otra terminal (`python -m urc.app`), desde la raíz del repo:

```powershell
& C:\msys64\usr\bin\bash.exe -lc "g++ -std=c++11 firmware/pc/uci_serie.cpp firmware/firmware.cpp -o /tmp/uci_serie && /tmp/uci_serie"
& C:\msys64\usr\bin\bash.exe -lc "socat -d -d /dev/pty0,b115200,rawer TCP:127.0.0.1:9000"
```

En Cygwin, que es la base de MSYS2, un PTY cerrado no se puede volver a abrir. Por eso, cada vez que socat cierra el puerto, `uci_serie` crea uno nuevo y anuncia su nombre (`/dev/pty1`, …).

`tests/test_serie_socat.py` hace todo esto solo: compila `uci_serie`, levanta la sesión real de la URC (`urc/session.py`, sin cambios), abre el puerto con socat y opera el robot como la página. Busca `socat` en el PATH o en `SOCAT` y, en Windows, en `C:\msys64`; si no lo encuentra, se omite.

**Resultado (30/10/2026, Windows 11, MSYS2 2026-09-27, socat 1.8.1.3, g++ 16.2):**

1. Al abrir el puerto, la UCI envía `BOOT scara/1 1` y la URC muestra el robot sin corriente (`S OFF`).
2. «Habilitar motores» y «Referencia manual» la dejan quieta y referenciada.
3. Un jog de J1 de 1 s, renovado cada 150 ms como lo hace la página, la lleva a unos 5° con J2 en 0 (acople M1/M2), y `JOG STOP` la frena referenciada.
4. «Deshabilitar motores» deja `S OFF` sin referencia. Ni la URC ni el firmware informaron errores ni líneas inválidas.
5. Al cortar socat, la URC muestra la UCI desconectada. Al abrir el puerto de nuevo, la UCI envía otro `BOOT`.

Se corrió tres veces seguidas sin fallas, junto con el resto de la suite.

Por qué así y no al revés: socat también puede crear el PTY (`PTY,link=…`) y dejar que la UCI lo abra. En MSYS2, socat no espera a que la UCI lo abra (`wait-slave` no funciona) y se cierra solo con un error de E/S. Además, con la UCI del lado de la placa, socat corre exactamente la receta del robot real.
