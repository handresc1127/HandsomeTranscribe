# Verified RCA: reporter-none-segment-join

**Date**: 2026-03-15
**Verifier**: AI Agent (RCA Verifier)
**Original RCA**: `rca-report.md`
**Status**: VERIFIED WITH NOTES

---

## Verification Summary

| Check                     | Result | Notes                                                                 |
| ------------------------- | ------ | --------------------------------------------------------------------- |
| 5 Whys Depth              | ✅     | 5 levels, each genuinely deeper than previous                         |
| Root Cause Fundamental    | ✅     | Design gap at serialization boundary — not a shallow symptom          |
| Execution Path            | ✅     | All code claims accurate; 2 minor line-number offsets (see notes)     |
| Fix Strategies            | ✅     | Both strategies address cause; companion fix covers existing files     |
| Side Effects              | ✅     | `report.speakers` used only at the 2 crash sites; no other consumers  |

---

## Root Cause (Confirmed)

`_save_transcript` in `workers.py:334` uses `getattr(seg, 'speaker_id', 'Unknown')`, which
returns the field's value (`None`) rather than the default string `'Unknown'`, because
`speaker_id` is a declared dataclass field (`Optional[int] = None`) and `getattr`'s third
argument only fires when the **attribute is absent**, not when it is `None`. This emits
`"speaker": null` into JSON, which then passes through `dict.get("speaker", "Unknown")` at
read-time unchanged (key is present), and flows as `None` into the speakers set, bypassing
the `!= "Unknown"` filter.

**Category**: Design Gap — misused `getattr` idiom at the serialization boundary when the
field type is `Optional[int]`.

---

## Recommended Fix Strategy

**Primary**: Strategy 1 — Fix at JSON serialization boundary (`workers.py:334`)

```python
# Before
"speaker": getattr(seg, 'speaker_id', 'Unknown')

# After
"speaker": str(seg.speaker_id) if seg.speaker_id is not None else "Unknown"
```

**Companion**: Strategy 2 — Defensive deserialization (`workers.py:640` and `workers.py:521`)

```python
# Before (both locations)
speaker=seg.get("speaker", "Unknown")

# After (both locations)
speaker=seg.get("speaker") or "Unknown"
```

**Risk Level**: Low (both changes)
**Files to Modify**: 1 file, 3 lines

---

## Verification Notes

### Line-Number Discrepancies Found

The following line references in the RCA are slightly off. Both are cosmetic — they point to
blank lines inside function bodies rather than the function definitions. Neither undermines
the logical analysis.

| RCA Reference                                    | Claim                            | Actual Line | Actual Content              |
| ------------------------------------------------ | -------------------------------- | ----------- | --------------------------- |
| `workers.py:634` (Execution Entry Point)         | `ReporterWorker.run()` starts    | **618**     | `def run(self):`            |
| `report_generator.py:88` (generate() call site) | `ReportGenerator.generate()`     | **67**      | `def generate(`             |

All other critical references confirmed accurate:

| Reference                     | Content Verified                                            |
| ----------------------------- | ----------------------------------------------------------- |
| `workers.py:334`              | `"speaker": getattr(seg, 'speaker_id', 'Unknown')` ✅      |
| `workers.py:640`              | `speaker=seg.get("speaker", "Unknown")` in ReporterWorker ✅|
| `workers.py:521`              | `speaker=seg.get("speaker", "Unknown")` in SummarizerWorker ✅|
| `models.py:133`               | `speaker_id: Optional[int] = None` ✅                      |
| `report_generator.py:90-91`   | Speaker set comprehension with `!= "Unknown"` filter ✅    |
| `report_generator.py:169`     | `', '.join(report.speakers)` in `_write_pdf` ✅            |
| `report_generator.py:226`     | `', '.join(report.speakers)` in `_render_markdown` ✅      |

### Side-Effect Analysis

- `report.speakers` is consumed only at `report_generator.py:169` and `:226` — both already
  identified crash sites. No other code in the project reads `report.speakers`.
- No code in the project reads back `"speaker": null` from JSON and expects numeric `None` —
  the fix at the write side introduces no regressions.
- `or "Unknown"` in Strategy 2 would coerce an empty-string speaker to `"Unknown"`. This is
  acceptable: empty string is not a valid speaker label in this domain.

### 5 Whys Quality Assessment

| Check           | Result | Detail                                                                              |
| --------------- | ------ | ----------------------------------------------------------------------------------- |
| Depth (≥5)      | ✅     | Exactly 5 levels traversed                                                          |
| Progression     | ✅     | Each Why moves from observable behavior → code behavior → data → design decision    |
| Fundamentality  | ✅     | Why 5 cannot be explained by adding more code — it names the wrong idiom choice     |
| Specificity     | ✅     | Pinpoints `getattr` vs. explicit null-check at a single line                        |
| Category Fit    | ✅     | "Design Gap" correctly distinguishes from a logic error or missing feature          |

---

## Corrections Required

None. The RCA is logically sound and fully actionable. The two line-number offsets noted
above should be corrected in the rca-report.md for traceability but do not block
implementation.

---

## Ready for Next Phase: Implementation Planning
