# Bug: transcription-language-not-passed

**Title:** Recording transcription ignores language setting in desktop app
**Status:** Open
**Priority:** High
**Created:** 2026-03-15
**Source:** Manual description (Copilot Chat)

## Description

The desktop application starts a session and generates a recording (recording.wav), but the transcription does not produce correct results. The language field exists in the UI (ConfigPanel has a `language_input` QLineEdit) but the value is never wired through the pipeline:

1. `SessionConfig` dataclass has no `idioma_transcripcion` field
2. `ConfigPanel._on_start_session()` builds `SessionConfig` without reading `self.language_input`
3. `SessionManager._start_transcription()` creates `TranscriberWorker` without `language=`
4. `SessionManager._start_partial_transcription()` same issue
5. `ConfigManager.load_config()` / `save_config()` don't persist language
6. `_load_saved_config()` doesn't restore language into UI

This means Whisper always auto-detects the language, which often fails for short or non-English audio clips.

## Steps to Reproduce

1. Open desktop app
2. Set language to "es" in the language input field
3. Start session → record Spanish audio (e.g. "dos, tres, cuatro")
4. Stop recording → transcription runs with language=None (auto-detect)
5. Observe incorrect or garbled transcription

## Expected Behavior

The language code entered in the UI should be forwarded through `SessionConfig` → `SessionManager` → `TranscriberWorker` → `whisper.transcribe(language=...)`.

## Actual Behavior

The language input value is silently discarded. Whisper auto-detects language, often incorrectly for short clips.

## Environment

- Session: session_20260315_150807
- Config in metadata.json shows no language field
- Desktop app (PySide6), Whisper "base" model

## Additional Context

The `TranscriberWorker` already accepts a `language` parameter in its constructor and correctly passes it to `whisper.transcribe()`. The only missing piece is wiring it from UI → config → session manager → worker.

---
*Note: This bug context was created from a manual description. No external ticket system is associated.*
