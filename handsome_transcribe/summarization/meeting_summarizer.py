"""Meeting summarization module.

Generates a structured meeting summary from a transcript, extracting:
- Overall summary
- Key topics discussed
- Action items and decisions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rich.console import Console

from handsome_transcribe.transcription.whisper_transcriber import Transcript

console = Console()

# Patterns used by the lightweight rule-based fallback summariser
_ACTION_PATTERNS = [
    r"\b(?:will|shall|must|need to|needs to|should|going to|have to|has to)\s+\w+",
    r"\b(?:action item|todo|to-do|follow.?up|follow up)\b",
    r"\b(?:assign(?:ed)?|responsible for|owner)\b",
]

_DECISION_PATTERNS = [
    r"\b(?:decided|agreed|approved|confirmed|resolved|concluded)\b",
    r"\b(?:we will|let's|let us)\s+\w+",
    r"\b(?:the decision is|decision:)\b",
]


@dataclass
class MeetingSummary:
    """Structured meeting summary."""

    summary: str
    key_topics: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "summary": self.summary,
            "key_topics": self.key_topics,
            "action_items": self.action_items,
            "decisions": self.decisions,
        }


class MeetingSummarizer:
    """Produces a structured :class:`MeetingSummary` from a :class:`Transcript`.

    Uses one of two back-ends, selected automatically:

    1. **Transformer-based** (preferred): loads a lightweight summarisation
       model from 🤗 Transformers (``facebook/bart-large-cnn`` by default).
    2. **Rule-based fallback**: pattern matching + extractive summarisation
       when transformers are not installed or when *use_transformers=False*.
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-cnn",
        use_transformers: bool = True,
    ) -> None:
        self.model_name = model_name
        self.use_transformers = use_transformers
        self._pipeline = None  # Lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(self, transcript: Transcript) -> MeetingSummary:
        """Generate a :class:`MeetingSummary` from *transcript*.

        Args:
            transcript: The (optionally speaker-labelled) transcript.

        Returns:
            A :class:`MeetingSummary` with summary, topics, actions, decisions.
        """
        full_text = transcript.full_text
        if not full_text.strip():
            return MeetingSummary(
                summary="No content to summarize.",
                key_topics=[],
                action_items=[],
                decisions=[],
            )

        console.print("[bold green]Generating meeting summary…[/bold green]")

        summary = self._generate_summary(full_text)
        key_topics = self._extract_key_topics(full_text)
        action_items = self._extract_matches(full_text, _ACTION_PATTERNS)
        decisions = self._extract_matches(full_text, _DECISION_PATTERNS)

        return MeetingSummary(
            summary=summary,
            key_topics=key_topics,
            action_items=action_items,
            decisions=decisions,
        )

    # ------------------------------------------------------------------
    # Summarisation back-ends
    # ------------------------------------------------------------------

    def _generate_summary(self, text: str) -> str:
        """Return a prose summary using the configured back-end."""
        if self.use_transformers:
            try:
                return self._transformer_summary(text)
            except Exception as exc:  # noqa: BLE001
                console.print(
                    f"[yellow]Transformer summariser unavailable ({exc}). "
                    "Falling back to extractive summariser.[/yellow]"
                )

        return self._extractive_summary(text)

    def _transformer_summary(self, text: str) -> str:
        """Use a HuggingFace summarisation pipeline."""
        from transformers import pipeline as hf_pipeline  # noqa: PLC0415

        if self._pipeline is None:
            console.print(
                f"[dim]Loading summarisation model '{self.model_name}'…[/dim]"
            )
            self._pipeline = hf_pipeline(
                "summarization",
                model=self.model_name,
                tokenizer=self.model_name,
            )

        # BART has a max input of ~1024 tokens; truncate if necessary
        max_chars = 3000
        truncated = text[:max_chars]

        result = self._pipeline(
            truncated,
            max_length=200,
            min_length=40,
            do_sample=False,
        )
        return result[0]["summary_text"]

    @staticmethod
    def _extractive_summary(text: str, num_sentences: int = 5) -> str:
        """Simple extractive summariser: return the first *num_sentences*."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        selected = sentences[:num_sentences]
        return " ".join(selected)

    # ------------------------------------------------------------------
    # Information extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_key_topics(text: str, max_topics: int = 10) -> list[str]:
        """Extract candidate topics using simple noun-phrase heuristics."""
        # Attempt to use NLTK for noun-chunk extraction
        try:
            import nltk  # noqa: PLC0415

            try:
                nltk.data.find("tokenizers/punkt_tab")
            except LookupError:
                nltk.download("punkt_tab", quiet=True)
            try:
                nltk.data.find("taggers/averaged_perceptron_tagger_eng")
            except LookupError:
                nltk.download("averaged_perceptron_tagger_eng", quiet=True)

            tokens = nltk.word_tokenize(text)
            tagged = nltk.pos_tag(tokens)
            # Collect consecutive noun sequences
            topics: list[str] = []
            chunk: list[str] = []
            for word, tag in tagged:
                if tag.startswith("NN"):
                    chunk.append(word)
                else:
                    if len(chunk) >= 2:
                        topics.append(" ".join(chunk))
                    chunk = []
            if len(chunk) >= 2:
                topics.append(" ".join(chunk))

            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for t in topics:
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(t)
            return unique[:max_topics]

        except Exception:  # noqa: BLE001
            pass

        # Fallback: extract words longer than 5 characters as rough topics
        words = re.findall(r"\b[A-Za-z]{6,}\b", text)
        seen_w: set[str] = set()
        topics_fb: list[str] = []
        for w in words:
            lw = w.lower()
            if lw not in seen_w:
                seen_w.add(lw)
                topics_fb.append(w)
        return topics_fb[:max_topics]

    @staticmethod
    def _extract_matches(text: str, patterns: list[str]) -> list[str]:
        """Return sentences from *text* that match any of the given regex *patterns*."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        matches: list[str] = []
        for sentence in sentences:
            for pattern in patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    sentence_clean = sentence.strip()
                    if sentence_clean and sentence_clean not in matches:
                        matches.append(sentence_clean)
                    break
        return matches
