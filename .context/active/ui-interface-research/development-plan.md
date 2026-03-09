# Plan de Desarrollo: MVP Desktop Python - PySide6

Date: 2026-03-09
Status: READY_FOR_EXECUTION
Source Priority: IMPLEMENTATION_PLAN > DECISION_MATRIX

## Resumen Ejecutivo

Implementar Fase 1 Desktop Python con interfaz gráfica PySide6 para HandsomeTranscribe.
MVP: **sesión única activa** con grabación en vivo con **multi-threading** (RecorderWorker + TranscriberWorker + SpeakerEmbeddingWorker en paralelo), transcripción incremental en tiempo real, reconocimiento de speakers con voice embeddings, **auto-guardado progresivo cada 2 minutos máximo** (triggers: cambio de speaker, pausa, finalización), diarizacion, resumen y reproducción de resultados.
5 sprints de desarrollo incremental, totalizando ~65-80 horas de implementación estimadas.
Estrategia: arquitectura limpia (capas desacopladas) con **SQLite para persistencia** (sessions, speakers, embeddings) que preserve CLI existente.
**Restricciones críticas:** Una sola sesión activa a la vez, no cerrar app durante grabación, auto-guardado frecuente para evitar pérdida de datos, exportación pospuesta para versión futura.

## Estado Actual

- ✅ CLI funcional con pipeline batch (`main.py`)
- ✅ Modulos core: audio/, transcription/, diarization/, summarization/, reporting/
- ✅ Tests unitarios por modulo (`tests/test_*.py`)
- ⚠️ Sin UI gráfica
- ⚠️ Sin capa de orquestación/eventos para tiempo real
- ⚠️ Sin persistencia SQLite para sesiones y speakers
- ⚠️ Sin reconocimiento de speakers con embeddings
- ⚠️ Sin funcionalidad pause/resume

## Meta Final

Al terminar Sprint 5:
- ✅ Desktop app con SessionWindow funcional con 4 tabs: Session (principal), Configuration, Interlocutores, Sesiones
- ✅ **Una sola sesión activa a la vez** (no permitir múltiples sesiones simultáneas)
- ✅ Grabar audio, transcribir y reconocer speakers en **tiempo real y paralelo** (multi-threading)
- ✅ **Auto-guardado progresivo** cada 2 minutos máximo con triggers en: cambio de speaker, pausa, finalización
- ✅ **Voice embeddings** para identificación automática de speakers (>=98% confianza) e incremental enrichment
- ✅ **SQLite database** con 4 tablas: sessions, speakers, session_speakers, transcript_segments
- ✅ **Pause/Resume** durante grabación sin perder contexto (trigger de auto-guardado)
- ✅ **Speaker Library** (tab Interlocutores) para gestionar perfiles con avatares, nombres, tags
- ✅ **Contexto de sesión opcional** (textarea markdown/texto plano): "Hoy hablaremos sobre..." guardado en SQLite para futuro uso con LLM API
- ✅ ConfigPanel con selección de modelos y opciones
- ✅ ResultsPanel con reproducción de audio y acceso a reportes
- ✅ CLI original intacto y tests pasando
- ✅ README actualizado con instrucciones de lanzamiento
- ⏸️ **Exportación de sesión completa pospuesta** para versión futura (no en MVP)
- 🔮 **Uso de contexto con LLM API** para mejorar transcripción/resumen pospuesto para versión futura (contexto se guarda pero no se usa en MVP)

---

## Sprint 1: Infraestructura (Semana 1)

### Objetivo
Establecer capa de servicios y modelos sin UI gráfica. Base para sprints posteriores.

### Tareas

#### 1.1 Crear estructura de directorio
**Responsable:** developer
**Duración:** 1 hora
**Entregables:**
```
handsome_transcribe/ui/
├── __init__.py
├── models.py
├── database.py          # NEW: SQLite schema y ORM
├── speaker_manager.py  # NEW: gestión de speakers y embeddings
├── event_bus.py
├── session_manager.py
├── config_manager.py
├── workers.py
├── exceptions.py
└── constants.py

outputs/
├── sessions/
│   ├── session_20260325_143000/   # Formato: session_YYYYMMDD_HHMMSS
│   │   ├── recording.wav          # Audio final completo
│   │   ├── transcript.txt         # Transcripción final
│   │   ├── summary.md             # Resumen final (si generado)
│   │   ├── metadata.json          # Metadatos de sesión
│   │   └── temp/                  # Archivos temporales
│   │       ├── part1.wav          # Grabaciones parciales (auto-guardado)
│   │       ├── part2.wav
│   │       └── ...
│   └── session_20260325_150000/
├── reports/                       # Reportes generados (PDF, MD, JSON)
└── audio/                         # DEPRECATED: migrar a sessions/
```
**Verificacion:**
```bash
cd handsome_transcribe/ui/
ls -la
# Debe existir cada archivo .py
```

#### 1.2 Implementar models.py (dataclasses)
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** 1.1
**Entregables:**
- `SessionConfig`: modelo de configuración (modelo_whisper, habilitar_diarizacion, habilitar_resumen, dispositivo_audio, hf_token, **session_context: Optional[str]**)  # NEW: contexto previo opcional en markdown/texto plano
- `SessionData`: modelo de sesión con estructura de paths:
  - `id: int`
  - `created_at: datetime`
  - `session_dir: Path` (ej: `outputs/sessions/session_20260325_143000/`)
  - `recording_path: Path` (`session_dir / "recording.wav"`) - audio final completo
  - `transcript_path: Path` (`session_dir / "transcript.txt"`)
  - `summary_path: Optional[Path]` (`session_dir / "summary.md"`)
  - `metadata_path: Path` (`session_dir / "metadata.json"`)
  - `temp_dir: Path` (`session_dir / "temp/"`) - para archivos parciales (part1.wav, part2.wav, ...)
  - `config: SessionConfig`
  - `state: SessionState`
  - `session_context: Optional[str]`
  - `partial_audio_count: int` (contador para part1.wav, part2.wav, ...)
- `SessionState`: enum (IDLE, RECORDING, **PAUSED**, TRANSCRIBING, DIARIZING, SUMMARIZING, COMPLETED, ERROR)
- `TranscriptSegmentData`: modelo serializable de segmento
- **`SpeakerProfile`**: modelo de speaker (id, name, avatar_path, voice_embedding_blob, tags, created_at, last_seen)
- **`SpeakerMatch`**: modelo de matching (confidence: float, speaker_id: int, is_new: bool)
- **`SessionSpeaker`**: relación session-speaker (session_id, speaker_id, segments_count, total_duration_sec)
**Criterio de Éxito:**
```bash
pytest tests/ui/test_models.py -v
# Todos los tests de serialization/deserialization pasan
# Tests de SpeakerProfile con embeddings
# Tests de SessionConfig con session_context opcional
```

#### 1.3 Implementar database.py (SQLite schema)
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** 1.1, 1.2
**Entregables:**
- Clase `Database` con SQLite connection pool
- Schema con 4 tablas:
  ```sql
  CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,   -- Timestamp formato YYYYMMDD_HHMMSS
    session_dir TEXT NOT NULL,  -- Path completo: outputs/sessions/session_20260325_143000/
    state TEXT NOT NULL,
    recording_path TEXT,        -- session_dir/recording.wav
    transcript_path TEXT,       -- session_dir/transcript.txt
    summary_path TEXT,          -- session_dir/summary.md (opcional)
    context_text TEXT,          -- Contexto previo opcional (markdown/texto plano)
    config_json TEXT,
    metadata_json TEXT
  );
  
  CREATE TABLE speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    avatar_path TEXT,
    voice_embedding BLOB,  -- numpy array serializado
    tags TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    last_seen TEXT
  );
  
  CREATE TABLE session_speakers (
    session_id INTEGER NOT NULL,
    speaker_id INTEGER NOT NULL,
    segments_count INTEGER DEFAULT 0,
    total_duration_sec REAL DEFAULT 0.0,
    PRIMARY KEY (session_id, speaker_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (speaker_id) REFERENCES speakers(id)
  );
  
  CREATE TABLE transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    speaker_id INTEGER,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (speaker_id) REFERENCES speakers(id)
  );
  ```
- Métodos CRUD para cada tabla
- `get_or_create_speaker(embedding, threshold=0.98) -> SpeakerProfile`
- `update_speaker_embedding(speaker_id, new_embedding)` para incremental enrichment
- Migrations basico (version 1)
**Criterio de Éxito:**
```bash
pytest tests/ui/test_database.py -v
# Tests CRUD, constraints, y matching de embeddings
```

