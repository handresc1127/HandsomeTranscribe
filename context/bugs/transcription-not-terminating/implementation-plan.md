# Implementation Plan: transcription-not-terminating

**Date**: 2026-03-15
**Status**: DRAFT
**Bug**: Transcription process never terminates/completes in desktop app
**Root Cause**: Pipeline built for happy path only — no error signal connections in SessionManager, no logging, no tests. Error signal infrastructure partially scaffolded but never completed.
**Fix Strategy**: Connect error signals + centralized error handler + full logging + EventBus emit helpers

---

## Bug Summary

| Field | Value |
|-------|-------|
| Bug ID | transcription-not-terminating |
| Priority | High |
| Root Cause | Design gap — zero error signal handlers in SessionManager; missing emit helpers in EventBus; no logging or tests |
| Risk Level | Low–Medium |
| Files Changed | 4 production + 2 test files |

---

## Phase 1: EventBus Emit Helpers

Add the three missing emit helper methods to `EventBus` for stage-specific error signals that are already defined but have no emitter.

### Changes

- [ ] **[event_bus.py](../../../handsome_transcribe/ui/event_bus.py) after L160 (after `emit_transcription_error`)**: Add `emit_diarization_error(self, error_msg: str)` method that emits `self.diarization_error.emit(error_msg)`. Follow the exact pattern of `emit_transcription_error` (L145–L160).
- [ ] **[event_bus.py](../../../handsome_transcribe/ui/event_bus.py) after the new diarization helper**: Add `emit_summarization_error(self, error_msg: str)` method that emits `self.summarization_error.emit(error_msg)`.
- [ ] **[event_bus.py](../../../handsome_transcribe/ui/event_bus.py) after the new summarization helper**: Add `emit_report_generation_error(self, error_msg: str)` method that emits `self.report_generation_error.emit(error_msg)`.

### Implementation Details

Each method follows the existing pattern:
```python
def emit_diarization_error(self, error_msg: str):
    """
    Emit diarization error.
    
    Args:
        error_msg: Error message
    """
    self.diarization_error.emit(error_msg)

def emit_summarization_error(self, error_msg: str):
    """
    Emit summarization error.
    
    Args:
        error_msg: Error message
    """
    self.summarization_error.emit(error_msg)

def emit_report_generation_error(self, error_msg: str):
    """
    Emit report generation error.
    
    Args:
        error_msg: Error message
    """
    self.report_generation_error.emit(error_msg)
```

### Automated Success Criteria

- [ ] `grep -c "def emit_diarization_error" handsome_transcribe/ui/event_bus.py` returns 1
- [ ] `grep -c "def emit_summarization_error" handsome_transcribe/ui/event_bus.py` returns 1
- [ ] `grep -c "def emit_report_generation_error" handsome_transcribe/ui/event_bus.py` returns 1
- [ ] All existing tests pass (`pytest tests/`)

### Manual Verification

- [ ] Each new method emits the correct signal (matches the signal name defined at L40, L45, L50)

---

## Phase 2: Debug Logging in All Workers and SessionManager

Add `AppLogger` debug logging throughout the transcription pipeline for observability.

### Changes

#### SessionManager ([session_manager.py](../../../handsome_transcribe/ui/session_manager.py))

- [ ] **L11 (imports section)**: Add `from .logger import AppLogger`
- [ ] **L65 (inside `__init__`, after `super().__init__()`)**: Add `self._logger = AppLogger.get_logger("ui.session_manager")`
- [ ] **L339 (`_transition_state`, after state change)**: Add `self._logger.debug(f"State transition: {old_state.value} -> {new_state.value}")`
- [ ] **L454 (`_start_transcription`)**: Add `self._logger.debug(f"Starting transcription worker: audio={self.current_session.recording_path}, model={self.config.modelo_whisper}, lang={self.config.idioma_transcripcion}")` before `self._thread_pool.start()`
- [ ] **L493 (`_start_diarization`)**: Add `self._logger.debug("Starting diarization worker")` before `self._thread_pool.start()`. Also add `self._logger.debug("Diarization skipped (disabled or no session)")` in the skip branches.
- [ ] **L521 (`_start_summarization`)**: Add `self._logger.debug("Starting summarization worker")` before start, and `self._logger.debug("Summarization skipped (disabled)")` in skip branch.
- [ ] **L542 (`_start_reporting`)**: Add `self._logger.debug("Starting reporting worker")` before start.
- [ ] **L587 (`_on_transcription_complete`)**: Add `self._logger.debug("Transcription complete callback fired")`
- [ ] **L603 (`_on_diarization_complete`)**: Add `self._logger.debug("Diarization complete callback fired")`
- [ ] **L619 (`_on_summarization_complete`)**: Add `self._logger.debug("Summarization complete callback fired")`
- [ ] **L635 (`_on_reports_ready`)**: Add `self._logger.debug("Reports ready callback fired")`
- [ ] **L559 (`_complete_session`)**: Add `self._logger.debug("Session completed successfully")`

