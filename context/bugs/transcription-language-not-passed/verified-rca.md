# Verified RCA: transcription-language-not-passed

**Date**: 2026-03-15
**Verifier**: AI Agent (RCA Verifier)
**Original RCA**: `rca-report.md`
**Status**: VERIFIED WITH NOTES

---

## Verification Summary

| Check                     | Result | Notes                                                                          |
| ------------------------- | ------ | ------------------------------------------------------------------------------ |
| 5 Whys Depth              | ✅     | 5 levels for a multi-layer pipeline bug; each level digs deeper                |
| Root Cause Fundamental    | ✅     | "Incomplete feature integration" — cannot be asked WHY further from code alone |
| Execution Path            | ✅     | All 7 break points confirmed in source; 2 line refs off by 1 (notes below)     |
| Fix Strategies            | ✅     | Strategy 1 addresses all 7 break points; additive only; backward compatible    |
| Side Effects              | ✅     | `SessionConfig.from_dict()` and `from_json()` backward compatible with `None` default; no regressions expected |

---

## Root Cause (Confirmed)

The language feature was added to **both ends** of the pipeline — the UI widget (`language_input` QLineEdit) and the worker parameter (`TranscriberWorker.language`) — but the **5 intermediate wiring steps** that connect them were never implemented:

1. `SessionConfig` has no `language` field (data carrier missing)
2. `_on_start_session` does not read `language_input.text()` (value never captured)
3. `config_manager.save_config` never persists language (not saved)
4. `config_manager.load_config` never reads language (not restored)
5. `_load_saved_config` does not populate `language_input` (UI not restored on launch)
6. `_start_transcription` constructs `TranscriberWorker` without `language=` (not forwarded)
7. `_start_partial_transcription` same omission (not forwarded on pause)

**Category**: Design Gap (Incomplete Feature Integration)

The root cause is not a regression or a logic error. Both ends were correctly implemented; the connection between them was never built.

---

## File:Line Reference Verification

All critical references from the Break Point Chain table were verified against the live codebase.

| RCA Reference                  | Actual Lines | Status | Notes                                          |
| ------------------------------ | ------------ | ------ | ---------------------------------------------- |
| `models.py:29-36`              | 28–36        | ✅     | `@dataclass` decorator at 28, class at 29      |
| `panels.py:90`                 | 90           | ✅     | `self.language_input = QLineEdit()` confirmed  |
| `panels.py:334`                | 334          | ✅     | `self.language_input.clear()` confirmed        |
| `panels.py:341`                | 341          | ✅     | `def _on_start_session(self):` confirmed       |
| `panels.py:354-360`            | **353–360**  | ⚠️     | `config = SessionConfig(` is at 353, not 354   |
| `panels.py:275-308`            | 275–308      | ✅     | `def _load_saved_config(self):` confirmed      |
| `panels.py:395`                | 395          | ✅     | `def _set_panel_enabled(self, enabled: bool):` |
| `config_manager.py:33-64`     | 33–64        | ✅     | `def load_config(self):` confirmed             |
| `config_manager.py:66-87`     | 66–87        | ✅     | `def save_config(self, config: SessionConfig):` |
| `session_manager.py:435-440`  | 435–440      | ✅     | `TranscriberWorker(...)` — no `language=` kwarg |
| `session_manager.py:455-462`  | 455–462      | ✅     | `partial_transcriber_worker = TranscriberWorker(...)` |
| `workers.py:235`               | **234**      | ⚠️     | `language: Optional[str] = None` is at 234    |
| `workers.py:271-275`           | 271–275      | ✅     | `model.transcribe(... language=self.language ...)` confirmed |
| `tests/ui/conftest.py:88-94`  | 88–94        | ✅     | `SessionConfig(...)` fixture confirmed         |
| `tests/ui/test_config_manager.py:21` | 21    | ✅     | `def test_save_and_load_config` confirmed      |
| `tests/ui/test_workers.py:55` | 55           | ✅     | `def test_create_transcriber_worker` confirmed; file exists |

**⚠️ Minor discrepancies** (2): Both are off-by-1 and consistent with the variance already documented in `verified-research.md`. The code content at each location matches RCA descriptions exactly — only the start line is shifted by 1. These do not affect analysis validity.

---

## 5 Whys Validation

| Why | Claim | Verdict | Basis |
| --- | ----- | ------- | ----- |
| 1 | Whisper runs with `language=None` because `TranscriberWorker` is constructed without `language=` | ✅ Confirmed | `session_manager.py:435-440` and `455-462` show `TranscriberWorker` calls with no `language` kwarg |
| 2 | `SessionManager` has no language to pass because `SessionConfig` has no `language` field | ✅ Confirmed | `models.py:29-36` — 6 fields, none is language |
| 3 | `SessionConfig` has no language field because no one added it when the UI widget was created | ✅ Confirmed | The `session_context` field was added (line 36) but language was not — clear omission |
| 4 | The session_context pattern was followed for optional fields but language was skipped | ✅ Confirmed | `panels.py:90` widget exists, `panels.py:395` enable/disable exists, `panels.py:334` reset exists — but no `models.py` field and no read in `_on_start_session` |
| 5 (ROOT) | Feature was partially implemented — UI widget and worker support exist, 5 middle wiring steps do not | ✅ Fundamental | Cannot ask WHY further; this is the implementation boundary. The two ends are correct; the pipeline connection was simply never built |

