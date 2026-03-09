# Convenciones - HandsomeTranscribe

## Python

- Seguir PEP 8 y type hints en codigo nuevo.
- Mantener docstrings en funciones publicas.
- Preferir `pathlib.Path` sobre rutas string.
- Mensajes de error con contexto util (archivo, operacion).

## CLI

- Mantener consistencia en opciones cortas/largas y textos `help`.
- No romper comandos existentes sin actualizar README y tests.

## Testing

- Agregar o ajustar tests para cada cambio funcional.
- Priorizar pruebas por modulo (`audio`, `transcription`, `diarization`, `summarization`, `reporting`).

## Salidas

- Mantener formato estable de JSON de transcript y reportes.
- Evitar cambios breaking sin migracion documentada.