#### TranscriberWorker ([workers.py L257–L301](../../../handsome_transcribe/ui/workers.py#L257))

- [ ] **Inside `run()`, at entry**: Add `logger = AppLogger.get_logger("ui.workers.transcriber")` then `logger.debug(f"TranscriberWorker.run() started: audio={self.audio_path}, model={self.model_name}, lang={self.language}")`
- [ ] **After `model = whisper.load_model(...)`**: Add `logger.debug(f"Whisper model '{self.model_name}' loaded")`
- [ ] **After `result = model.transcribe(...)`**: Add `logger.debug(f"Transcription finished: {len(result.get('segments', []))} segments")`
- [ ] **In `except` block (L300)**: Add `logger.error(f"TranscriberWorker failed: {e}")`

#### DiarizerWorker ([workers.py L426–L456](../../../handsome_transcribe/ui/workers.py#L426))

- [ ] **Inside `run()`, at entry**: Add `logger = AppLogger.get_logger("ui.workers.diarizer")` then `logger.debug(f"DiarizerWorker.run() started: audio={self.audio_path}")`
- [ ] **After diarization completes (before emit)**: Add `logger.debug(f"Diarization finished: {len(speaker_map)} segments")`
- [ ] **In `except` block (L455)**: Add `logger.error(f"DiarizerWorker failed: {e}")`

#### SummarizerWorker ([workers.py L459–L538](../../../handsome_transcribe/ui/workers.py#L459))

- [ ] **Inside `run()`, at entry**: Add `logger = AppLogger.get_logger("ui.workers.summarizer")` then `logger.debug(f"SummarizerWorker.run() started: transcript={self.transcript_path}")`
- [ ] **After summary is saved (before emit)**: Add `logger.debug("Summarization finished")`
- [ ] **In `except` block (L537)**: Add `logger.error(f"SummarizerWorker failed: {e}")`

#### ReporterWorker ([workers.py L575–L657](../../../handsome_transcribe/ui/workers.py#L575))

- [ ] **Inside `run()`, at entry**: Add `logger = AppLogger.get_logger("ui.workers.reporter")` then `logger.debug(f"ReporterWorker.run() started: session_dir={self.session_dir}")`
- [ ] **After reports generated (before emit)**: Add `logger.debug(f"Report generation finished: {list(reports.keys())}")`
- [ ] **In `except` block (L656)**: Add `logger.error(f"ReporterWorker failed: {e}")`

### Automated Success Criteria

- [ ] `grep -c "AppLogger" handsome_transcribe/ui/session_manager.py` returns ≥2
- [ ] `grep -c "logger.debug\|logger.error" handsome_transcribe/ui/workers.py` returns ≥12 (3 per non-recorder worker × 4)
- [ ] `grep -c "logger.debug" handsome_transcribe/ui/session_manager.py` returns ≥10
- [ ] All existing tests pass (`pytest tests/`)

### Manual Verification

- [ ] Run app with `recording1.wav`; inspect log file in `logs/` — debug entries visible for each pipeline stage

---

## Phase 3: Error Signal Connections in SessionManager

Connect error signals in each `_start_*` method alongside the existing success connections.

### Changes

- [ ] **[session_manager.py](../../../handsome_transcribe/ui/session_manager.py) `_start_transcription()` (~L470, after `transcription_complete.connect`)**: Add:
  ```python
  self.event_bus.transcription_error.connect(
      self._on_pipeline_error, Qt.ConnectionType.QueuedConnection
  )
  ```
  Log: `self._logger.debug("Connected transcription_error -> _on_pipeline_error")`