#### 1.4 Implementar speaker_manager.py
**Responsable:** developer
**Duración:** 3 horas
**Dependencia:** 1.1, 1.2, 1.3
**Entregables:**
- Clase `SpeakerManager`:
  - `match_speaker(embedding: np.ndarray, threshold_auto=0.98, threshold_review=0.60) -> SpeakerMatch`
  - Lógica de matching:
    - confidence >= 98%: auto-identificar speaker existente
    - 60% <= confidence < 98%: marcar para review manual
    - confidence < 60%: crear nuevo speaker
  - `enrich_embedding(speaker_id, new_embedding)`: promedia embeddings para enriquecimiento incremental
  - `create_speaker(name, embedding, avatar=None) -> SpeakerProfile`
  - `get_all_speakers() -> list[SpeakerProfile]`
  - `update_speaker(speaker_id, **kwargs)`
- Cosine similarity para comparación de embeddings
- Avatar auto-generation (iniciales + color aleatorio)
**Criterio de Éxito:**
```bash
pytest tests/ui/test_speaker_manager.py -v
# Tests de matching, enrichment, y avatar generation
```

#### 1.5 Implementar event_bus.py
**Responsable:** developer
**Duración:** 2.5 horas
**Dependencia:** 1.1, 1.2
**Entregables:**
- Clase `EventBus(QObject)` con signals:
  - `recording_frame_ready(int frames_count, float duration_sec)`
  - `recording_paused(float duration_at_pause)`  # NEW
  - `recording_resumed(float duration_at_resume)`  # NEW
  - `partial_transcript_ready(list segments)`  # Emitido en tiempo real
  - `speaker_identified(int speaker_id, str name, float confidence)`  # NEW
  - `speaker_needs_review(int temp_id, float confidence, bytes embedding)`  # NEW
  - `speaker_update_ready(dict speaker_map)`
  - `stage_progress(str stage_name, int percent)`
  - `session_completed(dict results)`
  - `session_error(str error_msg, str stage)`
**Criterio de Éxito:**
```bash
pytest tests/ui/test_event_bus.py -v
# Signals emiten y listeners reciben correctamente
# Tests para nuevas signals de pause/resume y speaker recognition
```

#### 1.6 Implementar session_manager.py (con multi-threading y auto-guardado)
**Responsable:** developer
**Duración:** 6 horas
**Dependencia:** 1.1, 1.2, 1.3, 1.4, 1.5
**Entregables:**
- Clase `SessionManager(QObject)` con:
  - `__init__(config: SessionConfig, event_bus: EventBus, database: Database, speaker_mgr: SpeakerManager)`
  - `start_session() -> SessionData` # **Valida que no haya sesión activa previa + crea estructura de directorios**
    - Crear directorio de sesión: `outputs/sessions/session_{timestamp}/` donde timestamp es `YYYYMMDD_HHMMSS`
    - Crear subdirectorio `temp/` para archivos parciales
    - Inicializar SessionData con paths correctos (recording.wav, transcript.txt, summary.md, metadata.json)
    - Guardar sesión inicial en Database con session_dir
  - `pause_recording()` # NEW: pause sin detener workers + **trigger auto-guardado + guarda audio parcial**
  - `resume_recording()` # NEW: continua desde donde quedó
  - `stop_recording()` # Finaliza y dispara procesamiento + **auto-guardado final + consolida audio parcial a recording.wav**
  - `get_current_state() -> SessionState`
  - `cancel_session()`
  - **Multi-threading architecture:**
    - RecorderWorker: captura audio en background (thread 1), guarda archivos parciales en temp/
    - TranscriberWorker: transcribe chunks en paralelo a grabación (thread 2)
    - SpeakerEmbeddingWorker: extrae embeddings y reconoce speakers en paralelo (thread 3)
  - Transiciones de estado validadas (IDLE -> RECORDING -> PAUSED <-> RECORDING -> TRANSCRIBING -> ... -> COMPLETED)
  - **Restricción de sesión única:** `start_session()` verifica que no exista sesión activa (state != IDLE), lanza excepción si intenta iniciar múltiples
  - Manejo de errores por etapa (emit session_error)
  - Buffer management para chunks de audio (10-30 seg enviados a transcriber/embedder)
  - **Auto-guardado progresivo:**
    - QTimer con intervalo de 2 minutos (120,000 ms) para guardado periódico
    - Triggers adicionales de guardado inmediato:
      - Al detectar cambio de speaker activo (`_on_speaker_change()`)
      - Al pausar grabación (`pause_recording()`)
      - Al finalizar sesión (`stop_recording()`)
    - Método `_auto_save_progress()`: guarda estado actual de sesión, transcripts acumulados, speakers identificados a SQLite sin interrumpir grabación
    - **Guarda audio parcial**: `temp/part{N}.wav` donde N es contador incremental (part1.wav, part2.wav, ...)
    - **Al finalizar**: consolida todos los archivos parciales en `recording.wav` final
- Métodos privados:
  - `_transition_state(new_state)` con validacion
  - `_create_session_directory(timestamp: str) -> Path`: crea `outputs/sessions/session_{timestamp}/` + `temp/`
  - `_on_audio_chunk_ready(chunk_data)`: dispatcher para TranscriberWorker y SpeakerEmbeddingWorker
  - `_on_transcript_chunk_ready(segments)`: emit partial_transcript_ready + **verifica cambio de speaker**
  - `_on_speaker_embedding_ready(embedding)`: match con SpeakerManager y emit signals
  - `_on_speaker_change(old_speaker_id, new_speaker_id)`: **trigger auto-guardado**
  - `_auto_save_progress()`: **guarda sesión actual a SQLite (UPDATE sessions, INSERT transcript_segments) + guarda audio parcial temp/partN.wav**
  - `_consolidate_partial_audio()`: **concatena temp/part*.wav en recording.wav final al terminar sesión**
  - `_start_autosave_timer()`: inicia QTimer de 2 minutos
  - `_stop_autosave_timer()`: detiene QTimer
**Criterio de Éxito:**
```bash
pytest tests/ui/test_session_manager.py -v
# Transiciones de estado correctas
# Pause/resume sin pérdida de datos
# Multi-threading sin race conditions
# Auto-guardado se dispara cada 2 minutos
# Auto-guardado se dispara en cambio de speaker
# Auto-guardado se dispara en pause
# Validación de sesión única (error si intenta start_session() con sesión activa)
# Mock workers, no dependencia real de audio
```

#### 1.7 Implementar config_manager.py
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** 1.1, 1.2
**Entregables:**
- Clase `ConfigManager`:
  - `load_config() -> SessionConfig` (from QSettings + env vars)
  - `save_config(config: SessionConfig)`
  - `get_audio_devices() -> list[dict]`
  - `validate_hf_token(token: str) -> bool`
  - `validate_whisper_model(model: str) -> bool`
- Cross-platform config dir (`~/.config/handsome_transcribe/` via `QStandardPaths`)
- Defaults sensatos (modelo base, diarizacion off por defecto, token from env)
**Criterio de Éxito:**
```bash
pytest tests/ui/test_config_manager.py -v
# Config persiste, carga, valida sin errores
```

#### 1.8 Implementar workers.py (con SpeakerEmbeddingWorker)
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** 1.1, 1.2, 1.3, 1.4, 1.5
**Entregables:**
- Clases base para workers (QRunnable):
  - `RecorderWorker`: 
    - Captura audio en background, emite progress
    - Genera chunks de audio cada 10-30 seg para procesamiento paralelo
    - **Guarda audio parcial** en `temp/partN.wav` cuando se llama `save_partial()` (durante auto-guardado, pause)
    - **Buffer acumulativo**: mantiene audio completo en memoria para consolidación final
    - Al finalizar: guarda audio completo en `recording.wav`
  - `TranscriberWorker`: **procesa chunks en paralelo**, emite partial_transcript_ready en tiempo real
  - **`SpeakerEmbeddingWorker` (NEW):** extrae embeddings de chunks de audio, llama a SpeakerManager.match_speaker(), emite speaker_identified o speaker_needs_review
  - `DiarizerWorker`: (batch post-grabación) emite speaker map placeholder
  - `SummarizerWorker`: (batch post-grabación) emite summary placeholder
  - `ReporterWorker`: (batch post-grabación) emite paths placeholder
- Cada worker conectado a EventBus para emitir signals
- Thread safety con QMutex para acceso a buffers compartidos
- RecorderWorker genera chunks y los enqueue para TranscriberWorker y SpeakerEmbeddingWorker
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py -v
# Test multi-threading con mocks (RecorderWorker -> TranscriberWorker + SpeakerEmbeddingWorker paralelos)
# Test RecorderWorker.save_partial() guarda temp/partN.wav sin detener grabación
# Test consolidación de archivos parciales en recording.wav final
```

#### 1.9 Agregar PySide6 a requirements.txt
```

