# Bug: reporter-none-segment-join

**Title:** ReporterWorker fails with "sequence item 0: expected str instance, NoneType found"
**Status:** Open
**Priority:** High (blocks successful session completion)
**Created:** 2026-03-15
**Source:** Manual description (Copilot Chat)

## Description

After completing a recording session and transcription, the ReporterWorker crashes during report generation with the error:

```
ReporterWorker failed: sequence item 0: expected str instance, NoneType found
Report generation failed: sequence item 0: expected str instance, NoneType found
```

This causes a pipeline failure at the 'reporting' stage and transitions the session state to 'error'.

## Steps to Reproduce

1. Launch `desktop_app.py`
2. Start a recording session (language: `es`, model: `base`)
3. Pause and resume recording at least once
4. Stop recording to trigger transcription
5. Wait for transcription to complete (returns 2 segments)
6. ReporterWorker starts → crashes immediately with the above error

## Expected Behavior

ReporterWorker completes successfully, generating a session report from the transcription segments and saving it to the session directory.

## Actual Behavior

ReporterWorker fails with:
```
sequence item 0: expected str instance, NoneType found
```
The error originates from a `str.join()` (or equivalent string concatenation) being called on a sequence that contains at least one `None` value instead of a string. The session transitions to the `error` state and no report is produced.

## Error Details from Logs

```
2026-03-15 22:12:30,887 - handsome_transcribe.ui.workers.reporter - DEBUG - No summary.md found (summarization skipped), using empty summary
22:12:30 [ERROR] handsome_transcribe.ui.workers.reporter: ReporterWorker failed: sequence item 0: expected str instance, NoneType found
2026-03-15 22:12:30,888 - handsome_transcribe.ui.workers.reporter - ERROR - ReporterWorker failed: sequence item 0: expected str instance, NoneType found
22:12:30 [ERROR] handsome_transcribe.ui.session_manager: Reporting error: Report generation failed: sequence item 0: expected str instance, NoneType found
22:12:30 [ERROR] handsome_transcribe.ui.session_manager: Pipeline failure at 'reporting': Report generation failed: sequence item 0: expected str instance, NoneType found
2026-03-15 22:12:30,969 - handsome_transcribe.ui.session_manager - DEBUG - State transition: transcribing -> error
```

## Pipeline Context

- Transcription returned 2 segments
- Diarization was **disabled** (skipped)
- Summarization was **disabled** (skipped) → `summary` is empty string
- ReporterWorker receives: `session_dir=outputs\sessions\session_20260315_221209`
- The error occurs immediately inside `ReporterWorker.run()`

## Environment

- OS: Windows
- Python: 3.13
- Model: Whisper `base`
- Language: `es`
- Diarization: disabled
- Summarization: disabled

## Additional Context

The error pattern `sequence item 0: expected str instance, NoneType found` is a Python `TypeError` raised by `str.join()` when one or more items in the iterable are `None`. Given the pipeline context, likely candidates are:
- A transcription segment field (`text`, `start`, `end`, or `speaker`) being `None`
- The `segments` list itself containing `None` entries
- A field being accessed from transcript JSON that is absent/null

The word "item 0" suggests the very first segment has a `None` value for a field expected to be a string.

---
*Note: This bug context was created from a manual description. No external ticket system is associated.*
