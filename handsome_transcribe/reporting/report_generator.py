"""Meeting report generation module.

Produces structured meeting reports in three formats:
- Markdown (.md)
- JSON (.json)
- PDF  (.pdf)  — requires the ``reportlab`` package
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

from rich.console import Console

from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
from handsome_transcribe.transcription.whisper_transcriber import Transcript

console = Console()

OUTPUTS_REPORTS_DIR = Path("outputs/reports")


@dataclass
class MeetingReport:
    """Complete meeting report data model."""

    title: str
    date: str
    speakers: List[str]
    transcript: Transcript
    summary: MeetingSummary
    output_dir: Path = field(default_factory=lambda: OUTPUTS_REPORTS_DIR)

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the full report to a dictionary."""
        return {
            "title": self.title,
            "date": self.date,
            "speakers": self.speakers,
            "transcript": self.transcript.to_dict(),
            "summary": self.summary.to_dict(),
        }


class ReportGenerator:
    """Generates meeting reports in Markdown, JSON, and PDF formats."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or OUTPUTS_REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        transcript: Transcript,
        summary: MeetingSummary,
        title: str = "Meeting",
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """Generate reports in the requested *formats*.

        Args:
            transcript: The (speaker-labelled) transcript.
            summary: The structured meeting summary.
            title: Title of the meeting.
            formats: List of output formats (``"markdown"``, ``"json"``, ``"pdf"``).
                     Defaults to all three.

        Returns:
            A mapping from format name to the saved file path.
        """
        if formats is None:
            formats = ["markdown", "json", "pdf"]

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        speakers = sorted(
            {seg.speaker for seg in transcript.segments if seg.speaker != "Unknown"}
        ) or ["Unknown"]

        report = MeetingReport(
            title=title,
            date=date_str,
            speakers=speakers,
            transcript=transcript,
            summary=summary,
            output_dir=self.output_dir,
        )

        stem = self._safe_stem(title)
        saved: dict[str, Path] = {}

        for fmt in formats:
            fmt_lower = fmt.lower()
            if fmt_lower == "markdown":
                path = self._write_markdown(report, stem)
                saved["markdown"] = path
            elif fmt_lower == "json":
                path = self._write_json(report, stem)
                saved["json"] = path
            elif fmt_lower == "pdf":
                path = self._write_pdf(report, stem)
                saved["pdf"] = path
            else:
                console.print(f"[yellow]Unknown format '{fmt}' — skipped.[/yellow]")

        for fmt, path in saved.items():
            console.print(f"[bold blue]Report ({fmt}) saved to:[/bold blue] {path}")

        return saved

    # ------------------------------------------------------------------
    # Format writers
    # ------------------------------------------------------------------

    def _write_markdown(self, report: MeetingReport, stem: str) -> Path:
        """Write a Markdown report and return the path."""
        path = self.output_dir / f"{stem}_report.md"
        content = self._render_markdown(report)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_json(self, report: MeetingReport, stem: str) -> Path:
        """Write a JSON report and return the path."""
        path = self.output_dir / f"{stem}_report.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2, ensure_ascii=False)
        return path

    def _write_pdf(self, report: MeetingReport, stem: str) -> Path:
        """Write a PDF report using reportlab and return the path."""
        path = self.output_dir / f"{stem}_report.pdf"
        try:
            from reportlab.lib.pagesizes import LETTER  # noqa: PLC0415
            from reportlab.lib.styles import getSampleStyleSheet  # noqa: PLC0415
            from reportlab.lib.units import inch  # noqa: PLC0415
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: PLC0415

            styles = getSampleStyleSheet()
            doc = SimpleDocTemplate(str(path), pagesize=LETTER)
            story = []

            def add_heading(text: str, level: int = 1) -> None:
                style_name = "Heading1" if level == 1 else "Heading2"
                story.append(Paragraph(text, styles[style_name]))
                story.append(Spacer(1, 0.1 * inch))

            def add_body(text: str) -> None:
                # Escape HTML special chars for reportlab
                safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, styles["Normal"]))
                story.append(Spacer(1, 0.05 * inch))

            add_heading(report.title)
            add_body(f"Date: {report.date}")
            add_body(f"Speakers: {', '.join(report.speakers)}")

            add_heading("Summary", 2)
            add_body(report.summary.summary)

            if report.summary.key_topics:
                add_heading("Key Topics", 2)
                for topic in report.summary.key_topics:
                    add_body(f"• {topic}")

            if report.summary.action_items:
                add_heading("Action Items", 2)
                for item in report.summary.action_items:
                    add_body(f"• {item}")

            if report.summary.decisions:
                add_heading("Decisions", 2)
                for decision in report.summary.decisions:
                    add_body(f"• {decision}")

            add_heading("Full Transcript", 2)
            current_speaker = None
            for seg in report.transcript.segments:
                if seg.speaker != current_speaker:
                    current_speaker = seg.speaker
                    add_body(f"[{current_speaker}]")
                add_body(seg.text.strip())

            doc.build(story)

        except ImportError:
            console.print(
                "[yellow]reportlab not installed — PDF generation skipped. "
                "Install it with: pip install reportlab[/yellow]"
            )
            # Write a placeholder so the function still returns a consistent path
            path.write_text(
                "PDF generation requires reportlab. "
                "Install it with: pip install reportlab\n",
                encoding="utf-8",
            )

        return path

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _render_markdown(report: MeetingReport) -> str:
        """Build the full Markdown string for *report*."""
        lines: list[str] = []

        lines += [
            f"# {report.title}",
            "",
            f"**Date:** {report.date}",
            f"**Speakers:** {', '.join(report.speakers)}",
            "",
            "---",
            "",
            "## Summary",
            "",
            report.summary.summary,
            "",
        ]

        if report.summary.key_topics:
            lines += ["## Key Topics", ""]
            for topic in report.summary.key_topics:
                lines.append(f"- {topic}")
            lines.append("")

        if report.summary.action_items:
            lines += ["## Action Items", ""]
            for item in report.summary.action_items:
                lines.append(f"- {item}")
            lines.append("")

        if report.summary.decisions:
            lines += ["## Decisions", ""]
            for decision in report.summary.decisions:
                lines.append(f"- {decision}")
            lines.append("")

        lines += ["---", "", "## Full Transcript", ""]

        current_speaker = None
        for seg in report.transcript.segments:
            if seg.speaker != current_speaker:
                current_speaker = seg.speaker
                lines += ["", f"**[{current_speaker}]**", ""]
            lines.append(seg.text.strip())

        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_stem(title: str) -> str:
        """Return a filesystem-safe version of *title*."""
        import re  # noqa: PLC0415

        safe = re.sub(r"[^\w\s-]", "", title)
        safe = re.sub(r"\s+", "_", safe.strip())
        return safe.lower() or "meeting"