- [ ] **[session_manager.py](../../../handsome_transcribe/ui/session_manager.py) `_start_diarization()` (~L517, after `speaker_update_ready.connect`)**: Add:
  ```python
  self.event_bus.session_error.connect(
      self._on_diarization_error_wrapper, Qt.ConnectionType.QueuedConnection
  )
  ```
  **Rationale**: `DiarizerWorker` emits `session_error(str, str)`, not `diarization_error(str)`. We connect `session_error` here but use a wrapper that checks the second arg (stage tag) to distinguish from benign `session_error` emissions. Connection is placed AFTER the guard clauses (no HF token / disabled) so those benign `emit_session_error` calls happen before the connect, thus do NOT trigger the error handler.

  Log: `self._logger.debug("Connected session_error -> _on_diarization_error_wrapper")`

- [ ] **[session_manager.py](../../../handsome_transcribe/ui/session_manager.py) `_start_summarization()` (~L538, after `summarization_complete.connect`)**: Add:
  ```python
  self.event_bus.session_error.connect(
      self._on_summarization_error_wrapper, Qt.ConnectionType.QueuedConnection
  )
  ```
  **Note**: If diarization was active, the previous `session_error` connection (diarization wrapper) must have been disconnected first by `_on_diarization_complete`. The summarization wrapper filters on stage tag `"summarization"`.

  Log: `self._logger.debug("Connected session_error -> _on_summarization_error_wrapper")`

- [ ] **[session_manager.py](../../../handsome_transcribe/ui/session_manager.py) `_start_reporting()` (~L555, after `reports_ready.connect`)**: Add:
  ```python
  self.event_bus.session_error.connect(
      self._on_reporting_error_wrapper, Qt.ConnectionType.QueuedConnection
  )
  ```
  Log: `self._logger.debug("Connected session_error -> _on_reporting_error_wrapper")`

- [ ] **Each success callback (`_on_transcription_complete`, `_on_diarization_complete`, `_on_summarization_complete`, `_on_reports_ready`)**: Disconnect the corresponding error signal connection alongside the existing success-signal disconnect. Example for `_on_transcription_complete` (L587):
  ```python
  try:
      self.event_bus.transcription_error.disconnect(self._on_pipeline_error)
  except RuntimeError:
      pass
  ```
  For the other three, disconnect `session_error` from their respective wrappers.

### Implementation Details — Signal Routing & `session_error` Dual Role

The `session_error` signal is used by three workers (diarizer, summarizer, reporter) as a generic error channel AND by `_start_diarization()` for benign skip paths. The design handles this as follows:

1. **Benign paths fire BEFORE the `.connect()` call**: The guard clauses in `_start_diarization()` (L496–L503) call `emit_session_error()` and `_start_summarization()` then `return` — this happens before line L517 where we add the `.connect()`. So the error handler is not yet wired when the benign emission occurs. No false trigger.

2. **Stage-specific wrappers**: Each `session_error` connection uses a stage-specific wrapper that checks the second argument (stage tag string: `"diarization"`, `"summarization"`, `"reporting"`) to ensure only the intended error is handled. Unrecognized tags are logged and ignored.

3. **One `session_error` connection at a time**: Each success callback disconnects its stage's `session_error` wrapper before advancing to the next stage. This prevents stale connections from firing on a subsequent stage's error.

### Automated Success Criteria

- [ ] `grep -c "transcription_error.connect\|session_error.connect" handsome_transcribe/ui/session_manager.py` returns ≥4
- [ ] `grep -c "_on_pipeline_error\|_error_wrapper" handsome_transcribe/ui/session_manager.py` returns ≥8
- [ ] All existing tests pass (`pytest tests/`)

### Manual Verification

- [ ] Force a transcription error (e.g., pass invalid audio path) → session transitions to ERROR state; UI shows error message

---

## Phase 4: Error Handler Method in SessionManager

Add the centralized `_on_pipeline_error` and stage-specific wrappers.

### Changes

- [ ] **[session_manager.py](../../../handsome_transcribe/ui/session_manager.py) (new method after `_on_reports_ready`, ~L645)**: Add `_on_pipeline_error(self, error_msg: str)`:
  ```python
  def _on_pipeline_error(self, error_msg: str):
      """Handle pipeline error from transcription_error signal (single arg)."""
      self._logger.error(f"Pipeline error: {error_msg}")
      # Disconnect error signal
      try:
          self.event_bus.transcription_error.disconnect(self._on_pipeline_error)
      except RuntimeError:
          pass
      # Also disconnect success signal to prevent stale callbacks
      try:
          self.event_bus.transcription_complete.disconnect(self._on_transcription_complete)
      except RuntimeError:
          pass
      self._handle_pipeline_failure(error_msg, "transcription")
  ```

