# Investigacion: Implementacion MVP Desktop Python - PySide6

Date: 2026-03-09
Status: ACTIVE
Source Priority: DECISION_MATRIX > FEATURE_CONTEXT > CODEBASE

## Objetivo
Documentar estrategia tecnica y arquitectonico para implementar Fase 1 Desktop Python con PySide6.
Objetivo: sesion en vivo con captura, vista incremental, configuracion y reproduccion de resultados.

## Stack Propuesto

### Razon de PySide6 sobre CustomTkinter
- PySide6: Qt modern, soporte completo gestos/threads, mejor UX visual, familiar en industria.
- CustomTkinter: mas "lightweight", pero Qt no agrega complejidad significativa para MVP.
- Desicion: PySide6 como base.

### Dependencias nuevas a agregar
```
PySide6>=6.6.0
python-dotenv>=1.0.0  # Para manejo de env vars (HF_TOKEN, etc)
```

### Dependencias existentes reutilizadas
- modules: `handsome_transcribe/audio/`, `transcription/`, `diarization/`, `summarization/`, `reporting/`
- externos: `sounddevice`, `whisper`, `pyannote.audio`, `transformers`, `reportlab`, `ffmpeg`

## Arquitectura Propuesta

### Capas

```
┌─────────────────────────────────────────┐
│  UI Layer (PySide6)                     │
│  ├─ SessionWindow (main)                │
│  ├─ ConfigPanel                         │
│  ├─ LiveTranscriptView                  │
│  ├─ ResultsPanel                        │
│  └─ SettingsDialog                      │
└─────────────────────────────────────────┘
                    ▲
                    │ (signals/slots)
┌─────────────────────────────────────────┐
│  Application Service Layer              │
│  ├─ SessionManager                      │
│  ├─ EventBus (sesion events)            │
│  └─ ConfigManager                       │
└─────────────────────────────────────────┘
                    ▲
                    │ (metodos publicos)
┌─────────────────────────────────────────┐
│  Pipeline Workers (threads)             │
│  ├─ RecorderWorker                      │
│  ├─ TranscriberWorker                   │
│  ├─ DiarizerWorker                      │
│  ├─ SummarizerWorker                    │
│  └─ ReporterWorker                      │
└─────────────────────────────────────────┘
                    ▲
                    │ (importa modulos)
┌─────────────────────────────────────────┐
│  Pipeline Modules (existentes)          │
│  ├─ audio/recorder.py                   │
│  ├─ transcription/whisper_transcriber   │
│  ├─ diarization/speaker_identifier      │
│  ├─ summarization/meeting_summarizer    │
│  └─ reporting/report_generator          │
└─────────────────────────────────────────┘
```

## Componentes Principales

### 1. SessionManager (Orquestador)
Responsabilidad: gestionar ciclo de vida de sesion, coordinar workers, emitir eventos.

```
class SessionManager:
    - Estado: IDLE, RECORDING, TRANSCRIBING, DIARIZING, SUMMARIZING, COMPLETED, ERROR
    - Metodos:
      * start_session(config) -> Session
      * stop_recording()
      * get_live_updates() -> dict (transcript parcial, speakers detectados)
      * get_results() -> ResultsData
      * cancel_session()
    - Signals:
      * session_started
      * recording_progress
      * transcript_partial
      * speakers_detected
      * session_completed
      * session_error
```

### 2. EventBus (Notificacion en tiempo real)
Responsabilidad: emitir eventos de sesion para actualizar UI sin acoplamiento directo.

```
class EventBus (QObject):
    - Signals:
      * on_recording_frame(frames_count, duration_sec)
      * on_partial_transcript(segments)
      * on_speaker_update(speaker_map)
      * on_stage_progress(stage_name, percent)
      * on_session_complete(results_path)
      * on_error(error_msg, stage)
```

### 3. RecorderWorker (Thread)
Responsabilidad: captura de audio en background, emite eventos de progreso.