#### 1.7 Agregar PySide6 a requirements.txt
**Responsable:** developer
**Duración:** 30 min
**Entregables:**
```
PySide6>=6.6.0
python-dotenv>=1.0.0
```
**Criterio de Éxito:**
```bash
pip install -r requirements.txt
python 10 Crear tests unitarios para infraestructura
**Responsable:** QA
**Duración:** 5 horas
**Dependencia:** 1.1-1.9
**Entregables:**
```
tests/ui/
├── __init__.py
├── conftest.py (fixtures)
├── test_models.py
├── test_database.py         # NEW: CRUD, embeddings matching, migrations
├── test_speaker_manager.py  # NEW: matching logic, enrichment, avatar gen 
├── test_event_bus.py
├── test_session_manager.py  # NEW: agregar tests de auto-guardado y sesión única
├── test_config_manager.py
└── test_workers.py
```
**Tests críticos de session_manager.py:**
- `test_autosave_timer_triggers_every_2_minutes()`: verifica QTimer dispara auto-guardado
- `test_autosave_on_speaker_change()`: verifica guardado al cambiar speaker activo
- `test_autosave_on_pause()`: verifica guardado al pausar
- `test_autosave_on_finalize()`: verifica guardado al finalizar
- `test_single_session_validation()`: verifica que start_session() lanza excepción si sesión activa
- `test_no_data_loss_on_autosave()`: verifica que auto-guardado no corrompe datos
**Criterio de Éxito:**
```bash
pytest tests/ui/ -v
# Min 80% cobertura en ui/
# Todos los tests pasan
# Tests de SQLite y speaker matching funcionan
# Tests de auto-guardado y sesión única pasan
```

### Validacion de Sprint 1

#### Automatizada
```bash
# Correr todos los tests UI
pytest tests/ui/ -v --cov=handsome_transcribe/ui --cov-fail-under=80

# Verificar que CLI original no se rompe
pytest tests/ -v -k "not ui"
```

#### Manual
- [ ] Crear instancia de SessionManager con config mock
- [ ] Emitir events manualmente, verificar que signals se reciben
- [ ] Validate serialization de SessionData a JSON y viceversa

### Riesgos Sprint 1

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|---|---|---|
| PySide6 incompatibilidad en Windows | Baja | Alto | Probar en Windows early, usar versión moderna |
| Acople entre SessionManager y workers | Media | Medio | Usar EventBus como mediador, mock workers |
| Tests complejos para mocks | Media | Bajo | Usar pytest-mock, factory fixtures |
| Pérdida de datos si cierre inesperado | Media | Alto | **MITIGADO:** Auto-guardado cada 2 min + triggers en eventos clave |
| Auto-guardado bloquea grabación | Baja | Medio | Ejecutar auto-guardado en thread separado, no bloquear RecorderWorker |

### Criterio de Salida Sprint 1
- ✅ Todos los tests UI pasan
- ✅ CLI original sin cambios, tests pasando
- ✅ Estructura modular clara sin UI gráfica
- ✅ SessionManager lista para ser usada por UI layer

---

## Sprint 2: UI Base (Semana 2)

### Objetivo
Construir ventanas principales con 4 tabs y paneles. Integración con SessionManager y SpeakerManager.

### Tareas

#### 2.1 Implementar SessionWindow (main window con sesión única)
**Responsable:** developer
**Duración:** 5 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `SessionWindow(QMainWindow)`:
  - Central widget con 4 tabs: **Session (principal)**, Configuration, Interlocutores, Sesiones
  - Menu bar: File (New, ~~Open~~, Exit), Help (About, Docs) # **Open removido: sesión única**
  - Status bar con estado actual (IDLE, RECORDING, PAUSED, etc.) + **indicador de última auto-guardado**
  - Inicializa SessionManager, Database, SpeakerManager en background
  - Conecta signals del SessionManager a slots de panels
  - **Validación de sesión única:**
    - Verifica estado de SessionManager antes de permitir "Iniciar Sesión"
    - Si existe sesión activa (RECORDING/PAUSED), muestra warning y bloquea inicio de nueva
    - Slot `on_close_event()` con advertencia si sesión en progreso (RECORDING/PAUSED): "¿Seguro que deseas salir? Datos no guardados podrían perderse" (aunque auto-guardado minimiza riesgo)
  - Slot `on_autosave_triggered()`: actualiza status bar con timestamp de último guardado
- Tamaño inicial: 1200x800, resizable, centrado en pantalla
- Icono de app (placeholder)
**Criterio de Éxito:**
```bash
python desktop_app.py
# Ventana abre sin crashes
# Puede cambiar entre 4 tabs
# Status bar visible con estado actual
```

#### 2.2 Implementar ConfigPanel (tab Configuration)
**Responsable:** developer
**Duración:** 3.5 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `ConfigPanel(QWidget)`:
  - QComboBox: Modelo Whisper (tiny, base, small, medium, large)
  - QCheckBox: Habilitar diarizacion + QLineEdit HF_TOKEN (read-only desde env)
  - QCheckBox: Habilitar resumen
  - QComboBox: Dispositivo de audio (auto-poblado de `ConfigManager.get_audio_devices()`)
  - **QLabel: "Contexto de sesión (opcional)"**  # NEW
  - **QTextEdit: textarea para contexto previo** (acepta markdown/texto plano, placeholder: "Hoy hablaremos sobre...")  # NEW
  - **QLabel (help text): "Este contexto puede mejorar transcripción/resumen con LLM API (funcionalidad futura)"** (fuente pequeña, gris)  # NEW
  - QLabel: "Modo Gratuito/Local" (status, coloreado verde)
  - QPushButton: "Iniciar Sesión"
- Cargar configuracion default desde ConfigManager
- **Leer session_context de QTextEdit (opcional, puede estar vacío)**
- Guardar selecciones al presionar "Iniciar Sesión" (incluir session_context en SessionConfig)
- Validar antes de permitir inicio (ej: si diarizacion checked, verificar token)
**Criterio de Éxito:**
```bash
python desktop_app.py
# ConfigPanel visible en tab Configuration
# Combos y checkboxes funcionales
# "Iniciar Sesion" disabled si config invalida
```

#### 2.3 Implementar LiveSessionView (tab Session - principal)
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `LiveSessionView(QWidget)`:
  - **Multiple speaker avatars** con QHBoxLayout: cada speaker visible con avatar (icono + label), **speaker activo resaltado**
  - QPlainTextEdit (read-only) para transcript en vivo con scroll automático
  - QProgressBar para duracion de sesion
  - QPushButton: **"Pause"** (alterna con "Resume") # NEW
  - QPushButton: "Finalizar" (antes "Detener Grabación")
  - QLabel para stage actual (ej "Transcribiendo...")
- Slots conectados a EventBus:
  - `on_partial_transcript(segments)` -> append a QPlainTextEdit en tiempo real
  - `on_speaker_identified(speaker_id, name, confidence)` -> highlight speaker activo
  - `on_speaker_needs_review(temp_id, confidence, embedding)` -> mostrar badge de review
  - `on_recording_progress(duration)` -> update ProgressBar
  - `on_recording_paused(duration)` -> update UI a estado paused
  - `on_recording_resumed(duration)` -> update UI a estado recording
  - `on_stage_progress(stage, percent)` -> update stage label
- Pause: detiene grabación temporalmente, mantiene UI visible, botón cambia a "Resume"
- Resume: continúa grabación desde donde quedó
- Finalizar: detiene y dispara procesamiento final
**Criterio de Éxito:**
```bash
python desktop_app.py
# Abrir tab Session
# Botones Pause/Resume y Finalizar visibles
# Multiple speakers visibles con activo resaltado
# Texto es read-only con scroll automático
```

#### 2.4 Implementar InterlocutoresPanel (tab Interlocutores - Speaker Library)
**Responsable:** developer
**Duración:** 3.5 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `InterlocutoresPanel(QWidget)`:
  - QListWidget con lista de speakers conocidos (desde Database)
  - Cada item muestra: avatar, nombre, tags, last_seen
  - QPushButton: "Agregar Speaker Manual"
  - QPushButton: "Editar Speaker"
  - QPushButton: "Eliminar Speaker"
  - QDialog para editar speaker: editar nombre, tags, avatar
  - QDialog para speakers pending review: lista de speakers con 60-98% confidence, botón "Asociar con existente" o "Crear nuevo"
- Conectado a SpeakerManager para CRUD operations
- Slot `on_speaker_needs_review()` -> auto-open review dialog
**Criterio de Éxito:**
```bash
python desktop_app.py
# Tab Interlocutores visible
# Lista de speakers (vacía initially)
# Botones CRUD funcionales
# Review dialog abre cuando speaker needs review
```

#### 2.5 Placeholder SessionHistoryPanel (tab Sesiones)
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `SessionHistoryPanel(QWidget)`:
  - QTableWidget con columnas: ID, Fecha, Duración, Speakers, Estado
  - QPushButton: "Abrir Sesión"
  - QPushButton: "Eliminar Sesión"
  - Carga sesiones desde Database.get_all_sessions()
- Placeholder, sera completado en Sprint 5
**Criterio de Éxito:**
```bash
python desktop_app.py
# Tab Sesiones visible
# Tabla con headers
# Botones visibles (disabled si no hay selección)
```

#### 2.6 Placeholder ResultsPanel (legacy, puede removerse)
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `ResultsPanel(QWidget)`:
  - QTreeWidget (placeholder con items "Audio", "Transcript", "Reportes")
  - QLabel: "Resultados aparecerán aquí después de sesion"
  - Disabled cuando no hay resultados
- **NOTA:** Este panel puede ser redundante con SessionHistoryPanel, evaluar en Sprint 5
**Criterio de Éxito:**
```bash
python desktop_app.py
# Tab visible si se mantiene
```

#### 2.7 Crear archivo de estilos (QSS)
**Responsable:** designer (o developer)
**Duración:** 2.5 horas
**Dependencia:** 2.1-2.6
**Entregables:**
- `handsome_transcribe/ui/styles.py`: funciones para generar QSS
- Colores: verde (#27ae60) para éxito, rojo (#e74c3c) para error, azul (#3498db) para info, naranja (#f39c12) para review
- Fuentes: Segoe UI / Ubuntu para cross-platform
- Estilos para speaker avatars (circular, coloreado)
- QSS aplicado en SessionWindow.__init__()
**Criterio de Éxito:**
```bash
python desktop_app.py
# Colores y fuentes consistentes
# Speaker avatars con estilo circular
```

#### 2.8 Integrar ConfigPanel -> SessionManager (con validación sesión única)
**Responsable:** developer
**Duración:** 2.5 horas
**Dependencia:** 2.1, 2.2, Sprint 1 completo
**Entregables:**
- Al presionar "Iniciar Sesión" en ConfigPanel:
  1. **Validar que no exista sesión activa** (verificar `session_manager.get_current_state() == IDLE`)
  2. Si sesión activa detectada: mostrar QMessageBox error "Ya existe una sesión activa. Finaliza la sesión actual antes de iniciar una nueva."
  3. Validar config
  4. Crear SessionConfig desde widget values (**incluir session_context de QTextEdit, puede ser vacío**)
  5. Llamar `session_manager.start_session(config)` (puede lanzar excepción si sesión activa)
  6. Cambiar a LiveSessionView tab automáticamente
  7. Crear sesión en Database (**guardar context_text en tabla sessions**)
  8. **Iniciar auto-save timer** (SessionManager lo maneja internamente)
- Manejar errores con QMessageBox
- Botón "Iniciar Sesión" disabled durante sesión activa
- **Nota:** session_context se guardará pero no se usará en MVP; se reserva para futura integración con LLM API para mejorar transcripción/resumen
**Criterio de Éxito:**
```bash
python desktop_app.py
# ConfigPanel visible
# Llenar campos, presionar "Iniciar Sesion"
# Cambiar a tab Session (LiveSessionView)
# Sesión guardada en SQLite
```9 Crear desktop_app.py (entry point)
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** 2.1-2.8er
**Duración:** 1 hora
**Dependencia:** 2.1-2.6
**Entregables:**
```python
# desktop_app.py
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SessionWindow()
    window.show()
    sys.exit(app.exec())
