---
status: accepted
---

# Modelo de motores: pasos y pérdida de pasos, sin modelo eléctrico

La planta simulada representa los motores en dos niveles. Primero, pasos discretos con microstepping y transmisión, incluido el acople M1/M2. Segundo, par limitado según la velocidad: una carga o aceleración excesiva produce pérdida de pasos que el firmware no advierte. Se deja fuera el modelo eléctrico (corrientes, inductancia, resonancias): exige datos que el maestro no trae y pasos de simulación mucho más chicos, y no cambia lo que se quiere mostrar. Decidido el 29/10/2026.
