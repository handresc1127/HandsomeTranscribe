# Fix Summary: reporter-none-segment-join

**Date**: 2026-03-16
**Status**: COMPLETE

## Changes Made

| File | Lines Changed | Type | Description |
|------|---------------|------|-------------|
| `handsome_transcribe/ui/workers.py` | 334 | Modified | Replace `getattr(seg, 'speaker_id', 'Unknown')` with explicit `None`-to-`"Unknown"` conversion in `_save_transcript()` |
| `handsome_transcribe/ui/workers.py` | 521 | Modified | Replace `seg.get("speaker", "Unknown")` with `seg.get("speaker") or "Unknown"` in `SummarizerWorker.run()` |
| `handsome_transcribe/ui/workers.py` | 640 | Modified | Replace `seg.get("speaker", "Unknown")` with `seg.get("speaker") or "Unknown"` in `ReporterWorker.run()` |
| `handsome_transcribe/reporting/report_generator.py` | 91 | Modified | Add `seg.speaker is not None` guard to the speakers set comprehension in `generate()` (Strategy 3, applied during Phase 2 to satisfy regression tests) |
| `tests/test_report_generator.py` | Added | New tests | Two regression tests covering `None` speaker scenarios |

## Verification Results

| Phase | Automated | Manual | Status |
|-------|-----------|--------|--------|
| Phase 1 | ✅ 3/3 | ✅ 2/2 | PASS |
| Phase 2 | ✅ 4/4 | — | PASS |

## Regression Tests

| Test | Location | Covers |
|------|----------|--------|
| `test_generate_report_with_none_speaker` | `tests/test_report_generator.py` | `ReportGenerator.generate()` does not raise `TypeError` when `TranscriptSegment.speaker` is `None`; speakers fall back to `["Unknown"]` |
| `test_generate_report_with_mixed_speakers` | `tests/test_report_generator.py` | Only valid non-None, non-Unknown speakers appear in `report.speakers`; `None` and `"Unknown"` are both excluded |

## Root Cause Addressed

The root cause — `getattr(seg, 'speaker_id', 'Unknown')` firing its fallback only on attribute absence, not on `None` values — is eliminated at `workers.py:334`. `None` speaker IDs are now explicitly converted to the `"Unknown"` string sentinel before JSON serialization.

Defense-in-depth was applied at three additional points:
- `workers.py:521` and `:640`: defensive `or "Unknown"` on deserialization, healing existing `transcript.json` files with `"speaker": null`
- `report_generator.py:91`: `is not None` guard in the speakers set comprehension, making the library-style module robust against `None` from any upstream source

**Before fix**: `transcript.json` written with `"speaker": null` → ReporterWorker reads `None` → `str.join([None])` → `TypeError` → session transitions to `error` state.

**After fix**: `transcript.json` written with `"speaker": "Unknown"` → all downstream code handles `"Unknown"` correctly → session completes successfully.