```
**Criterio de Éxito:**
```bash
python desktop_app.py
# App lanza sin argumentos
# Ventana principal visible
```

#### 2.10 Crear run_venv_desktop.ps1 (Windows launcher)
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** 2.9
**Entregables:**
```powershell
# run_venv_desktop.ps1
.\.venv\Scripts\Activate.ps1
python desktop_app.py
```
**Criterio de Éxito:**
```powershell
.\run_venv_desktop.ps1
# App lanza en Windows sin errores de venv
```

#### 2.11 Tests de UI (no headless, visual checks)
**Responsable:** QA
**Duración:** 3 horas
**Dependencia:** 2.1-2.10
**Entregables:**
```
tests/ui/
├── test_main_window.py
├── test_config_panel.py
├── test_live_session_view.py
├── test_interlocutores_panel.py  # NEW
├── test_session_history_panel.py  # NEW
└── test_results_panel.py
```
**Criterio de Éxito:**
```bash
# Tests que verifican que widgets existen y tienen propiedades correctas
pytest tests/ui/test_*_panel.py -v
# Tests de InterlocutoresPanel (CRUD speakers, review dialog)
```

### Validacion de Sprint 2

#### Automatizada
```bash
pytest tests/ui/ -v --cov=handsome_transcribe/ui --cov-fail-under=80
```

#### Manual
- [ ] Abrir app, ver ConfigPanel
- [ ] Cambiar entre tabs libremente
- [ ] Presionar "Iniciar Sesion" con config valida (no rockea)
- [ ] Status bar actualiza estado
- [ ] CLI original sigue funcionando

### Riesgos Sprint 2

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|---|---|---|
| UI slow en Windows | Media | Medio | Optimizar renderizado, lazy loading |
| Accesibilidad (colores, fuentes) | Baja | Bajo | Seguir WCAG basico coolor contrast |
| QSettings no persiste (OSX permisos) | Baja | Bajo | Test en todas las plataformas |

### Criterio de Salida Sprint 2
- ✅ SessionWindow, ConfigPanel, LiveTranscriptView, ResultsPanel funcionales
- ✅ ConfigPanel -> SessionManager integrado
- ✅ Cambio de tabs fluido
- ✅ desktop_app.py puede lanzarse
- ✅ CLI original intacto
- ✅ Tests UI pasan

---

## Sprint 3: Captura de Audio (Semana 3)

### Objetivo
Integrar RecorderWorker en vivo con UI. Usuario puede grabar, detener, ver progreso.

### Tareas

#### 3.1 Implementar RecorderWorker completo
**Responsable:** developer
**Duración:** 3.5 horas
**Dependencia:** Sprint 1 completo
**Entregables:**
- Clase `RecorderWorker(QRunnable)`:
  - Hereda `AudioRecorder` existente
  - `run()` captura audio en background
  - Emite signals a EventBus cada N frames:
    - `recording_frame_ready(frames_count, duration_sec)`
  - **Buffer acumulativo**: mantiene audio completo en memoria durante grabación
  - **Método `save_partial(path: Path, part_num: int)`**: guarda audio acumulado hasta el momento en `temp/part{part_num}.wav` sin detener captura
  - **Método `save_final(path: Path)`**: guarda audio completo final en `recording.wav`
  - Al detener: llama `save_final()`, emite `recording_stopped(audio_path)`
  - Maneja errores: emite `recording_error(error_msg)`
- Selección de dispositivo desde config
- Duración: infinita hasta que user presione "Detener"
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py::TestRecorderWorker -v
# Mock captura, guarda WAV, emite signals
# Test save_partial() guarda sin detener grabación
# Test save_final() guarda audio completo
```

#### 3.2 Integrar RecorderWorker en SessionManager
**Responsable:** developer
**Duración:** 2.5 horas
**Dependencia:** 3.1, Sprint 1 completo
**Entregables:**
- SessionManager.start_session():
  1. Crear directorio de sesión: `outputs/sessions/session_{YYYYMMDD_HHMMSS}/` + `temp/`
  2. Crear RecorderWorker con config y session_dir
  3. Conectar signals a EventBus
  4. Lanzar en QThreadPool
  5. Cambiar estado a RECORDING
- SessionManager.pause_recording():
  1. Llamar `RecorderWorker.save_partial(session_dir/temp/part{N}.wav, N)` (N es contador)
  2. Incrementar contador de archivos parciales
  3. Trigger auto-guardado (SQLite update)
  4. Cambiar estado a PAUSED (audio worker sigue capturando pero no procesando)
- SessionManager.stop_recording():
  1. Señalar al RecorderWorker que pare
  2. Llamar `RecorderWorker.save_final(session_dir/recording.wav)`
  3. Consolidar metadata (listar archivos generados)
  4. Disparar TranscriberWorker con `recording.wav`
  5. Cambiar estado a TRANSCRIBING
- Manejo de errores: emitir session_error
**Criterio de Éxito:**
```bash
# Test con mock RecorderWorker
pytest tests/ui/test_session_manager.py::TestRecorderIntegration -v
# Test creación de directorios con timestamp correcto
# Test archivos parciales se guardan en pause/autosave
# Test recording.wav final se crea correctamente
```

