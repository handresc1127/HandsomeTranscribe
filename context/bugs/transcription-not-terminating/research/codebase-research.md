# Codebase Research: transcription-not-terminating

**Date**: 2026-03-15
**Researcher**: AI Agent (Bug Researcher)
**Bug**: Transcription process never terminates/completes in desktop app
**Status**: Research Complete - Pending Verification

---

## Research Summary

The pipeline in `SessionManager` connects to worker **completion** signals but does **not** connect to any **error** signals. When a worker throws an exception, it emits an error signal (e.g., `transcription_error` or `session_error`), but `SessionManager` has no handler for these signals, so the pipeline stops advancing and hangs indefinitely. Additionally, three of the four pipeline workers (`TranscriberWorker`, `DiarizerWorker`, `SummarizerWorker`, `ReporterWorker`) emit `session_error` on failure instead of their stage-specific error signal (only `TranscriberWorker` emits its own `transcription_error`), and `SessionManager` has zero logging, making diagnosis impossible.

---

## Detailed Findings

### Code Locations

| File | Lines | Component | Description |
|------|-------|-----------|-------------|
| [session_manager.py](handsome_transcribe/ui/session_manager.py) | 32-650 | `SessionManager` | Pipeline orchestrator; manages session lifecycle and worker coordination |
| [workers.py](handsome_transcribe/ui/workers.py) | 196-301 | `TranscriberWorker` | Whisper transcription; emits `transcription_complete` on success, `transcription_error` on failure |
| [workers.py](handsome_transcribe/ui/workers.py) | 399-456 | `DiarizerWorker` | pyannote diarization; emits `speaker_update_ready` on success, `session_error` on failure |
| [workers.py](handsome_transcribe/ui/workers.py) | 459-538 | `SummarizerWorker` | Meeting summarization; emits `summarization_complete` on success, `session_error` on failure |
| [workers.py](handsome_transcribe/ui/workers.py) | 575-657 | `ReporterWorker` | Report generation; emits `reports_ready` on success, `session_error` on failure |
| [event_bus.py](handsome_transcribe/ui/event_bus.py) | 12-71 | `EventBus` | Central signal definitions: defines `transcription_error`, `diarization_error`, `summarization_error`, `report_generation_error` signals |
| [workers.py](handsome_transcribe/ui/workers.py) | 23-33 | `WorkerSignals` | Unused QObject with generic `finished`, `error`, `progress`, `result` signals |
| [logger.py](handsome_transcribe/ui/logger.py) | 1-100 | `AppLogger` | Logging infrastructure with console (INFO+) and file (DEBUG+) handlers |

---

### Code Flow Analysis

#### Entry Point

