# Work Log

This file records durable project checkpoints so future sessions can resume
from the documented state instead of re-inspecting the whole workspace.

## 2026-08-27 Checkpoint

- Recovered the master prompt from `../VisionAI_Unified_Claude_Code_Codex_Master_Prompt.pdf`.
- Current trusted project is `visionai/`; `../jarvis` remains untrusted reference/prototype material.
- `visionai/docs/PROJECT_STATE.md` is the main source of truth for implemented,
  tested, in-progress, and next-task status.
- Git status at checkpoint:
  staged `docs/PROJECT_STATE.md` has a one-line test-count update (`200` to
  `201` passed); unstaged work exists in `src/visionai/app.py`,
  `src/visionai/config/__init__.py`, `src/visionai/ui/main_window.py`, and
  `tests/unit/test_main_window.py`; untracked files are this log and
  `src/visionai/config/user_settings.py`.
- Current progress against the prompt: Phase 0 foundation, Phase 1 safety,
  Phase 4 initial safe capabilities, deterministic text planning, event
  orchestration, and a first Phase 2 desktop UI slice are implemented and
  documented. Current unstaged code appears to add persistent user settings,
  log-level editing, and one-time onboarding, but that slice is not recorded as
  verified here yet. Voice, gesture, live screen-reader verification, and
  release packaging remain unfinished.
- Verification attempted for the unstaged settings/onboarding slice:
  `.venv312\Scripts\python.exe -m pytest tests\unit\test_main_window.py -q`
  failed before pytest started because the venv points to missing
  `C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe`.

## Future Entry Format

- Date/time:
- User request:
- Files changed:
- Commands/tests run:
- Result:
- Next task:

## 2026-08-27 Phase 2 Settings/Onboarding Follow-up

- Date/time: 2026-08-27
- User request: continue from the recorded project progress and do the next part.
- Files changed: `src/visionai/ui/main_window.py`, `src/visionai/orchestration/event_orchestrator.py`, `tests/unit/test_main_window.py`, `tests/unit/test_dispatcher.py`, `tests/unit/test_event_orchestrator.py`, `tests/unit/test_meta.py`, `tests/unit/test_user_settings.py`, `docs/USER_GUIDE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git -C .\visionai diff --check` passed; elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_user_settings.py tests\unit\test_main_window.py -q` passed with `30 passed`; elevated `.\scripts\verify.ps1` passed with Ruff, mypy for 37 source files, `208 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: fixed the duplicate/contradictory Settings text in the user guide, added direct unit coverage for `UserSettingsStore` persistence, invalid log-level fallback, malformed JSON rejection, and `effective_log_level()` fallback, fixed the UI worker busy-state race by treating an allocated worker thread as busy until cleanup, and prevented orchestrator execution cleanup from masking unexpected handler exceptions with `EXECUTING -> IDLE` transition errors.
- Next task: continue the WCAG 2.2 AA pass with a real NVDA/Narrator screen-reader check, or begin the voice/gesture adapter slice that publishes real events into `EventOrchestrator`.

## 2026-08-27 GitHub Tracking Rule

- Date/time: 2026-08-27
- User request: push completed steps to `https://github.com/5hubhamMishra/VISIONAI` so progress is easy to track.
- Result: from this point forward, each completed verified slice should be committed and pushed to `origin/main` before moving to the next slice.

## 2026-08-27 Input Adapter Slice

- Date/time: 2026-08-27
- User request: continue to the next project step.
- Files changed: `src/visionai/orchestration/event_orchestrator.py`, `src/visionai/orchestration/__init__.py`, `src/visionai/runtime.py`, `tests/unit/test_runtime.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_runtime.py -q` passed with `10 passed`; elevated `.\scripts\verify.ps1` passed with Ruff, mypy for 37 source files, `213 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: added `InputAdapter` in the existing orchestrator module, exposed it on `Runtime`, verified already-recognized transcript text reaches the real orchestrator/planner/dispatcher path, verified already policy-approved gestures queue as typed `GestureEvent`s, and verified invalid transcript text is rejected before publishing.
- Next task: add the smallest real Phase 3 voice boundary feeding `InputAdapter.publish_transcript()`; keep raw audio out of stored events by default.

## 2026-08-27 Injectable Voice Boundary Slice

- Date/time: 2026-08-27
- User request: move on to the next part.
- Files changed: `src/visionai/orchestration/event_orchestrator.py`, `tests/unit/test_runtime.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_runtime.py -q` passed with `12 passed`; elevated `.\scripts\verify.ps1` passed with Ruff, mypy for 37 source files, `215 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: added `InputAdapter.publish_voice_capture()`, a one-shot injectable STT/push-to-talk boundary that publishes only final transcript text through the existing validated event path and stores no raw audio. Verified injected STT output reaches the real orchestrator/planner/dispatcher path and invalid output is rejected before publishing.
- Next task: add microphone device selection or a real push-to-talk runner feeding the existing injectable STT boundary; keep raw audio out of events and storage by default.

## 2026-08-27 Temporal Gesture Recognizer Slice

