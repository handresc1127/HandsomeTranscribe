# Context: Investigacion UI de HandsomeTranscribe

Date: 2026-03-09
Status: ACTIVE
Source Priority: USER_INPUT > CODEBASE > PROJECT_CONTEXT

## Resumen
El foco actual es definir la interfaz grafica del producto (desktop Python o web local).
El usuario prioriza uso de microfono, visualizacion en vivo de conversacion/interlocutores y consulta de artefactos al finalizar sesion.
La evidencia del repo confirma un pipeline CLI batch, por lo que el requerimiento de tiempo real requiere nueva capa de orquestacion/eventos.
Se mantiene la politica local-only y costo bajo como restriccion transversal para la decision de UI.

## Input del Usuario (fuente principal)
- Se requiere UI (desktop o web).
- El microfono y permisos son parte critica del diseno.
- Se desea visualizacion en vivo de la reunion.
- Deben verse interlocutores en vivo.
- Al finalizar, la UI debe permitir reproducir audio, transcript y reportes.

## Componentes Implicados
- `main.py`: pipeline actual y comandos existentes a preservar.
- `handsome_transcribe/audio/recorder.py`: captura de audio y seleccion de dispositivo.
- `handsome_transcribe/transcription/whisper_transcriber.py`: transcripcion local y salida JSON.
- `handsome_transcribe/diarization/speaker_identifier.py`: etiquetado de speakers.
- `handsome_transcribe/reporting/report_generator.py`: archivos finales mostrables en UI.

## Flujo Actual
1. Record.
2. Transcribe.
3. Diarize.
4. Summarize.
5. Generate report.

## Dependencias
- Internas: modulos del pipeline actual.
- Externas: sounddevice, whisper, pyannote.audio, transformers opcional, reportlab, ffmpeg.

## Reglas y Restricciones
- Mantener modo gratuito/local como default.
- No romper CLI sin actualizar tests y README.
- Evitar acoplar UI de forma que degrade flujo batch existente.

## Riesgos de Regresion
- Introducir tiempo real sin desacoplar etapas puede romper estabilidad.
- Agregar UI sin abstraccion de servicio puede duplicar logica.

## Validacion Recomendada
- Automatizada: tests actuales del pipeline + tests de nueva capa de eventos.
- Manual: pruebas con microfono, permisos, sesion completa y reproduccion final.

## Preguntas Abiertas
- Target inicial: desktop Windows-only o web local multiplataforma.
- Grado de tiempo real esperado.
- Alcance de soporte para multiples microfonos.

## Referencia
- Ver detalle completo en `.context/active/ui-interface-research/feature-context.md`.

## Decision Matrix (2026-03-09)
- Matriz ponderada completada en `.context/active/ui-interface-research/decision-matrix.md`.
- Resultado: Desktop Python 86.0 vs Web Local 71.0 (escala 0-100).
- Recomendacion actual: iniciar Fase 1 con Desktop Python por prioridad de microfono/perifericos y menor friccion tecnica inicial.

## Implementation Plan (2026-03-09)
- Plan de arquitectura y componentes: `.context/active/ui-interface-research/implementation-plan.md`.
- Stack: PySide6, separacion UI + Application Services + Workers + Pipeline existente.
- MVP: sesion grabacion/transcripcion en vivo (bloque) + diarizacion + resumen + resultados reproducibles.
- 5 sprints incrementales propuestos, desde infraestructura hasta polish final.

## Development Plan (2026-03-09) - LISTO PARA EJECUCION
- Plan detallado por sprint: `.context/active/ui-interface-research/development-plan.md`.
- 5 sprints de 1 semana c/u: Sprint 1 (Infrastructure), Sprint 2 (UI Base), Sprint 3 (Audio Capture), Sprint 4 (Pipeline), Sprint 5 (Results+Polish).
- 85+ tests, min 80% coverage.
- Horas estimadas: 60-72 horas (3-4 semanas con 1 dev full-time).
- Criterios de aceptacion claros y medibles.
- Riesgos documentados y mitigaciones por sprint.
- Rollback plan definido.

## Estado Investigacion y Planificacion
- CERRADO: Investigacion de interfaz (feature context), decision matrix, implementation plan.
- ABIERTO: Ejecucion (requiere desarrollador).
- Contexto yplanes listos para coordinar con `implementator` o equipo de desarrollo.