```
class RecorderWorker(QRunnable):
    - Hereda: sounddevice + Audio Recorder existente
    - Emite:
      * recording_frame_ready(frame_data, timestamp)
      * recording_stopped(audio_path)
      * audio_error(error_msg)
    - Maneja: seleccion de dispositivo, duracion/manual stop, volumen
```

### 4. LiveTranscriptView (Widget UI)
Responsabilidad: mostrar texto transcrito e interlocutores en vivo.

```
class LiveTranscriptView(QWidget):
    - Widgets:
      * QPlainTextEdit (transcript en vivo, no editable)
      * QLabel (speaker actual, coloreado)
      * QProgressBar (duracion sesion)
    - Actualiza:
      * on_partial_transcript(segments) -> append/update texto
      * on_speaker_update(speaker_map) -> actualiza label y propiedades de color
```

### 5. ConfigPanel (Widget UI)
Responsabilidad: seleccionar modo, modelos, opciones.

```
class ConfigPanel(QWidget):
    - QComboBox: Modelo Whisper (tiny, base, small, medium, large)
    - QCheckBox: Habilitar diarizacion (requiere HF_TOKEN)
    - QCheckBox: Habilitar resumen (usa transformers o fallback)
    - QLineEdit: Custom HF_TOKEN (opcional, carga de env fallback)
    - QComboBox: Dispositivo de audio (auto-poblado)
    - QLabel: Modo "Gratuito/Local" (status, no editable)
```

### 6. ResultsPanel (Widget UI)
Responsabilidad: mostrar y acceder a artefactos finales.

```
class ResultsPanel(QWidget):
    - TreeView:
      * Audio (reproducible con QPushButton "Play")
      * Transcript (mostrable en editor/modal)
      * Resumen (mostrable)
      * Reportes (JSON, Markdown, PDF)
    - Botones: Abrir carpeta outputs/, Copiar paths, Exportar
```

### 7. Storage/Session Model
Responsabilidad: serializar estado de sesion para permitir re-usar resultados.

```
@dataclass
class SessionData:
    - id: str (timestamp-based)
    - created_at: datetime
    - config: SessionConfig (modelo whisper, diarizacion, resumen)
    - audio_path: Path
    - transcript_path: Path
    - transcript_with_speakers_path: Path
    - summary: MeetingSummary (opcional)
    - reports: dict[str, Path] (md, json, pdf)
    - metadata: dict (speaker_count, duration_sec, etc)
```

## Flujo de Sesion (Interaccion)

### 1. Inicio (Usuario abre app)
1. UI: SessionWindow carga ConfigPanel.
2. ConfigPanel: auto-detecta dispositivos de audio, carga HF_TOKEN de env.
3. Usuario: selecciona configuracion.

### 2. Grabacion (Usuario presiona "Iniciar")
1. UI: SessionWindow emite `start_session(config)`.
2. SessionManager: valida config, crea RecorderWorker en thread.
3. RecorderWorker: comienza grabacion, emite progress cada N frames.
4. UI: LiveTranscriptView actualiza duracion.

### 3. Detener (Usuario presiona "Detener")
1. UI: SessionManager.stop_recording().
2. RecorderWorker: finaliza grabacion, guarda WAV, emite `recording_stopped(path)`.
3. SessionManager: dispara TranscriberWorker (inmediato).

### 4. Transcripcion (Batch)
1. TranscriberWorker: carga Whisper, llama `whisper_transcriber.transcribe(audio_path)`.
2. Emite: `transcript_ready(Transcript)`.
3. EventBus: notifica LiveTranscriptView.
4. UI: muestra transcript completo con speakers = "Unknown".
5. SessionManager: decide si diarizar basado en config.

### 5. Diarizacion (Batch, si enabled)
1. DiarizerWorker: carga pyannote, llama `speaker_identifier.diarize(audio_path)`.
2. Emite: `diarization_complete(diarized_segments)`.
3. SessionManager: llama `speaker_identifier.assign_speakers(transcript, diarized_segments)`.
4. UI: LiveTranscriptView re-renderiza con speaker labels.

