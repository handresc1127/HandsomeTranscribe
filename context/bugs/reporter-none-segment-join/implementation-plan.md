# Implementation Plan: reporter-none-segment-join

**Date**: 2026-03-16
**Status**: APPROVED
**Bug**: ReporterWorker fails with "sequence item 0: expected str instance, NoneType found"
**Root Cause**: `getattr(seg, 'speaker_id', 'Unknown')` at `workers.py:334` returns `None` instead of `"Unknown"` because the attribute exists as a declared dataclass field (`Optional[int] = None`). The fallback only fires on attribute absence, not on `None` values.
**Fix Strategy**: Strategy 1 (fix serialization boundary) + Strategy 2 (defensive deserialization)

---

## Bug Summary

| Field | Value |
|-------|-------|
| Bug ID | reporter-none-segment-join |
| Priority | High (blocks session completion) |
| Root Cause | `getattr` fallback doesn't fire for `None`-valued dataclass fields |
| Risk Level | Low |
| Files Changed | 1 (`handsome_transcribe/ui/workers.py`) |
| Lines Changed | 3 |

---

## Phase 1: Fix Serialization & Deserialization

### Changes

- [x] **`handsome_transcribe/ui/workers.py:334`**: Replace `getattr(seg, 'speaker_id', 'Unknown')` with `str(seg.speaker_id) if seg.speaker_id is not None else "Unknown"` — this ensures `None` speaker IDs are converted to the `"Unknown"` sentinel string before writing to JSON, and integer speaker IDs are converted to their string representation.

- [x] **`handsome_transcribe/ui/workers.py:640`**: Replace `speaker=seg.get("speaker", "Unknown")` with `speaker=seg.get("speaker") or "Unknown"` — this makes the deserialization in `ReporterWorker.run()` robust against existing `transcript.json` files that already contain `"speaker": null`.

- [x] **`handsome_transcribe/ui/workers.py:521`**: Replace `speaker=seg.get("speaker", "Unknown")` with `speaker=seg.get("speaker") or "Unknown"` — same defensive fix in `SummarizerWorker.run()` which has the identical vulnerability.

### Automated Success Criteria

- [x] Running the existing test suite (`pytest tests/`) passes with no regressions
- [x] No occurrence of `getattr(seg, 'speaker_id', 'Unknown')` remains in `workers.py`
- [x] Both `seg.get("speaker", "Unknown")` patterns in `ReporterWorker` and `SummarizerWorker` are replaced with `seg.get("speaker") or "Unknown"`

### Manual Verification

- [x] Start a recording session with diarization disabled, stop, and confirm the report generates without error
- [x] Inspect the generated `transcript.json` — verify `"speaker"` values are `"Unknown"` (not `null`)

---

## Phase 2: Testing & Regression Prevention

### Changes

- [x] **`tests/test_report_generator.py`**: Add a test `test_generate_report_with_none_speaker` that creates a `Transcript` with `TranscriptSegment(speaker=None)` and verifies `ReportGenerator.generate()` does NOT raise `TypeError`. The speakers list should fall back to `["Unknown"]`.

- [x] **`tests/test_report_generator.py`**: Add a test `test_generate_report_with_mixed_speakers` that creates a `Transcript` with segments having `speaker=None`, `speaker="Unknown"`, and `speaker="SPEAKER_01"` — verifies only `"SPEAKER_01"` appears in `report.speakers`.

### Automated Success Criteria

- [x] New test `test_generate_report_with_none_speaker` passes
- [x] New test `test_generate_report_with_mixed_speakers` passes
- [x] All existing tests in `tests/test_report_generator.py` still pass
- [x] Full suite `pytest tests/` passes

---

## Rollback Plan

### Steps to Revert

1. Restore `workers.py:334` to `"speaker": getattr(seg, 'speaker_id', 'Unknown')`
2. Restore `workers.py:640` to `speaker=seg.get("speaker", "Unknown")`
3. Restore `workers.py:521` to `speaker=seg.get("speaker", "Unknown")`
4. Remove the two new test functions from `tests/test_report_generator.py`

### Verification After Rollback

- [ ] `pytest tests/` passes (excluding the removed regression tests)
- [ ] The original bug reproduces when running with diarization disabled

---

## Open Questions

None — all questions resolved during planning.