- [session_manager.py](handsome_transcribe/ui/session_manager.py#L244-L268): `stop_recording()` is called when the user stops recording. It calls `self.recorder_worker.stop()`, saves final audio, stops timers, then calls `self._start_transcription()`.

#### Execution Flow (Happy Path)

```
stop_recording()                              → session_manager.py:244
  ↓
  recorder_worker.stop()                      → session_manager.py:255
  recorder_worker.save_final(recording_path)  → session_manager.py:258
  _start_transcription()                      → session_manager.py:269
  ↓
_start_transcription()                        → session_manager.py:458
  _transition_state(TRANSCRIBING)             → session_manager.py:462
  Creates TranscriberWorker                   → session_manager.py:464-469
  Connects: transcription_complete → _on_transcription_complete  → session_manager.py:470
  _thread_pool.start(transcriber_worker)      → session_manager.py:472
  ↓
TranscriberWorker.run()                       → workers.py:265
  whisper.load_model()                        → workers.py:271
  model.transcribe()                          → workers.py:275
  emit_transcription_complete(result)         → workers.py:299
  ↓
_on_transcription_complete(transcript)        → session_manager.py:585
  Disconnects transcription_complete signal   → session_manager.py:593
  _start_diarization()                        → session_manager.py:596
  ↓
_start_diarization()                          → session_manager.py:499
  If diarization disabled → _start_summarization()  → session_manager.py:504
  _transition_state(DIARIZING)                → session_manager.py:512
  Creates DiarizerWorker                      → session_manager.py:514-517
  Connects: speaker_update_ready → _on_diarization_complete  → session_manager.py:517
  _thread_pool.start(diarizer_worker)         → session_manager.py:519
  ↓
_on_diarization_complete(speaker_map)         → session_manager.py:598
  _start_summarization()                      → session_manager.py:610
  ↓
_start_summarization()                        → session_manager.py:522
  If summarization disabled → _start_reporting()  → session_manager.py:527
  _transition_state(SUMMARIZING)              → session_manager.py:529
  Creates SummarizerWorker                    → session_manager.py:531-535
  Connects: summarization_complete → _on_summarization_complete  → session_manager.py:538
  _thread_pool.start(summarizer_worker)       → session_manager.py:540
  ↓
_on_summarization_complete(summary)           → session_manager.py:612
  _start_reporting()                          → session_manager.py:624
  ↓
_start_reporting()                            → session_manager.py:543
  Creates ReporterWorker                      → session_manager.py:548-552
  Connects: reports_ready → _on_reports_ready → session_manager.py:555
  _thread_pool.start(reporter_worker)         → session_manager.py:557
  ↓
_on_reports_ready(reports)                    → session_manager.py:626
  _complete_session()                         → session_manager.py:638
  ↓
_complete_session()                           → session_manager.py:559
  _transition_state(COMPLETED)                → session_manager.py:563
  emit_session_completed(session_info, result) → session_manager.py:576
  _transition_state(IDLE)                     → session_manager.py:579
```

#### Error Path (Pipeline Hang)

```
stop_recording()                              → session_manager.py:244
  ↓
_start_transcription()                        → session_manager.py:458
  Connects ONLY: transcription_complete       → session_manager.py:470
  Does NOT connect: transcription_error       ← MISSING
  _thread_pool.start(transcriber_worker)      → session_manager.py:472
  ↓
TranscriberWorker.run() THROWS EXCEPTION      → workers.py:265
  except Exception:                           → workers.py:300
    emit_transcription_error(msg)             → workers.py:301
  ↓
transcription_error signal emitted            → event_bus.py:31
  NO HANDLER CONNECTED IN SessionManager      ← pipeline hangs here
  ↓
  (nothing happens — pipeline stuck in TRANSCRIBING state forever)
```

---

### Finding 1: Signal Connections in SessionManager

#### Connected Signals (Completion Only)

All `.connect()` calls in `SessionManager`:

| Location | Signal Connected | Handler | Purpose |
|----------|-----------------|---------|---------|
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L80) | `_autosave_timer.timeout` | `_auto_save_progress` | Timer |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L85) | `_partial_transcription_timer.timeout` | `_periodic_partial_transcription` | Timer |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L96) | `pause_recording_requested` | `pause_recording` | UI request |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L97) | `resume_recording_requested` | `resume_recording` | UI request |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L98) | `stop_recording_requested` | `stop_recording` | UI request |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L470) | `transcription_complete` | `_on_transcription_complete` | Pipeline stage advance |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L517) | `speaker_update_ready` | `_on_diarization_complete` | Pipeline stage advance |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L538) | `summarization_complete` | `_on_summarization_complete` | Pipeline stage advance |
| [session_manager.py](handsome_transcribe/ui/session_manager.py#L555) | `reports_ready` | `_on_reports_ready` | Pipeline stage advance |

#### Error Signals NOT Connected

The following error signals exist in `EventBus` but are **never connected** to any handler in `SessionManager`:

| EventBus Signal | Defined At | Connected in SessionManager? |
|-----------------|-----------|------------------------------|
| `transcription_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L31) | **No** |
| `diarization_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L40) | **No** |
| `summarization_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L45) | **No** |
| `report_generation_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L50) | **No** |
| `recording_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L25) | **No** |
| `session_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L64) | **No** |

---

### Finding 2: Worker Error Emission Mismatch

Each worker's `except Exception` handler emits a different signal. The signals emitted by three workers do **not** match their stage-specific error signal defined in EventBus:

