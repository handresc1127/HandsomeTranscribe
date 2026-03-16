"""HandsomeTranscribe — CLI entry point.

Usage examples:
    python main.py record
    python main.py record --duration 60
    python main.py transcribe outputs/audio/recording_20240101_120000.wav
    python main.py diarize outputs/audio/recording_20240101_120000.wav
    python main.py summarize outputs/transcripts/recording_20240101_120000_transcript.json
    python main.py generate-report outputs/transcripts/recording_20240101_120000_transcript.json
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="handsome-transcribe",
    help="Record meetings, transcribe speech, identify speakers, and generate reports.",
    add_completion=False,
)
console = Console()


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

@app.command()
def record(
    duration: Optional[float] = typer.Option(
        None,
        "--duration",
        "-d",
        help="Recording duration in seconds. Omit for manual stop (press Enter).",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output filename (without extension). Defaults to a timestamp.",
    ),
    sample_rate: int = typer.Option(
        16000,
        "--sample-rate",
        "-r",
        help="Sample rate in Hz.",
    ),
) -> None:
    """Record audio from the system microphone."""
    from handsome_transcribe.audio.recorder import AudioRecorder  # noqa: PLC0415

    recorder = AudioRecorder(sample_rate=sample_rate)
    path = recorder.record(duration=duration, filename=output)
    console.print(f"[bold green]✔[/bold green] Recording saved: [cyan]{path}[/cyan]")


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------

@app.command()
def transcribe(
    audio_file: Path = typer.Argument(
        ...,
        help="Path to the audio file (WAV or MP3).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    model: str = typer.Option(
        "base",
        "--model",
        "-m",
        help="Whisper model size: tiny | base | small | medium | large.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="BCP-47 language code to force (e.g. 'es', 'en'). Auto-detects if omitted.",
    ),
    no_save: bool = typer.Option(
        False,
        "--no-save",
        help="Do not save the transcript to disk.",
    ),
) -> None:
    """Transcribe an audio file using local Whisper."""
    from handsome_transcribe.transcription.whisper_transcriber import WhisperTranscriber  # noqa: PLC0415

    transcriber = WhisperTranscriber(model_name=model, language=language)
    transcript = transcriber.transcribe(audio_file, save=not no_save)

    table = Table(title="Transcript Preview", show_lines=True)
    table.add_column("Start (s)", style="dim", width=10)
    table.add_column("End (s)", style="dim", width=10)
    table.add_column("Speaker", style="cyan", width=12)
    table.add_column("Text")

    for seg in transcript.segments[:20]:
        table.add_row(
            f"{seg.start:.1f}",
            f"{seg.end:.1f}",
            seg.speaker,
            seg.text.strip(),
        )

    console.print(table)
    if len(transcript.segments) > 20:
        console.print(
            f"[dim]… {len(transcript.segments) - 20} more segment(s) not shown.[/dim]"
        )


# ---------------------------------------------------------------------------
# diarize
# ---------------------------------------------------------------------------

@app.command()
def diarize(
    audio_file: Path = typer.Argument(
        ...,
        help="Path to the audio file (WAV or MP3).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    transcript_file: Optional[Path] = typer.Option(
        None,
        "--transcript",
        "-t",
        help="Path to an existing transcript JSON file to annotate with speaker labels.",
    ),
    hf_token: Optional[str] = typer.Option(
        None,
        "--hf-token",
        envvar="HF_TOKEN",
        help="Hugging Face token for pyannote.audio.",
    ),
) -> None:
    """Run speaker diarization on an audio file."""
    from handsome_transcribe.diarization.speaker_identifier import SpeakerIdentifier  # noqa: PLC0415
    from handsome_transcribe.transcription.whisper_transcriber import WhisperTranscriber  # noqa: PLC0415

    identifier = SpeakerIdentifier(hf_token=hf_token)
    diarized_segments = identifier.diarize(audio_file)

    table = Table(title="Speaker Diarization", show_lines=True)
    table.add_column("Start (s)", style="dim", width=10)
    table.add_column("End (s)", style="dim", width=10)
    table.add_column("Speaker", style="cyan")

    for seg in diarized_segments:
        table.add_row(f"{seg.start:.1f}", f"{seg.end:.1f}", seg.speaker)

    console.print(table)

    if transcript_file:
        transcript = WhisperTranscriber.load_transcript(transcript_file)
        labelled_transcript = identifier.assign_speakers(transcript, diarized_segments)
        from handsome_transcribe.transcription.whisper_transcriber import WhisperTranscriber as WT  # noqa: PLC0415

        out_path = transcript_file.parent / (
            transcript_file.stem + "_speakers.json"
        )
        import json  # noqa: PLC0415

        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(labelled_transcript.to_dict(), fh, indent=2, ensure_ascii=False)
        console.print(
            f"[bold blue]Speaker-labelled transcript saved to:[/bold blue] {out_path}"
        )


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

@app.command()
def summarize(
    transcript_file: Path = typer.Argument(
        ...,
        help="Path to a transcript JSON file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    no_transformers: bool = typer.Option(
        False,
        "--no-transformers",
        help="Use the rule-based summariser instead of a transformer model.",
    ),
    model: str = typer.Option(
        "facebook/bart-large-cnn",
        "--model",
        "-m",
        help="HuggingFace summarisation model to use.",
    ),
) -> None:
    """Summarize a meeting transcript."""
    from handsome_transcribe.summarization.meeting_summarizer import MeetingSummarizer  # noqa: PLC0415
    from handsome_transcribe.transcription.whisper_transcriber import WhisperTranscriber  # noqa: PLC0415

    transcript = WhisperTranscriber.load_transcript(transcript_file)
    summarizer = MeetingSummarizer(
        model_name=model,
        use_transformers=not no_transformers,
    )
    meeting_summary = summarizer.summarize(transcript)

    console.rule("[bold]Meeting Summary[/bold]")
    console.print(meeting_summary.summary)

    if meeting_summary.key_topics:
        console.rule("[bold]Key Topics[/bold]")
        for topic in meeting_summary.key_topics:
            console.print(f"  • {topic}")

    if meeting_summary.action_items:
        console.rule("[bold]Action Items[/bold]")
        for item in meeting_summary.action_items:
            console.print(f"  • {item}")

    if meeting_summary.decisions:
        console.rule("[bold]Decisions[/bold]")
        for decision in meeting_summary.decisions:
            console.print(f"  • {decision}")


# ---------------------------------------------------------------------------
# generate-report
# ---------------------------------------------------------------------------

@app.command()
def generate_report(
    transcript_file: Path = typer.Argument(
        ...,
        help="Path to a transcript JSON file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    title: str = typer.Option("Meeting", "--title", "-t", help="Meeting title."),
    formats: List[str] = typer.Option(
        ["markdown", "json", "pdf"],
        "--format",
        "-f",
        help="Output format(s): markdown, json, pdf. Can be repeated.",
    ),
    no_transformers: bool = typer.Option(
        False,
        "--no-transformers",
        help="Use the rule-based summariser instead of a transformer model.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory for report files. Defaults to outputs/reports.",
    ),
) -> None:
    """Generate a structured meeting report (Markdown, JSON, PDF)."""
    from handsome_transcribe.reporting.report_generator import ReportGenerator  # noqa: PLC0415
    from handsome_transcribe.summarization.meeting_summarizer import MeetingSummarizer  # noqa: PLC0415
    from handsome_transcribe.transcription.whisper_transcriber import WhisperTranscriber  # noqa: PLC0415

    transcript = WhisperTranscriber.load_transcript(transcript_file)

    summarizer = MeetingSummarizer(use_transformers=not no_transformers)
    meeting_summary = summarizer.summarize(transcript)

    generator = ReportGenerator(output_dir=output_dir)
    saved = generator.generate(
        transcript=transcript,
        summary=meeting_summary,
        title=title,
        formats=formats,
    )

    console.rule("[bold green]Report Generation Complete[/bold green]")
    for fmt, path in saved.items():
        console.print(f"  [bold cyan]{fmt.upper()}[/bold cyan] → {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
