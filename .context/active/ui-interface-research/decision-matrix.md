# Decision Matrix: UI Desktop vs Web Local

Date: 2026-03-09
Status: ACTIVE
Source Priority: USER_INPUT > CODEBASE > PROJECT_CONTEXT

## Objetivo
Seleccionar la primera interfaz a implementar para HandsomeTranscribe, considerando requerimientos de microfono, vista en vivo, costo y esfuerzo de desarrollo.

## Escenarios evaluados
- Opcion A: Desktop Python (PySide6 / CustomTkinter)
- Opcion B: Web local (backend Python + frontend en navegador)

## Criterios y pesos
Escala de score: 1 (muy bajo) a 5 (muy alto)

- Acceso a microfono y perifericos: 25
- Soporte de multiples dispositivos de audio: 15
- Velocidad de implementacion inicial: 15
- Facilidad para vista en vivo (streaming UI): 15
- Experiencia de usuario visual: 10
- Complejidad de distribucion/operacion local: 10
- Reutilizacion del pipeline Python actual: 10

Suma de pesos: 100

## Puntuacion

| Criterio | Peso | Desktop Python | Web Local |
|---|---:|---:|---:|
| Acceso a microfono y perifericos | 25 | 5 | 3 |
| Soporte de multiples dispositivos de audio | 15 | 5 | 3 |
| Velocidad de implementacion inicial | 15 | 4 | 3 |
| Facilidad para vista en vivo | 15 | 4 | 4 |
| Experiencia de usuario visual | 10 | 3 | 5 |
| Complejidad de distribucion/operacion local | 10 | 3 | 4 |
| Reutilizacion del pipeline Python actual | 10 | 5 | 4 |

## Resultado ponderado
Formula: score_final = sum(score_criterio * peso_criterio)

- Desktop Python:
  - 5x25 + 5x15 + 4x15 + 4x15 + 3x10 + 3x10 + 5x10 = 430
  - Normalizado sobre 500: 86.0
- Web Local:
  - 3x25 + 3x15 + 3x15 + 4x15 + 5x10 + 4x10 + 4x10 = 355
  - Normalizado sobre 500: 71.0

## Decision recomendada
Recomendacion: iniciar con Desktop Python como fase 1.

Justificacion:
- El requerimiento critico es microfono/perifericos (incluyendo varios microfonos), donde desktop tiene ventaja clara.
- Permite reutilizar el pipeline Python actual con menos capas intermedias.
- Reduce friccion de permisos del navegador y variaciones por browser.

## Estrategia por fases
- Fase 1 (MVP): Desktop Python
  - Pantalla de sesion: iniciar/detener grabacion.
  - Vista en vivo incremental (texto parcial + speaker provisional).
  - Panel de configuracion: modo gratuito/local, modelo Whisper, diarizacion, resumen.
  - Vista de resultados: reproducir audio y abrir transcript/reportes.
- Fase 2: Web companion opcional
  - Dashboard de lectura de sesiones y reportes.
  - Streaming remoto opcional cuando exista capa de eventos estable.

## Riesgos y mitigaciones
- Riesgo: UI desktop menos moderna visualmente.
  - Mitigacion: usar PySide6 (Qt) en lugar de toolkit basico.
- Riesgo: acople con CLI existente.
  - Mitigacion: extraer capa de aplicacion/servicios y reutilizar desde CLI y UI.
- Riesgo: tiempo real inestable al inicio.
  - Mitigacion: usar actualizacion incremental por bloques de tiempo (por ejemplo, cada 2-5 segundos) en lugar de palabra a palabra.

## Criterio de salida de esta decision
La decision se considera aprobada cuando:
- Se confirme Fase 1 Desktop Python.
- Se acepte latencia objetivo inicial para vivo (por ejemplo 2-5 s).
- Se defina si multi-microfono es simultaneo o seleccion de un dispositivo por sesion.
