"""Tests for the ReportGenerator module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from handsome_transcribe.reporting.report_generator import MeetingReport, ReportGenerator
from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
from handsome_transcribe.transcription.whisper_transcriber import (
    Transcript,
    TranscriptSegment,
)


@pytest.fixture
def sample_transcript() -> Transcript:
    return Transcript(
        audio_file="test.wav",
        language="en",
        segments=[
            TranscriptSegment(
                start=0.0,
                end=5.0,
                text="Good morning everyone.",
                speaker="SPEAKER_00",
            ),
            TranscriptSegment(
                start=5.0,
                end=10.0,
                text="Let's review the roadmap.",
                speaker="SPEAKER_01",
            ),
        ],
    )


@pytest.fixture
def sample_summary() -> MeetingSummary:
    return MeetingSummary(
        summary="The team discussed the Q1 roadmap.",
        key_topics=["roadmap", "Q1"],
        action_items=["Prepare financial report"],
        decisions=["Move release to March"],
    )


class TestReportGenerator:
    def test_generate_markdown(
        self,
        tmp_path: Path,
        sample_transcript: Transcript,
        sample_summary: MeetingSummary,
    ) -> None:
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            sample_transcript,
            sample_summary,
            title="Test Meeting",
            formats=["markdown"],
        )
        assert "markdown" in saved
        md_path = saved["markdown"]
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "# Test Meeting" in content
        assert "SPEAKER_00" in content
        assert "roadmap" in content

    def test_generate_json(
        self,
        tmp_path: Path,
        sample_transcript: Transcript,
        sample_summary: MeetingSummary,
    ) -> None:
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            sample_transcript,
            sample_summary,
            title="Test Meeting",
            formats=["json"],
        )
        assert "json" in saved
        json_path = saved["json"]
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["title"] == "Test Meeting"
        assert "transcript" in data
        assert "summary" in data

    def test_generate_all_formats(
        self,
        tmp_path: Path,
        sample_transcript: Transcript,
        sample_summary: MeetingSummary,
    ) -> None:
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            sample_transcript,
            sample_summary,
            title="Full Meeting",
            formats=["markdown", "json", "pdf"],
        )
        assert "markdown" in saved
        assert "json" in saved
        assert "pdf" in saved
        assert saved["markdown"].exists()
        assert saved["json"].exists()
        assert saved["pdf"].exists()

    def test_safe_stem(self) -> None:
        assert ReportGenerator._safe_stem("Q1 Planning Meeting!") == "q1_planning_meeting"
        assert ReportGenerator._safe_stem("") == "meeting"
        assert ReportGenerator._safe_stem("  Hello World  ") == "hello_world"

    def test_markdown_includes_action_items(
        self,
        tmp_path: Path,
        sample_transcript: Transcript,
        sample_summary: MeetingSummary,
    ) -> None:
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            sample_transcript,
            sample_summary,
            title="Meeting",
            formats=["markdown"],
        )
        content = saved["markdown"].read_text(encoding="utf-8")
        assert "Action Items" in content
        assert "Prepare financial report" in content

    def test_markdown_includes_decisions(
        self,
        tmp_path: Path,
        sample_transcript: Transcript,
        sample_summary: MeetingSummary,
    ) -> None:
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            sample_transcript,
            sample_summary,
            title="Meeting",
            formats=["markdown"],
        )
        content = saved["markdown"].read_text(encoding="utf-8")
        assert "Decisions" in content
        assert "Move release to March" in content

    # Regression tests for: reporter-none-segment-join
    # Root cause: getattr(seg, 'speaker_id', 'Unknown') emits None when speaker_id
    # is a declared Optional[int] = None dataclass field. None then passes through
    # dict.get("speaker", "Unknown") and causes TypeError in str.join(report.speakers).

    def test_generate_report_with_none_speaker(
        self,
        tmp_path: Path,
        sample_summary: MeetingSummary,
    ) -> None:
        transcript = Transcript(
            audio_file="test.wav",
            language="es",
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="Hola.", speaker=None),
            ],
        )
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            transcript,
            sample_summary,
            title="None Speaker Meeting",
            formats=["markdown", "json"],
        )
        assert "markdown" in saved
        assert "json" in saved
        content = saved["markdown"].read_text(encoding="utf-8")
        assert "Unknown" in content

    def test_generate_report_with_mixed_speakers(
        self,
        tmp_path: Path,
        sample_summary: MeetingSummary,
    ) -> None:
        transcript = Transcript(
            audio_file="test.wav",
            language="es",
            segments=[
                TranscriptSegment(start=0.0, end=3.0, text="Hola.", speaker=None),
                TranscriptSegment(start=3.0, end=6.0, text="Bien.", speaker="Unknown"),
                TranscriptSegment(start=6.0, end=9.0, text="Gracias.", speaker="SPEAKER_01"),
            ],
        )
        gen = ReportGenerator(output_dir=tmp_path)
        saved = gen.generate(
            transcript,
            sample_summary,
            title="Mixed Speaker Meeting",
            formats=["json"],
        )
        data = json.loads(saved["json"].read_text(encoding="utf-8"))
        speakers = data["speakers"]
        assert "SPEAKER_01" in speakers
        assert None not in speakers
        assert "Unknown" not in speakers