### 6. Resumen (Batch, si enabled)
1. SummarizerWorker: carga Transformers (o fallback), resumen.
2. Emite: `summary_ready(MeetingSummary)`.
3. UI (opcional): muestra preview en ResultsPanel.

### 7. Reportes (Batch)
1. ReporterWorker: llama `report_generator.generate(transcript, summary, title="Session-{id}")`.
2. Genera: md, json, pdf en `outputs/reports/`.
3. Emite: `reports_ready(dict[str, Path])`.
4. UI: ResultsPanel poblada con archivos.

### 8. Resultados (Usuario revisa)
1. UI: ResultsPanel muestra artefactos.
2. Usuario: puede reproducir audio, leer transcript, abrir PDFs, etc.
3. Boton "Nueva sesion" -> vuelve a paso 1.

## Consideraciones Tecnicas

### Thread Safety
- Whisper/Transformers/pyannote son CPU-bound: deben correr en threads separados.
- UI updates deben ocurrir en main thread: usar `pyqtSignal` para emitir desde workers.
- Usar `QThreadPool` para gestionar workers.

### Manejo de Errores
- Cada worker emite señal de error con contexto (stage, mensaje).
- SessionManager captura y decide: reintentar, cancelar o notificar usuario.
- UI muestra dialog de error con boton "Reintentar" o "Cancelar sesion".

### Configuracion Persistente
- `~/.config/handsome_transcribe/` (cross-platform con `QStandardPaths`).
- Guardar: modelo Whisper default, HF_TOKEN (encriptado o desde env).
- Cargar: config al abrir app.

### Latencia Objetivo
- Captura+Transcripcion: batch, sin latencia estricta.
- UI update de partial transcript: cada 2-5 seg (cuando termina nuevo segmento Whisper).
- Speaker update: cuando completa diarizacion o re-score en background.

## Vista "En Vivo" - Opciones

### Opcion A: "Vivo-simulado" (MVP realista)
1. Grabar 30 seg de audio.
2. Transcribir ese bloque.
3. Mostrar en UI simulando scroll incremental.
4. Repetir para siguientes 30 seg.
5. Ventaja: reusa pipeline perfecto, UI refresca visualmente cada bloque.
6. Desventaja: latencia visible de ~30 seg.

### Opcion B: "Vivo-real" con streaming (futuro)
1. Capturar chunks de 1-2 seg.
2. Transcribir en background de forma incremental.
3. Diarizar segmentos parciales.
4. Mostrar palabra a palabra.
5. Ventaja: UX premium.
6. Desventaja: precision y estabilidad bajan; requiere refactor profundo del pipeline.

**Recomendacion para MVP: Opcion A** (bloque cada 30-60seg).

## Archivos a Crear/Modificar

### Nuevos archivos
- `handsome_transcribe/ui/` (paquete nuevo)
  * `__init__.py`
  * `main_window.py` (SessionWindow)
  * `config_panel.py` (ConfigPanel)
  * `live_view.py` (LiveTranscriptView)
  * `results_panel.py` (ResultsPanel)
  * `workers.py` (RecorderWorker, TranscriberWorker, etc)
  * `event_bus.py` (EventBus)
  * `session_manager.py` (SessionManager)
  * `models.py` (@dataclass SessionData, SessionConfig)
  * `styles.py` (QSS stylesheets)
- `desktop_app.py` (punto de entrada: `if __name__ == "__main__"`)
- `setup.py` o actualizar `requirements.txt` con PySide6

### Cambios minimos en existentes
- `run_venv_desktop.ps1` (script para lanzar desktop desde venv en Windows)

### Preservar
- `main.py` (CLI existente, sin cambios)
- Pipeline modules bajo `handsome_transcribe/{audio,transcription,diarization,summarization,reporting}/`

## Testing Strategy