| Worker | Location | Signal Emitted on Error | Stage-Specific Error Signal in EventBus |
|--------|----------|------------------------|----------------------------------------|
| `TranscriberWorker` | [workers.py](handsome_transcribe/ui/workers.py#L301) | `emit_transcription_error()` → `transcription_error` | `transcription_error` ✅ matches |
| `DiarizerWorker` | [workers.py](handsome_transcribe/ui/workers.py#L456) | `emit_session_error()` → `session_error` | `diarization_error` ❌ different |
| `SummarizerWorker` | [workers.py](handsome_transcribe/ui/workers.py#L538) | `emit_session_error()` → `session_error` | `summarization_error` ❌ different |
| `ReporterWorker` | [workers.py](handsome_transcribe/ui/workers.py#L657) | `emit_session_error()` → `session_error` | `report_generation_error` ❌ different |

The relevant error emission code in each worker:

**TranscriberWorker** ([workers.py](handsome_transcribe/ui/workers.py#L300-L301)):
```python
except Exception as e:
    self.event_bus.emit_transcription_error(f"Transcription failed: {str(e)}")
```

**DiarizerWorker** ([workers.py](handsome_transcribe/ui/workers.py#L455-L456)):
```python
except Exception as e:
    self.event_bus.emit_session_error(f"Diarization failed: {str(e)}", "diarization")
```

**SummarizerWorker** ([workers.py](handsome_transcribe/ui/workers.py#L537-L538)):
```python
except Exception as e:
    self.event_bus.emit_session_error(f"Summarization failed: {str(e)}", "summarization")
```

**ReporterWorker** ([workers.py](handsome_transcribe/ui/workers.py#L656-L657)):
```python
except Exception as e:
    self.event_bus.emit_session_error(f"Report generation failed: {str(e)}", "reporting")
```

---

### Finding 3: EventBus Defines Error Emit Methods That Are Never Called

EventBus has no `emit_diarization_error()`, `emit_summarization_error()`, or `emit_report_generation_error()` helper methods. The workers fall back to `emit_session_error()` instead.

The EventBus emit methods that **do** exist:

| Method | Signal Emitted | Location |
|--------|---------------|----------|
| `emit_transcription_error(msg)` | `transcription_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L153-L160) |
| `emit_recording_error(msg)` | `recording_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L124-L131) |
| `emit_session_error(title, msg)` | `session_error` | [event_bus.py](handsome_transcribe/ui/event_bus.py#L237-L245) |

The following error signals **exist** in EventBus but have **no emit helper method**:
- `diarization_error` (defined at [event_bus.py](handsome_transcribe/ui/event_bus.py#L40))
- `summarization_error` (defined at [event_bus.py](handsome_transcribe/ui/event_bus.py#L45))
- `report_generation_error` (defined at [event_bus.py](handsome_transcribe/ui/event_bus.py#L50))

---

### Finding 4: WorkerSignals Class Is Unused

[workers.py](handsome_transcribe/ui/workers.py#L23-L33) defines a `WorkerSignals` class with generic `finished`, `error`, `progress`, `result` signals. No worker instantiates or uses this class. All workers communicate exclusively through the `EventBus`.

```python
class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int)
    result = Signal(object)
```

---

### Finding 5: Logging Coverage

#### Workers with logging:

| Worker | Uses AppLogger? | Logger Name | Logging Locations |
|--------|----------------|-------------|-------------------|
| `RecorderWorker` | Yes | `"ui.workers.recorder"` | [workers.py](handsome_transcribe/ui/workers.py#L75), [workers.py](handsome_transcribe/ui/workers.py#L85), [workers.py](handsome_transcribe/ui/workers.py#L92), [workers.py](handsome_transcribe/ui/workers.py#L97), [workers.py](handsome_transcribe/ui/workers.py#L118-L119) |
| `TranscriberWorker` | **No** | — | No logging in `run()` method |
| `DiarizerWorker` | **No** | — | No logging in `run()` method |
| `SummarizerWorker` | **No** | — | No logging in `run()` method |
| `ReporterWorker` | **No** | — | No logging in `run()` method |

#### SessionManager logging:

`SessionManager` at [session_manager.py](handsome_transcribe/ui/session_manager.py) contains **zero** logging statements. No `AppLogger`, no `logging` import, no `logger` variable exists anywhere in the file.

---

### Finding 6: QThreadPool Configuration

[session_manager.py](handsome_transcribe/ui/session_manager.py#L76):
```python
self._thread_pool = QThreadPool.globalInstance()
```

`SessionManager` uses the global `QThreadPool` instance. No explicit configuration of `maxThreadCount` is performed. Workers are started with:

| Worker Start | Location |
|-------------|----------|
| `self._thread_pool.start(self.recorder_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L159) |
| `self._thread_pool.start(self.transcriber_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L472) |
| `self._thread_pool.start(self.partial_transcriber_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L491) |
| `self._thread_pool.start(diarizer_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L519) |
| `self._thread_pool.start(summarizer_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L540) |
| `self._thread_pool.start(reporter_worker)` | [session_manager.py](handsome_transcribe/ui/session_manager.py#L557) |

The `QThreadPool.globalInstance()` default `maxThreadCount` equals `QThread.idealThreadCount()` (typically the number of CPU cores). Workers are submitted sequentially (not simultaneously) so thread pool exhaustion is unlikely for the pipeline stages.

---

### Finding 7: TranscriberWorker.run() in Detail

[workers.py](handsome_transcribe/ui/workers.py#L265-L301):

```python
def run(self):
    """Execute transcription in background thread."""
    try:
        import whisper

        if self.emit_progress:
            self.event_bus.emit_stage_progress("Transcribing", 25)
        model = whisper.load_model(self.model_name)

        if self.emit_progress:
            self.event_bus.emit_stage_progress("Transcribing", 50)
        result = model.transcribe(
            str(self.audio_path),
            language=self.language,
            verbose=False
        )

        if self.emit_progress:
            self.event_bus.emit_stage_progress("Transcribing", 75)
        segments = []
        for seg in result.get("segments", []):
            segment = TranscriptSegmentData(
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"].strip(),
                confidence=seg.get("no_speech_prob", 0.0)
            )
            segments.append(segment)

        self._save_transcript(segments)

        if self.emit_progress:
            self.event_bus.emit_stage_progress("Transcribing", 100)
        self.event_bus.emit_partial_transcript(segments)
        if self.emit_complete:
            self.event_bus.emit_transcription_complete(result)

    except Exception as e:
        self.event_bus.emit_transcription_error(f"Transcription failed: {str(e)}")
```

Key observations:
- `import whisper` is inside `run()` (lazy load) — if `whisper` is not installed, this throws `ModuleNotFoundError` which goes to the except block and emits `transcription_error`
- `whisper.load_model()` can fail if the model download fails or is corrupted
- `model.transcribe()` can hang if Whisper processes audio indefinitely (no timeout)
- `self.emit_complete` flag controls whether `transcription_complete` is emitted — for full transcription it defaults to `True`, for partial transcription it is `False`
- No logging anywhere in this method

---

### Finding 8: Diarization Signal Mismatch

`SessionManager._start_diarization()` at [session_manager.py](handsome_transcribe/ui/session_manager.py#L517) connects to `speaker_update_ready`:
```python
self.event_bus.speaker_update_ready.connect(self._on_diarization_complete, Qt.ConnectionType.QueuedConnection)
```

`DiarizerWorker.run()` at [workers.py](handsome_transcribe/ui/workers.py#L453) emits `speaker_update_ready`:
```python
self.event_bus.emit_speaker_update(speaker_map)
```

This is consistent — the completion path uses `speaker_update_ready` (not `diarization_complete`). The `diarization_complete` signal defined in EventBus at [event_bus.py](handsome_transcribe/ui/event_bus.py#L39) is **never emitted by any code**.

---

### Finding 9: State Transition Validation

[session_manager.py](handsome_transcribe/ui/session_manager.py#L309-L335) defines valid transitions. When a worker error occurs and no error handler fires, the state remains at the previous stage (e.g., `TRANSCRIBING`). The valid transitions from each processing state include `ERROR`:

```python
valid_transitions = {
    SessionState.TRANSCRIBING: [SessionState.DIARIZING, SessionState.SUMMARIZING, SessionState.COMPLETED, SessionState.ERROR],
    SessionState.DIARIZING: [SessionState.SUMMARIZING, SessionState.COMPLETED, SessionState.ERROR],
    SessionState.SUMMARIZING: [SessionState.COMPLETED, SessionState.ERROR],
    ...
}
```

All processing states allow transition to `ERROR`, but nothing triggers this transition when an error occurs because no error handlers are connected.

---

### Related Tests

| Test File | Description |
|-----------|-------------|
| No test files found for `SessionManager`, `TranscriberWorker`, or pipeline error handling | — |

A search for test files covering `session_manager`, `workers`, `event_bus`, or the pipeline error paths returned no results.

---

## Confidence Assessment

- **File References**: 27 locations identified
- **Code Snippets**: 12 exact snippets captured
- **Confidence Level**: HIGH
- **Gaps**: 
  - No test files exist for the pipeline components to verify expected behavior
  - Could not confirm whether `whisper.load_model()` or `model.transcribe()` is the specific call that hangs (requires runtime testing)
  - `QThreadPool.globalInstance().maxThreadCount()` value depends on runtime environment
