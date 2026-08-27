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