#### 3.3 Conectar RecorderWorker signals a LiveTranscriptView
**Responsable:** developer
**Duración:** 1.5 horas
**Dependencia:** 3.1, 3.2
**Entregables:**
- LiveTranscriptView slots:
  - `on_recording_progress(frames_count, duration_sec)`:
    - Update ProgressBar con duration
    - Update stage label ("Grabando... 00:15")
  - `on_recording_error(error_msg)`:
    - Show QMessageBox con error
    - Reset UI a IDLE
**Criterio de Éxito:**
```bash
python desktop_app.py
# Abrir ConfigPanel, presionar "Iniciar Sesion"
# Ir a LiveTranscriptView
# ProgressBar debe moverse (aunque simulado)
```

#### 3.4 Implementar boton "Detener Grabación"
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** 3.2, 3.3
**Entregables:**
- QPushButton en LiveTranscriptView
- Slot conectado: `on_stop_recording_clicked()`
  1. Deshabilitar boton (prevent double-click)
  2. Llamar `session_manager.stop_recording()`
  3. Cambiar label a "Procesando..."
  4. Esperar callback de session_manager
**Criterio de Éxito:**
```bash
python desktop_app.py
# Grabar (simulado), presionar "Detener"
# Estado cambia a TRANSCRIBING
# No crashes
```

#### 3.5 Tests de flujo de grabacion
**Responsable:** QA
**Duración:** 2.5 horas
**Dependencia:** 3.1-3.4
**Entregables:**
```
tests/ui/test_recorder_flow.py
- test_record_and_save_wav
- test_progress_updates
- test_stop_recording
- test_pause_and_save_partial
- test_consolidate_final_recording
- test_device_selection
- test_session_directory_creation
```
**Criterio de Éxito:**
```bash
pytest tests/ui/test_recorder_flow.py -v
```

### Validacion de Sprint 3

#### Manual (IMPORTANTE: esta es la primera etapa "real" de audio)
- [ ] Conectar microfono
- [ ] Abrir app, seleccionar dispositivo
- [ ] "Iniciar Sesion" -> Grabando
- [ ] Hablar 10 segundos
- [ ] Verificar que se crea directorio `outputs/sessions/session_YYYYMMDD_HHMMSS/` con subdirectorio `temp/`
- [ ] Pausar -> verificar que se crea `temp/part1.wav`
- [ ] Reanudar, hablar 10 segundos más
- [ ] Pausar nuevamente -> verificar que se crea `temp/part2.wav`
- [ ] Presionar "Detener" (Finalizar)
- [ ] Verificar que `recording.wav` existe en directorio raíz de sesión (audio consolidado)
- [ ] Validar que `recording.wav` es reproducible (ffprobe o player) y contiene audio completo
- [ ] Verificar que archivos parciales siguen en `temp/` para debugging

#### Automatizada
```bash
pytest tests/ui/ -v --cov=handsome_transcribe/ui
pytest tests/ -k "not ui" -v  # CLI original intacto
```

### Riesgos Sprint 3

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|---|---|---|
| sounddevice no detecta dispositivo | Media | Alto | Mostrar lista de dispositivos, allow fallback a default |
| Audio corrompido en WAV | Baja | Alto | Validar con ffprobe antes de transcribir |
| UI freeze durante grabacion | Media | Medio | RecorderWorker en thread separado, no block main |
| Ruido/silencio ambiental | Baja | Bajo | Mostrar advertencia, continuar de todas formas |

### Criterio de Salida Sprint 3
- ✅ RecorderWorker captura audio real en background
- ✅ UI actualiza progreso en vivo (cada N frames)
- ✅ User puede detener grabacion
- ✅ WAV guardado en outputs/audio/
- ✅ Boton "Detener" solo activo durante RECORDING
- ✅ Dispositivo seleccionable
- ✅ Tests pasan, CLI intacto

---

### Ejecución Sprint 3

**Iniciada:** 2026-03-09
**Completada:** 2026-03-09
**Tiempo total:** ~2 horas
**Ejecutor:** implementator
**Estado:** COMPLETADO

#### Hallazgos Clave

##### [INFO] - Infrastructure Already Implemented
- **RecorderWorker**: Ya existe completamente implementado en `handsome_transcribe/ui/workers.py` (~200 líneas)
  - Buffer acumulativo con `_audio_buffer` list + `threading.Lock` para thread-safety
  - `save_partial(path, part_num)`: Guarda audio sin detener grabación (convierte float32→int16)
  - `save_final(path)`: Consolida audio completo en recording.wav
  - Emite `recording_frame_ready` cada ~1 segundo con frames_count y duration_sec
  - Métodos pause/resume con señales `recording_paused` y `recording_resumed`
  - Error handling con `recording_error` signal

- **SessionManager**: pause/resume/stop ya implementados en `handsome_transcribe/ui/session_manager.py` (~350 líneas)
  - `start_session()`: Crea directorio `session_YYYYMMDD_HHMMSS/` con subdirectorio `temp/`, inicializa RecorderWorker
  - `pause_recording()`: Llama `_save_partial_audio()` que incrementa `partial_audio_count` y guarda en temp/
  - `resume_recording()`: Reanuda grabación sin perder buffer
  - `stop_recording()`: Llama `save_final(recording.wav)`, dispara transcripción
  - `_auto_save_progress()`: Auto-guardado cada 120000ms (2 min) + metadata JSON
  - `_transition_state()`: Validación de transiciones de estado con mapa de estados válidos

- **LiveSessionView**: Botones ya implementados en `handsome_transcribe/ui/windows/panels.py` (~600 líneas)
  - Botón Pause/Resume con `_on_pause_resume()` conectado a `event_bus.emit_pause_recording()` y `emit_resume_recording()`
  - Botón Stop con `_on_stop()` mostrando diálogo de confirmación, conectado a `event_bus.emit_stop_recording()`
  - Slots para `partial_transcript_ready`, `speaker_identified`, `session_state_changed`, `stage_progress`

##### [MENOR] - Signal Connection Missing
- **recording_frame_ready**: No estaba conectado en LiveSessionView para actualizar barra de progreso
- **Impacto**: ProgressBar no mostraría duración durante grabación en tiempo real
- **Solución implementada**: Agregada conexión y slot `_on_recording_progress(frames_count, duration_sec)`

#### Resumen de Cambios

**Archivos modificados:** 2
- `handsome_transcribe/ui/windows/panels.py`:
  - Línea ~472: Agregada conexión `self.event_bus.recording_frame_ready.connect(self._on_recording_progress)` en `_connect_signals()`
  - Líneas ~613-627: Agregado slot `_on_recording_progress(frames_count, duration_sec)` que:
    - Actualiza `duration_progress.setValue(int(duration_sec))`
    - Formatea tiempo como MM:SS con `setFormat(f"{minutes:02d}:{seconds:02d}")`

**Archivos creados:** 1
- `tests/ui/test_recorder_flow.py` (~320 líneas):
  - 7 tests de integración completos con fixtures para EventBus, ConfigManager, Database, SpeakerManager, SessionManager
  - `test_record_and_save_wav`: Valida creación de directorio de sesión y llamada a save_final()
  - `test_progress_updates`: Verifica emisión periódica de recording_frame_ready con frames_count y duration_sec
  - `test_stop_recording`: Valida stop_recording() llama worker.stop() y save_final(), transiciona a TRANSCRIBING
  - `test_pause_and_save_partial`: Verifica pause_recording() llama save_partial() con contador incrementado, transiciona a PAUSED
  - `test_consolidate_final_recording`: Valida save_final() usa wave.open con parámetros correctos (16kHz, mono, 16-bit)
  - `test_device_selection`: Verifica RecorderWorker acepta device_name desde config
  - `test_session_directory_creation`: Valida estructura session_YYYYMMDD_HHMMSS/temp/ con metadata_path, recording_path, transcript_path

**Tests ejecutados:** 38 (7 UI + 31 CLI)
**Tests pasados:** 38 (100%)
**Tests fallidos:** 0

#### Verificación Ejecutada

##### Automatizada
- ✅ Sintaxis: No errores en `handsome_transcribe/ui/windows/panels.py` y `tests/ui/test_recorder_flow.py`
- ✅ pytest UI: 7/7 tests en `tests/ui/test_recorder_flow.py` pasan (1.15s)
  - test_record_and_save_wav: PASSED
  - test_progress_updates: PASSED
  - test_stop_recording: PASSED
  - test_pause_and_save_partial: PASSED
  - test_consolidate_final_recording: PASSED
  - test_device_selection: PASSED
  - test_session_directory_creation: PASSED