- Date/time: 2026-08-27
- User request: move on to the next part; asked which of the remaining approved next tasks to take on and chose the Phase 5 vision gesture capture boundary over the voice mic boundary and the accessibility screen-reader pass.
- Files changed: `src/visionai/recognition/__init__.py` (new), `src/visionai/recognition/gesture.py` (new), `src/visionai/orchestration/event_orchestrator.py`, `tests/unit/test_gesture_recognizer.py` (new), `tests/unit/test_runtime.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_gesture_recognizer.py tests\unit\test_runtime.py -q` passed with `24 passed`; elevated `.\scripts\verify.ps1`-equivalent (`ruff check .`, `mypy src`, `pytest --cov=src/visionai --cov-report=term-missing`, `bandit -q -r src`) passed with Ruff clean, mypy passing for 39 source files, `227 passed`, 93% coverage, and Bandit clean (`pip-audit` not re-run since no dependency changed).
- Result: added `visionai.recognition.gesture.TemporalGestureRecognizer`, the first "recognition services" pipeline component -- a deterministic, injected-clock temporal voting gate over raw single-frame gesture candidates requiring a sustained hold (`min_hold_ms`) at or above `min_confidence` before voting, resetting on a gesture/hand change or low-confidence/no-gesture frame, and enforcing a per-gesture cooldown (`cooldown_ms`) against repeat-firing a held pose. Wired it to the bus via `InputAdapter.publish_gesture_observation()`, mirroring how `publish_voice_capture()` wires the STT provider. Gestures still are not mapped to any capability -- `EventOrchestrator.process_event()` still only handles `TranscriptEvent`s -- satisfying approved next task 4's explicit requirement not to map gestures to actions before this voting/rejection/cooldown gate existed.
- Next task: continue Phase 5 vision with a real camera/landmark adapter feeding raw per-frame candidates into `TemporalGestureRecognizer.observe()` via `InputAdapter.publish_gesture_observation()`; or continue Phase 3 voice with microphone device selection/a real push-to-talk runner; or the still-outstanding WCAG 2.2 AA live screen-reader pass.

## 2026-08-27 Temporal Gesture Boundary Slice

- Date/time: 2026-08-27
- User request: move on to the next part.
- Files changed: `src/visionai/recognition/__init__.py`, `src/visionai/recognition/gesture.py`, `src/visionai/orchestration/event_orchestrator.py`, `tests/unit/test_gesture_recognizer.py`, `tests/unit/test_runtime.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_gesture_recognizer.py tests\unit\test_runtime.py -q` passed with `24 passed`; elevated `.\scripts\verify.ps1` passed with Ruff, mypy for 39 source files, `227 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: added `TemporalGestureRecognizer`, a deterministic temporal voting/cooldown gate over single-frame gesture candidates, and wired it through `InputAdapter.publish_gesture_observation()` so only confirmed `GestureVote`s publish `GestureEvent`s. No camera frames, landmarks, or gesture-to-action mapping are stored or routed yet.
- Next task: add a camera/landmark adapter or per-frame classifier that feeds `TemporalGestureRecognizer`; keep raw camera data out of events and storage by default.

## 2026-08-27 Push-To-Talk Runner Slice

- Date/time: 2026-08-27
- User request: next part for the project.
- Files changed: `src/visionai/orchestration/event_orchestrator.py`, `src/visionai/orchestration/__init__.py`, `src/visionai/platform/__init__.py`, `src/visionai/platform/camera.py`, `src/visionai/recognition/__init__.py`, `src/visionai/recognition/capture.py`, `tests/unit/test_camera_adapter.py`, `tests/unit/test_gesture_capture_loop.py`, `tests/unit/test_runtime.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_runtime.py -q` passed with `14 passed`; elevated `.\scripts\verify.ps1`-equivalent (`ruff check .`, `mypy src`, `pytest --cov=src/visionai --cov-report=term-missing`, `bandit -q -r src`) passed with Ruff clean, mypy for 41 source files, `233 passed`, 93% coverage, Bandit clean (`pip-audit` not re-run since no dependency changed).
- Result: added `PushToTalkRunner`, a tiny press/release control boundary around the existing injected STT path. It ignores duplicate presses, treats release-without-press as a no-op, and publishes exactly one final transcript on a valid release. Also added the camera/landmark boundary (`GestureCandidate`, `LandmarkAdapter`, `StaticLandmarkAdapter`) and `GestureCaptureLoop`, which reads one candidate, runs temporal voting, and publishes only confirmed gestures. No microphone capture, raw audio storage/routing, camera frame storage/routing, or gesture-to-action mapping was added.
- Next task: add microphone device selection, real audio capture, or a real STT provider feeding `PushToTalkRunner`; or add a real webcam/landmark implementation behind `LandmarkAdapter`. Keep raw audio/camera data out of events and storage by default.

## 2026-08-27 Real Microphone Capture Slice

- Date/time: 2026-08-27
- User request: asked which slice to pick up next among real mic capture, real webcam capture, or the WCAG screen-reader pass; chose real mic capture (Phase 3).
- Files changed: `src/visionai/platform/microphone.py` (new), `src/visionai/orchestration/microphone_capture.py` (new), `src/visionai/platform/__init__.py`, `tests/unit/test_microphone.py` (new), `tests/unit/test_microphone_capture.py` (new), `requirements/voice.txt` (new), `requirements/dev.txt`, `requirements/optional.txt`, `pyproject.toml`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_microphone.py tests\unit\test_microphone_capture.py -q` passed with `10 passed`; elevated `.\scripts\verify.ps1`-equivalent (`ruff check .`, `mypy src`, `pytest --cov=src/visionai --cov-report=term-missing`, `bandit -q -r src`, `pip_audit -r requirements/base.txt -r requirements/dev.txt`) passed with Ruff clean, mypy for 43 source files, `243 passed`, 93% coverage, Bandit clean, and pip-audit reporting no known vulnerabilities. Additionally live-verified manually (not part of the automated suite): real device enumeration found 17 real input devices, and a real 1-second capture returned real, non-zero audio samples.
- Result: added the `voice` optional dependency group (`sounddevice==0.5.6`, `numpy==2.5.2`), `visionai.platform.microphone` (real device listing, `MicrophoneCapture` with an injectable stream factory so tests never touch real hardware), and `visionai.orchestration.microphone_capture.MicrophonePushToTalk`, which starts/stops real recording on press/release and publishes exactly one final transcript through the existing `InputAdapter.publish_voice_capture()` path via an injected transcriber. No STT engine bundled -- callers still supply their own transcriber, same as before.
- Next task: plug a real STT provider into `MicrophonePushToTalk`'s `transcribe` callable; wire real device selection into a UI/CLI surface; or pick up the real webcam capture / WCAG screen-reader work instead.

