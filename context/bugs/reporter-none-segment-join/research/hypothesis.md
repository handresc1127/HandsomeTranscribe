# Research Hypotheses: reporter-none-segment-join

**Date**: 2026-03-15
**Bug**: ReporterWorker fails with "sequence item 0: expected str instance, NoneType found"

---

## Symptom Analysis

### Observable Behavior

ReporterWorker crashes immediately after loading the empty summary, before producing any
report output. The session transitions to `error` state and no report files are generated.

### Trigger Conditions

- A recording session completes with diarization disabled
- Transcription returns at least one segment
- Summarization is also disabled
- ReporterWorker.run() is invoked with the session directory

### Affected Components (Suspected)

- `handsome_transcribe/ui/workers.py` – `TranscriberWorker._save_transcript()` and `ReporterWorker.run()`
- `handsome_transcribe/reporting/report_generator.py` – `ReportGenerator.generate()` and `_render_markdown()`
- The `TranscriptSegmentData` UI model and the `TranscriptSegment` domain model

---

## Investigation Areas

### Area 1: ReporterWorker — transcript segment deserialization

**Why investigate**: The error message `sequence item 0: expected str instance, NoneType found`
points to `str.join()` being called on a list containing `None`. The only `str.join()` call in
the reporter code path is on the speakers list, so the issue is in how `speaker` values are
read back from the transcript JSON.

**Search targets**:

- Files: `handsome_transcribe/ui/workers.py`
- Functions: `ReporterWorker.run()`, `TranscriberWorker._save_transcript()`
- Patterns: `seg.get("speaker", ...)`, `getattr(seg, 'speaker_id', ...)`

**Questions to answer**:

- What value is written to `"speaker"` in the JSON by `TranscriberWorker`?
- What value does `seg.get("speaker", "Unknown")` return when the stored JSON has `null`?

---

### Area 2: TranscriptSegmentData vs TranscriptSegment — field name mismatch

**Why investigate**: UI model `TranscriptSegmentData` uses `speaker_id: Optional[int]` while
domain model `TranscriptSegment` uses `speaker: str`. The write step accesses
`getattr(seg, 'speaker_id', 'Unknown')`, which may produce an integer or `None` rather than
the string `"Unknown"`.

**Search targets**:

- Files: `handsome_transcribe/ui/models.py`, `handsome_transcribe/transcription/whisper_transcriber.py`
- Functions/classes: `TranscriptSegmentData`, `TranscriptSegment`
- Patterns: `speaker_id`, `speaker`

**Questions to answer**:

- What is the default value of `TranscriptSegmentData.speaker_id`?
- What field name/type does `TranscriptSegment` define for speaker information?

---

### Area 3: ReportGenerator speakers list building

**Why investigate**: The `speakers` list is the value passed to `', '.join(...)`. If it contains
`None`, the join fails. The list is built by a set comprehension that filters on
`seg.speaker != "Unknown"`, which does NOT filter out `None` values.

**Search targets**:

- Files: `handsome_transcribe/reporting/report_generator.py`
- Functions: `ReportGenerator.generate()`, `_render_markdown()`, `_write_pdf()`
- Patterns: `sorted({seg.speaker ...})`, `', '.join(report.speakers)`

**Questions to answer**:

- Does the filter `if seg.speaker != "Unknown"` exclude `None` values?
- Where exactly is `', '.join(report.speakers)` called?

---

## Research Strategy

### Priority Order

1. Area 2 — Confirm the `speaker_id`/`speaker` field name mismatch producing `null` in JSON
2. Area 1 — Confirm `seg.get("speaker", "Unknown")` behavior with existing-but-null key
3. Area 3 — Confirm the exact `str.join()` call site that raises the TypeError
