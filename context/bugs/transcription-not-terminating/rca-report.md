# RCA Report: transcription-not-terminating

**Date**: 2026-03-15
**Analyst**: AI Agent (RCA Analyst)
**Based On**: `research/verified-research.md` (Confidence: HIGH)
**Bug Context**: `bug-context.md`

---

## Symptom Analysis

### Observable Behavior

- After stopping recording, the desktop app UI hangs indefinitely — the transcription pipeline never completes.
- The session state transitions to `TRANSCRIBING` but never progresses to `DIARIZING`, `SUMMARIZING`, or `COMPLETED`.
- No debug logging is emitted during pipeline execution, making the stall point invisible to users and developers.
- Affects all audio inputs (Spanish `recording1.wav` / `recording2.wav`), not limited to a specific file or language.

### Trigger Conditions

The bug triggers whenever **any worker in the pipeline** encounters an exception during execution:
- `TranscriberWorker.run()` throws (e.g., Whisper model load failure, corrupt audio)
- `DiarizerWorker.run()` throws (e.g., missing HF token, pyannote failure)
- `SummarizerWorker.run()` throws (e.g., missing transcript JSON, import failure)
- `ReporterWorker.run()` throws (e.g., missing summary file, ReportLab error)

### Expected vs Actual

| Aspect | Expected | Actual |
|--------|----------|--------|
| Pipeline on error | Transition to `ERROR` state, notify user | Pipeline hangs forever in current state |
| Error visibility | Errors logged and displayed | No logging; error signals emitted to void |
| Session recovery | User can cancel/retry | Session stuck; app must be killed |

### Severity: **Critical**

- Session data may be lost (no cleanup on hang)
- App becomes unresponsive (must force-quit)
- No diagnostic information available to user or developer

---

## Fault Localization

### Entry Point

