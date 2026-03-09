# Referencia Rapida - HandsomeTranscribe

## Que hace el proyecto

HandsomeTranscribe graba reuniones, transcribe audio con Whisper, identifica hablantes y genera reportes.

## Comandos CLI

```bash
python main.py record
python main.py transcribe outputs/audio/archivo.wav
python main.py diarize outputs/audio/archivo.wav
python main.py summarize outputs/transcripts/archivo_transcript.json
python main.py generate-report outputs/transcripts/archivo_transcript.json --title "Meeting"
```

## Flujo recomendado

1. Grabar o preparar audio.
2. Transcribir audio.
3. Ejecutar diarizacion.
4. Generar resumen.
5. Exportar reportes.

## Rutas clave

- `handsome_transcribe/audio/recorder.py`
- `handsome_transcribe/transcription/whisper_transcriber.py`
- `handsome_transcribe/diarization/speaker_identifier.py`
- `handsome_transcribe/summarization/meeting_summarizer.py`
- `handsome_transcribe/reporting/report_generator.py`
- `tests/`

## Criterios de calidad

- Mantener compatibilidad de la CLI.
- Manejar entradas vacias o archivos invalidos con errores claros.
- Evitar cambios de API sin actualizar tests y README.
- Priorizar rutas con `pathlib.Path` para cross-platform.
