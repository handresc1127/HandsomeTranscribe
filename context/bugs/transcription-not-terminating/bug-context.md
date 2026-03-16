# Bug: transcription-not-terminating

**Title:** Transcription process never terminates/completes in desktop app
**Status:** Open
**Priority:** High
**Created:** 2026-03-15
**Source:** Manual description (Copilot Chat)

## Description

The desktop application starts a recording session successfully, but when the recording is stopped, the transcription process never completes. The pipeline hangs and never transitions to completion. The user has two Spanish audio files (recording1.wav and recording2.wav) that should produce Spanish transcription output but the process never finishes.

Additionally, there is no debug-level logging during transcription, making it impossible to diagnose where the pipeline stalls.

## Steps to Reproduce

1. Open desktop app
2. Configure language to Spanish
3. Start session and record audio (or use recording1.wav / recording2.wav)
4. Stop recording
5. Observe: transcription never completes, UI stays stuck

## Expected Behavior

1. After stopping recording, transcription should run to completion
2. Pipeline should transition through: TRANSCRIBING → DIARIZING → SUMMARIZING → COMPLETED
3. Debug logs should show progress through each stage
4. Spanish audio files (recording1.wav, recording2.wav) should produce correct Spanish transcription

## Actual Behavior

1. Transcription starts but never terminates
2. No debug logging visible during transcription stages
3. Pipeline hangs indefinitely

## Environment

- Desktop app (PySide6), Whisper model
- Audio files: recording1.wav (~465KB, 16-bit PCM, 16kHz mono), recording2.wav (~252KB, 16-bit PCM, 16kHz mono)
- Language: Spanish (es)

## Additional Context

- Previous fixes successfully wired language parameter from UI to TranscriberWorker
- Previous fixes added 30s periodic partial transcription timer
- The TranscriberWorker emits transcription_error on exception, but SessionManager may not handle this signal
- The pipeline chain is: _start_transcription → _on_transcription_complete → _start_diarization → _start_summarization → _start_reporting → _complete_session
- If any stage fails silently or error signals are not connected, the pipeline will hang

---
*Note: This bug context was created from a manual description. No external ticket system is associated.*
