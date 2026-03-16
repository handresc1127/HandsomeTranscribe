# RCA Report: transcription-language-not-passed

**Date**: 2026-03-15
**Analyst**: AI Agent (RCA Analyst)
**Based on**: `research/verified-research.md` (VERIFIED WITH CORRECTIONS)
**Status**: RCA COMPLETE

---

## 1. Symptom Analysis

### User Experience

When a user types a language code (e.g. "es") into the language input field and starts a transcription session, Whisper always runs with `language=None` (auto-detect mode). For short audio clips or non-English speech, auto-detection frequently fails, producing garbled or incorrect transcription output.

### Trigger Conditions

- User enters any value in the `language_input` QLineEdit
- User starts a session and records audio
- Transcription runs on stop or pause

### Expected vs Actual Behavior

| Aspect | Expected | Actual |
|--------|----------|--------|
| Language parameter | `whisper.transcribe(language="es")` | `whisper.transcribe(language=None)` |
| Config persistence | Language saved/restored across sessions | Language never persisted |
| UI restore on launch | Language field populated with saved value | Language field always empty |

### Severity: **High**

Feature is present in the UI but completely non-functional. Users who rely on language specification get incorrect transcription with no error or warning that their setting was ignored.

---

## 2. Fault Localization

### Entry Point

