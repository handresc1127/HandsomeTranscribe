# Verified Research: transcription-language-not-passed

**Date**: 2026-03-15
**Verifier**: AI Agent (Research Verifier)
**Original Research**: `codebase-research.md`
**Status**: VERIFIED WITH CORRECTIONS

---

## Verification Summary

**Overall Confidence**: MEDIUM

The core bug diagnosis and code logic descriptions are **fully accurate**. All 7 break points correctly identify where the language value is lost. However, the majority of line number references are incorrect. Code content matches actual source; only line numbers need correction.

| Category        | Verified | Corrections   | Confidence |
| --------------- | -------- | ------------- | ---------- |
| File References | 4/25     | 21 corrections| LOW        |
| Code Claims     | 16/16    | 0 corrections | HIGH       |
| Code Snippets   | 8/8      | 0 corrections | HIGH       |
| Relationships   | 7/7      | 0 corrections | HIGH       |

---

## Verified Claims ✅

### Bug Diagnosis (fully verified)

- `SessionConfig` has no `language` field — **CONFIRMED** (models.py:29)
- `_on_start_session` does not call `self.language_input.text()` when building `SessionConfig` — **CONFIRMED** (panels.py:341)
- `save_config` persists no language to QSettings — **CONFIRMED** (config_manager.py:66)
- `load_config` loads no language from QSettings — **CONFIRMED** (config_manager.py:33)
- `_load_saved_config` does not restore `language_input` text — **CONFIRMED** (panels.py:275)
- `_start_transcription` creates `TranscriberWorker` without `language=` — **CONFIRMED** (session_manager.py:428)
- `_start_partial_transcription` creates `TranscriberWorker` without `language=` — **CONFIRMED** (session_manager.py:447)
- `TranscriberWorker.__init__` accepts `language: Optional[str] = None` — **CONFIRMED** (workers.py:228)
- `TranscriberWorker.run` passes `language=self.language` to `model.transcribe()` — **CONFIRMED** (workers.py:273)

### Code Snippets (all content-accurate)

All 8 code snippets in the research document match the actual source code. Functional logic, parameter names, and code structure are correct.

### Relationships (all verified)

- `_on_start_session` → `config_manager.save_config()` → `session_requested.emit(config)` ✅
- `pause_recording()` → `_start_partial_transcription()` → `TranscriberWorker` ✅
- `stop_recording()` → `_start_transcription()` → `TranscriberWorker` ✅
- `TranscriberWorker.run()` → `model.transcribe(language=self.language)` ✅

### Correct Line References

| File | Claim | Status |
|------|-------|--------|
| `panels.py:89-92` | `language_input` QLineEdit widget block | ✅ Correct |
| `tests/ui/conftest.py:88-94` | `SessionConfig(...)` construction in fixture | ✅ Correct |
| `tests/ui/test_config_manager.py:21` | `test_save_and_load_config` def start | ✅ Correct |
| `tests/test_transcriber.py:141` | `TestWhisperTranscriberLanguage` class start | ✅ Correct |

---

## Corrections Made

Line number discrepancies are pervasive but follow a consistent pattern (likely caused by file content having grown since research was written, or off-by-N counting from section starts).

### Correction 1 — `models.py`: SessionConfig class start

**Original**: `models.py:30-36` (table) / snippet header `models.py:30-36`
**Actual**: `@dataclass` at line **28**, `class SessionConfig:` at line **29**, fields at lines 31–36; full class declaration: **28–36**
**Impact**: Minor. The `@dataclass` decorator and class declaration are at 28–29, not 30. Code content is correct.

---

### Correction 2 — `panels.py`: `ConfigPanel.__init__()` line

**Original**: Flow diagram references `panels.py:53` for `ConfigPanel.__init__()`
**Actual**: `def __init__` is at line **46**; `self._load_saved_config()` call is at line **57**
**Impact**: Minor. `__init__` starts at 46, not 53.

---

### Correction 3 — `panels.py`: `_load_saved_config` line range (MAJOR)

**Original**: `panels.py:213-243`
**Actual**: `def _load_saved_config(self):` at line **275**, function ends at approximately line **308** → correct range: **275–308**
**Impact**: High. All sub-references inside this function cited in the Code Flow section are also wrong:

| Research Claim | Actual Line |
|---------------|-------------|
| Sets whisper_combo → `panels.py:221` | ~282 |
| Sets diarization_check → `panels.py:225` | ~287 |
| Sets hf_token_input → `panels.py:228` | ~290 |
| Sets summarization_check → `panels.py:233` | ~295 |
| Sets device_combo → `panels.py:236` | ~298 |
| Sets context_text → `panels.py:241` | ~304 |

