# HandsomeTranscribe

HandsomeTranscribe is a Python-based tool that records in-person meetings, automatically transcribes the conversation, identifies speakers, and generates structured meeting summaries and minutes.

---

## Features

- 🎙️ **Audio Recording** — capture microphone input (configurable duration or manual stop)
- 📝 **Speech-to-Text** — accurate transcription via [OpenAI Whisper](https://github.com/openai/whisper)
- 👥 **Speaker Diarization** — label each segment by speaker using [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- 📋 **Meeting Summarization** — extract summary, key topics, action items, and decisions
- 📄 **Report Generation** — export reports as Markdown, JSON, and PDF

---

## Project Structure

```
HandsomeTranscribe/
├── handsome_transcribe/
│   ├── audio/
│   │   └── recorder.py           # Microphone recording
│   ├── transcription/
│   │   └── whisper_transcriber.py # Whisper-based speech-to-text
│   ├── diarization/
│   │   └── speaker_identifier.py  # pyannote.audio speaker diarization
│   ├── summarization/
│   │   └── meeting_summarizer.py  # Meeting summarization & extraction
│   └── reporting/
│       └── report_generator.py    # Markdown / JSON / PDF reports
├── outputs/
│   ├── audio/       # Recorded WAV files
│   ├── transcripts/ # Transcript JSON files
│   └── reports/     # Generated reports
├── tests/
│   └── test_*.py
├── main.py          # CLI entry point
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) installed and on your `PATH`

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/handresc1127/HandsomeTranscribe.git
cd HandsomeTranscribe
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install ffmpeg

| OS      | Command                         |
|---------|---------------------------------|
| Ubuntu  | `sudo apt install ffmpeg`       |
| macOS   | `brew install ffmpeg`           |
| Windows | Download from https://ffmpeg.org |

### 5. (Optional) Hugging Face token for speaker diarization

Speaker diarization uses `pyannote/speaker-diarization-3.1`, which requires a
[Hugging Face](https://huggingface.co/) account and acceptance of the model's
usage conditions.

```bash
export HF_TOKEN="hf_your_token_here"
```

---

## Usage

### Record a meeting

```bash
# Record until you press Enter
python main.py record

# Record for exactly 60 seconds
python main.py record --duration 60

# Record with a custom file name
python main.py record --output my_meeting
```

### Transcribe an audio file

```bash
python main.py transcribe outputs/audio/recording_20240101_120000.wav

# Use a larger (more accurate) Whisper model
python main.py transcribe outputs/audio/recording_20240101_120000.wav --model medium
```

### Run speaker diarization

```bash
# Diarize only
python main.py diarize outputs/audio/recording_20240101_120000.wav

# Diarize and annotate an existing transcript with speaker labels
python main.py diarize outputs/audio/recording_20240101_120000.wav \
  --transcript outputs/transcripts/recording_20240101_120000_transcript.json
```

### Summarize a transcript

```bash
python main.py summarize outputs/transcripts/recording_20240101_120000_transcript.json

# Use the lightweight rule-based summariser (no GPU/download required)
python main.py summarize outputs/transcripts/recording_20240101_120000_transcript.json \
  --no-transformers
```

### Generate a full meeting report

```bash
# All formats: Markdown + JSON + PDF
python main.py generate-report \
  outputs/transcripts/recording_20240101_120000_transcript.json \
  --title "Q1 Planning Meeting"

# Markdown only
python main.py generate-report \
  outputs/transcripts/recording_20240101_120000_transcript.json \
  --title "Q1 Planning Meeting" \
  --format markdown
```

---

## Output Files

| Location                            | Contents                            |
|-------------------------------------|-------------------------------------|
| `outputs/audio/*.wav`               | Raw meeting recordings              |
| `outputs/transcripts/*_transcript.json` | Whisper transcripts             |
| `outputs/transcripts/*_speakers.json`   | Speaker-annotated transcripts   |
| `outputs/reports/*_report.md`       | Markdown report                     |
| `outputs/reports/*_report.json`     | JSON report                         |
| `outputs/reports/*_report.pdf`      | PDF report                          |

---

## Example Transcript Output

```
[Speaker 1]
Good morning everyone, let's start the meeting.

[Speaker 2]
Today we will review the Q1 roadmap.
```

---

## Transcript JSON Schema

```json
{
  "audio_file": "outputs/audio/recording.wav",
  "language": "en",
  "segments": [
    { "start": 0.0, "end": 3.5, "text": "Good morning everyone.", "speaker": "SPEAKER_00" }
  ]
}
```

---

## License

MIT

