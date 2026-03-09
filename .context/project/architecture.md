# Arquitectura HandsomeTranscribe

## Stack

- Python 3.10+
- CLI con Typer
- Salida de consola con Rich
- Transcripcion con Whisper
- Diarizacion con pyannote.audio
- Resumen con Transformers (fallback extractivo)
- Reportes con ReportLab
- Tests con Pytest

## Modulos

- `main.py`: comandos CLI y orquestacion del flujo.
- `handsome_transcribe/audio/`: captura de audio.
- `handsome_transcribe/transcription/`: conversion audio a texto.
- `handsome_transcribe/diarization/`: segmentacion por hablante.
- `handsome_transcribe/summarization/`: resumen y extraccion.
- `handsome_transcribe/reporting/`: exportacion de reportes.

## Flujo de datos

Audio -> Transcript -> Speaker labels -> Summary -> Report files

## Artefactos

- `outputs/audio/`
- `outputs/transcripts/`
- `outputs/reports/`
