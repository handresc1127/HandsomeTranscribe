# Codebase Research: transcription-language-not-passed

**Date**: 2026-03-15
**Researcher**: AI Agent (Bug Researcher)
**Bug**: Recording transcription ignores language setting in desktop app
**Status**: Research Complete - Pending Verification

---

## Research Summary

The UI has a `language_input` QLineEdit widget that collects a language code from the user, but the value is never read when constructing `SessionConfig` because the dataclass has no language field. Consequently, `ConfigManager` does not persist/load language, and `SessionManager` does not pass language to `TranscriberWorker`. The `TranscriberWorker` already accepts and forwards a `language` parameter to `whisper.transcribe()`, so the gap is entirely in the upstream chain from UI → config → session manager.

---

## Detailed Findings

### Code Locations

| File | Lines | Component | Description |
|------|-------|-----------|-------------|
| `handsome_transcribe/ui/models.py` | 30-36 | `SessionConfig` | Dataclass with 6 fields; no language field present |
| `handsome_transcribe/ui/windows/panels.py` | 89-92 | `ConfigPanel._setup_ui` | Creates `self.language_input` QLineEdit widget |
| `handsome_transcribe/ui/windows/panels.py` | 333-348 | `ConfigPanel._on_start_session` | Builds `SessionConfig` without reading `language_input` |
| `handsome_transcribe/ui/windows/panels.py` | 213-243 | `ConfigPanel._load_saved_config` | Restores all fields except language |
| `handsome_transcribe/ui/windows/panels.py` | 317 | `ConfigPanel._on_reset_config` | Clears `language_input` (aware of field) |
| `handsome_transcribe/ui/windows/panels.py` | 396 | `ConfigPanel._set_panel_enabled` | Enables/disables `language_input` (aware of field) |
| `handsome_transcribe/ui/config_manager.py` | 40-60 | `ConfigManager.load_config` | Returns `SessionConfig` without language |
| `handsome_transcribe/ui/config_manager.py` | 65-82 | `ConfigManager.save_config` | Persists model, diarization, summarization, device; no language |
| `handsome_transcribe/ui/session_manager.py` | 437-449 | `SessionManager._start_transcription` | Creates `TranscriberWorker` without `language=` |
| `handsome_transcribe/ui/session_manager.py` | 451-465 | `SessionManager._start_partial_transcription` | Creates `TranscriberWorker` without `language=` |
| `handsome_transcribe/ui/workers.py` | 222-255 | `TranscriberWorker.__init__` | Accepts `language: Optional[str] = None` |
| `handsome_transcribe/ui/workers.py` | 270-274 | `TranscriberWorker.run` | Passes `language=self.language` to `whisper.transcribe()` |
| `tests/ui/conftest.py` | 88-94 | `session_config` fixture | Creates `SessionConfig` without language field |
| `tests/ui/test_config_manager.py` | 21-36 | `test_save_and_load_config` | Tests save/load without language |
| `tests/ui/test_workers.py` | 53-67 | `test_create_transcriber_worker` | Creates worker with `language=None` |
| `tests/test_transcriber.py` | 141-200 | `TestWhisperTranscriberLanguage` | Tests CLI-layer `WhisperTranscriber` language forwarding (passes) |

### Code Flow Analysis

#### Entry Points

The language value enters the system through user input in the ConfigPanel UI widget.

