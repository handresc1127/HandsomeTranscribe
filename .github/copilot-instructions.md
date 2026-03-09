# Contexto del Proyecto HandsomeTranscribe

Este es un proyecto personal de handresc1127.
No existe proyecto Jira asociado ni dependencia de flujos Jira.

## Contexto canonico

Leer primero:
- `.context/project/architecture.md`
- `.context/project/patterns.md`
- `.context/project/conventions.md`
- `.context/project/constraints.md`

## Agentes oficiales (unicos)

- coordinator
- context-builder
- reasearch-codebase
- research-verifier
- plan-creator
- plan-verification
- implementator

## Stack

- Python 3.10+
- Typer (CLI)
- Rich (console)
- Whisper (transcripcion)
- pyannote.audio (diarizacion)
- Transformers opcional (resumen)
- ReportLab (PDF)
- Pytest (tests)

## Reglas base

- No romper comandos CLI existentes sin actualizar tests y README.
- Usar `pathlib.Path` para paths cross-platform.
- Mantener mensajes de error claros por etapa del pipeline.
- Preferir cambios pequenos con pruebas por modulo.
