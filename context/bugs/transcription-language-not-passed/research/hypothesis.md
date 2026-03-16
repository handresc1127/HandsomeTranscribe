# Research Hypotheses: transcription-language-not-passed

**Date**: 2026-03-15
**Bug**: Recording transcription ignores language setting in desktop app

---

## Symptom Analysis

### Observable Behavior

The desktop app has a language input field (`QLineEdit`) in the ConfigPanel UI, but transcription always runs with `language=None`, causing Whisper to auto-detect the language. For short or non-English clips, auto-detection often produces garbled results.

### Trigger Conditions

The behavior occurs on every transcription session. The user enters a language code (e.g., "es") in the UI, but the value is silently discarded at multiple points in the pipeline.

### Affected Components (Suspected)

1. `SessionConfig` dataclass — missing a language field
2. `ConfigPanel._on_start_session()` — does not read the language input widget
3. `ConfigManager.load_config()` / `save_config()` — do not persist language
4. `ConfigPanel._load_saved_config()` — does not restore language into UI
5. `SessionManager._start_transcription()` — does not pass language to worker
6. `SessionManager._start_partial_transcription()` — same gap

---

## Investigation Areas

### Area 1: SessionConfig Dataclass

**Why investigate**: This is the data carrier between UI and workers. If it lacks a language field, no downstream component can receive the value.

**Search targets**:

- Files: `handsome_transcribe/ui/models.py`
- Classes: `SessionConfig`
- Fields: all dataclass fields

**Questions to answer**:

- Does `SessionConfig` have any field for language?
- Does `to_dict()` / `from_dict()` handle language?

---

### Area 2: ConfigPanel (UI Layer)

**Why investigate**: This is where the user enters the language value. If `_on_start_session` doesn't read it, the value is lost at the source.

**Search targets**:

- Files: `handsome_transcribe/ui/windows/panels.py`
- Functions: `_on_start_session`, `_load_saved_config`, `_on_reset_config`
- Widgets: `language_input`

**Questions to answer**:

- Is `language_input.text()` read when building `SessionConfig`?
- Is language restored from saved config?

---

### Area 3: ConfigManager (Persistence Layer)

**Why investigate**: If `load_config` / `save_config` don't handle language, the setting won't persist across sessions.

**Search targets**:

- Files: `handsome_transcribe/ui/config_manager.py`
- Functions: `load_config`, `save_config`

**Questions to answer**:

- Does `save_config` write a language setting to QSettings?
- Does `load_config` read a language setting from QSettings?

---

### Area 4: SessionManager (Orchestration Layer)

**Why investigate**: Even if `SessionConfig` carried language, the SessionManager must forward it to `TranscriberWorker`.

**Search targets**:

- Files: `handsome_transcribe/ui/session_manager.py`
- Functions: `_start_transcription`, `_start_partial_transcription`

**Questions to answer**:

- Is `language=` passed to `TranscriberWorker` constructor?

---

### Area 5: TranscriberWorker (Execution Layer)

**Why investigate**: To confirm the worker already supports language and the gap is purely in the upstream chain.

**Search targets**:

- Files: `handsome_transcribe/ui/workers.py`
- Functions: `TranscriberWorker.__init__`, `TranscriberWorker.run`

**Questions to answer**:

- Does the constructor accept `language`?
- Is `self.language` passed to `whisper.transcribe()`?

---

## Research Strategy

### Priority Order

1. `SessionConfig` dataclass — the core data gap
2. `ConfigPanel._on_start_session` — source of the value
3. `ConfigManager` persistence — save/load
4. `SessionManager` worker creation — forwarding
5. `TranscriberWorker` — confirm it already handles language
