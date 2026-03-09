# Matriz Final Costo-Calidad para CLI (Local-Only)

Date: 2026-03-09
Project: HandsomeTranscribe
Status: READY

## Objetivo
Definir perfiles operativos listos para ejecutar con el CLI actual, manteniendo transcripcion 100% local.

## Supuestos

- Se usan comandos existentes en main.py.
- No hay proveedores pagos activos en runtime.
- La diarizacion con pyannote requiere HF_TOKEN de forma opcional.

## Matriz Final

| Perfil | Costo estimado | Calidad esperada | Latencia | Dependencias externas | Uso recomendado |
|---|---:|---|---|---|---|
| Modo Gratis | 0 USD API | Media | Media | ffmpeg + Whisper local | Uso diario, pruebas, entornos publicos |
| Modo Low-Cost | 0 USD API | Media-Alta | Media | ffmpeg + Whisper local, HF opcional, transformers opcional | Produccion liviana con mejor calidad |
| Modo Calidad Alta | 0 USD API | Alta | Alta (mas lenta) | ffmpeg + Whisper local, HF opcional, transformers | Entregables finales y audios complejos |

## Perfiles listos (comandos CLI)

Notas:

- Reemplaza <AUDIO_WAV> y <TRANSCRIPT_JSON> por rutas reales.
- Los tres perfiles usan solo capacidades locales disponibles hoy.

### 1. Modo Gratis

Estrategia:

- Whisper local liviano (base).
- Resumen extractivo (--no-transformers).
- Reporte local en markdown/json.

Comandos:

```bash
python main.py transcribe <AUDIO_WAV> --model base
python main.py summarize <TRANSCRIPT_JSON> --no-transformers
python main.py generate-report <TRANSCRIPT_JSON> --title "Meeting" --no-transformers --format markdown --format json
```

Diarizacion opcional (si tienes HF_TOKEN):

```bash
python main.py diarize <AUDIO_WAV> --transcript <TRANSCRIPT_JSON>
```

### 2. Modo Low-Cost

Estrategia:

- Whisper local balanceado (small).
- Resumen con transformers segun recursos de hardware.
- PDF opcional.

Comandos:

```bash
python main.py transcribe <AUDIO_WAV> --model small
python main.py summarize <TRANSCRIPT_JSON>
python main.py generate-report <TRANSCRIPT_JSON> --title "Meeting" --format markdown --format json --format pdf
```

Diarizacion opcional:

```bash
python main.py diarize <AUDIO_WAV> --transcript <TRANSCRIPT_JSON>
```

### 3. Modo Calidad Alta

Estrategia:

- Whisper local de mayor calidad (medium o large).
- Resumen con transformers habilitado.
- Diarizacion opcional para mejorar legibilidad del acta.

Comandos:

```bash
python main.py transcribe <AUDIO_WAV> --model medium
python main.py diarize <AUDIO_WAV> --transcript <TRANSCRIPT_JSON>
python main.py summarize <TRANSCRIPT_JSON>
python main.py generate-report <TRANSCRIPT_JSON> --title "Meeting" --format markdown --format json --format pdf
```

Variante maxima calidad local:

```bash
python main.py transcribe <AUDIO_WAV> --model large
```

## Seleccion rapida

- Prioridad costo cero: Modo Gratis.
- Prioridad balance: Modo Low-Cost.
- Prioridad precision: Modo Calidad Alta.

## Estado de integraciones cloud

- OpenAI API: plan futuro (desactivado)
- Google: plan futuro (desactivado)
- Azure: plan futuro (desactivado)
- AWS: plan futuro (desactivado)

No hay uso activo de proveedores pagos en esta version del proyecto.