- ✅ pytest CLI: 31/31 tests CLI originales pasan sin regresiones (4.47s)
  - test_recorder.py: 6 passed
  - test_report_generator.py: 6 passed
  - test_speaker_identifier.py: 6 passed
  - test_summarizer.py: 7 passed
  - test_transcriber.py: 6 passed

##### Manual Sugerida
- [ ] `python desktop_app.py` → UI debe lanzar sin errores
- [ ] Conectar micrófono → Seleccionar dispositivo en ConfigPanel
- [ ] "Iniciar Sesión" → Verificar que se crea directorio `outputs/sessions/session_YYYYMMDD_HHMMSS/temp/`
- [ ] Grabar 10 segundos → ProgressBar debe mostrar tiempo transcurrido (MM:SS)
- [ ] Pausar → Verificar que se crea `temp/part1.wav` y ProgressBar se detiene
- [ ] Reanudar → Grabar 10 segundos más, verificar ProgressBar continúa
- [ ] Pausar → Verificar que se crea `temp/part2.wav`
- [ ] "Detener" → Confirmar diálogo, verificar que se crea `recording.wav` en raíz de sesión
- [ ] Reproducir `recording.wav` → Validar que contiene audio completo (~20 segundos)
- [ ] Verificar archivos parciales permanecen en `temp/` para debugging

#### Riesgos Identificados

- [MENOR] **Thread-safety**: RecorderWorker usa `threading.Lock` para `_audio_buffer`, pero no se validó con tests de concurrencia. Requiere test específico en tarea 3.5.
- [MENOR] **Progress bar maximum**: LiveSessionView inicializa `duration_progress.setMaximum(3600)` (1 hora). Para sesiones más largas, necesita ajuste dinámico o máximo configurable.
- [INFO] **Validación de audio**: No hay validación con `ffprobe` antes de iniciar transcripción (mencionado en riesgos Sprint 3). Recomendar agregar en SessionManager._start_transcription() validación básica (duración > 0, formato válido).

#### Pendientes

- [ ] **Validación manual completa**: Ejecutar checklist de verificación manual con micrófono real (requiere entorno con audio)
  - Conectar micrófono
  - `python desktop_app.py` → UI lanza sin errores
  - Seleccionar dispositivo en ConfigPanel
  - "Iniciar Sesión" → Verificar directorio `outputs/sessions/session_YYYYMMDD_HHMMSS/temp/` creado
  - Grabar 10 segundos → ProgressBar muestra tiempo MM:SS
  - Pausar → Verificar `temp/part1.wav` creado
  - Reanudar → Grabar 10 segundos, verificar ProgressBar continúa
  - Pausar → Verificar `temp/part2.wav` creado
  - "Detener" → Confirmar diálogo, verificar `recording.wav` en raíz
  - Reproducir `recording.wav` → Validar audio completo (~20 segundos)
  - Verificar archivos parciales en `temp/` para debugging

- [ ] **Ajuste dinámico de progress bar**: Si sesión supera 1 hora, `duration_progress.setMaximum()` debe incrementarse dinámicamente
  - Ejemplo: cada vez que `duration_sec > maximum - 60`, doblar el máximo
  - Implementar en `_on_recording_progress()` con lógica condicional

- [ ] **Validación de audio pre-transcripción**: Agregar validación básica en `SessionManager._start_transcription()`
  - Verificar duración > 0 usando `wave.open()` o similar
  - Verificar formato válido (16kHz, mono, 16-bit)
  - Emitir error temprano si audio corrompido antes de iniciar Whisper

---

## Sprint 4: Pipeline (Semana 4)

### Objetivo
Integrar TranscriberWorker, DiarizerWorker, SummarizerWorker, ReporterWorker.
Usuario ve transcript en vivo, speakers en vivo, summary al finalizar.

### Tareas

#### 4.1 Implementar TranscriberWorker completo
**Responsable:** developer
**Duración:** 3 horas
**Dependencia:** Sprint 1-3 completo
**Entregables:**
- Clase `TranscriberWorker(QRunnable)`:
  - Hereda `WhisperTranscriber` existente
  - `run(audio_path: Path, model_name: str, output_path: Path)`:  # audio_path es session_dir/recording.wav, output_path es session_dir/transcript.txt
    1. Emite `stage_progress("Transcribiendo", 0%)`
    2. Carga Whisper model (emit 25%)
    3. Transcribe audio (emit 50%, 75%, 100%)
    4. **Guarda transcript en `session_dir/transcript.txt`** (formato legible con timestamps)
    5. Emite `partial_transcript_ready(Transcript)` con contenido completo
  - Maneja errores: `transcription_error(error_msg)`
- Notificar a EventBus de progreso granular
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py::TestTranscriberWorker -v
# Mock Whisper, emite signals
# Test guarda transcript.txt en session_dir
```

#### 4.2 Implementar DiarizerWorker completo
**Responsable:** developer
**Duración:** 3 horas
**Dependencia:** Sprint 1-3 completo
**Entregables:**
- Clase `DiarizerWorker(QRunnable)`:
  - Hereda `SpeakerIdentifier` existente
  - `run(audio_path, transcript, hf_token)`:
    1. Emite `stage_progress("Diarizando", 0%)`
    2. Valida HF_TOKEN (25%)
    3. Carga pyannote (50%)
    4. Diariza audio (75%)
    5. Asigna speakers a transcript (100%)
    6. Emite `partial_transcript_ready(Transcript with speakers)`
  - Si HF_TOKEN invalido o no disponible: skip, emitir warning pero continuar
- Completamente opcional basado en config
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py::TestDiarizerWorker -v
```