**Fundamentality check**: Passes. The root cause identifies a **design gap** — both ends of the pipeline were implemented but they were never connected. This is not a symptom of a deeper bug; it is the terminal explanation available from code analysis.

---

## Recommended Fix Strategy

**Strategy**: Full Pipeline Wiring (Strategy 1 from rca-report.md)
**Risk Level**: Low
**Files to Modify**: 5 source files, 3 test files

### Why Strategy 1 over alternatives

- **vs. Strategy 2 (Config-Less Pass-Through)**: Strategy 1 also adds persistence via `ConfigManager`. Language is a user preference analogous to `modelo_whisper` (persisted) — not session-specific like `session_context` (not persisted). Omitting persistence leaves break points 3–5 unresolved by design, which is an inconsistent UX.
- **vs. Strategy 3 (Worker-Level Patch)**: Creates a parallel data path outside `SessionConfig`, violates the existing architecture pattern, and introduces tech debt without benefit.

### Regression Risk Assessment

All changes are **additive**:
- `idioma_transcripcion: Optional[str] = None` in `SessionConfig` — existing consumers of `SessionConfig` unaffected; `from_dict()` and `from_json()` backward compatible since field has a default
- `ConfigManager` saves/loads with `QSettings` key `"whisper/language"` — new key, no conflicts
- `TranscriberWorker` already accepts `language` — no worker changes required
- Existing sessions without language (all current `outputs/sessions/*/metadata.json`) remain valid — `from_dict()` will use `None` default

**Existing tests will not break.** The `session_config` fixture in `conftest.py:88-94` does not specify `idioma_transcripcion`, which will default to `None` — all existing tests continue to reflect language-not-set behavior.

### Implementation Targets (Corrected Line Numbers)

| File | Corrected Line | Change |
| ---- | -------------- | ------ |
| `models.py:36` | After `session_context` | Add `idioma_transcripcion: Optional[str] = None` |
| `panels.py:353-360` | Inside `_on_start_session` `SessionConfig(...)` | Add `idioma_transcripcion=self.language_input.text() or None` |
| `config_manager.py:48` | In `load_config`, after `dispositivo_audio` | Add `idioma = self.settings.value("whisper/language", None)` |
| `config_manager.py:62` | `SessionConfig(...)` constructor | Add `idioma_transcripcion=idioma` |
| `config_manager.py:82` | In `save_config`, after `dispositivo_audio` | Add `self.settings.setValue("whisper/language", config.idioma_transcripcion)` |
| `panels.py:304` | In `_load_saved_config`, after `session_context` block | Add language_input restore |
| `session_manager.py:435-440` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |
| `session_manager.py:455-462` | `TranscriberWorker(...)` | Add `language=self.config.idioma_transcripcion` |

---

## Verification Notes

1. **`tests/ui/test_workers.py` confirmed to exist** at the workspace path. `test_create_transcriber_worker` is at line 55 and already tests worker construction with `language=None`. The plan to add a test for `language="es"` is appropriate.

2. **`config_manager.py` save_config comment** already states `# Do NOT save session_context (session-specific)`. When adding language persistence, this comment should be updated or left as-is (the comment only covers `session_context`, not the new language field — no change needed).

3. **`_load_saved_config` insertion point**: The corrected range 275–308 ends at `print(f"Error loading config: {e}")`. The language restoration block should be inserted at approximately line 304, inside the `try` block, after the `session_context` block (line 303–305), to follow the established ordering pattern.

4. **`or None` idiom**: The RCA recommends `self.language_input.text() or None` which converts empty string to `None`. This is correct — an empty string would otherwise reach `whisper.transcribe(language="")` which would cause a Whisper error. The `or None` guard is essential.

---

## Corrections to RCA

No structural corrections required. The following minor line-number adjustments are noted for implementation precision:

| Location in RCA | Stated | Actual | Severity |
| --------------- | ------ | ------ | -------- |
| Break Point 2, Execution Flow | `panels.py:354-360` | `panels.py:353-360` | Minor (off by 1 at open) |
| Why 1 Evidence footnote | `workers.py:235` | `workers.py:234` | Minor (off by 1) |

Both within the ±1 variance already documented in `verified-research.md`.

---

## Final Verdict

**VERIFIED WITH NOTES** — The RCA is accurate and complete. The root cause is correctly identified as **incomplete feature integration** (Design Gap). The 5 Whys reaches a genuinely fundamental cause. All break points are confirmed in the codebase. Strategy 1 (Full Pipeline Wiring) is the correct fix, with low risk and no expected regressions.

Ready for implementation planning.
