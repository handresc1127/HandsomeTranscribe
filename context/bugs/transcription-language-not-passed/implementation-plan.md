# Implementation Plan: transcription-language-not-passed

**Date**: 2026-03-15
**Status**: DRAFT
**Bug**: Recording transcription ignores language setting in desktop app
**Root Cause**: Incomplete feature integration — UI widget and worker support exist, but the 5 intermediate wiring steps connecting them were never implemented
**Fix Strategy**: Full Pipeline Wiring (Strategy 1)

---

## Bug Summary

| Field | Value |
|-------|-------|
| Bug ID | transcription-language-not-passed |
| Priority | High |
| Root Cause | Design Gap — `SessionConfig` has no language field; value never flows from UI to worker |
| Risk Level | Low |
| Files Changed | 5 source + 3 test = 8 total |

---

## Phase 1: Data Model — Add Language Field to `SessionConfig`

### Changes

- [ ] **`handsome_transcribe/ui/models.py:36`**: Add `idioma_transcripcion: Optional[str] = None` field after `session_context` in the `SessionConfig` dataclass. This creates the data carrier for the language value through the entire pipeline.

```python
# Current (line 36):
    session_context: Optional[str] = None  # Optional context text (markdown/plain text)

# After:
    session_context: Optional[str] = None  # Optional context text (markdown/plain text)
    idioma_transcripcion: Optional[str] = None  # Optional language code (e.g. "es", "en")
```

### Automated Success Criteria

- [ ] `SessionConfig()` still instantiates with no arguments (all defaults)
- [ ] `SessionConfig(idioma_transcripcion="es").idioma_transcripcion == "es"`
- [ ] `SessionConfig().idioma_transcripcion is None`
- [ ] `SessionConfig.from_dict({"modelo_whisper": "base"}).idioma_transcripcion is None` (backward compatible)
- [ ] `SessionConfig(idioma_transcripcion="es").to_dict()["idioma_transcripcion"] == "es"`

### Manual Verification

- [ ] No existing tests break after this change

---

## Phase 2: UI Capture — Read Language in `_on_start_session`

### Changes

- [ ] **`handsome_transcribe/ui/windows/panels.py:353-360`**: Add `idioma_transcripcion=self.language_input.text().strip() or None` to the `SessionConfig(...)` constructor call inside `_on_start_session()`.

```python
# Current (lines 353-360):
        config = SessionConfig(
            modelo_whisper=self.whisper_combo.currentText(),
            habilitar_diarizacion=self.diarization_check.isChecked(),
            habilitar_resumen=self.summarization_check.isChecked(),
            dispositivo_audio=self.device_combo.currentText(),
            hf_token=self.config_manager.load_config().hf_token,
            session_context=self.context_text.toPlainText() or None
        )

# After:
        config = SessionConfig(
            modelo_whisper=self.whisper_combo.currentText(),
            habilitar_diarizacion=self.diarization_check.isChecked(),
            habilitar_resumen=self.summarization_check.isChecked(),
            dispositivo_audio=self.device_combo.currentText(),
            hf_token=self.config_manager.load_config().hf_token,
            session_context=self.context_text.toPlainText() or None,
            idioma_transcripcion=self.language_input.text().strip() or None
        )
```

**Note**: `.strip()` prevents whitespace-only strings from reaching Whisper. `or None` converts empty string to `None` (auto-detect), which is essential to avoid passing `language=""` to Whisper.

### Automated Success Criteria

- [ ] When `language_input.text()` returns `"es"`, config receives `idioma_transcripcion="es"`
- [ ] When `language_input.text()` returns `""`, config receives `idioma_transcripcion=None`
- [ ] When `language_input.text()` returns `"  "`, config receives `idioma_transcripcion=None`

### Manual Verification

- [ ] Start a session with "es" typed in language field → config object has `idioma_transcripcion="es"`

---

## Phase 3: Config Persistence — Save and Load Language

### Changes

- [ ] **`handsome_transcribe/ui/config_manager.py:50`** (inside `load_config`, after `dispositivo_audio` load at line 50): Add language load from QSettings.

```python
# Add after line 50 (dispositivo_audio = self.settings.value("audio/device", None)):
        idioma_transcripcion = self.settings.value("whisper/language", None)
```

- [ ] **`handsome_transcribe/ui/config_manager.py:59-64`** (inside `load_config`, the `SessionConfig(...)` return constructor): Add `idioma_transcripcion=idioma_transcripcion` to the constructor.