#### 4.3 Implementar SummarizerWorker completo
**Responsable:** developer
**Duración:** 3 horas
**Dependencia:** Sprint 1-3 completo
**Entregables:**
- Clase `SummarizerWorker(QRunnable)`:
  - Hereda `MeetingSummarizer` existente
  - `run(transcript_path: Path, output_path: Path, use_transformers=True)`:  # transcript_path es session_dir/transcript.txt, output_path es session_dir/summary.md
    1. Emite `stage_progress("Resumiendo", 0%)`
    2. Si use_transformers: cargar modelo (50%)
    3. Summarize + extract (75%)
    4. **Guarda summary en `session_dir/summary.md`** (formato markdown)
    5. Emite `summary_ready(MeetingSummary)` (100%)
  - Fallback a extractive si transformers falla
  - Completamente opcional basado en config
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py::TestSummarizerWorker -v
# Test guarda summary.md en session_dir
```

#### 4.4 Implementar ReporterWorker completo
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** Sprint 1-3 completo
**Entregables:**
- Clase `ReporterWorker(QRunnable)`:
  - Hereda `ReportGenerator` existente
  - `run(session_dir: Path, session_id: int)`:  # Lee transcript.txt y summary.md de session_dir
    1. Emite `stage_progress("Generando reportes", 0%)`
    2. Lee `session_dir/transcript.txt` y `session_dir/summary.md`
    3. Genera MD (33%) -> `outputs/reports/session_{session_id}_report.md`
    4. Genera JSON (66%) -> `outputs/reports/session_{session_id}_report.json`
    5. Genera PDF (100%) -> `outputs/reports/session_{session_id}_report.pdf`
    6. Emite `reports_ready(dict[str, Path])` (100%) con paths de reportes generados
  - Guarda reportes en `outputs/reports/` (separado de sesión para fácil acceso)
**Criterio de Éxito:**
```bash
pytest tests/ui/test_workers.py::TestReporterWorker -v
# Test genera reportes en outputs/reports/ con session_id en nombre
```
```bash
pytest tests/ui/test_workers.py::TestReporterWorker -v
```

#### 4.5 Cadena de workers en SessionManager
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** 4.1-4.4, Sprint 1-3 completo
**Entregables:**
- SessionManager.stop_recording() dispara cadena:
  1. RecorderWorker finaliza -> guarda WAV
  2. `state = TRANSCRIBING` -> TranscriberWorker inicia
  3. TranscriberWorker completa -> si diarizacion enabled: DiarizerWorker
  4. Else: SummarizerWorker inicia
  5. DiarizerWorker completa -> SummarizerWorker inicia
  6. SummarizerWorker completa -> ReporterWorker inicia
  7. ReporterWorker completa -> `state = COMPLETED`, emitir `session_completed(results)`
- Manejo de errores en cualquier etapa: `state = ERROR`, emitir `session_error(stage, msg)`
- Permitir cancelacion soft en cualquier etapa (if possible)
**Criterio de Éxito:**
```bash
# Test completo sin real audio (mock todo)
pytest tests/ui/test_session_manager.py::TestFullPipeline -v
```

#### 4.6 Actualizar LiveTranscriptView para mostrar partial updates
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** 4.1-4.5, Sprint 2-3
**Entregables:**
- LiveTranscriptView slots nuevos:
  - `on_partial_transcript(Transcript)`: append text + speaker labels
  - `on_speaker_update(speaker_map)`: update speaker label widget
  - `on_stage_progress(stage, percent)`: update label + progress
- Simular scroll incremental: append por bloque cada que se recibe update
- El texto NO se borra entre updates, se acumula
**Criterio de Éxito:**
```bash
python desktop_app.py
# Grabar -> Detener -> Ver transcript apareciendo en vivo
```

#### 4.7 Tests de pipeline completo (E2E)
**Responsable:** QA
**Duración:** 3 horas
**Dependencia:** 4.1-4.6
**Entregables:**
```
tests/ui/test_pipeline_e2e.py
- test_full_flow_record_transcribe_summarize
- test_diarization_optional
- test_summarization_fallback
- test_error_handling_at_each_stage
```
**Criterio de Éxito:**
```bash
pytest tests/ui/test_pipeline_e2e.py -v
```

### Validacion de Sprint 4

#### Manual (IMPORTANTE: primera sesion completa real)
- [ ] Grabar 30 segundos de audio
- [ ] Ver transcript apareciendo en LiveTranscriptView en vivo (bloque)
- [ ] Ver speaker labels actualizándose
- [ ] Ver progreso de "Resumiendo"
- [ ] Al finalizar: session_completed, resultados listos
- [ ] Verificar estructura de sesión:
  ```
  outputs/sessions/session_20260309_143000/
  ├── recording.wav        (audio final completo)
  ├── transcript.txt       (transcripción legible con timestamps)
  ├── summary.md           (resumen en markdown)  
  ├── metadata.json        (metadatos de sesión)
  └── temp/
      ├── part1.wav        (archivos parciales de auto-guardado)
      └── part2.wav
  ```
- [ ] Verificar reportes en `outputs/reports/`:
  - `session_1_report.pdf`
  - `session_1_report.md`
  - `session_1_report.json`

#### Automatizada
```bash
pytest tests/ui/test_pipeline_e2e.py -v --tb=short
pytest tests/ -v  # TODO: revisar si hay regressions en CLI
```

### Riesgos Sprint 4

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|---|---|---|
| Latencia larga en transcripcion (10+ min para audio largo) | Alta | Medio | Mostrar splash con ETA, permitir background |
| Memoria exhausted si modelos grandes | Media | Alto | Cargar/descargar modelos por worker, usar `del` |
| pyannote falla sin HF_TOKEN | Alta | Bajo | Make optional, skip, show warning |
| Transformers falla en CPU lento | Media | Medio | Fallback a extractive, timeout si tarda >30seg |

### Criterio de Salida Sprint 4
- ✅ Cadena completa de workers funcional
- ✅ Transcript en vivo visible
- ✅ Speakers detectados y mostrados
- ✅ Reportes generados automaticamente
- ✅ Errores en cualquier etapa manejados sin crash
- ✅ Tests E2E pasan
- ✅ CLI original intacto

---

## Sprint 5: Resultados y Polish (Semana 5)

### Objetivo
Implementar ResultsPanel, reproduccion de audio, acceso a reportes.
Pulir UI, documentar, hacer MVP "shippable".

### Tareas

#### 5.1 Implementar ResultsPanel completo
**Responsable:** developer
**Duración:** 4 horas
**Dependencia:** Sprint 1-4 completo
**Entregables:**
- Clase `ResultsPanel(QWidget)`:
  - QTreeWidget con items:
    - "Sesión" (expandible): id, fecha, duración, speakers, directorio
    - "Audio": `recording.wav` con botón Play
    - "Transcript": `transcript.txt` con botón View
    - "Resumen": `summary.md` (si generado) con botón View
    - "Reportes": links a PDF, Markdown, JSON en `outputs/reports/` con botones Open
    - "Archivos parciales": link a carpeta `temp/` (opcional, para debugging)
  - Slots conectados a EventBus:
    - `on_session_completed(results)`: populate tree con artefactos de session_dir
  - Botones funcionales:
    - "Play": abrir `recording.wav` con QMediaPlayer o sistema player
    - "View Transcript": abrir `transcript.txt` en read-only QPlainTextEdit
    - "View Summary": abrir `summary.md` en modal con formato markdown
    - "Open Report": abrir PDF/Markdown/JSON en app del SO
    - "Abrir carpeta sesión": abrir `session_dir` en explorador de archivos
    - "Open": abrir PDF/Markdown en app del SO
    - "Abrir carpeta outputs/"
**Criterio de Éxito:**
```bash
python desktop_app.py
# Grabar + procesar
# ResultsPanel poblado con items
# Clickear Play -> sonido
# Clickear View -> transcript visible
```

#### 5.2 Integrar QMediaPlayer para reproduccion de audio
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** 5.1
**Entregables:**
- Agregar QMediaPlayer a ResultsPanel
- Boton Play inicia reproduccion
- Slider de volumen
- Label de tiempo actual / duracion total
- Pause y stop buttons
**Criterio de Éxito:**
```bash
python desktop_app.py
# Play audio, escuchar sin clicks
```

#### 5.3 Crear dialogo de ViewTranscript
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** 5.1
**Entregables:**
- Modal QDialog con QPlainTextEdit (read-only)
- Lee y muestra `transcript.txt` de forma legible:
  ```
  [00:00-00:05] Speaker 1: "Good morning."
  [00:05-00:10] Speaker 2: "Hello!"
  ```
- Botones: Copy All, Save As..., Close
- Soporte para búsqueda dentro del transcript (Ctrl+F)
**Criterio de Éxito:**
```bash
python desktop_app.py
# ResultsPanel -> View Transcript
# Modal con transcript.txt legible
# Botón Copy All funciona
```
# Modal con texto legible
```

#### 5.4 Crear dialogo de ViewSummary
**Responsable:** developer
**Duración:** 2 horas
**Dependencia:** 5.1
**Entregables:**
- Modal QDialog con QTextBrowser (read-only, con soporte markdown rendering)
- Lee y renderiza `summary.md`:
  ```markdown
  # Summary
  ...
  
  ## Key Topics
  - ...
  
  ## Action Items
  - ...
  
  ## Decisions
  - ...
  ```
- Botones: Copy All (raw markdown), Save As..., Close
**Criterio de Éxito:**
```bash
python desktop_app.py
# ResultsPanel -> View Summary
# Modal con summary.md renderizado (markdown)
```

#### 5.5 Boton "Nueva Sesion"
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** Sprint 1-5
**Entregables:**
- QPushButton en ResultsPanel: "Nueva Sesion"
- Slot:
  1. Limpiar ResultsPanel
  2. Reset SessionManager y UI
  3. Cambiar tab a ConfigPanel
  4. Clear transcript view
**Criterio de Éxito:**
```bash
python desktop_app.py
# Grabar + procesar
# "Nueva Sesion" -> vuelve a ConfigPanel limpio
```

#### 5.6 Ayuda y About dialog
**Responsable:** developer
**Duración:** 1 hora
**Dependencia:** 5.1
**Entregables:**
- Menu Help > About:
  - Nombre: "HandsomeTranscribe Desktop"
  - Version: vx.y.z
  - Descripcion de features
  - Copyright y licencia (MIT)
- Menu Help > Documentation:
  - Abrir README.md en editor/navegador
**Criterio de Éxito:**
```bash
python desktop_app.py
# Menu Help > About
# Dialog visible
```

#### 5.7 Logging y diagnosticos
**Responsable:** developer
**Duración:** 1.5 horas
**Dependencia:** Sprint 1-5
**Entregables:**
- Agregar logging a app usando `logging` modulo
- Log file: `~/.config/handsome_transcribe/app.log`
- Incluir timestamps, level (INFO, WARNING, ERROR)
- Menu Help > View Logs: mostrar ultimos 100 lineas en dialog
**Criterio de Éxito:**
```bash
# Abrir app, verificar que app.log se crea
cat ~/.config/handsome_transcribe/app.log
# Debe tener entries
```

#### 5.8 Pulir UI con estilos mejorados
**Responsable:** designer (o developer)
**Duración:** 2 horas
**Dependencia:** Sprint 2 (styles.py)
**Entregables:**
- Actualizar QSS con:
  - Botones con rounded corners e icons
  - Progress bars más lindas
  - Tabs con underline on active
  - QPlainTextEdit con monospace font (Consolas/Monaco)
  - Colores consistentes (verde éxito, rojo error, azul info)
- No necesita ser "productivo", pero si pulido
**Criterio de Éxito:**
```bash
python desktop_app.py
# UI "se ve profesional" (subjetivo pero mejora)
```

