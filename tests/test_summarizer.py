"""Tests for the MeetingSummarizer module."""

from __future__ import annotations

import pytest

from handsome_transcribe.summarization.meeting_summarizer import (
    MeetingSummarizer,
    MeetingSummary,
)
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
                text="Good morning everyone. Let's start the meeting.",
                speaker="SPEAKER_00",
            ),
            TranscriptSegment(
                start=5.0,
                end=10.0,
                text="Today we will review the Q1 roadmap and budget.",
                speaker="SPEAKER_01",
            ),
            TranscriptSegment(
                start=10.0,
                end=15.0,
                text="John will prepare the financial report by Friday.",
                speaker="SPEAKER_00",
            ),
            TranscriptSegment(
                start=15.0,
                end=20.0,
                text="We decided to move the release date to March 15th.",
                speaker="SPEAKER_01",
            ),
        ],
    )


@pytest.fixture
def empty_transcript() -> Transcript:
    return Transcript(audio_file="empty.wav", language="en", segments=[])


class TestMeetingSummary:
    def test_to_dict(self) -> None:
        ms = MeetingSummary(
            summary="Test summary.",
            key_topics=["roadmap", "budget"],
            action_items=["Prepare report"],
            decisions=["Move release date"],
        )
        d = ms.to_dict()
        assert d["summary"] == "Test summary."
        assert "roadmap" in d["key_topics"]
        assert "Prepare report" in d["action_items"]


class TestMeetingSummarizer:
    def test_summarize_empty_transcript(self, empty_transcript: Transcript) -> None:
        summarizer = MeetingSummarizer(use_transformers=False)
        result = summarizer.summarize(empty_transcript)
        assert "No content" in result.summary

    def test_extractive_summary_returns_text(self, sample_transcript: Transcript) -> None:
        summarizer = MeetingSummarizer(use_transformers=False)
        result = summarizer.summarize(sample_transcript)
        assert len(result.summary) > 0

    def test_action_items_detected(self, sample_transcript: Transcript) -> None:
        summarizer = MeetingSummarizer(use_transformers=False)
        result = summarizer.summarize(sample_transcript)
        # "will prepare" matches action pattern
        assert any("John" in item or "will" in item.lower() for item in result.action_items)

    def test_decisions_detected(self, sample_transcript: Transcript) -> None:
        summarizer = MeetingSummarizer(use_transformers=False)
        result = summarizer.summarize(sample_transcript)
        # "decided" matches decision pattern
        assert any("decided" in d.lower() for d in result.decisions)

    def test_extract_matches_empty_text(self) -> None:
        from handsome_transcribe.summarization.meeting_summarizer import _ACTION_PATTERNS

        result = MeetingSummarizer._extract_matches("", _ACTION_PATTERNS)
        assert result == []

    def test_extractive_summary_respects_sentence_count(self) -> None:
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six."
        result = MeetingSummarizer._extractive_summary(text, num_sentences=3)
        # Should contain only 3 sentences
        sentences = [s for s in result.split(". ") if s]
        assert len(sentences) == 3
