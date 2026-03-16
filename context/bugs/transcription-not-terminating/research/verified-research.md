# Verified Research: transcription-not-terminating

**Date**: 2026-03-15
**Verifier**: AI Agent (Research Verifier)
**Original Research**: `codebase-research.md`
**Status**: VERIFIED WITH CORRECTIONS

---

## Verification Summary

**Overall Confidence**: HIGH

All critical substantive claims are accurate. Inaccuracies are limited to line number references (off by 1–25 lines in various locations). No hallucinations detected.

| Category        | Verified | Corrections   | Confidence |
| --------------- | -------- | ------------- | ---------- |
| File References | 6/6      | 0 corrections | HIGH       |
| Code Claims     | 5/5      | 0 corrections | HIGH       |
| Code Snippets   | 4/4      | 0 corrections | HIGH       |
| Line Numbers    | 8/23     | 15 corrections | MEDIUM     |

---

## Verified Claims

### Claim 1: SessionManager connects to ZERO error signals ✅

**Verified**. Grep of all `.connect()` calls in `session_manager.py` found exactly 9 connections — none are error signals:

| Line | Signal Connected | Handler |
|------|-----------------|---------|
| 80 | `_autosave_timer.timeout` | `_auto_save_progress` |
| 85 | `_partial_transcription_timer.timeout` | `_periodic_partial_transcription` |
| 96 | `pause_recording_requested` | `pause_recording` |
| 97 | `resume_recording_requested` | `resume_recording` |
| 98 | `stop_recording_requested` | `stop_recording` |
| 470 | `transcription_complete` | `_on_transcription_complete` |
| 517 | `speaker_update_ready` | `_on_diarization_complete` |
| 538 | `summarization_complete` | `_on_summarization_complete` |
| 555 | `reports_ready` | `_on_reports_ready` |

No `transcription_error`, `diarization_error`, `summarization_error`, `report_generation_error`, `recording_error`, or `session_error` connections exist anywhere in `session_manager.py`.

---

### Claim 2: Worker error signal mismatch ✅

**Verified** at exact line numbers. Each worker's exception handler emits:

| Worker | Line | Signal Emitted | Expected Stage Signal |
|--------|------|----------------|-----------------------|
| `TranscriberWorker` | 301 | `emit_transcription_error()` → `transcription_error` | `transcription_error` ✅ matches |
| `DiarizerWorker` | 456 | `emit_session_error()` → `session_error` | `diarization_error` ❌ mismatch |
| `SummarizerWorker` | 538 | `emit_session_error()` → `session_error` | `summarization_error` ❌ mismatch |
| `ReporterWorker` | 657 | `emit_session_error()` → `session_error` | `report_generation_error` ❌ mismatch |

Code snippets confirmed exact character match with source.

---

### Claim 3: No logging in SessionManager or workers except RecorderWorker ✅

**Verified**. `AppLogger` usage in `workers.py`:
- Line 19: `from .logger import AppLogger` (import only)
- Line 75: `logger = AppLogger.get_logger("ui.workers.recorder")` — inside `RecorderWorker.run()`
- Line 118: `logger = AppLogger.get_logger("ui.workers.recorder")` — inside `RecorderWorker`'s except block

No `AppLogger`, `logging`, or `logger` references exist anywhere in `session_manager.py`. `TranscriberWorker`, `DiarizerWorker`, `SummarizerWorker`, and `ReporterWorker` contain no logging.

---

### Claim 4: `diarization_complete` signal is never emitted ✅

**Verified**. Workspace-wide grep for `diarization_complete.emit` and `emit_diarization_complete` returned zero results. The `DiarizerWorker.run()` emits `emit_speaker_update(speaker_map)` on success (→ `speaker_update_ready` signal), not `diarization_complete`. The `diarization_complete` signal defined in `event_bus.py` at line 39 is unreachable dead code.

---

### Claim 5: EventBus has no emit helpers for diarization_error, summarization_error, report_generation_error ✅

**Verified**. Complete grep of all `def emit_` methods in `event_bus.py` confirms the only error-related emit helpers are:

| Method | Signal | Actual Line |
|--------|--------|-------------|
| `emit_recording_error` | `recording_error` | 118 |
| `emit_transcription_error` | `transcription_error` | 145 |
| `emit_session_error` | `session_error` | 235 |

No `emit_diarization_error`, `emit_summarization_error`, or `emit_report_generation_error` methods exist. The corresponding signals (`diarization_error` L40, `summarization_error` L45, `report_generation_error` L50) are defined but have no emitter helper.

---

### Claim 6: WorkerSignals class is unused ✅