---

### Correction 4 — `panels.py`: `_on_reset_config` and `language_input.clear()`

**Original**: `panels.py:317` for `_on_reset_config`; `panels.py:317` for `language_input.clear()`
**Actual**: `def _on_reset_config(self):` at line **324**; `self.language_input.clear()` at line **334**
**Impact**: Moderate. Two separate claimed references both said line 317.

---

### Correction 5 — `panels.py`: `_on_start_session` and `SessionConfig` construction

**Original**: Function at `panels.py:333-348`; `SessionConfig(...)` construction at `panels.py:340-348`
**Actual**: `def _on_start_session(self):` at line **341** (decorator `@Slot()` at 340); `config = SessionConfig(` at line **353**, closing `)` at line **360** → correct range: **341–380**
**Impact**: Moderate. Break point 2 table entry (`panels.py:340-348`) needs correction to **353–360**.

---

### Correction 6 — `panels.py`: `_set_panel_enabled` and `session_requested.emit`

**Original**: `_set_panel_enabled` at `panels.py:396`; `session_requested.emit(config)` at `panels.py:358`
**Actual**: `def _set_panel_enabled(self, enabled: bool):` at line **395**; `self.session_requested.emit(config)` at line **377**
**Impact**: Minor for `_set_panel_enabled` (off by 1); moderate for `session_requested.emit` (off by 19).

---

### Correction 7 — `panels.py`: Validation error `QMessageBox.warning`

**Original**: Error handling at `panels.py:353-354`
**Actual**: `is_valid, error = self.config_manager.validate_config(config)` at line **363**; `QMessageBox.warning(...)` for invalid config at line **365**
**Impact**: Minor.

---

### Correction 8 — `config_manager.py`: `load_config` line range

**Original**: `config_manager.py:40-60`
**Actual**: `def load_config(self) -> SessionConfig:` at line **33**, function closes at approximately line **64** → correct range: **33–64**
**Impact**: Moderate. Start is off by 7 lines.

---

### Correction 9 — `config_manager.py`: `save_config` line range

**Original**: `config_manager.py:65-82`
**Actual**: `def save_config(self, config: SessionConfig):` at line **66** → correct range: **66–87** (approx)
**Impact**: Minor (off by 1 at start).

---

### Correction 10 — `config_manager.py`: Validation error handling (MAJOR)

**Original**: Error handling at `config_manager.py:157-168`
**Actual**: Lines 151–175 contain `validate_hf_token()`; `def validate_config(...)` is at line **192**
**Impact**: High. The claimed range (157–168) points to `validate_hf_token`, not `validate_config`. The correct reference is **192–230**.

---

### Correction 11 — `session_manager.py`: `_start_transcription` line range

**Original**: `session_manager.py:437-449`
**Actual**: `def _start_transcription(self):` at line **428**; `TranscriberWorker(...)` construction at **435–440**; function ends at line **446** → correct range: **428–446**
**Impact**: Moderate. Break point 6 table entry (`session_manager.py:439-445`) needs correction to **435–440**.

---

### Correction 12 — `session_manager.py`: `_start_partial_transcription` line range

**Original**: `session_manager.py:451-465`
**Actual**: `def _start_partial_transcription(self, partial_audio_path: Path):` at line **447**; `partial_transcriber_worker = TranscriberWorker(...)` at **455–462**; function ends at line **463** → correct range: **447–463**
**Impact**: Minor. Break point 7 table entry (`session_manager.py:456-463`) needs correction to **455–462**.

---

### Correction 13 — `session_manager.py`: `pause_recording` and `stop_recording` line references

**Original**: `pause_recording()` → `session_manager.py:158`; `stop_recording()` → `session_manager.py:194`
**Actual**: `def pause_recording(self):` at line **170**; `def stop_recording(self):` at line **220**
**Impact**: Moderate (off by 12 and 26 respectively).

---

### Correction 14 — `workers.py`: `TranscriberWorker` class and `__init__` range

**Original**: `workers.py:222-255` for `TranscriberWorker.__init__`
**Actual**: `class TranscriberWorker(QRunnable):` at line **221**; `def __init__(` at line **228**; `__init__` body ends at line **255** → class declaration starts at **221**, `__init__` range: **228–255**
**Impact**: Minor (off by 1 for class start).

---

### Correction 15 — `workers.py`: `model.transcribe()` call range

**Original**: `workers.py:270-274`
**Actual**: `result = model.transcribe(` at line **271**; closing `)` at line **275** → correct range: **271–275**
**Impact**: Minor (off by 1).

---