## 2026-08-27 CLI Microphone Listing Slice

- Date/time: 2026-08-27
- User request: next step.
- Files changed: `src/visionai/app.py`, `tests/unit/test_app.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: elevated `.venv312\Scripts\python.exe -m pytest tests\unit\test_app.py -q` passed with `12 passed`; elevated `.\scripts\verify.ps1` passed with Ruff, mypy for 43 source files, `245 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: added `visionai --list-microphones`, which lists audio input device index/name/channel count through the existing real `list_input_devices()` boundary without building the runtime, recording audio, or dispatching any capability. Tests pin success formatting and failure reporting with an injected lister.
- Next task: plug a real STT provider into `MicrophonePushToTalk`'s `transcribe` callable, optionally expose microphone selection in the desktop settings UI, or pick up real webcam / WCAG screen-reader work.

## 2026-08-27 Desktop Microphone Selection Slice

- Date/time: 2026-08-27
- User request: next step.
- Files changed: `src/visionai/config/user_settings.py`, `src/visionai/ui/main_window.py`, `tests/unit/test_user_settings.py`, `tests/unit/test_main_window.py`, `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/TESTING.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git diff --check` passed; focused settings/UI tests passed; `scripts/verify.ps1` passed with Ruff, mypy for 43 source files, 248 pytest tests, 93% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: the desktop Settings dialog now lazily lists real input devices, persists a validated device index, and keeps the default microphone available when enumeration fails. No audio is recorded or stored by this preference slice.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, add a real webcam/landmark implementation, or complete the live screen-reader pass.

## 2026-08-27 Saved Microphone Wiring Slice

- Date/time: 2026-08-27
- User request: next part.
- Files changed: `src/visionai/platform/microphone.py`, `src/visionai/orchestration/microphone_capture.py`, `tests/unit/test_microphone.py`, `tests/unit/test_microphone_capture.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git diff --check` passed; focused microphone tests passed with 12 tests; `scripts/verify.ps1` passed with Ruff, mypy for 43 source files, 250 pytest tests, 93% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: `MicrophonePushToTalk` now defaults to a capture built from the persisted Settings microphone index, while explicit capture injection remains supported. Raw audio is still not stored or published.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, add a real webcam/landmark implementation, or complete the live screen-reader pass.

## 2026-08-27 Wake-Word Gate Slice