- [panels.py:89-92](handsome_transcribe/ui/windows/panels.py#L89-L92) — `self.language_input = QLineEdit()` created in `_setup_ui()`
- [panels.py:333](handsome_transcribe/ui/windows/panels.py#L333) — `_on_start_session()` triggered by "Start Session" button click

#### Execution Flow — Current Behavior

```
User types "es" into language_input QLineEdit
↓
User clicks "Start Session"
↓
_on_start_session()                        → panels.py:333
  ├─ config = SessionConfig(               → panels.py:340-348
  │    modelo_whisper=...,
  │    habilitar_diarizacion=...,
  │    habilitar_resumen=...,
  │    dispositivo_audio=...,
  │    hf_token=...,
  │    session_context=...
  │  )
  │  ⚠ language_input.text() is NOT read
  │  ⚠ SessionConfig has NO language field
  │
  ├─ config_manager.save_config(config)    → config_manager.py:65
  │  ⚠ No language in config to save
  │
  └─ session_requested.emit(config)        → panels.py:358
     ↓
SessionManager receives config             → session_manager.py:52-56
     ↓
User records audio, then stops
     ↓
stop_recording()                           → session_manager.py:194
  └─ _start_transcription()                → session_manager.py:437
       ├─ TranscriberWorker(
       │    event_bus=...,
       │    audio_path=...,
       │    output_path=...,
       │    model_name=self.config.modelo_whisper
       │  )
       │  ⚠ language= NOT passed → defaults to None
       │
       └─ worker.run()                     → workers.py:262
            └─ model.transcribe(
                 str(self.audio_path),
                 language=None,            ← auto-detect
                 verbose=False
               )                           → workers.py:270-274
```

#### Parallel Path — Partial Transcription (on Pause)

```
User pauses recording
↓
pause_recording()                          → session_manager.py:158
  └─ _start_partial_transcription(path)    → session_manager.py:451
       └─ TranscriberWorker(
            event_bus=...,
            audio_path=partial_audio_path,
            output_path=output_path,
            model_name=self.config.modelo_whisper,
            emit_progress=False,
            emit_complete=False
          )
          ⚠ language= NOT passed → defaults to None
```

#### Config Load/Restore Flow

```
App starts → ConfigPanel.__init__()        → panels.py:53
  └─ _load_saved_config()                  → panels.py:213
       ├─ config = config_manager.load_config()  → config_manager.py:40
       │   Returns SessionConfig with:
       │     modelo_whisper, habilitar_diarizacion,
       │     habilitar_resumen, dispositivo_audio,
       │     hf_token, session_context=None
       │   ⚠ No language field loaded
       │
       ├─ Sets whisper_combo                → panels.py:221
       ├─ Sets diarization_check            → panels.py:225
       ├─ Sets hf_token_input               → panels.py:228
       ├─ Sets summarization_check          → panels.py:233
       ├─ Sets device_combo                 → panels.py:236
       └─ Sets context_text                 → panels.py:241
          ⚠ language_input is NOT restored
```

#### Dependencies

| Dependency | Location | Purpose |
|------------|----------|---------|
| `SessionConfig` | [models.py:30-36](handsome_transcribe/ui/models.py#L30-L36) | Data carrier from UI to workers |
| `ConfigManager` | [config_manager.py:40-82](handsome_transcribe/ui/config_manager.py#L40-L82) | Persists/loads config via QSettings |
| `SessionManager` | [session_manager.py:437-465](handsome_transcribe/ui/session_manager.py#L437-L465) | Creates `TranscriberWorker` instances |
| `TranscriberWorker` | [workers.py:222-274](handsome_transcribe/ui/workers.py#L222-L274) | Executes Whisper transcription |
| `QSettings` | PySide6 | Cross-platform settings persistence |

#### Error Handling

| Location | Error Type | Handling |
|----------|-----------|----------|
| [panels.py:353-354](handsome_transcribe/ui/windows/panels.py#L353-L354) | Validation error | Shows `QMessageBox` warning |
| [workers.py:293](handsome_transcribe/ui/workers.py#L293) | Transcription exception | Emits `transcription_error` signal |
| [config_manager.py:157-168](handsome_transcribe/ui/config_manager.py#L157-L168) | Config validation | Returns `(False, error_msg)` tuple |

No error handling exists for a missing or invalid language code. The value is silently discarded.

### Break Points — Where Language Value Is Lost

| Step | Location | What Happens |
|------|----------|--------------|
| 1 | [models.py:30-36](handsome_transcribe/ui/models.py#L30-L36) | `SessionConfig` has no field to carry language |
| 2 | [panels.py:340-348](handsome_transcribe/ui/windows/panels.py#L340-L348) | `_on_start_session` does not call `self.language_input.text()` |
| 3 | [config_manager.py:65-82](handsome_transcribe/ui/config_manager.py#L65-L82) | `save_config` has no language to write to QSettings |
| 4 | [config_manager.py:40-60](handsome_transcribe/ui/config_manager.py#L40-L60) | `load_config` does not read language from QSettings |
| 5 | [panels.py:213-243](handsome_transcribe/ui/windows/panels.py#L213-L243) | `_load_saved_config` does not restore `language_input` text |
| 6 | [session_manager.py:439-445](handsome_transcribe/ui/session_manager.py#L439-L445) | `_start_transcription` omits `language=` when creating worker |
| 7 | [session_manager.py:456-463](handsome_transcribe/ui/session_manager.py#L456-L463) | `_start_partial_transcription` omits `language=` when creating worker |

### Related Patterns

#### Similar Code

| File | Lines | Similarity |
|------|-------|------------|
| [panels.py:340-348](handsome_transcribe/ui/windows/panels.py#L340-L348) | 340-348 | `session_context` IS read from `self.context_text.toPlainText()` and passed to `SessionConfig` — language should follow the same pattern |
| [models.py:35](handsome_transcribe/ui/models.py#L35) | 35 | `session_context: Optional[str] = None` field on `SessionConfig` — language would be a similar Optional[str] field |
| [config_manager.py:55](handsome_transcribe/ui/config_manager.py#L55) | 55 | Session context is explicitly NOT persisted (by design); language persistence is a separate decision |

#### Existing Language Support (CLI Layer)

| File | Lines | What It Tests |
|------|-------|--------------|
| [tests/test_transcriber.py](tests/test_transcriber.py#L141-L200) | 141-200 | `TestWhisperTranscriberLanguage` — verifies CLI `WhisperTranscriber` correctly forwards `language=` to `whisper.transcribe()`. These tests pass, confirming the CLI pipeline handles language correctly |

#### Related Tests (UI Layer)

| Test File | Line | What It Tests |
|-----------|------|---------------|
| [tests/ui/test_config_manager.py](tests/ui/test_config_manager.py#L21-L36) | 21-36 | `test_save_and_load_config` — tests save/load without language |
| [tests/ui/test_session_manager.py](tests/ui/test_session_manager.py#L1-L100) | 1-100 | Session lifecycle tests — no language parameter tested |
| [tests/ui/test_workers.py](tests/ui/test_workers.py#L53-L67) | 53-67 | `test_create_transcriber_worker` — creates worker with `language=None` |
| [tests/ui/conftest.py](tests/ui/conftest.py#L88-L94) | 88-94 | `session_config` fixture — builds `SessionConfig` without language |

### Exact Code Snippets

#### SessionConfig Dataclass (no language field)

From [models.py:30-36](handsome_transcribe/ui/models.py#L30-L36):
```python
@dataclass
class SessionConfig:
    """Configuration for a transcription session."""
    modelo_whisper: str = "base"
    habilitar_diarizacion: bool = False
    habilitar_resumen: bool = False
    dispositivo_audio: Optional[str] = None
    hf_token: Optional[str] = None
    session_context: Optional[str] = None  # Optional context text (markdown/plain text)
```

#### _on_start_session — language_input not read

From [panels.py:333-348](handsome_transcribe/ui/windows/panels.py#L333-L348):
```python
    @Slot()
    def _on_start_session(self):
        """Slot: start session button clicked."""
        # Check for active session
        if self._has_active_session:
            QMessageBox.warning(
                self,
                "Active Session",
                "A session is already active. Finish or pause it before starting a new one."
            )
            return
        
        # Collect configuration
        config = SessionConfig(
            modelo_whisper=self.whisper_combo.currentText(),
            habilitar_diarizacion=self.diarization_check.isChecked(),
            habilitar_resumen=self.summarization_check.isChecked(),
            dispositivo_audio=self.device_combo.currentText(),
            hf_token=self.config_manager.load_config().hf_token,
            session_context=self.context_text.toPlainText() or None
        )
```

#### _start_transcription — no language= parameter

From [session_manager.py:437-449](handsome_transcribe/ui/session_manager.py#L437-L449):
```python
    def _start_transcription(self):
        """Start transcription worker after recording completes."""
        if not self.current_session:
            return
        
        self._transition_state(SessionState.TRANSCRIBING)
        
        self.transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=self.current_session.recording_path,
            output_path=self.current_session.transcript_path,
            model_name=self.config.modelo_whisper
        )
```

#### _start_partial_transcription — no language= parameter

From [session_manager.py:451-465](handsome_transcribe/ui/session_manager.py#L451-L465):
```python
    def _start_partial_transcription(self, partial_audio_path: Path):
        """Start partial transcription without advancing the pipeline."""
        if not self.current_session:
            return
        if not partial_audio_path.exists():
            return

        output_path = self.current_session.temp_dir / f"partial_{partial_audio_path.stem}.txt"
        self.partial_transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=partial_audio_path,
            output_path=output_path,
            model_name=self.config.modelo_whisper,
            emit_progress=False,
            emit_complete=False
        )
```

#### TranscriberWorker — already accepts language

From [workers.py:222-255](handsome_transcribe/ui/workers.py#L222-L255):
```python
class TranscriberWorker(QRunnable):
    def __init__(
        self,
        event_bus: EventBus,
        audio_path: Path,
        output_path: Path,
        model_name: str = "base",
        language: Optional[str] = None,
        emit_progress: bool = True,
        emit_complete: bool = True
    ):
        ...
        self.language = language
```

From [workers.py:270-274](handsome_transcribe/ui/workers.py#L270-L274):
```python
            result = model.transcribe(
                str(self.audio_path),
                language=self.language,
                verbose=False
            )
```

#### save_config — no language persisted

From [config_manager.py:65-82](handsome_transcribe/ui/config_manager.py#L65-L82):
```python
    def save_config(self, config: SessionConfig):
        self.settings.setValue("whisper/model", config.modelo_whisper)
        self.settings.setValue("features/diarization", config.habilitar_diarizacion)
        self.settings.setValue("features/summarization", config.habilitar_resumen)
        
        if config.dispositivo_audio:
            self.settings.setValue("audio/device", config.dispositivo_audio)
        
        # Do NOT save HF_TOKEN to settings (security)
        # Do NOT save session_context (session-specific)
        
        self.settings.sync()
```

#### load_config — no language loaded

From [config_manager.py:40-60](handsome_transcribe/ui/config_manager.py#L40-L60):
```python
    def load_config(self) -> SessionConfig:
        modelo_whisper = self.settings.value("whisper/model", DEFAULT_WHISPER_MODEL)
        habilitar_diarizacion = self.settings.value("features/diarization", False, type=bool)
        habilitar_resumen = self.settings.value("features/summarization", False, type=bool)
        dispositivo_audio = self.settings.value("audio/device", None)
        hf_token = os.getenv("HF_TOKEN") or self.settings.value("auth/hf_token", None)
        session_context = None
        
        return SessionConfig(
            modelo_whisper=modelo_whisper,
            habilitar_diarizacion=habilitar_diarizacion,
            habilitar_resumen=habilitar_resumen,
            dispositivo_audio=dispositivo_audio,
            hf_token=hf_token,
            session_context=session_context
        )
```

---

## Confidence Assessment

- **File References**: 17 locations identified
- **Code Snippets**: 8 exact snippets captured
- **Confidence Level**: HIGH
- **Gaps**: None — the full chain from UI input → config → session manager → worker has been traced. Every break point where the language value is lost is documented with exact file:line references.
