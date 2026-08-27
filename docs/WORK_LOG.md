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
