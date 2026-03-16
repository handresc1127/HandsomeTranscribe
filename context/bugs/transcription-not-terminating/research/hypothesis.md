# Research Hypotheses: transcription-not-terminating

**Date**: 2026-03-15
**Bug**: Transcription process never terminates/completes in desktop app

---

## Symptom Analysis

### Observable Behavior

After stopping a recording, the transcription pipeline starts but never transitions to completion. The UI stays in a stuck/processing state indefinitely. No debug logging is visible during the transcription stages.

### Trigger Conditions

1. Start a recording session in the desktop app
2. Stop the recording
3. Pipeline enters TRANSCRIBING state but never progresses to COMPLETED

### Affected Components (Suspected)

- SessionManager (pipeline orchestration)
- TranscriberWorker (Whisper transcription execution)
- EventBus (signal routing between workers and manager)
- All downstream workers (DiarizerWorker, SummarizerWorker, ReporterWorker)

---

## Investigation Areas

### Area 1: Signal Connections in SessionManager

**Why investigate**: If error signals from workers are not connected to handlers in SessionManager, a worker exception would cause the pipeline to hang silently — no completion signal fires, no error handler advances the state.

**Search targets**:

- Files: `handsome_transcribe/ui/session_manager.py`
- Functions: `__init__`, `_start_transcription`, `_start_diarization`, `_start_summarization`, `_start_reporting`
- Patterns: `.connect(` calls for error signals

**Questions to answer**:

- Does SessionManager connect to `transcription_error`?
- Does SessionManager connect to `diarization_error`, `summarization_error`, `report_generation_error`?
- Does SessionManager connect to `session_error`?

### Area 2: Worker Error Emission Patterns

**Why investigate**: Workers may emit error signals that differ from what SessionManager expects. If a worker emits `session_error` but SessionManager listens for `transcription_error`, the signal is lost.

**Search targets**:

- Files: `handsome_transcribe/ui/workers.py`
- Functions: `run()` methods of all workers
- Patterns: `except Exception` blocks, `emit_*_error` calls

**Questions to answer**:

- Which exact signal does each worker emit on error?
- Are these signals consistent with what's defined in EventBus?

### Area 3: Logging Gaps in Pipeline Workers

**Why investigate**: Without logging in the pipeline workers, it is impossible to diagnose where the pipeline stalls.

**Search targets**:

- Files: `handsome_transcribe/ui/workers.py`, `handsome_transcribe/ui/session_manager.py`
- Patterns: `AppLogger`, `logger`, `logging`

**Questions to answer**:

- Which workers use AppLogger?
- Does SessionManager have any logging?

---

## Research Strategy

### Priority Order

1. Signal connections in SessionManager — determine if error signals are unhandled
2. Worker error emission — determine what signals workers actually emit on failure
3. Logging gaps — determine visibility into pipeline execution