```python
# Current (lines 59-64):
        return SessionConfig(
            modelo_whisper=modelo_whisper,
            habilitar_diarizacion=habilitar_diarizacion,
            habilitar_resumen=habilitar_resumen,
            dispositivo_audio=dispositivo_audio,
            hf_token=hf_token,
            session_context=session_context
        )

# After:
        return SessionConfig(
            modelo_whisper=modelo_whisper,
            habilitar_diarizacion=habilitar_diarizacion,
            habilitar_resumen=habilitar_resumen,
            dispositivo_audio=dispositivo_audio,
            hf_token=hf_token,
            session_context=session_context,
            idioma_transcripcion=idioma_transcripcion
        )
```

- [ ] **`handsome_transcribe/ui/config_manager.py:82`** (inside `save_config`, after the `dispositivo_audio` save block): Add language persistence to QSettings.

```python
# Add after the dispositivo_audio block (after line 82):
        if config.idioma_transcripcion:
            self.settings.setValue("whisper/language", config.idioma_transcripcion)
        else:
            self.settings.remove("whisper/language")
```

**Note**: Using `remove()` when `None` prevents stale language values from persisting when the user clears the field. This follows the same conditional pattern as `dispositivo_audio`.

### Automated Success Criteria

- [ ] `save_config(SessionConfig(idioma_transcripcion="es"))` → `load_config().idioma_transcripcion == "es"`
- [ ] `save_config(SessionConfig(idioma_transcripcion=None))` → `load_config().idioma_transcripcion is None`
- [ ] `load_config()` returns `idioma_transcripcion=None` when no value has been saved (fresh QSettings)

### Manual Verification

- [ ] Set language, restart app → language value persists

---

## Phase 4: UI Restore — Populate Language Input on Launch

### Changes

- [ ] **`handsome_transcribe/ui/windows/panels.py:305-306`** (inside `_load_saved_config`, after the `session_context` block): Add language input restoration.

```python
# Current (lines 304-308):
            # Set session context
            if config.session_context:
                self.context_text.setPlainText(config.session_context)
        
        except Exception as e:
            print(f"Error loading config: {e}")

# After:
            # Set session context
            if config.session_context:
                self.context_text.setPlainText(config.session_context)
            
            # Set language
            if config.idioma_transcripcion:
                self.language_input.setText(config.idioma_transcripcion)
        
        except Exception as e:
            print(f"Error loading config: {e}")
```

### Automated Success Criteria

- [ ] After `_load_saved_config()` with `idioma_transcripcion="es"`, `self.language_input.text() == "es"`
- [ ] After `_load_saved_config()` with `idioma_transcripcion=None`, `self.language_input.text() == ""`

### Manual Verification

- [ ] Set language to "es", restart app → language input shows "es"
- [ ] Clear language, restart app → language input is empty

---

## Phase 5: Worker Forwarding — Pass Language to `TranscriberWorker`

### Changes

- [ ] **`handsome_transcribe/ui/session_manager.py:435-440`** (in `_start_transcription`): Add `language=self.config.idioma_transcripcion` to the `TranscriberWorker(...)` constructor.

```python
# Current (lines 435-440):
        self.transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=self.current_session.recording_path,
            output_path=self.current_session.transcript_path,
            model_name=self.config.modelo_whisper
        )

# After:
        self.transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=self.current_session.recording_path,
            output_path=self.current_session.transcript_path,
            model_name=self.config.modelo_whisper,
            language=self.config.idioma_transcripcion
        )
```

- [ ] **`handsome_transcribe/ui/session_manager.py:457-462`** (in `_start_partial_transcription`): Add `language=self.config.idioma_transcripcion` to the `TranscriberWorker(...)` constructor.

```python
# Current (lines 457-462):
        self.partial_transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=partial_audio_path,
            output_path=output_path,
            model_name=self.config.modelo_whisper,
            emit_progress=False,
            emit_complete=False
        )

# After:
        self.partial_transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=partial_audio_path,
            output_path=output_path,
            model_name=self.config.modelo_whisper,
            language=self.config.idioma_transcripcion,
            emit_progress=False,
            emit_complete=False
        )
```

### Automated Success Criteria

- [ ] When `self.config.idioma_transcripcion == "es"`, the created `TranscriberWorker` has `worker.language == "es"`
- [ ] When `self.config.idioma_transcripcion is None`, the created `TranscriberWorker` has `worker.language is None`
- [ ] Both `_start_transcription` and `_start_partial_transcription` forward the language value

### Manual Verification