### Unit Tests (pytest)
- `tests/ui/test_session_manager.py`: mock workers, validar transiciones de estado.
- `tests/ui/test_event_bus.py`: validar emision de signals.
- `tests/ui/test_models.py`: serialization/deserialization de SessionData.

### Integration Tests
- `tests/ui/test_flow_end_to_end.py`: simular flujo completo con archivos reales.

### Manual Tests
- Grabar 10 seg, validar transcripcion partial.
- Habilitar diarizar, validar speaker labels.
- Reproducir audio desde UI.
- Abrir PDF desde UI.

## Dependencias de Terceros a Revisar

### PySide6
- Instalacion facil con pip.
- Compatible con Python 3.10+.
- Documentacion excelente.

### pyaudio vs sounddevice
- Actual: sounddevice (mejor mantenimiento).
- Mantener para captura.

### Configuracion Storage
- QSettings (nativo Qt, cross-platform).
- Alternativa: configparser + archivos YAML.
- Recomendacion: QSettings por simplicity.

## Riesgos y Mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Acople UI-pipeline rompe CLI | Extraer SessionManager como servicio reutilizable; CLI y UI llaman servicios. |
| Threads/GIL ralentizan UI | Usar QThreadPool, mantener main thread limpio de I/O pesado. |
| HF_TOKEN requerido en diarizacion | Hacer diarizacion completamente opcional; validar token antes de activar checkbox. |
| Whisper/Transformers grandes descargan lentamente | Mostrar splash screen con progreso; cachear modelos en ~/.cache/huggingface. |
| Usuario intenta detener mientras se procesa | Agregar estado CANCELLING, permitir cancelacion soft en cada stage. |
| Audio corrompido o ruidoso | Validar WAV antes de transcribir; mostrar advertencia. |

## Preguntas Abiertas

1. **Duracion inicial de sesion**: ¿usuario detiene manualmente, o hay timeout/limite?
2. **Multi-microfono**: ¿seleccionar uno al inicio, o durante sesion?
3. **Soporte offline**: ¿si HF_TOKEN no disponible, permitir diarizacion local (sin pyannote)?
4. **Reproduccion de audio**: ¿integrada en app (QMediaPlayer) o abrir con player del SO?
5. **Historico de sesiones**: ¿guardar lista de sesiones pasadas para re-abrir?
6. **Update de modelos**: ¿permitir descargar nuevos modelos desde UI?
7. **Resolucion inicial**: ¿tamano ventana recomendado, responsive o fixed?

## Criterio de Salida (MVP Completo)

El MVP se considera completo cuando:
1. SessionWindow carga, ConfigPanel funciona.
2. Grabar 10 seg, detener, ver transcript en vivo.
3. Trigger diarizacion si enabled, speakers visibles.
4. Outputs (audio, transcript, reportes) accesibles desde ResultsPanel.
5. Tests de SessionManager y flujo E2E pasan.
6. CLI original intacto y tests pasando.
7. README actualizado con instrucciones de lanzar desktop.

## Plan de Implementacion Incremental

### Sprint 1: Infraestructura
- Crear estructura `/ui/`.
- Implementar EventBus y models.
- Escribir SessionManager basico.
- Tests de models y event bus.

### Sprint 2: UI Base
- SessionWindow y ConfigPanel.
- Estilo QSS minimo.
- Integrar ConfigPanel con SessionManager.

### Sprint 3: Captura de Audio
- RecorderWorker integrado.
- LiveTranscriptView basico.
- Botones Iniciar/Detener.

### Sprint 4: Pipeline
- TranscriberWorker.
- DiarizerWorker (si token disponible).
- SummarizerWorker.
- ReporterWorker.

### Sprint 5: Resultados y Polish
- ResultsPanel funcional.
- Reproduccion de audio.
- Tests E2E.
- Documentacion.

---

## Referencia

- Documentacion PySide6: https://doc.qt.io/qtforpython/
- Ejemplo threading en Qt: https://wiki.qt.io/QThread_Recommended_Usage
- Actual pipeline: `handsome_transcribe/` (modules y `main.py`)