`SessionManager.stop_recording()` at [session_manager.py](../../../handsome_transcribe/ui/session_manager.py#L234) — user clicks "Stop", triggering `_start_transcription()`.

### Execution Flow (Happy Path)

```
stop_recording() [L234]
  → _start_transcription() [L454]
    → transcription_complete.connect(_on_transcription_complete) [L470]
    → thread_pool.start(transcriber_worker)
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

### Fault Location (Error Path)

When any worker's `run()` method throws, the worker emits an error signal and **does not** emit the success signal. Since `SessionManager` only connects to success signals, the next stage callback is never invoked.

**Deviation point**: The `except` block of every worker's `run()` method. The error signal fires into the void because `SessionManager.__init__()` ([session_manager.py](../../../handsome_transcribe/ui/session_manager.py#L62-L98)) connects zero error signal handlers.

### Data Transformation Map

```
Worker Exception → worker emits error signal → ∅ (no handler)
                 → worker does NOT emit success signal → next stage callback never fires
                 → SessionManager.current_state stuck at last transition
                 → UI frozen, session never completes or transitions to ERROR
```

---

## 5 Whys Analysis

### Why 1: The pipeline hangs when a worker fails

**Evidence**: [session_manager.py](../../../handsome_transcribe/ui/session_manager.py#L470) — `_start_transcription()` connects only `transcription_complete` to `_on_transcription_complete`. If `TranscriberWorker.run()` raises an exception ([workers.py](../../../handsome_transcribe/ui/workers.py#L300-L301)), it emits `transcription_error` instead of `transcription_complete`. Since `_on_transcription_complete` is never called, `_start_diarization()` is never reached.

**Connection**: But why does the error signal go unhandled?

### Why 2: SessionManager has zero error signal connections

**Evidence**: The complete set of `.connect()` calls in `SessionManager.__init__()` ([session_manager.py](../../../handsome_transcribe/ui/session_manager.py#L80-L98)) consists of:
- 2 timer connections (`_autosave_timer.timeout`, `_partial_transcription_timer.timeout`)
- 3 UI request connections (`pause_recording_requested`, `resume_recording_requested`, `stop_recording_requested`)

The pipeline stage connections (`transcription_complete`, `speaker_update_ready`, `summarization_complete`, `reports_ready`) are established in each `_start_*` method. **No error signals** (`transcription_error`, `session_error`, `diarization_error`, `summarization_error`, `report_generation_error`) are connected anywhere in `SessionManager`.

**Connection**: But why weren't error connections added alongside success connections?

### Why 3: The pipeline was designed for the happy path only

**Evidence**: Each `_start_*` method follows an identical pattern — connect ONE success signal, start ONE worker:
- [_start_transcription() L454-L473](../../../handsome_transcribe/ui/session_manager.py#L454-L473): connects `transcription_complete` only
- [_start_diarization() L493-L519](../../../handsome_transcribe/ui/session_manager.py#L493-L519): connects `speaker_update_ready` only
- [_start_summarization() L521-L540](../../../handsome_transcribe/ui/session_manager.py#L521-L540): connects `summarization_complete` only
- [_start_reporting() L542-L557](../../../handsome_transcribe/ui/session_manager.py#L542-L557): connects `reports_ready` only

There is no error handling pattern, no timeout, no fallback. The code assumes workers always succeed.

**Connection**: But why is there no error handling infrastructure to build on?

### Why 4: Workers emit inconsistent error signals with no corresponding handler infrastructure

**Evidence**: The workers use two different error emission patterns:

| Worker | Error signal emitted | Method used |
|--------|---------------------|-------------|
| `TranscriberWorker` ([workers.py L301](../../../handsome_transcribe/ui/workers.py#L301)) | `transcription_error` | `emit_transcription_error()` |
| `DiarizerWorker` ([workers.py L456](../../../handsome_transcribe/ui/workers.py#L456)) | `session_error` | `emit_session_error()` |
| `SummarizerWorker` ([workers.py L538](../../../handsome_transcribe/ui/workers.py#L538)) | `session_error` | `emit_session_error()` |
| `ReporterWorker` ([workers.py L657](../../../handsome_transcribe/ui/workers.py#L657)) | `session_error` | `emit_session_error()` |

`EventBus` defines stage-specific error signals (`diarization_error` [event_bus.py L40](../../../handsome_transcribe/ui/event_bus.py#L40), `summarization_error` [event_bus.py L45](../../../handsome_transcribe/ui/event_bus.py#L45), `report_generation_error` [event_bus.py L50](../../../handsome_transcribe/ui/event_bus.py#L50)) but has **no emit helper methods** for them. So 3 of 4 workers fall back to `emit_session_error()` as a generic catch-all — but that signal has no handler either.

Additionally, the `WorkerSignals` class defined at [workers.py L23](../../../handsome_transcribe/ui/workers.py#L23) (with `finished`, `error`, `progress`, `result` signals) is **never used** by any worker. The error signaling architecture was started but never completed.

**Connection**: But why wasn't this caught during development or testing?

### Why 5 (ROOT CAUSE): No error path testing, no logging, and no observability in the pipeline

**Evidence**:
1. **No tests for SessionManager or pipeline error paths** — no test files exist for `SessionManager`, and existing worker tests don't cover error scenarios.
2. **No logging in SessionManager or pipeline workers** — `AppLogger` is only used in `RecorderWorker.run()` ([workers.py L75](../../../handsome_transcribe/ui/workers.py#L75), [L118](../../../handsome_transcribe/ui/workers.py#L118)). `TranscriberWorker`, `DiarizerWorker`, `SummarizerWorker`, `ReporterWorker`, and `SessionManager` have **zero** logger usage.
3. **Dead code in EventBus** — `diarization_complete` signal ([event_bus.py L39](../../../handsome_transcribe/ui/event_bus.py#L39)) is defined but never emitted anywhere. Stage-specific error signals are defined but have no emitter helpers. `WorkerSignals` class exists but is unused.

**This is fundamental because**: The root cause is a **design gap** — the pipeline was built without error handling by design, and the absence of logging and tests meant this gap was never detected during development. The error signal infrastructure was partially scaffolded (signals defined in EventBus, one worker uses the correct stage-specific error) but never completed across all workers or connected in SessionManager.

### Root Cause Category: **Design Gap** (compounded by Missing Observability)

The pipeline architecture uses an event-driven chain where each stage's success signal triggers the next stage, but no corresponding error signal chain exists. The error path was partially designed (signals exist in EventBus) but never implemented end-to-end. The absence of logging and tests made this invisible.

---

## Fix Strategies

### Strategy 1: Connect Error Signals + Add Error Handler (RECOMMENDED)

**Approach**: Add error signal connections in each `_start_*` method alongside the existing success connections. Create a centralized `_on_pipeline_error()` handler that transitions the session to `ERROR` state, logs the failure, and emits `session_error` for the UI.

**Files to modify**:
- [session_manager.py L454-L473](../../../handsome_transcribe/ui/session_manager.py#L454-L473) — `_start_transcription()`: add `transcription_error.connect(_on_pipeline_error)`
- [session_manager.py L493-L519](../../../handsome_transcribe/ui/session_manager.py#L493-L519) — `_start_diarization()`: add `session_error.connect(_on_pipeline_error)` (and/or fix worker to use `diarization_error`)
- [session_manager.py L521-L540](../../../handsome_transcribe/ui/session_manager.py#L521-L540) — `_start_summarization()`: add error connection
- [session_manager.py L542-L557](../../../handsome_transcribe/ui/session_manager.py#L542-L557) — `_start_reporting()`: add error connection
- [session_manager.py](../../../handsome_transcribe/ui/session_manager.py) — Add new `_on_pipeline_error()` method
- [session_manager.py](../../../handsome_transcribe/ui/session_manager.py) — Add `AppLogger` import and logger initialization

**Pros**:
- Directly addresses root cause (missing error connections)
- Minimal code changes (one new method + 4 connect lines)
- Session properly transitions to ERROR state
- Users see error feedback instead of frozen UI

**Cons**:
- Does not fix worker signal inconsistency (DiarizerWorker/SummarizerWorker/ReporterWorker still emit `session_error` instead of stage-specific signals)
- Needs careful handling of `session_error` signal args (2 args: title, message) vs `transcription_error` (1 arg: message)

**Risk Level**: Low
**Estimated Complexity**: Low
**Regression Risk**: Low — only adds new connections; existing happy path unchanged. Must verify error handler properly disconnects signals to avoid duplicate triggers.

---

### Strategy 2: Full Error Signal Normalization + Error Handler (ALTERNATIVE)

**Approach**: Fix all workers to emit stage-specific error signals (add missing emit helpers to EventBus), then connect all stage-specific error signals in SessionManager. Also add logging to all workers and SessionManager.

**Files to modify**:
- [event_bus.py](../../../handsome_transcribe/ui/event_bus.py) — Add `emit_diarization_error()`, `emit_summarization_error()`, `emit_report_generation_error()` helpers
- [workers.py L456](../../../handsome_transcribe/ui/workers.py#L456) — `DiarizerWorker.run()`: change `emit_session_error()` to `emit_diarization_error()`
- [workers.py L538](../../../handsome_transcribe/ui/workers.py#L538) — `SummarizerWorker.run()`: change to `emit_summarization_error()`
- [workers.py L657](../../../handsome_transcribe/ui/workers.py#L657) — `ReporterWorker.run()`: change to `emit_report_generation_error()`
- [session_manager.py](../../../handsome_transcribe/ui/session_manager.py) — Connect each stage-specific error signal; add `AppLogger` throughout
- [workers.py](../../../handsome_transcribe/ui/workers.py) — Add `AppLogger` to all worker `run()` methods

**Pros**:
- Clean, consistent architecture (each stage has its own success and error signal)
- Better diagnostics (logging everywhere)
- Easier future debugging
- Dead code (`WorkerSignals`, unused signals) can be cleaned up

**Cons**:
- Larger change surface
- More files touched
- Signal signature differences need resolving (`transcription_error(str)` vs `session_error(str, str)`)

**Risk Level**: Medium
**Estimated Complexity**: Medium
**Regression Risk**: Medium — changing signal emissions in workers could affect any other components that might listen to `session_error`. Must verify no UI code connects to `session_error` from these workers.

---

### Strategy 3: Timeout-Based Fallback (MINIMAL)

**Approach**: Add a per-stage timeout timer in SessionManager. If a stage doesn't complete within N seconds, transition to ERROR state and clean up.

**Files to modify**:
- [session_manager.py](../../../handsome_transcribe/ui/session_manager.py) — Add `QTimer` per stage with configurable timeout; add timeout handler

**Pros**:
- Works regardless of signal wiring issues
- Safety net against truly hanging workers (e.g., Whisper blocking indefinitely)
- Independent of error signal architecture

**Cons**:
- Does NOT fix root cause (error signals still unhandled)
- Hard to set correct timeout values (Whisper transcription may legitimately take minutes for long audio)
- User may see timeout errors for slow-but-working operations
- No specific error information (just "stage timed out")

**Risk Level**: Medium
**Estimated Complexity**: Low
**Regression Risk**: Medium — false positives on slow audio processing could prematurely abort valid sessions.

---

## Recommendation

**Strategy 1 (Connect Error Signals + Add Error Handler)** is recommended as the primary fix. It directly addresses the root cause with minimal code changes and low regression risk.

**Strategy 2** should be considered as a follow-up improvement to normalize the signal architecture and add observability. It's not required for the immediate fix but will make future maintenance easier.

**Strategy 3** should be considered as a complementary safety net (not a replacement) to handle truly blocking workers, but only after Strategy 1 is in place and with carefully tuned timeout values.

### Implementation Priority

1. **Immediate**: Strategy 1 — connect error signals, add error handler + basic logging
2. **Follow-up**: Strategy 2 — normalize worker error signals, add full logging
3. **Optional**: Strategy 3 — add timeout safety net for edge cases

---

## References

- Verified Research: [verified-research.md](research/verified-research.md)
- Bug Context: [bug-context.md](bug-context.md)
- Source files:
  - [session_manager.py](../../../handsome_transcribe/ui/session_manager.py)
  - [workers.py](../../../handsome_transcribe/ui/workers.py)
  - [event_bus.py](../../../handsome_transcribe/ui/event_bus.py)
