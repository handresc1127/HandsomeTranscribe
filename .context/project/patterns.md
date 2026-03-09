# Patrones - HandsomeTranscribe

## Patrones usados

- Pipeline por etapas: audio -> transcripcion -> diarizacion -> resumen -> reporte.
- Dataclasses para modelos de intercambio (`Transcript`, `TranscriptSegment`, `MeetingSummary`).
- Lazy loading de modelos pesados (Whisper, Transformers) para reducir costo inicial.
- Fallback strategy: resumen por transformer con alternativa extractiva.

## Buenas practicas

- Interfaces claras entre modulos.
- Serializacion estable a JSON.
- Manejo de errores explicito por etapa.