#### 5.9 Actualizar README.md para incluir instrucciones Desktop
**Responsable:** developer
**Duración:** 1.5 horas
**Dependencia:** Sprint 5 completo
**Entregables:**
```markdown
## Running the Desktop App

### Windows
```powershell
.\run_venv_desktop.ps1
```

### Linux / macOS
```bash
source .venv/bin/activate
python desktop_app.py
```

### First Time Setup
1. Install dependencies: `pip install -r requirements.txt`
2. (Optional) Set HF_TOKEN: `export HF_TOKEN="hf_..."`
3. Run app

### Features
- Record from microphone
- **Single active session** (one at a time)
- **Auto-save every 2 minutes** during recording (also saves on pause, speaker change, finalization)
- Live transcription with speaker identification using voice embeddings
- Speaker Library for managing known speakers
- Optional diarization and summarization
- Access to generated reports (PDF/Markdown/JSON)
- **Note:** Full session export functionality (audio + transcript + summary bundle) is planned for future version
```
**Criterio de Éxito:**
```bash
# Follow README steps, app launches
```

#### 5.10 Ejemplo de session-data persistence (opcional)
**Responsable:** developer
**Duración:** 1.5 horas
**Dependencia:** Sprint 5 completo
**Entregables:**
- Guardar SessionData en SQLite local `~/.config/handsome_transcribe/sessions.db`
- Menu File > Open Past Session: ver lista de sesiones anteriores
- Recargar ResultsPanel desde SessionData
**Criterio de Éxito:**
```bash
python desktop_app.py
# Procesar sesion
# Cerrar app
# Abrir app
# Menu File > Open Past Session -> ver sesion anterior
```

#### 5.11 Tests finales y cobertura
**Responsable:** QA
**Duración:** 3 horas
**Dependencia:** Sprint 5 completo
**Entregables:**
```
tests/ui/
├── test_results_panel.py
├── test_media_player.py
├── test_dialogs.py
└── test_full_app_flow.py
```
**Criterio de Éxito:**
```bash
pytest tests/ -v --cov=handsome_transcribe --cov-fail-under=80
# Min 80% coverage
# Todos los tests PASAN
```

#### 5.12 Bug fixes y regression testing
**Responsable:** QA
**Duración:** 2 horas
**Dependencia:** 5.11
**Entregables:**
- Ejecutar full test suite multiple veces
- Manual smoke tests en Windows y Linux (si possible)
- Verificar que CLI original NO se rompio
**Criterio de Éxito:**
```bash
pytest tests/ -v
python main.py record --duration 5  # CLI works
```

### Validacion de Sprint 5

#### Manual (IMPORTANTE: MVP completo)
- [ ] Grabar 30 segundos
- [ ] Ver transcript + speakers en vivo
- [ ] Escuchar audio desde app
- [ ] Leer transcript en dialog
- [ ] Leer summary en dialog
- [ ] Abrir PDF en navegador
- [ ] "Nueva Sesion" -> grabar otra sesion
- [ ] Cerrar app, abrir: historial visible
- [ ] README actualizado y claro

#### Automatizada
```bash
pytest tests/ -v --cov --cov-fail-under=80
pytest tests/ -k "not ui" -v  # CLI original intacto
```

### Riesgos Sprint 5

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|---|---|---|
| QMediaPlayer lento en algunos formatos | Baja | Bajo | Reconvertir WAV si es necesario |
| SQLite locks en concurrency | Baja | Bajo | Single writer, readers OK |
| Share PDF desde app en macOS | Baja | Bajo | Use subprocess.open() |

### Criterio de Salida Sprint 5
- ✅ ResultsPanel completo: audio play, transcript view, summary view
- ✅ "Nueva Sesion" -> vuelve a inicio
- ✅ Historial de sesiones (opcional pero deseado)
- ✅ README actualizado
- ✅ Logging y diagnosticos
- ✅ Tests E2E pasan, cobertura 80%+
- ✅ CLI original intacto
- ✅ **MVP EMPAQUETABLE Y ENTREGABLE**

---

## Plan de Testing Integrado

### Pirámide de Testing
```
        Top (Manual E2E)
       /      \
      /        \  5%
     /          \
    / Integration \
   /              \ 15%
  /  _____________\
 /   /              \
/ Unit Tests        \ 80%
/____________________\
```

### Test Suites por Sprint
- Sprint 1: Unit tests (models, event_bus, session_manager stubs) ~ 30 tests
- Sprint 2: UI widget tests ~ 20 tests
- Sprint 3: Integration tests (recorder + UI) ~ 15 tests
- Sprint 4: E2E pipeline tests ~ 10 tests
- Sprint 5: Full app tests ~ 10 tests
- **Total: ~85 tests, min 80% cobertura**

### Comando de Testing
```bash
# Run all UI tests
pytest tests/ui/ -v --cov=handsome_transcribe/ui --cov-report=html

# Run all tests (CLI + UI)
pytest tests/ -v --cov=handsome_transcribe --cov-fail-under=80

# Run specific test
pytest tests/ui/test_session_manager.py::TestSessionManager::test_state_transition -v

# Watch mode (optional)
pytest-watch tests/
```

---

## Risk Management

### Riesgos Transversales

| Riesgo | Probabilidad | Impacto | Mitigacion Proactiva |
|--------|---|---|---|
| Whisper/Transformers modulos grandes frenan instalacion | Media | Medio | Instrucciones claras de setup, cache modelos |
| pyannote/HF requiere token obligatorio | Alta | Bajo | Marcar diarizacion como OPCIONAL, validar token |
| Audio device no detectado en windows | Media | Alto | Mostrar lista de devices, allow fallback |
| PySide6 incompatibilidad en x86 viejo | Baja | Alto | Support solo 64-bit, documentar reqs minimos |
| GIL bloquea UI durante transcripcion | Media | Medio | Usar threads separados, QThreadPool |
| Serialization de models fallan | Baja | Bajo | Tests exhaustivos de JSON round-trip |

### Plan de Rollback por Sprint
- Sprint 1: Revert `handsome_transcribe/ui/` folder
- Sprint 2: Revert UI layer, preserve models/workers
- Sprint 3: Disable recorder, preserve stub
- Sprint 4: Disable pipeline workers, preserve UI
- Sprint 5: Disable results panel, preserve everything else

---

## Criterios de Aceptacion Final (MVP)

El MVP se considera **COMPLETO Y APROBADO** cuando:

1. **Funcional**
   - ✅ Sesion: grabar -> transcribir -> diarizar -> resumir -> reportes
   - ✅ UI: ConfigPanel, LiveTranscriptView, ResultsPanel, NewSession
   - ✅ Audio play, transcript view, summary view, PDF open
   - ✅ CLI original intacto y tests pasando

2. **Calidad**
   - ✅ Tests: 85+ tests, min 80% coverage
   - ✅ No crashes en flujo happy path
   - ✅ Errores manejados con dialogs claros
   - ✅ Logging funcional

3. **Documentacion**
   - ✅ README actualizado con instrucciones desktop
   - ✅ Comentarios en codigo para componentes complejos
   - ✅ docstrings en todas las clases publicas

4. **Multiplataforma**
   - ✅ Testado en Windows
   - ✅ Testado en Linux (si posible)
   - ✅ Paths cross-platform con `pathlib.Path`
   - ✅ Config storage cross-platform con `QStandardPaths`

5. **Performance**
   - ✅ UI no freeze durante grabacion (RecorderWorker en thread)
   - ✅ Transcripcion < 2min para audio de 5min (hardware dependent)
   - ✅ Memory footprint < 1GB tipico

---

## Cronograma

| Semana | Sprint | Focus | Horas |
|--------|--------|-------|-------|
| W1 | Sprint 1 | Infraestructura (models, events, session mgr) | 12-15 |
| W2 | Sprint 2 | UI Base (windows, panels, styles) | 13-15 |
| W3 | Sprint 3 | Captura de audio (recorder worker integration) | 8-10 |
| W4 | Sprint 4 | Pipeline (workers, E2E) | 15-18 |
| W5 | Sprint 5 | Resultados, polish, documentacion | 12-14 |
| **Total** | | | **60-72 horas** |

**Timeline realista: 3-4 semanas con 1 developer full-time.**

---

## Siguiente Paso

Este plan esta listo para ser ejecutado por un **implementador** o equipo de desarrollo.
Recomendacion: 
1. Revisar y aprobar plan con stakeholders.
2. Asignar developer(s) a sprints.
3. Setup CI/CD básico (pytest en cada commit).
4. Lanzar Sprint 1.

**Success criteria**: Al finalizar Sprint 5, tener MVP entregable en produccion (o beta publica).
