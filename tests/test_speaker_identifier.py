"""Tests for the SpeakerIdentifier module."""

from __future__ import annotations

import pytest

from handsome_transcribe.diarization.speaker_identifier import (
    DiarizedSegment,
    SpeakerIdentifier,
)
from handsome_transcribe.transcription.whisper_transcriber import (
    Transcript,
    TranscriptSegment,
)


@pytest.fixture
def diarized_segments() -> list[DiarizedSegment]:
    return [
        DiarizedSegment(start=0.0, end=5.0, speaker="SPEAKER_00"),
        DiarizedSegment(start=5.0, end=10.0, speaker="SPEAKER_01"),
        DiarizedSegment(start=10.0, end=15.0, speaker="SPEAKER_00"),
    ]


@pytest.fixture
def transcript() -> Transcript:
    return Transcript(
        audio_file="test.wav",
        language="en",
        segments=[
            TranscriptSegment(start=0.5, end=4.5, text="Hello everyone."),
            TranscriptSegment(start=5.5, end=9.5, text="Good morning."),
            TranscriptSegment(start=10.5, end=14.5, text="Let's begin."),
        ],
    )


class TestFindSpeaker:
    def test_exact_overlap(self, diarized_segments: list[DiarizedSegment]) -> None:
        speaker = SpeakerIdentifier._find_speaker(0.5, 4.5, diarized_segments)
        assert speaker == "SPEAKER_00"

    def test_second_speaker(self, diarized_segments: list[DiarizedSegment]) -> None:
        speaker = SpeakerIdentifier._find_speaker(5.5, 9.5, diarized_segments)
        assert speaker == "SPEAKER_01"

    def test_no_overlap_returns_unknown(self, diarized_segments: list[DiarizedSegment]) -> None:
        speaker = SpeakerIdentifier._find_speaker(20.0, 25.0, diarized_segments)
        assert speaker == "Unknown"

    def test_majority_overlap(self, diarized_segments: list[DiarizedSegment]) -> None:
        # 4.5 - 5.0 = 0.5s in SPEAKER_00, 5.0 - 6.0 = 1s in SPEAKER_01
        speaker = SpeakerIdentifier._find_speaker(4.5, 6.0, diarized_segments)
        assert speaker == "SPEAKER_01"


class TestAssignSpeakers:
    def test_assigns_correct_speakers(
        self,
        transcript: Transcript,
        diarized_segments: list[DiarizedSegment],
    ) -> None:
        identifier = SpeakerIdentifier()
        labelled = identifier.assign_speakers(transcript, diarized_segments)

        assert labelled.segments[0].speaker == "SPEAKER_00"
        assert labelled.segments[1].speaker == "SPEAKER_01"
        assert labelled.segments[2].speaker == "SPEAKER_00"

    def test_original_transcript_not_mutated(
        self,
        transcript: Transcript,
        diarized_segments: list[DiarizedSegment],
    ) -> None:
        identifier = SpeakerIdentifier()
        identifier.assign_speakers(transcript, diarized_segments)
        assert all(seg.speaker == "Unknown" for seg in transcript.segments)

    def test_text_preserved(
        self,
        transcript: Transcript,
        diarized_segments: list[DiarizedSegment],
    ) -> None:
        identifier = SpeakerIdentifier()
        labelled = identifier.assign_speakers(transcript, diarized_segments)
        assert labelled.segments[0].text == "Hello everyone."