- [ ] **Add `_on_diarization_error_wrapper(self, error_title: str, error_stage: str)`**:
  ```python
  def _on_diarization_error_wrapper(self, error_title: str, error_stage: str):
      """Handle session_error during diarization stage."""
      if error_stage != "diarization":
          self._logger.debug(f"Ignoring session_error for stage '{error_stage}' during diarization")
          return
      self._logger.error(f"Diarization error: {error_title}")
      try:
          self.event_bus.session_error.disconnect(self._on_diarization_error_wrapper)
      except RuntimeError:
          pass
      try:
          self.event_bus.speaker_update_ready.disconnect(self._on_diarization_complete)
      except RuntimeError:
          pass
      self._handle_pipeline_failure(error_title, "diarization")
  ```

- [ ] **Add `_on_summarization_error_wrapper(self, error_title: str, error_stage: str)`**: Same pattern, filter on `error_stage != "summarization"`, disconnect `summarization_complete` and `session_error` wrapper.

- [ ] **Add `_on_reporting_error_wrapper(self, error_title: str, error_stage: str)`**: Same pattern, filter on `error_stage != "reporting"`, disconnect `reports_ready` and `session_error` wrapper.

- [ ] **Add `_handle_pipeline_failure(self, error_msg: str, stage: str)`**: Shared logic:
  ```python
  def _handle_pipeline_failure(self, error_msg: str, stage: str):
      """Transition to ERROR state and notify UI."""
      self._logger.error(f"Pipeline failure at '{stage}': {error_msg}")
      try:
          self._transition_state(SessionState.ERROR)
      except SessionError:
          self._logger.warning(f"Could not transition to ERROR from {self.current_state.value}")
          self.current_state = SessionState.ERROR
      self._stop_autosave_timer()
      self.event_bus.emit_session_error(f"Pipeline error: {stage}", error_msg)
  ```

### Implementation Details

- `_on_pipeline_error`: Handles the `transcription_error(str)` signal (1 argument).
- `_on_*_error_wrapper`: Handle the `session_error(str, str)` signal (2 arguments) with stage-tag filtering.
- `_handle_pipeline_failure`: Shared finalization — transitions to `ERROR`, stops timers, emits `session_error` for UI.
- On error, both the error and success signals for the current stage are disconnected to prevent stale callbacks.

### Automated Success Criteria

- [ ] `grep -c "def _on_pipeline_error\|def _on_diarization_error_wrapper\|def _on_summarization_error_wrapper\|def _on_reporting_error_wrapper\|def _handle_pipeline_failure" handsome_transcribe/ui/session_manager.py` returns 5
- [ ] `grep -c "_transition_state(SessionState.ERROR)" handsome_transcribe/ui/session_manager.py` returns ≥1
- [ ] All existing tests pass (`pytest tests/`)

### Manual Verification

- [ ] Force an error at each stage; verify session transitions to ERROR and UI shows error

---

## Phase 5: Tests

### 5A: Unit Tests for Error Handling

- [ ] **Create `tests/ui/test_session_manager_errors.py`**: Unit tests using mocked EventBus and workers.

  Tests to include:
  1. `test_transcription_error_transitions_to_error_state` — Mock `TranscriberWorker` to emit `transcription_error`; verify `SessionManager` transitions to `ERROR`.
  2. `test_diarization_error_transitions_to_error_state` — Mock `DiarizerWorker` to emit `session_error("...", "diarization")`; verify transition to `ERROR`.
  3. `test_summarization_error_transitions_to_error_state` — Same for summarization.
  4. `test_reporting_error_transitions_to_error_state` — Same for reporting.
  5. `test_diarization_skip_does_not_trigger_error` — Disable diarization or omit HF token; verify pipeline advances to summarization without triggering error handler.
  6. `test_session_error_wrong_stage_ignored` — Emit `session_error("msg", "unrelated")` while in diarization; verify error handler ignores it.
  7. `test_error_handler_disconnects_signals` — After error fires, verify both error and success signals are disconnected (no duplicate triggers).