- Date/time: 2026-08-27
- User request: asked to change the wake word and rename the project from jarvis to visionai. The project is already named VisionAI throughout (pyproject.toml, README, GitHub repo), so nothing needed renaming there; clarified that "change the wake up command" meant adding a real, migration-gated wake-word capability, since VisionAI's voice input was push-to-talk only with no wake-word concept at all. Also found and committed a prior session's already-verified, uncommitted "Wire saved microphone choice into capture" slice before starting this one, per the repo's own commit-before-next-slice rule, and confirmed with the user that a second session was concurrently active on this same repo.
- Files changed: `src/visionai/orchestration/wake_word.py` (new), `src/visionai/orchestration/__init__.py`, `src/visionai/config/user_settings.py`, `tests/unit/test_wake_word.py` (new), `tests/unit/test_runtime.py`, `tests/unit/test_user_settings.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `.\scripts\verify.ps1` passed with Ruff, mypy for 44 source files, `267 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: added `visionai.orchestration.wake_word.WakeWordGate`, a pure deterministic text matcher (case-insensitive, whitespace-normalized, supports multi-word phrases) that strips a configured wake word from an already-transcribed utterance or rejects it (`None`) if absent or empty after stripping, and `WakeWordVoiceRunner`, which wires that gate to `InputAdapter.publish_voice_capture()` -- publishing only on a match, mirroring `publish_gesture_observation()`'s "most calls return `None`" shape. Added `UserSettingsStore.get_wake_word()`/`set_wake_word()`/`effective_wake_word()`, mirroring the existing log-level override pattern, defaulting to `"visionai"`. This is text-matching only: no real continuous microphone capture, no hotword-spotting engine, and not yet wired into `app.py` or `MainWindow` -- the same scope `PushToTalkRunner` had before `MicrophonePushToTalk` connected it to real hardware. Corrected `docs/USER_GUIDE.md`'s now-inaccurate "there is no wake word" claim. Separately, verified and corrected two stale `docs/PROJECT_STATE.md` claims about `../jarvis`: its venv is runnable (previously documented as broken), and its runaway camera-read-retry log growth was fixed and the oversized logs deleted with user approval, directly in `../jarvis` (a prototype-only bug fix, not a capability migration, so it did not go through `docs/MIGRATION_QUARANTINE.md`'s gate).
- Next task: plug a real STT provider into `MicrophonePushToTalk`, wire the wake-word gate into a real continuous-listening loop or hotword-spotting engine, add wake-word editing to the desktop Settings dialog, add a real webcam/landmark implementation, or complete the live screen-reader pass.

## 2026-08-27 Cross-Session Audit and Sync

- Date/time: 2026-08-27
- User request: since a second agent (Codex) is now also working in this repo, analyze all work done here and sync it so it operates consistently with the shared master prompt (`../VisionAI_Unified_Claude_Code_Codex_Master_Prompt.pdf`, previously recovered into this log's first checkpoint entry).
- Files changed: `docs/RELEASE_NOTES.md`, `docs/DECISIONS/0002-package-layout-deviation.md` (new), `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` (confirmed no unseen remote commits before and after this session's edits); repo-wide search for forbidden tool-metadata files (`CLAUDE.md`, `AGENTS.md`, `AGENT.md`, `CODEX.md`, `.claude/`, `.codex/`) -- none found; repo-wide case-insensitive search for "jarvis" outside `.venv312`/`.git` -- every hit is either a neutral doc discussing the quarantined `../jarvis` prototype (required by `docs/MIGRATION_QUARANTINE.md`) or a literal test string, never product branding; search for `shell=True`, `os.system(`, `os.startfile(`, `subprocess.call`, `eval(`, `exec(` in `src/` -- only a docstring describing the *old* prototype's behavior and Qt's unrelated `QDialog.exec()`/`QApplication.exec()`; search for hardcoded API-key/secret/password/token literals in `src/` -- none found; `.\scripts\verify.ps1` passed with Ruff, mypy for 44 source files, `267 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: confirmed the repository has no hard violations of the master prompt's Section 3 (repository presentation) or Section 15/23 (banned patterns, JARVIS naming) requirements, and that `docs/PROJECT_STATE.md` already carries all twelve fields Section 4 mandates. Found and fixed two real gaps: `docs/RELEASE_NOTES.md` was stale, missing roughly fifteen shipped-work entries since "Clear the local audit history" (settings/onboarding, cancellation tokens, input adapter, gesture recognizer, push-to-talk, camera/landmark boundary, real microphone capture, CLI/desktop microphone selection, saved-microphone wiring, and the wake-word gate) -- brought current. The package layout has grown to Phase 5-partial without ever creating the master prompt's Section 6 `audio`/`vision`/`intelligence`/`storage`/`plugins` packages, and no decision record justified that; added `docs/DECISIONS/0002-package-layout-deviation.md`, which maps each missing package to where its functionality currently lives, why splitting it out now would be premature, and the concrete trigger (not a phase number) for revisiting each one later. This satisfies Section 6's "changing it only through a documented decision" rule without a disruptive, purely-cosmetic reorg across ~44 source files and 267 passing tests. Mid-session, a concurrent Codex session pushed `fdd5c8c` ("Add shared agent coordination contract"), adding `docs/AGENT_COORDINATION.md` and a pointer to it from `docs/DEVELOPMENT.md` -- an explicit handoff protocol that independently converges on the same goal this audit was doing by hand. It references this session's `06e0b28` wake-word commit as the current boundary. Rebased this session's doc-only changes on top with `git merge --ff-only` (no file overlap, no conflicts) rather than committing on a stale base.
- Next task: as recorded above -- plug a real STT provider into `MicrophonePushToTalk`, wire the wake-word gate into real continuous listening, add wake-word editing to the desktop Settings dialog, add a real webcam/landmark implementation, or complete the live screen-reader pass. Whichever agent picks up next should follow `docs/AGENT_COORDINATION.md`'s handoff steps, starting with `git fetch origin main`.

## 2026-08-27 Wake-Word Settings Slice

- Date/time: 2026-08-27
- User request: move on to the next step.
- Files changed: `src/visionai/ui/main_window.py`, `tests/unit/test_main_window.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` confirmed the shared branch; focused desktop Settings tests passed with 28 tests; `scripts/verify.ps1` passed with Ruff, mypy for 44 source files, 268 pytest tests, 93% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: the desktop Settings dialog now edits and persists the normalized wake word, rejects invalid values without changing other settings, and displays the effective wake word. The wake-word gate remains text-only and is not yet a continuous listener.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, wire the wake-word gate into real continuous listening, add a real webcam/landmark implementation, or complete the live screen-reader pass.

## 2026-08-27 Local STT Provider

- User request: set up a suitable STT provider.
- Result: selected and installed `faster-whisper==1.2.1` in `.venv312`, added `FasterWhisperTranscriber` with lazy local model loading, and made it the default when `MicrophonePushToTalk` has no custom transcriber. Configuration defaults to `base.en`, CPU, and int8 through `VISIONAI_STT_MODEL_SIZE`, `VISIONAI_STT_DEVICE`, and `VISIONAI_STT_COMPUTE_TYPE`. Audio remains in-memory and only final text enters the event pipeline.
- Verification: focused STT/microphone tests passed; `faster-whisper` imported successfully; the configured `base.en` model downloaded and loaded on CPU with int8; full verification passed with 281 tests, 92% coverage, Ruff, mypy for 46 source files, Bandit, and pip-audit reporting no known vulnerabilities.
- Next task: download the configured model on first use and live-test one microphone transcription, then connect the resulting transcript to wake-word continuous listening.

## 2026-08-27 Wake-Word CLI Surface

- Date/time: 2026-08-27
- User request: move on to the next step.
- Files changed: `src/visionai/app.py`, `tests/unit/test_app.py`, `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, `docs/TESTING.md`, `docs/PROJECT_STATE.md`, `docs/RELEASE_NOTES.md`, `docs/WORK_LOG.md`.
- Commands/tests run: focused CLI tests passed with 14 tests; full verification passed with Ruff, mypy for 44 source files, 271 pytest tests, 93% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: added `visionai --wake-word-text`, applying the saved wake word and routing matching already-transcribed text through the existing wake runner, event orchestrator, and policy/dispatcher path. Non-matches publish nothing and launch nothing. No STT or raw-audio path was added.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, connect it to the listening loop or a hotword engine, add real webcam/landmark capture, or complete the live screen-reader pass.

## 2026-08-27 Injectable Wake-Word Listening Loop

- Date/time: 2026-08-27
- User request: move on to the next step.
- Files changed: `src/visionai/orchestration/wake_word.py`, `src/visionai/orchestration/__init__.py`, `tests/unit/test_wake_word.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git status` confirmed the shared tree was clean before editing; focused wake-word tests passed with 11 tests; `scripts/verify.ps1` passed with Ruff, mypy for 44 source files, 269 pytest tests, 93% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: added `WakeWordListeningLoop`, which consumes an injected async stream of final transcripts, routes only wake-word matches through `WakeWordVoiceRunner`, counts accepted commands, and stops on `CancellationToken`. No STT dependency, microphone stream, raw-audio retention, or hotword engine was added.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, connect it to this loop or a hotword engine, add real webcam/landmark capture, or complete the live screen-reader pass.

## 2026-08-27 Wake-Word Settings Slice

- Date/time: 2026-08-27
- User request: move on to the next step.
- Files changed: `src/visionai/ui/main_window.py`, `tests/unit/test_main_window.py`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` confirmed the shared branch; `.\scripts\verify.ps1` passed with Ruff, mypy for 44 source files, `268 passed`, 93% coverage, Bandit passed, and `pip-audit` reporting no known vulnerabilities.
- Result: the desktop Settings dialog now edits and persists the normalized wake word, rejects invalid values without changing other settings, and displays the effective wake word. The wake-word gate remains text-only and is not yet a continuous listener.
- Next task: plug a real STT provider into `MicrophonePushToTalk`, wire the wake-word gate into real continuous listening, add a real webcam/landmark implementation, or complete the live screen-reader pass.

## 2026-08-27 Real Webcam/Landmark Boundary

- Date/time: 2026-08-27
- User request: move on to the next part of the project. Picked Phase 5 vision specifically to avoid overlapping a concurrent Codex session actively working on Phase 3's real-STT slice (`src/visionai/platform/stt.py`) in the same working tree at the same time -- confirmed via `docs/AGENT_COORDINATION.md`'s ownership split (vision/recognition work is this agent's lane) and by observing the file appear mid-session.
- Files changed: `src/visionai/platform/webcam.py` (new), `src/visionai/platform/__init__.py`, `tests/unit/test_webcam.py` (new), `requirements/vision.txt` (new), `requirements/optional.txt`, `pyproject.toml`, `docs/DECISIONS/0003-accepted-protobuf-cve.md` (new), `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` confirmed the shared branch; live-installed and compared `mediapipe` 1.0.1, 0.10.35, and 0.10.14 in `.venv312` to find one still shipping the legacy `solutions.hands` API on cp312/Windows (only 0.10.14 does); live-verified a real webcam frame opens via OpenCV and the real mediapipe `Hands` model runs end to end with no crash; `pytest tests/unit/test_webcam.py -q` (8 passed); `ruff check .` (whole repo, passed); `mypy` scoped to this slice's two files (passed; a full `mypy src` currently fails only on the concurrent session's in-progress `stt.py`, untouched here); full `pytest --cov=src/visionai --cov-report=term-missing` (281 passed, 92% coverage); `bandit -r src` (no issues); a full-environment `pip_audit --desc` surfaced one transitive CVE, addressed below rather than silently ignored.
- Result: added the first real `LandmarkAdapter`, `visionai.platform.webcam.WebcamLandmarkAdapter`, which reads one OpenCV frame and classifies it via mediapipe's offline `solutions.hands` API into `open_palm`/`closed_fist`/no-gesture using a pure, independently fixture-tested `classify_finger_count()` function decoupled from mediapipe's own landmark type. Both frame capture and classification are injectable, mirroring `MicrophoneCapture`'s pattern, so the automated suite needs neither a real camera nor the `vision` extra installed. Found mediapipe 0.10.14 -- the only Windows/cp312 wheel still offering the offline hand-landmark API without a downloaded model file -- hard-requires `protobuf<5`, and every 4.x protobuf release (including the latest patch) carries an unpatched DoS CVE with no fix in that range; asked the user how to handle it rather than deciding alone, since it would be the project's first non-clean `pip-audit` result. User chose to accept it with a documented decision record: `docs/DECISIONS/0003-accepted-protobuf-cve.md` explains the vulnerable code path (`google.protobuf.json_format.ParseDict()`) is never called anywhere in this codebase. Not yet wired into a CLI/desktop surface, a continuous capture loop, or gesture-to-capability mapping; only a no-crash pipeline check was live-verified, not classification of an actual hand gesture (needs a human holding a hand in frame).
- Next task: wire `WebcamLandmarkAdapter` into `GestureCaptureLoop` behind a CLI/desktop surface or continuous capture loop (mirroring voice's `--wake-word-text` precedent), live-verify real gesture classification with a human in frame, map a confirmed gesture to a capability request, or (separately) whatever the concurrent session's real-STT slice leaves as its own next task once it lands.

## 2026-08-27 Gesture Capture CLI and Live Verification

- Date/time: 2026-08-27
- User request: next step -- closing the previous slice's explicitly unverified gap (real gesture classification with an actual human hand in frame).
- Files changed: `src/visionai/app.py`, `tests/unit/test_app.py`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` (initially blocked by a transient network outage reaching github.com, retried before push); `ruff check .` and `mypy src` (whole repo, both clean -- the concurrent session's `stt.py` mypy issue from the prior slice is resolved); `pytest --cov=src/visionai --cov-report=term-missing` (283 passed, 92% coverage); `bandit -q -r src` (no issues); `pip_audit` for `requirements/base.txt`/`requirements/dev.txt` blocked by the same network outage at commit time, retried before push. Live-verified the real `visionai --gesture-frames N` CLI three times against the actual webcam and mediapipe model, with the user's consent and cooperation: a 150-frame run with no hand deliberately in position correctly reported `"No gesture detected."` (proving no false positive); a follow-up attempt with the hand raised also reported nothing, so a small debug script was written to print per-frame mediapipe detection state, and (with the user's explicit consent) one real frame was saved locally and viewed directly to diagnose it -- it showed the hand was simply outside the webcam's field of view, not a classifier bug; the debug snapshot was deleted immediately after viewing. Once the user repositioned closer and centered, the debug script confirmed ten consecutive real frames all classified as `open_palm` (0.89-0.99 confidence), and the real shipped CLI command then reported `Gesture detected: open_palm (left hand, held 406ms, confidence 0.99).`
- Result: added `visionai --gesture-frames N`, which builds a real `WebcamLandmarkAdapter` and `TemporalGestureRecognizer` (both injectable, mirroring `--wake-word-text`'s testability pattern) wired through the existing `GestureCaptureLoop`, reads up to N real frames, and reports the first confirmed gesture or `"No gesture detected."` -- observation only, since gestures still are not mapped to any capability. Closes the explicit "not yet verified" gap the previous slice left open: real gesture classification with an actual human hand is now confirmed working end to end through the real, shipped command. Also discovered mediapipe's CPU inference takes roughly 2 seconds per frame on the verified machine, far slower than the sub-100ms typically expected -- recorded as a known characteristic in `docs/PROJECT_STATE.md`'s Known Defects, not yet investigated further, and callers should pass a small frame count until it is.
- Next task: investigate the ~2s/frame mediapipe CPU inference latency (XNNPACK engagement, capture resolution, or inherent CPU-only cost), wire a continuous background gesture-capture loop rather than a fixed frame budget (mirroring `WakeWordListeningLoop`), add a desktop surface for gesture capture, or eventually map a confirmed gesture to a capability request.

## 2026-08-29 Latency Investigation and Continuous Gesture Loop

- Date/time: 2026-08-29
- User request: next step -- picked up the previous slice's own recorded next tasks.
- Files changed: `src/visionai/recognition/capture.py`, `src/visionai/recognition/__init__.py`, `tests/unit/test_gesture_capture_loop.py`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` (no new commits since the last push); before building anything, timed the real camera read and mediapipe `hands.process()` separately in isolation (10 frames: ~14ms average read, ~66ms average process) and timed the real `visionai --gesture-frames 20` CLI end to end (6.24s total including process startup and model load) -- both showed normal per-frame latency with no 2-second cost anywhere, so the earlier reading was very likely a system-load artifact of that specific run (several concurrent background installs/processes at the time), not a real characteristic; `pytest tests/unit/test_gesture_capture_loop.py -q` (4 passed); `.\scripts\verify.ps1` passed with Ruff, mypy for 46 source files, 285 pytest passed at 92% coverage, Bandit, and pip-audit reporting no known vulnerabilities.
- Result: investigated and ruled out the ~2s/frame latency claim the previous slice recorded as a known defect, removing that now-incorrect claim from `docs/PROJECT_STATE.md` rather than leaving a stale, misleading performance note. Added `visionai.recognition.GestureListeningLoop`, mirroring `WakeWordListeningLoop`'s cancellable-consumption shape: it drives an existing `GestureCaptureLoop` continuously until a `CancellationToken` is cancelled, counting confirmed gestures. Deliberately deviates from the mirror in one place -- `cancellation` is a required argument, not optional -- since a real (or fake/static) `LandmarkAdapter` is pulled on demand and has no natural "stream exhausted" end the way an injected async transcript source does, so an optional-cancellation version could spin forever with no way to stop it. Verified with an injected wrapper that cancels a token once a fixed read count is reached, with no artificial iteration cap in the loop itself: two gestures held in sequence are both confirmed and counted, and an already-cancelled token stops the loop before it reads anything. Like `WakeWordListeningLoop` before it, this ships as a tested class only -- not yet wired into a CLI or desktop entry point.
- Next task: wire `GestureListeningLoop` into a CLI or desktop entry point (the same stage `WakeWordListeningLoop` was at before `--wake-word-text` connected the one-shot voice path), continue the WCAG 2.2 AA screen-reader pass, or eventually map a confirmed gesture to a capability request.

## 2026-08-29 Gesture-Listen CLI and Gesture-to-Capability Mapping

- Date/time: 2026-08-29
- User request: next step -- picked up the previous slice's own recorded next task (wire `GestureListeningLoop` into a CLI entry point).
- Files changed: `src/visionai/app.py`, `src/visionai/recognition/capture.py`, `src/visionai/orchestration/event_orchestrator.py`, `src/visionai/platform/webcam.py`, `src/visionai/capabilities/meta.py`, `tests/unit/test_app.py`, `tests/unit/test_webcam.py`, `tests/unit/test_event_orchestrator.py`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` (no new commits); `ruff check .` and `mypy src` (whole repo, clean); `pytest --cov=src/visionai --cov-report=term-missing` (290 passed, 92% coverage); `bandit -q -r src` (no issues); `pip_audit` for `requirements/base.txt`/`requirements/dev.txt` (no known vulnerabilities). Live-verified the real camera/mediapipe pipeline is functioning on this machine with two standalone debug scripts run outside the shipped CLI: one confirmed `cv2.VideoCapture` opens and mediapipe detects a real hand in 3 of 40 slow-paced frames; a second, using the actual production `WebcamLandmarkAdapter`, ran at a healthy ~13 fps in one attempt. Ran the real, shipped `visionai --gesture-listen` command live four times with the user holding real gestures and pressing `Ctrl+C`; all four correctly started, printed the listening prompt, stayed responsive to interrupt, and shut down cleanly (proving the CLI/threading/cancellation wiring works end to end), but reported zero confirmed gestures each time. A follow-up debug run isolated the cause: camera+mediapipe throughput had dropped to ~0.9 fps (vs. the healthy ~13 fps run minutes earlier) with heavy concurrent system load at the time (multiple VS Code windows, a loaded Brave browser, ProtonVPN, and other background processes all consuming significant CPU, confirmed via `Get-Process`) -- no other process held the camera device itself, ruling out device contention specifically. This matches a pattern already recorded in this project's own history (the earlier, later-debunked "~2s/frame" latency reading was also a system-load artifact). The user chose to commit based on automated verification plus this machine's earlier-documented real-hardware confirmation, rather than keep retrying live capture under load.
- Result: added `visionai --gesture-listen`, running `GestureListeningLoop` on a worker thread (mirroring the desktop Stop button's off-GUI-thread pattern) so a `Ctrl+C` on the main thread calls `cancellation.cancel()` and waits for a clean stop -- an unhandled interrupt straight through `asyncio.run()` would abort mid-frame, skipping `close()` and losing the confirmed count. While this slice was in progress and uncommitted in the shared working tree, a concurrent Codex session (confirmed running via `Get-CimInstance Win32_Process`, the VS Code ChatGPT extension, active since 2026-08-28) picked up the same file and extended it further: `classify_finger_count()` grew from two gestures to six (`open_palm`, `closed_fist`, `thumbs_up`, `peace_sign`, `index_finger_up`, `two_fingers`), and `EventOrchestrator.process_event()` gained a `_GESTURE_COMMANDS` map that turns four of those six into a synthesized `TranscriptEvent`, routed through the same planner/policy/dispatcher path as any typed command -- closing the "map a confirmed gesture to a capability request" gap this project's docs had flagged as outstanding since Phase 5 began. `closed_fist` is deliberately left unmapped, reserved for a future voice-mode trigger; a dedicated test proves it publishes nothing. `GestureListeningLoop` gained an optional `stop_gesture_id`, and `--gesture-listen` sets it to `"open_palm"` so the loop can stop itself with no `Ctrl+C` needed. This was an unplanned, uncoordinated concurrent edit on the same file (a real instance of the exact risk `docs/AGENT_COORDINATION.md` warns about) that converged cleanly rather than colliding destructively -- both agents' work was verified together as one coherent, fully-tested slice before this commit, and `webcam.py`/`capture.py`/`event_orchestrator.py`/`meta.py` were left untouched by this session once Codex's edit was detected, per the "Codex owns runtime integration" ownership split.
- Next task: retry live confirmation of the full real-camera-to-real-dispatch path (hold a real thumbs-up, watch Notepad actually open through `--gesture-listen`) once the test machine is under normal load rather than the heavy concurrent load seen this session; add a gesture surface to `visionai-ui` (the desktop window currently has none); or continue the outstanding WCAG 2.2 AA live screen-reader pass.

## 2026-08-29 Gesture-Listen Live Confirmation Follow-Up

- Date/time: 2026-08-29
- User request: re-ran `visionai --gesture-listen` on their own after the previous slice's live attempts were blocked by system load.
- Files changed: `src/visionai/app.py`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `pytest -q` (290 passed) after a small concurrent Codex addition landed in `_run_gesture_listen` mid-session (again the same collision pattern as the previous slice, again converging cleanly).
- Result: the user ran the real, shipped `visionai --gesture-listen` command themselves and it printed `Stopped. Confirmed 7 gesture(s).` against real held gestures -- confirming the camera/mediapipe pipeline and the CLI/threading/cancellation wiring all work live now that the earlier heavy system load has eased, closing the live-verification gap the previous slice left open. Separately, `--gesture-listen` now drains and prints any `ActionResult` messages from the output bus once the session ends, so a future live run shows the dispatched action's outcome directly (e.g. `Opening notepad.`) instead of needing a separate check.
- Next task: add a gesture surface to `visionai-ui` (the desktop window currently has none); continue the outstanding WCAG 2.2 AA live screen-reader pass; or wire a continuous, real-microphone wake-word listening CLI (`visionai --wake-word-listen` or similar), mirroring `--gesture-listen`'s precedent -- `WakeWordListeningLoop` and the default faster-whisper STT provider both already exist but are not yet connected to a CLI/desktop entry point.

## 2026-08-29 Wake-Word-Listen CLI and Gesture-Triggered Voice Capture

- Date/time: 2026-08-29
- User request: next step -- picked up the previous slice's own recorded next task (a continuous, real-microphone wake-word listening CLI, mirroring `--gesture-listen`'s precedent).
- Files changed: `src/visionai/app.py`, `src/visionai/recognition/capture.py`, `tests/unit/test_app.py`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md`, `docs/WORK_LOG.md`.
- Commands/tests run: `git fetch origin main` (no new commits); `ruff check .` and `mypy src` (whole repo, clean); `pytest --cov=src/visionai --cov-report=term-missing` (295 passed, 92% coverage); `bandit -q -r src` (no issues); `pip_audit` for `requirements/base.txt`/`requirements/dev.txt` (no known vulnerabilities).
- Result: added `visionai --wake-word-listen`, wiring the existing `WakeWordListeningLoop` into a real continuous CLI surface for the first time via `_continuous_transcripts()` (repeated fixed-length record/transcribe chunks through the real microphone and default `faster-whisper` provider -- no VAD or streaming STT, the smallest real slice) and `_run_wake_word_listen()` (worker-thread pattern mirroring `_run_gesture_listen`, so `Ctrl+C` cancels cleanly and dispatched action results print once the session ends). While this was in progress, the same concurrent-Codex-collision pattern recorded in the previous two slices happened a third time on this same file: Codex added an `on_confirmed` callback to `GestureListeningLoop` and used it in `_run_gesture_listen` to give `closed_fist` a real job -- starting genuine push-to-talk voice capture via `MicrophonePushToTalk` (reusing this slice's new `_build_microphone_capture()`/`_build_transcriber()` factories directly) -- with `open_palm` releasing and sending it. This closed a real, previously-undocumented counting error this session's own earlier commit (`ee8082a`) had introduced: its docs claimed "four of six" gestures were mapped to commands when `_GESTURE_COMMANDS` actually maps five (`open_palm`, `thumbs_up`, `peace_sign`, `index_finger_up`, `two_fingers`); `closed_fist` was the only one ever unmapped, and it now has a real, different job instead of staying reserved. Corrected that miscount across `PROJECT_STATE.md`/`ARCHITECTURE.md`/`RELEASE_NOTES.md` (left as-is in already-pushed `WORK_LOG.md` entries, which are a historical record, not a living doc). Codex's addition initially left one trivial ruff import-sort error mid-edit, which resolved on its own (or was fixed by Codex) within about two minutes -- this session waited rather than editing the same file concurrently, per the established pattern from the previous two collisions. Also wrote the two tests Codex's addition had not covered yet: gesture-triggered voice capture happy path (`closed_fist` starts capture, `open_palm` sends it, the transcribed command actually dispatches and launches Notepad) and the microphone-unavailable error path (`OSError` caught and reported as `"Voice input unavailable: ..."` rather than crashing). A fourth, small concurrent Codex edit landed near the end of this session (`text_planner.py`/`test_text_planner.py`): a `TextCommandPlanner` app-name alias mapping the common STT misrecognition `"notebook"` to `"notepad"`, with its own regression test -- almost certainly found by Codex live-testing the real voice path.
- Next task: add a gesture and/or voice surface to `visionai-ui` (the desktop window currently has none for either); continue the outstanding WCAG 2.2 AA live screen-reader pass; live-verify the real `--wake-word-listen` and gesture-triggered voice paths with the user's actual microphone and voice (only unit-tested with fakes so far); or consider whether `--wake-word-listen` and gesture-triggered voice capture should eventually be unified into one continuous "listen for everything" mode rather than two separate CLI entry points.
