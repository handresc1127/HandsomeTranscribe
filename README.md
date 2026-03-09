# HandsomeTranscribe

HandsomeTranscribe is a Python-based tool that records in-person meetings, automatically transcribes the conversation, identifies speakers, and generates structured meeting summaries and minutes.

**NEW**: Desktop UI with real-time transcription, speaker management, and visual results viewer!

---

## Features

- 🎙️ **Audio Recording** — capture microphone input (configurable duration or manual stop)
- 📝 **Speech-to-Text** — accurate local transcription via [Whisper](https://github.com/openai/whisper)
- 👥 **Speaker Diarization** — label each segment by speaker using [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- 📋 **Meeting Summarization** — extract summary, key topics, action items, and decisions
- 📄 **Report Generation** — export reports as Markdown, JSON, and PDF
- 🖥️ **Desktop UI** — PySide6-based GUI with live transcription, speaker library, session history, and results viewer
- 🎵 **Audio Playback** — built-in audio player for session recordings
- 📊 **Session Management** — database-backed session history with auto-save and crash recovery

---

## User Interfaces

HandsomeTranscribe provides two interfaces:

### 1. Desktop GUI (NEW - Recommended)

A modern Qt-based desktop application with:
- **Real-time Recording**: Live audio capture with visual feedback
- **Live Transcription**: See transcription progress as you record
- **Speaker Library**: Manage speaker profiles for improved diarization
- **Session History**: Browse and filter past sessions
- **Results Viewer**: Interactive tree view of session artifacts with audio playback
- **Report Access**: Open PDF, Markdown, JSON reports with system apps
- **Auto-save**: Sessions saved incrementally (crash-safe)

**Launch Desktop App:**
```bash
python desktop_app.py
```

### 2. Command-Line Interface (CLI)

Traditional CLI for scripting and automation (original interface):
```bash
python main.py [command] [options]
```

Both interfaces share the same backend and produce identical outputs.

---

## Project Structure

```
HandsomeTranscribe/
├── handsome_transcribe/
│   ├── audio/
│   │   └── recorder.py            # Microphone recording
│   ├── transcription/
│   │   └── whisper_transcriber.py # Whisper-based speech-to-text
│   ├── diarization/
│   │   └── speaker_identifier.py  # pyannote.audio speaker diarization
│   ├── summarization/
│   │   └── meeting_summarizer.py  # Meeting summarization & extraction
│   ├── reporting/
│   │   └── report_generator.py    # Markdown / JSON / PDF reports
│   └── ui/                        # Desktop GUI (NEW)
│       ├── windows/
│       │   ├── session_window.py  # Main application window
│       │   └── panels.py          # Tab panels (Config, Session, Results, etc.)
│       ├── workers/
│       │   ├── recorder_worker.py # Audio recording background worker
│       │   ├── transcription_worker.py
│       │   ├── diarization_worker.py
│       │   ├── summarization_worker.py
│       │   └── reporting_worker.py
│       ├── database.py            # SQLite session persistence
│       ├── event_bus.py           # Signal/slot event system
│       ├── session_manager.py     # Session lifecycle coordinator
│       ├── speaker_manager.py     # Speaker library management
│       ├── config_manager.py      # Configuration persistence
│       └── logger.py              # Application logging
├── outputs/
│   ├── audio/       # Recorded WAV files (CLI)
│   ├── transcripts/ # Transcript JSON files (CLI)
│   ├── reports/     # Generated reports (CLI)
│   └── sessions/    # Session directories (Desktop UI)
│       └── session_<id>/
│           ├── recording.wav
│           ├── transcript.txt
│           ├── transcript.json
│           ├── summary.md
│           ├── session_<id>_report.{md,json,pdf}
│           └── temp/  # Partial recordings (auto-save)
├── logs/
│   └── handsome_transcribe_YYYYMMDD.log  # Application logs
├── tests/
│   ├── test_*.py          # CLI module tests
│   └── ui/
│       ├── sprint1_*.py   # Infrastructure tests
│       ├── sprint2_*.py   # UI base tests
│       ├── sprint3_*.py   # Audio capture tests
│       ├── sprint4_*.py   # Processing pipeline tests
│       └── sprint5_*.py   # Results & polish tests
├── main.py              # CLI entry point
├── desktop_app.py       # Desktop GUI entry point (NEW)
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) installed and on your `PATH`

---

## Cost Strategy

This is a public-use project and is designed to prioritize free or low-cost tools.

- Prefer local, open-source Python workflows by default
- Current runtime mode is local-only (no paid cloud STT providers enabled)
- Use lightweight/default models first, then scale up only if needed
- Future cloud integrations (OpenAI API, Google, Azure, AWS) are roadmap items and disabled for now

### Runtime Provider Policy

- Active provider today: local Whisper only
- Not active in runtime: OpenAI API, Google Speech-to-Text, Azure Speech, AWS Transcribe
- Any future cloud provider must be opt-in and documented before release

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

### Desktop GUI Workflow

1. **Launch the app:**
   ```bash
   python desktop_app.py
   ```

2. **Configure Settings** (Configuration tab):
   - Select audio input device
   - Choose Whisper model size (tiny, base, small, medium, large)
   - Set language (auto-detect or specify)
   - Enable/disable diarization and summarization
   - Select output report formats (Markdown, JSON, PDF)

3. **Add Speakers (Optional)** (Interlocutores tab):
   - Click "Add New Speaker"
   - Enter speaker name and email
   - Upload audio sample (WAV file, 10+ seconds recommended)
   - Speakers are stored for improved diarization accuracy

4. **Start Recording** (Session tab):
   - Click "Start Recording" button
   - Speak clearly into microphone
   - Live transcription appears in text area
   - Click "Complete Session" when done
   - Processing begins automatically (transcription → diarization → summary → reports)

5. **View Results** (Results tab):
   - Tree view shows all session artifacts:
     - **Audio Recording**: Play audio with built-in player
     - **Transcription**: View text or JSON transcript in dialog
     - **Summary**: View markdown summary in rendered dialog
     - **Reports**: Open PDF/Markdown/JSON reports with system apps
   - Click "Open Folder" to browse session directory in file explorer
   - Click "Nueva Sesión" to start a new recording

6. **Browse History** (Sesiones tab):
   - Table shows all past sessions with metadata
   - Filter by state (COMPLETED, RECORDING, ERROR)
   - Click rows to view session details
   - View session statistics (total sessions, average duration)

### CLI Workflow (Legacy)

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