### 5B: Copy Audio Fixtures

- [ ] **Copy `tests/records/recording1.wav` → `tests/fixtures/recording1.wav`**
- [ ] **Copy `tests/records/recording2.wav` → `tests/fixtures/recording2.wav`**

### 5C: Integration Tests with Real Audio

- [ ] **Create `tests/test_real_audio_integration.py`**: Integration tests gated by `HT_RUN_REAL_AUDIO_TEST=1` environment variable.

  ```python
  import os
  import pytest
  from pathlib import Path

  REAL_AUDIO = os.environ.get("HT_RUN_REAL_AUDIO_TEST") == "1"
  skip_unless_real = pytest.mark.skipif(not REAL_AUDIO, reason="HT_RUN_REAL_AUDIO_TEST not set")
  FIXTURES = Path(__file__).parent / "fixtures"
  ```

  Tests to include:
  1. `test_whisper_transcribes_recording1_spanish` — Load `recording1.wav`, run `whisper.load_model("base").transcribe(str(path), language="es")`, assert segments are non-empty and language detected or forced is "es".
  2. `test_whisper_transcribes_recording2_spanish` — Same for `recording2.wav`.
  3. `test_transcriber_worker_emits_complete` — Create real `TranscriberWorker` with a mock `EventBus`, run it, verify `emit_transcription_complete` is called with a result containing segments. (Uses `recording1.wav` or `recording2.wav`.)
  4. `test_transcriber_worker_emits_error_on_bad_file` — Create `TranscriberWorker` pointing to a non-existent file, run it, verify `emit_transcription_error` is called.

### 5D: EventBus Emit Helper Tests

- [ ] **Add to `tests/ui/test_event_bus.py` (create if needed)**: Test that calling `emit_diarization_error`, `emit_summarization_error`, `emit_report_generation_error` emits the corresponding signal. Use `SignalSpy` or mock `.emit()`.

### Automated Success Criteria

- [ ] `pytest tests/` (without `HT_RUN_REAL_AUDIO_TEST`) — all tests pass, integration tests skip cleanly
- [ ] `HT_RUN_REAL_AUDIO_TEST=1 pytest tests/test_real_audio_integration.py` — all integration tests pass
- [ ] `pytest tests/ui/test_session_manager_errors.py` — all error handling unit tests pass
- [ ] Zero test regressions in existing test suite

### Manual Verification

- [ ] Inspect test output to confirm skip messages for gated tests when env var not set
- [ ] Confirm `recording1.wav` and `recording2.wav` exist in `tests/fixtures/`

---

## Rollback Plan

### Steps to Revert

1. `git stash` or `git checkout -- handsome_transcribe/ui/event_bus.py handsome_transcribe/ui/session_manager.py handsome_transcribe/ui/workers.py` to revert production changes
2. Delete new test files: `tests/ui/test_session_manager_errors.py`, `tests/test_real_audio_integration.py`, `tests/ui/test_event_bus.py` (if created), and `tests/fixtures/recording*.wav`
3. Verify all original tests pass with `pytest tests/`

### Verification After Rollback

- [ ] `pytest tests/` passes with same results as before the fix
- [ ] `grep -c "def _on_pipeline_error" handsome_transcribe/ui/session_manager.py` returns 0
- [ ] App starts and records/transcribes (happy path) without changes visible

---

## File Change Summary

| File | Phase | Type | Description |
|------|-------|------|-------------|
| `handsome_transcribe/ui/event_bus.py` | 1 | Modified | Add 3 emit helpers |
| `handsome_transcribe/ui/workers.py` | 2 | Modified | Add debug logging to 4 workers |
| `handsome_transcribe/ui/session_manager.py` | 2, 3, 4 | Modified | Add logging + error signal connections + error handler methods |
| `tests/fixtures/recording1.wav` | 5B | Added | Copy from tests/records/ |
| `tests/fixtures/recording2.wav` | 5B | Added | Copy from tests/records/ |
| `tests/ui/test_session_manager_errors.py` | 5A | Created | Error handling unit tests |
| `tests/test_real_audio_integration.py` | 5C | Created | Integration tests with real audio |
| `tests/ui/test_event_bus.py` | 5D | Created | EventBus emit helper tests |

---

## Open Questions

None — all decisions resolved during planning.
