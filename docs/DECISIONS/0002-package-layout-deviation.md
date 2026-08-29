# Decision 0002: Package Layout Deviation From the Master Prompt's Target Structure

## Status

Accepted.

## Context

The master prompt (`../VisionAI_Unified_Claude_Code_Codex_Master_Prompt.pdf`, Section 6) names a target
`src/visionai` layout with `audio`, `vision`, `intelligence`, `storage`, and `plugins` packages, and says to change
that direction "only through a documented decision." No such decision existed yet, even though the codebase has
grown to Phase 5-partial without ever creating those five packages. This entry closes that gap by recording the
current layout as an intentional, reviewed choice rather than an oversight for a future session to "fix" by
restructuring.

## Decision

Keep the current organic layout for now:

- **`audio`** -> not created. Voice functionality is split across `platform/microphone.py` (real device
  enumeration/capture), `orchestration/microphone_capture.py` (press/release bridge), `orchestration/wake_word.py`
  (wake-word gate), and `orchestration/event_orchestrator.py` (`InputAdapter`, `PushToTalkRunner`). There is no VAD
  or bundled STT/TTS module yet -- STT stays an injected boundary by design (Section 10), and TTS is not implemented
  at all.
- **`vision`** -> not created. Camera/gesture functionality is split across `platform/camera.py` (capture/landmark
  adapter boundary) and `recognition/gesture.py` / `recognition/capture.py` (temporal voting, capture loop). No
  normalization, calibration, or cursor module exists yet -- those are real, not-yet-built Phase 5 scope, not a
  naming gap.
- **`intelligence`** -> created (see `docs/DECISIONS/0004-llm-provider-choice.md`), the trigger this entry
  originally deferred to. `orchestration/text_planner.py` (`TextCommandPlanner`) remains the deterministic-parsing
  half of Section 12; `intelligence/provider.py`/`intelligence/anthropic_provider.py` are the first slice of the LLM
  provider half. Still no `schemas` module or structured-planner/conversation-memory code -- Phase 6 has only its
  first, conversation-only, zero-execution-authority slice done so far.
- **`storage`** -> not created. Persistence is currently three small, independent JSON stores
  (`config/user_settings.py`, `policy/permissions.py`, `observability/audit.py`'s `JsonlAuditSink`), each already
  scoped to what it owns. There is not yet enough shared storage logic to justify a common package.
- **`plugins`** -> not created, matching Section 19's own phasing: plugin manifests and permissions are explicitly
  Phase 7 (Advanced, only after approval), which has not been reached.

`config`, `core`, `policy`, `capabilities`, `platform`, `ui`, and `observability` all exist and are populated, matching
the target directly. `ui/main_window.py` is one file covering what the target lists as separate `main window, tray,
confirmation, onboarding, settings, history, diagnostics` concerns; it has not been split because nothing has yet
outgrown one reasonably sized, well-tested module (see `docs/TESTING.md`'s `MainWindow` coverage).

## Consequences

- A future session adding real continuous audio capture, a bundled STT/TTS engine, or wake-word hardware
  integration should extract an `audio` package at that point rather than continuing to grow `platform`/
  `orchestration` indefinitely -- that is the natural trigger to revisit this decision, not a fixed phase number.
- Likewise, `vision` should be extracted when real webcam/landmark work (approved next task 4 in
  `docs/PROJECT_STATE.md`) lands -- done. `intelligence` was extracted when Phase 6 started -- see
  `docs/DECISIONS/0004-llm-provider-choice.md`.
- `MainWindow` should be split into the target's per-concern UI modules if or when it grows enough that one file
  materially hurts readability or test isolation -- not preemptively.
- This decision does not authorize skipping any package permanently; it only defers creating an empty or
  near-empty package ahead of the code that would justify it, consistent with Section 4's "never rewrite solely for
  preference" and Section 20's "no premature abstraction."