### Correction 16 — `workers.py`: `transcription_error` signal emission

**Original**: `workers.py:293`
**Actual**: `self.event_bus.emit_transcription_error(...)` at line **301**
**Impact**: Minor (off by 8).

---

### Correction 17 — `tests/ui/test_workers.py`: `test_create_transcriber_worker` start

**Original**: `test_workers.py:53-67`
**Actual**: `def test_create_transcriber_worker(self, event_bus):` at line **55** (class `TestTranscriberWorker` at line **52**)
**Impact**: Minor (off by 2).

---

## Corrected Code Locations Table

| File | Corrected Lines | Component | Description |
|------|-----------------|-----------|-------------|
| `handsome_transcribe/ui/models.py` | **28–36** | `SessionConfig` | Dataclass with 6 fields; `@dataclass` at 28, class at 29 |
| `handsome_transcribe/ui/windows/panels.py` | **90** | `ConfigPanel._setup_ui` | Creates `self.language_input = QLineEdit()` |
| `handsome_transcribe/ui/windows/panels.py` | **353–360** | `ConfigPanel._on_start_session` | Builds `SessionConfig` without reading `language_input` |
| `handsome_transcribe/ui/windows/panels.py` | **275–308** | `ConfigPanel._load_saved_config` | Restores all fields except language |
| `handsome_transcribe/ui/windows/panels.py` | **334** | `ConfigPanel._on_reset_config` | Clears `language_input` (aware of field) |
| `handsome_transcribe/ui/windows/panels.py` | **395** | `ConfigPanel._set_panel_enabled` | Enables/disables `language_input` (aware of field) |
| `handsome_transcribe/ui/config_manager.py` | **33–64** | `ConfigManager.load_config` | Returns `SessionConfig` without language |
| `handsome_transcribe/ui/config_manager.py` | **66–87** | `ConfigManager.save_config` | Persists model, diarization, summarization, device; no language |
| `handsome_transcribe/ui/session_manager.py` | **428–446** | `SessionManager._start_transcription` | Creates `TranscriberWorker` without `language=` |
| `handsome_transcribe/ui/session_manager.py` | **447–463** | `SessionManager._start_partial_transcription` | Creates `TranscriberWorker` without `language=` |
| `handsome_transcribe/ui/workers.py` | **228–255** | `TranscriberWorker.__init__` | Accepts `language: Optional[str] = None` |
| `handsome_transcribe/ui/workers.py` | **271–275** | `TranscriberWorker.run` | Passes `language=self.language` to `model.transcribe()` |
| `tests/ui/conftest.py` | **88–94** | `session_config` fixture | Creates `SessionConfig` without language field ✅ |
| `tests/ui/test_config_manager.py` | **21–36** | `test_save_and_load_config` | Tests save/load without language ✅ |
| `tests/ui/test_workers.py` | **55–67** | `test_create_transcriber_worker` | Creates worker with `language=None` |
| `tests/test_transcriber.py` | **141–200** | `TestWhisperTranscriberLanguage` | Tests CLI-layer language forwarding (passes) ✅ |

---

## Corrected Break Points Table

| Step | Corrected Location | What Happens |
|------|-------------------|--------------|
| 1 | `models.py:28–36` | `SessionConfig` has no field to carry language |
| 2 | `panels.py:353–360` | `_on_start_session` does not call `self.language_input.text()` |
| 3 | `config_manager.py:66–87` | `save_config` has no language to write to QSettings |
| 4 | `config_manager.py:33–64` | `load_config` does not read language from QSettings |
| 5 | `panels.py:275–308` | `_load_saved_config` does not restore `language_input` text |
| 6 | `session_manager.py:435–440` | `_start_transcription` omits `language=` when creating worker |
| 7 | `session_manager.py:455–462` | `_start_partial_transcription` omits `language=` when creating worker |

---

## Gaps Identified

None. The original research correctly identifies the full chain from UI input to Whisper. The gap is entirely in line number accuracy, not coverage.

---

## Recommendation

**PROCEED TO RCA**

**Reasoning**: The bug diagnosis is complete and fully accurate. All 7 break points are correctly identified. The code snippets, relationships, and behavioral descriptions are confirmed correct. The line number inaccuracies affect only navigation convenience — not the validity of the root cause analysis or fix strategy. A fix implementor can use the corrected line numbers from this document.

---

## References

- Original Research: `codebase-research.md`
- Verified files: `models.py`, `windows/panels.py`, `config_manager.py`, `session_manager.py`, `workers.py`, `tests/ui/conftest.py`, `tests/ui/test_config_manager.py`, `tests/ui/test_workers.py`, `tests/test_transcriber.py`