- [ ] Set language to "es", record Spanish audio → transcription output is correct Spanish text
- [ ] Leave language empty, record English audio → auto-detect works as before

---

## Phase 6: Testing & Regression Prevention

### Changes

- [ ] **`tests/ui/conftest.py:88-94`**: Update `session_config` fixture — no change strictly required (the new field defaults to `None` and existing tests still reflect language-not-set behavior). Optionally, add a second fixture variant for language-set scenarios.

- [ ] **`tests/ui/test_config_manager.py`**: Add test for language save/load round-trip.

```python
def test_save_and_load_config_with_language(self, config_manager):
    """Test saving and loading configuration with language."""
    config = SessionConfig(
        modelo_whisper="base",
        habilitar_diarizacion=False,
        habilitar_resumen=False,
        idioma_transcripcion="es"
    )
    config_manager.save_config(config)
    loaded = config_manager.load_config()
    assert loaded.idioma_transcripcion == "es"

def test_save_and_load_config_without_language(self, config_manager):
    """Test saving and loading configuration without language (None)."""
    config = SessionConfig(
        modelo_whisper="base",
        idioma_transcripcion=None
    )
    config_manager.save_config(config)
    loaded = config_manager.load_config()
    assert loaded.idioma_transcripcion is None
```

- [ ] **`tests/ui/test_workers.py`**: Add test for worker creation with explicit language.

```python
def test_create_transcriber_worker_with_language(self, event_bus):
    """Test creating a TranscriberWorker with explicit language."""
    worker = TranscriberWorker(
        event_bus=event_bus,
        audio_path=Path("test.wav"),
        output_path=Path("transcript.txt"),
        model_name="base",
        language="es"
    )
    assert worker.language == "es"
```

- [ ] **`tests/ui/test_models.py`** (or inline): Add test for `SessionConfig` backward compatibility.

```python
def test_session_config_language_default():
    """Test SessionConfig defaults to None language (backward compat)."""
    config = SessionConfig()
    assert config.idioma_transcripcion is None

def test_session_config_from_dict_without_language():
    """Test from_dict backward compatibility when language key is absent."""
    data = {"modelo_whisper": "base", "habilitar_diarizacion": False,
            "habilitar_resumen": False}
    config = SessionConfig.from_dict(data)
    assert config.idioma_transcripcion is None

def test_session_config_to_dict_with_language():
    """Test to_dict includes language field."""
    config = SessionConfig(idioma_transcripcion="es")
    d = config.to_dict()
    assert d["idioma_transcripcion"] == "es"
```

### Automated Success Criteria

- [ ] All new tests pass
- [ ] All existing tests pass unchanged (no fixture modifications required)
- [ ] `pytest tests/` exits 0

---

## Rollback Plan

### Steps to Revert

1. `git revert <commit-hash>` — all changes are in a single commit (recommended: commit all phases together)
2. If QSettings already has `"whisper/language"` key from testing, it will be harmlessly ignored after revert (orphaned key, no side effects)

### Verification After Rollback

- [ ] `pytest tests/` passes
- [ ] App starts without errors
- [ ] `SessionConfig()` has no `idioma_transcripcion` field (reverted)

---

## Implementation Order

All phases are independent at the code level but should be applied in order for incremental testability:

```
Phase 1 (models.py)           → can test immediately
Phase 2 (panels.py capture)   → depends on Phase 1
Phase 3 (config_manager.py)   → depends on Phase 1
Phase 4 (panels.py restore)   → depends on Phase 3
Phase 5 (session_manager.py)  → depends on Phase 1
Phase 6 (tests)               → depends on all above
```

## File Change Summary

| File | Phase | Lines Affected | Change Type |
|------|-------|---------------|-------------|
| `handsome_transcribe/ui/models.py` | 1 | 37 (new line) | Add field |
| `handsome_transcribe/ui/windows/panels.py` | 2 | 360 | Add kwarg to constructor |
| `handsome_transcribe/ui/config_manager.py` | 3 | 51, 65, 83-86 | Add load/save logic |
| `handsome_transcribe/ui/windows/panels.py` | 4 | 307-308 (new lines) | Add UI restore |
| `handsome_transcribe/ui/session_manager.py` | 5 | 440, 462 | Add kwarg to 2 constructors |
| `tests/ui/test_config_manager.py` | 6 | New tests | 2 new test methods |
| `tests/ui/test_workers.py` | 6 | New test | 1 new test method |
| `tests/ui/test_models.py` | 6 | New tests | 3 new test functions |

---

## Open Questions

None — all decisions resolved during planning.
