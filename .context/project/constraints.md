# Constraints - HandsomeTranscribe

## Dependencias externas

- `ffmpeg` debe estar disponible en PATH para workflows de audio.
- Whisper y modelos HF pueden requerir descargas pesadas; considerar modo offline/no-transformers.
- Diarizacion con pyannote puede requerir `HF_TOKEN`.

## Rendimiento

- Modelos grandes de Whisper/Transformers incrementan tiempo y memoria.
- Evitar cargar modelos repetidamente cuando sea posible.

## Portabilidad

- Compatible con Windows/Linux/macOS usando `pathlib.Path`.
- No asumir separadores de ruta ni shells especificos en codigo Python.

## Robustez

- Validar existencia y legibilidad de archivos de entrada.
- Manejar transcript vacio sin romper resumen/reporte.
- Fallar con mensajes claros cuando falta token o dependencia opcional.