**Verified**. `WorkerSignals` is defined at `workers.py` line 23. Grep confirms it is never instantiated or referenced by any worker class.

---

### Claim 7: Pipeline flow is structurally correct ✅

The described execution flow is accurate. In the happy path:

```
stop_recording() [L234]
  → _start_transcription() [L454]
    → transcription_complete.connect(_on_transcription_complete) [L470]
  → _on_transcription_complete() [L587]
    → _start_diarization() [L493]
      → speaker_update_ready.connect(_on_diarization_complete) [L517]
  → _on_diarization_complete() [L603]
    → _start_summarization() [L521]
      → summarization_complete.connect(_on_summarization_complete) [L538]
  → _on_summarization_complete() [L619]
    → _start_reporting() [L542]
      → reports_ready.connect(_on_reports_ready) [L555]
  → _on_reports_ready() [L635]
    → _complete_session() [L559]
```

The error path hang is confirmed: when any worker throws an exception, the emitted error signal has no connected handler in `SessionManager`, leaving the session frozen in its current state indefinitely.

---

## Corrections Made

### Correction 1: TranscriberWorker start line

**Original**: research component table says `workers.py: 196-301`
**Actual**: `TranscriberWorker` class definition starts at line **221** (off by 25)
**Impact**: Low — affects only the component table entry; functional claims about the worker are correct.

### Correction 2: `stop_recording()` line number

**Original**: research code flow says `session_manager.py:244`
**Actual**: `stop_recording()` defined at line **234** (off by 10)
**Impact**: Low — documentation accuracy only.

### Correction 3: `_start_transcription()` line number

**Original**: `session_manager.py:458`
**Actual**: line **454** (off by 4)
**Impact**: Low.

### Correction 4: `_start_diarization()` line number

**Original**: `session_manager.py:499`
**Actual**: line **493** (off by 6)
**Impact**: Low.

### Correction 5: Callback handler line numbers

**Original**:
- `_on_transcription_complete` at L585
- `_on_diarization_complete` at L598
- `_on_summarization_complete` at L612
- `_on_reports_ready` at L626

**Actual**:
- `_on_transcription_complete` at **L587** (off by 2)
- `_on_diarization_complete` at **L603** (off by 5)
- `_on_summarization_complete` at **L619** (off by 7)
- `_on_reports_ready` at **L635** (off by 9)

**Impact**: Low — documentation accuracy only.

### Correction 6: `TranscriberWorker.run()` start line

**Original**: Finding 7 code snippet says `workers.py#L265-L301`
**Actual**: `run()` method starts at line **257** (off by 8); except block at line 300-301 ✅
**Impact**: Low.

### Correction 7: EventBus emit method line numbers

**Original**:
- `emit_recording_error` at L124-131
- `emit_transcription_error` at L153-160
- `emit_session_error` at L237-245

**Actual**:
- `emit_recording_error` at **L118** (off by 6)
- `emit_transcription_error` at **L145** (off by 8)
- `emit_session_error` at **L235** (off by 2)

**Impact**: Low — functional claims about these methods are correct.

### Correction 8: Minor signal definition line offsets

**Original**: `transcription_error` signal at `event_bus.py:31`
**Actual**: line **30** (off by 1)
**Impact**: Negligible.

---

## Gaps Identified

1. **No unit tests for pipeline error handling** — No test files exist for `SessionManager`, `TranscriberWorker`, or the pipeline error paths. Impact: HIGH (cannot verify fix effectiveness without new tests).
2. **`model.transcribe()` hang not reproduced** — Cannot confirm whether the hang is Whisper blocking indefinitely vs. a signal never being emitted. Impact: MEDIUM (both are possible; fixing signal connections addresses both scenarios).
3. **`session_error` has no handler either** — Even though DiarizerWorker/SummarizerWorker/ReporterWorker emit `session_error` on failure, `SessionManager` also has no handler for `session_error`. The pipeline still hangs regardless of which signal is emitted. Impact: The research correctly identifies this; both problems must be fixed together.

---

## Recommendation

**PROCEED TO RCA**

**Reasoning**: All 5 critical claims are substantively verified. The root cause (no error signal handlers in `SessionManager`) is confirmed by direct code inspection. Line number inaccuracies are minor and do not affect the validity of the diagnosis or any proposed fix strategy. The pipeline hang on worker error is a real, confirmed defect.

---

## References

- Original Research: `codebase-research.md`
- Source files verified:
  - [session_manager.py](../../../../handsome_transcribe/ui/session_manager.py)
  - [workers.py](../../../../handsome_transcribe/ui/workers.py)
  - [event_bus.py](../../../../handsome_transcribe/ui/event_bus.py)