User types a language code into `self.language_input` (QLineEdit) created at [panels.py](handsome_transcribe/ui/windows/panels.py#L90).

### Execution Flow (Fault Trace)

```
language_input.text() = "es"       ← User enters value
        ↓
_on_start_session()                ← panels.py:341
  config = SessionConfig(...)      ← panels.py:354-360   ⚠ FAULT: language_input NOT read
        ↓
config_manager.save_config(config) ← config_manager.py:66  ⚠ No language field to save
        ↓
session_requested.emit(config)     ← panels.py:377
        ↓
SessionManager stores config       
        ↓
_start_transcription()             ← session_manager.py:428
  TranscriberWorker(               ← session_manager.py:435-440  ⚠ No language= kwarg
    model_name=...,
  )
        ↓
TranscriberWorker.run()            ← workers.py:262
  model.transcribe(
    language=self.language          ← workers.py:271-275  language is None (default)
  )
```

### Fault Location

The **initial fault** is at two coordinated locations:

1. **`models.py:29`** — `SessionConfig` has no `language` field, so there is no data carrier for the value.
2. **`panels.py:354-360`** — `_on_start_session` never calls `self.language_input.text()`, so even if a field existed, it wouldn't be populated.

These two faults create a cascade through the entire chain: no field → nothing to save/load → nothing to pass to the worker.

---

## 3. Root Cause Identification — 5 Whys Analysis

### Why 1: Whisper transcribes with `language=None` instead of the user's selected language

**Evidence**: [session_manager.py](handsome_transcribe/ui/session_manager.py#L435-L440) — `TranscriberWorker` is constructed without `language=` parameter.  
**Connection**: The `SessionManager` never receives a language value from the config, so it cannot pass one.

### Why 2: `SessionManager` has no language value to pass to `TranscriberWorker`

**Evidence**: [session_manager.py](handsome_transcribe/ui/session_manager.py#L435) — `self.config` is a `SessionConfig` instance that carries no language field.  
**Connection**: The `SessionConfig` dataclass doesn't include a language field.

### Why 3: `SessionConfig` has no language field

**Evidence**: [models.py](handsome_transcribe/ui/models.py#L29-L36) — The dataclass defines 6 fields: `modelo_whisper`, `habilitar_diarizacion`, `habilitar_resumen`, `dispositivo_audio`, `hf_token`, `session_context`. No language field.  
**Connection**: When `session_context` was added as an optional field, the same pattern was not applied for language.

### Why 4: The `session_context` pattern was followed for adding optional UI fields, but language was omitted

**Evidence**: [panels.py](handsome_transcribe/ui/windows/panels.py#L90-L92) — The `language_input` widget **was** created in the UI, but [panels.py](handsome_transcribe/ui/windows/panels.py#L354-L360) shows `session_context` is read via `self.context_text.toPlainText()` while `language_input.text()` is absent. The reset method at [panels.py](handsome_transcribe/ui/windows/panels.py#L334) and enable/disable at [panels.py](handsome_transcribe/ui/windows/panels.py#L395) both handle `language_input`, proving the widget was intentionally added.  
**Connection**: The UI widget was added but the data-binding (model field + read in `_on_start_session`) was never completed.

### Why 5 (ROOT CAUSE): The language feature was partially implemented — the UI widget was added but the data pipeline integration was never completed

**Evidence**:
- Widget created: [panels.py](handsome_transcribe/ui/windows/panels.py#L90) — `self.language_input = QLineEdit()`
- Widget in reset: [panels.py](handsome_transcribe/ui/windows/panels.py#L334) — `self.language_input.clear()`
- Widget in enable/disable: [panels.py](handsome_transcribe/ui/windows/panels.py#L395) — `self.language_input.setEnabled(enabled)`
- Worker supports it: [workers.py](handsome_transcribe/ui/workers.py#L235) — `language: Optional[str] = None`
- Worker forwards it: [workers.py](handsome_transcribe/ui/workers.py#L271-L275) — `language=self.language`
- **Missing**: No `SessionConfig.language` field, no read in `_on_start_session`, no save/load in `ConfigManager`, no restore in `_load_saved_config`, no `language=` in worker construction calls.

**This is fundamental because**: The UI layer and the worker layer were each implemented correctly for language support, but the 5 intermediate wiring steps (model field, config read, config save, config load, worker parameter) that connect them were never implemented. This is a **Design Gap** — an incomplete feature implementation where the two ends exist but the middle is missing.

### Root Cause Category: **Design Gap** (Incomplete Feature Integration)

The language feature was added to both ends of the pipeline (UI widget + worker parameter) but the data flow chain connecting them was never wired. This is not a logic error or a regression — it is an implementation that was never completed.

---

## 4. Break Point Chain (Verified)

| Step | File:Line | What's Missing | Impact |
|------|-----------|----------------|--------|
| 1 | `models.py:29-36` | `SessionConfig` has no `language` field | No data carrier exists |
| 2 | `panels.py:354-360` | `_on_start_session` doesn't read `language_input.text()` | Value never captured |
| 3 | `config_manager.py:66-87` | `save_config` has no language to persist | Value not saved to QSettings |
| 4 | `config_manager.py:33-64` | `load_config` doesn't read language from QSettings | Value not restored |
| 5 | `panels.py:275-308` | `_load_saved_config` doesn't restore `language_input` | UI not populated on launch |
| 6 | `session_manager.py:435-440` | `_start_transcription` omits `language=` | Worker gets `None` |
| 7 | `session_manager.py:455-462` | `_start_partial_transcription` omits `language=` | Partial worker gets `None` |

---

## 5. Fix Strategies

### Strategy 1: Full Pipeline Wiring (RECOMMENDED)

**Approach**: Add `language` field to `SessionConfig` and wire it through all 7 break points, following the existing `session_context` pattern for the model field and the `modelo_whisper` pattern for config persistence.

**Files to modify**:

| File | Line | Change |
|------|------|--------|
| `models.py:36` | After `session_context` field | Add `idioma_transcripcion: Optional[str] = None` |
| `panels.py:354-360` | `_on_start_session` `SessionConfig(...)` | Add `idioma_transcripcion=self.language_input.text() or None` |
| `config_manager.py:48` | After `dispositivo_audio` load | Add `idioma = self.settings.value("whisper/language", None)` |
| `config_manager.py:62` | `SessionConfig(...)` constructor | Add `idioma_transcripcion=idioma` |
| `config_manager.py:82` | After `dispositivo_audio` save | Add `self.settings.setValue("whisper/language", config.idioma_transcripcion)` |
| `panels.py:275-308` | `_load_saved_config` | Add language_input restoration after whisper_combo |
| `session_manager.py:435-440` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |
| `session_manager.py:455-462` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |

**Tests to update**:
- `tests/ui/conftest.py:88-94` — Add `idioma_transcripcion` to `session_config` fixture
- `tests/ui/test_config_manager.py:21` — Add language save/load assertion
- `tests/ui/test_workers.py:55` — Test worker creation with language

**Pros**:
- Complete fix covering all 7 break points
- Language persists across sessions (user convenience)
- Follows existing patterns exactly (`session_context` for model, `modelo_whisper` for persistence)
- `TranscriberWorker` already handles `language` — no worker changes needed

**Cons**:
- Touches 5 source files and 3 test files (moderate scope)

**Risk Level**: Low  
**Estimated Complexity**: Low  
**Regression Risk**: Low — all changes are additive (new optional field with `None` default). Existing behavior unchanged when language is not set. No existing tests should break since the new field defaults to `None`.

---

### Strategy 2: Config-Less Pass-Through (ALTERNATIVE)

**Approach**: Add `language` to `SessionConfig` and wire it from UI → session manager → worker, but do NOT persist it in `ConfigManager`. Treat language the same way `session_context` is treated (session-specific, not saved).

**Files to modify**:

| File | Line | Change |
|------|------|--------|
| `models.py:36` | After `session_context` | Add `idioma_transcripcion: Optional[str] = None` |
| `panels.py:354-360` | `_on_start_session` | Add `idioma_transcripcion=self.language_input.text() or None` |
| `session_manager.py:435-440` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |
| `session_manager.py:455-462` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |

**Pros**:
- Fewer files changed (4 instead of 5+)
- Simpler — no config persistence logic
- Fixes the core bug (language reaches Whisper)

**Cons**:
- Language not remembered across sessions (user must re-enter each time)
- Breaks points 3-5 remain (save/load/restore) — though they become "by design" rather than bugs
- Inconsistent with `modelo_whisper` which IS persisted

**Risk Level**: Low  
**Estimated Complexity**: Low  
**Regression Risk**: Very low — even fewer changes than Strategy 1

---

### Strategy 3: Minimal Worker-Level Patch (MINIMAL)

**Approach**: Skip `SessionConfig` entirely. Store a `self._language` attribute on `SessionManager` set directly from signal data, and pass it to workers. This would require the UI to emit the language separately.

**Files to modify**:

| File | Line | Change |
|------|------|--------|
| `panels.py:377` | After `session_requested.emit(config)` | Emit a separate `language_changed` signal |
| `session_manager.py` | New attribute | Store `self._language` |
| `session_manager.py:435-440` | `TranscriberWorker(...)` | Add `language=self._language` |
| `session_manager.py:455-462` | `TranscriberWorker(...)` | Add `language=self._language` |

**Pros**:
- Does not change `SessionConfig` (no model changes)
- Smallest possible fix for the core symptom

**Cons**:
- Introduces a parallel data path outside the config pattern
- Language not part of session metadata
- Violates the existing architecture pattern (all config flows through `SessionConfig`)
- Harder to maintain long-term
- Still no persistence

**Risk Level**: Medium  
**Estimated Complexity**: Low  
**Regression Risk**: Low for functionality, but medium for maintainability (tech debt)

---

## 6. Recommendation

**Strategy 1 (Full Pipeline Wiring)** is strongly recommended.

**Rationale**:
1. It is the only strategy that fully resolves all 7 break points
2. It follows existing patterns precisely — `session_context` as model for the optional field, `modelo_whisper` as model for config persistence
3. Risk is very low because all changes are additive with `None` defaults
4. The `TranscriberWorker` already handles `language` correctly — the worker layer needs zero changes
5. Language persistence across sessions is expected UX behavior (users shouldn't have to re-enter language every session)
6. The implementation complexity is low — each change is 1-3 lines of code following existing adjacent patterns

---

## References

- Verified Research: [verified-research.md](research/verified-research.md)
- Codebase Research: [codebase-research.md](research/codebase-research.md)
- Bug Context: [bug-context.md](bug-context.md)
