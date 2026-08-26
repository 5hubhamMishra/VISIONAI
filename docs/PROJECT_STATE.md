# Project State

## Current Phase

Phase 1 safety foundation locally verified; Phase 4 capability migration
complete for all four of Section 13's initial safe capabilities; Phase 2
desktop UI started (user decision) with a first minimal main-window slice.

## Last Verified Commit

Current `main` HEAD, pushed to https://github.com/5hubhamMishra/VISIONAI. Hosted CI ("VisionAI CI") has passed on every commit pushed so far -- see https://github.com/5hubhamMishra/VISIONAI/actions.

## Environment Verified

- Workspace inspected on Windows path: `C:\Users\shubh\OneDrive\Desktop\DESKTOP\projects\demo`
- Existing project classified as previous JARVIS prototype in `../jarvis`
- Python 3.12.10 installed and available in elevated shell sessions
- Python runtime in `../jarvis/venv` is broken because it points to a missing base interpreter
- Python runtime in `.venv` remains partially locked/broken
- Working local development environment created at `.venv312`
- Git initialized in `visionai/` on branch `main`

## Implemented and Tested

- Phase 0 package skeleton under `visionai/`
- Environment-backed settings loader
- Typed core event contracts with validation for text, confidence ranges, and immutable mappings
- Explicit assistant state machine with approved transitions
- Bounded asynchronous event bus with close semantics
- Structured logging setup with basic secret redaction
- Unit tests for event validation, state transitions, event bus behavior, and redaction
- Safe console entry point that reports Phase 0 status without enabling capabilities
- Phase 1 capability manifest schema and in-memory registry
- Phase 1 deterministic policy engine for registration, platform, permission, confirmation, locked-screen, and argument checks
- Phase 1 confirmation service with exact request binding, expiry, and single-use validation
- Phase 1 fixed-window capability rate limiter
- Phase 1 URL policy helper for HTTPS scheme checks, allowlisted hosts, private/local host blocking, credential rejection, control-character rejection, and safe search query encoding
- Phase 1 serialized dispatcher that runs policy before handlers, executes one handler at a time, and writes audit events
- Phase 1 in-memory audit sink for tests and early UI integration
- Phase 1 JSON permission store with atomic file replacement and malformed-store rejection
- Phase 1 JSON Lines audit sink with malformed-log rejection
- Phase 1 lock-state adapter boundary with conservative static fallback
- Phase 1 Windows lock-state adapter wrapper that checks whether the interactive desktop is reachable (`OpenInputDesktop`) and treats API failures or an unreachable desktop as locked
- CI workflow and local verification scripts for formatting, typing, tests, security scan, and dependency audit
- Migration quarantine documentation for the previous prototype
- Environment repair documentation for Python 3.12 and virtual environment recreation
- Phase 4 read-only system info capabilities (`system.time`, `system.date`, `system.battery`, `system.health`) with manifests and handlers
- Runtime assembly (`visionai.runtime.build_runtime`) wiring the registry, policy engine, rate limiter, audit sink, and dispatcher together
- Console entry point (`visionai.app.main`) that dispatches a read-only capability through the full policy + dispatcher path
- Battery and CPU/memory probes backed by `psutil`, injectable for testing, with a graceful "no battery detected" fallback on desktops/VMs without one
- Fixed a fail-open gap in `UrlPolicy`: an empty `allowed_hosts` previously allowed any public hostname through; it now denies by default, matching its documented behavior
- Fixed a critical gap in `WindowsLockStateAdapter`: it previously checked `ProcessIdToSessionId` on the current process, which cannot detect lock state at all (a process keeps its session whether the workstation is locked or not) and would have reported "unlocked" almost always, defeating locked-screen mutation blocking entirely. It now checks whether the input desktop can be opened, which correctly fails while the workstation is locked or a secure desktop (e.g. a UAC prompt) is active. Verified against the live unlocked session (no crash, correct result) and against mocked locked/failure branches; the true locked-state path still needs a human to lock the screen and confirm (see Known Defects).
- Fixed an audit-integrity gap in `SerializedDispatcher`: denied requests were audited using the caller-supplied `request.risk_level` instead of the registered capability's actual `manifest.risk_level`, so a request could understate its true severity in the audit log for denied attempts. Denials are now audited with the manifest's risk level, matching the already-correct behavior for successful executions.
- Fixed a thread-safety gap in `FixedWindowRateLimiter`: its per-key window state was mutated with no lock, unlike every other shared-mutable-state class in this codebase (`InMemoryAuditSink`, `JsonlAuditSink`). `SerializedDispatcher` only serializes handler execution, not policy evaluation, so once multiple recognition threads (voice, gesture) dispatch concurrently this had a real TOCTOU race that could let the limit be exceeded. Added a lock and a concurrency regression test (100 threads racing via a barrier) that verifies the limit holds exactly.
- Fixed a deadlock in `EventBus.close()`: it signalled closure by pushing a `None` sentinel onto the same bounded queue via `put_nowait`, silently dropped (`suppress(QueueFull)`) if the queue was already at capacity -- leaving any consumer blocked in `next_event()` waiting forever, since `publish()` now rejects new events but no close signal ever reached the queue. Reproduced the exact hang (2s timeout, confirmed) before fixing. The close signal now travels over a separate `asyncio.Event`, which can never be lost regardless of queue fullness; `next_event()`/`subscribe()` still drain any already-queued events before raising `EventBusClosed`.
- Fixed a thread-safety gap in `StateMachine` itself: `transition()`/`cancel()`/`on_transition()` had no lock, so concurrent callers (voice thread, gesture thread) could all observe the same starting state and all succeed, corrupting `history`'s from/to invariant -- exactly the uncontrolled shared-state problem this class exists to replace. Reproduced deterministically (50 threads racing via a barrier with `sys.setswitchinterval` tightened; 4/5 trials showed multiple simultaneous "successful" transitions to the same target before the fix, 0/10 after). Listeners are still notified outside the lock so a callback cannot deadlock or block other threads.
- Fixed the log redaction control (Section 15 "log redaction"): it did not work at all as wired. `RedactionFilter` was attached to the *root* logger via `Logger.addFilter`, but a filter on a logger only gates that logger's own calls -- it is never consulted for records from named child loggers (the only kind `get_logger()` returns) reaching the same handlers by propagating up the hierarchy, so redaction silently never ran for any real application logger. Separately, even when attached correctly, redacting `record.msg` and `record.args` independently before %-substitution could leave a placeholder in `msg` with no matching arg (e.g. a secret passed the idiomatic way, `logger.info("api_key=%s", key)`, has no "key=" prefix in `args` alone to match against), which either failed to redact the secret or crashed message rendering with `TypeError: not all arguments converted during string formatting`. Verified both failure modes live before fixing. Fix: attach the filter to each handler instead of the root logger, and redact the fully substituted message (`record.getMessage()`) rather than msg/args separately, then clear `args` so no further substitution is attempted.
- Migrated the first `../jarvis` prototype behavior into the trusted runtime, per the user's decision and `docs/MIGRATION_QUARANTINE.md`'s required steps: `app.open`, a Risk 1 (Reversible) capability that opens one allowlisted desktop application (`notepad`, `calculator`, `paint`) by its exact executable name with `shell=False`. Deliberately excludes anything from the old prototype's broader app list that is itself a general-purpose command surface (`cmd`, `powershell`, Task Manager), since those would reintroduce the arbitrary-execution risk this capability exists to avoid. Verified live end to end through the actual CLI and dispatcher: the denial path (`cmd` rejected) and the real launch path (Notepad actually opened as a live process, confirmed via `Get-Process`, then closed).
- Migrated browser/search behavior into the trusted runtime as reversible capabilities: `browser.open` opens one fixed allowlisted site, and `browser.search` opens an encoded Google search URL. Both validate through `UrlPolicy` before the opener is called, both are injectable for tests, and neither accepts arbitrary URLs.
- Migrated media behavior into the trusted runtime as `media.control`, a Risk 1 (Reversible) capability that accepts only fixed media actions (`play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`) and maps them to allowlisted media keys through an injectable key presser. Its real `default_key_presser` calls `pyautogui`, so `pyautogui` is declared in `requirements/base.txt` and `pyproject.toml`; automated verification injects a fake key presser and does not send live keyboard input.
- Added Section 13 initial safe meta capabilities: `system.capabilities` lists every registered capability by ID and description, and `system.help` summarizes current functionality and the registered count.
- Added the remaining Section 13 stop command as `system.stop`, backed by `OperationController`. It requests cooperative cancellation of the currently tracked operation, reports when nothing is active, and does not kill threads or processes directly.
- Locally quarantined the old `../jarvis` prototype execution path in this workspace: app parsing now rejects injection-shaped text instead of partially matching it, unknown app/site names no longer fall back to raw spoken text, app launch uses `subprocess.Popen([cmd], shell=False)`, command-surface apps are blocked, web opens are host/scheme allowlisted, search query encoding uses `quote_plus`, mutating system commands are hard-blocked, and touched debug prints are ASCII-safe on the Windows console. These source edits are outside the `visionai/` Git repository and therefore are not pushed to `5hubhamMishra/VISIONAI`; this document records the local hardening step.
- Added `visionai.orchestration.TextCommandPlanner` (Section 12's deterministic parser, text-only -- no voice, no LLM) and wired it into the CLI as `visionai --text "<command>"`. Matches a small set of reviewed phrases and allowlisted slot values (app names, site names, media actions) into a typed `Intent` + `ActionPlan`; anything else becomes non-executable conversation data. The planner is explicitly not the security boundary -- any `ActionRequest` it emits still passes through the same policy engine and dispatcher as a directly-invoked capability. Found and fixed a real bug via test execution (not just review): `_empty_plan()` passed the raw, unsanitized original text straight into `Intent`'s `SafeText` fields, so any input correctly rejected as non-executable but still containing a control character (e.g. `"open notepad\x00"`, or a search query with an embedded NUL byte) crashed the planner outright with a pydantic `ValidationError` instead of returning the intended graceful non-executable response. The rejection decision itself was already correct and made against the raw text; only the informational `Intent` object needed sanitizing, since it carries no executable authority. Added a second regression test for the app-name case beyond the one that first caught it.
- Added `visionai.orchestration.EventOrchestrator`, wiring a bounded input `EventBus`, `TextCommandPlanner`, `SerializedDispatcher`, `OperationController`, and the real `StateMachine` into one event-driven pipeline. A typed text command is framed as an instant, already-final `TranscriptEvent` and walked through the *unmodified* transition graph (IDLE -> LISTENING -> TRANSCRIBING -> INTERPRETING, one step at a time) rather than adding a new IDLE -> INTERPRETING edge -- this also means the same code path will handle real voice transcripts later with no changes. Catches `VisionAIError` specifically (never a broad `except Exception`), publishes an `ErrorEvent` instead of propagating, and always returns to IDLE in a `finally` block regardless of outcome. `system.stop` is deliberately excluded from starting its own tracked operation, avoiding a self-referential "stop cancels itself" case.
- Started Phase 2 (desktop UI) per the user's decision: `visionai.ui.main_window.MainWindow`, a minimal PySide6 window (command input, run button, Stop button, result display, audit-backed history, and tray icon) that adds no planning or execution logic of its own -- every typed command becomes a `TranscriptEvent` handed to the same `EventOrchestrator` the CLI uses. Verified PySide6 6.11.2 (latest, LGPL, actively maintained, Python 3.12/Windows supported) actually imports and constructs widgets on this machine before adopting it. Tested headless with `pytest-qt` and Qt's offscreen platform plugin; `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` automatically so this works in CI (a headless Windows runner) with no code changes to the CI workflow itself. This is the first slice only -- no settings, onboarding, diagnostics, or full accessibility audit yet; do not describe Phase 2 as complete.
- Added a Stop button to `MainWindow` toward Phase 2's "cancellation" exit criterion (Section 19). It requests cancellation the same way `visionai --text "stop"` does and is deliberately never disabled by the Run flow, so it stays reachable even while the command input/Run button are disabled during processing -- closing a real gap where cancellation was previously only reachable through the same input Run disables. It cannot yet interrupt anything mid-flight (`run_current_command` and `stop_current_operation` both call `asyncio.run()` synchronously on the GUI thread, and every registered capability is fast and synchronous), so clicking it before any long-running operation exists just reports that nothing is running -- see `docs/SECURITY.md` for why this is an honest limitation rather than a bug.
- Ran a first, partial accessibility pass on `MainWindow` toward Section 14's WCAG 2.2 AA target (approved next task 2) -- partial, not a full audit; see the honest scope note below. Found and fixed a real bug via test execution: the window set no initial focus at all on show (`focusWidget()` was `None`, confirmed with a failing test before the fix), so a keyboard-only user had no visible starting point. Fixed with `self._command_input.setFocus()`. Verified, with passing tests in both directions, that Tab and Shift+Tab cycle through every interactive control (command input, Run, Stop, result, history) with no keyboard trap -- disproving an initial suspicion that the read-only result `QTextEdit` might swallow Tab, which the test showed does not happen in this Qt version/configuration, so no speculative fix was added for it. Associated the "Result" and "History" labels with their widgets via `QLabel.setBuddy()`, matching the existing "Command" label pattern, so assistive technology can announce them. **Not verified**: actual contrast ratios and OS-level scaling (no custom colors or fonts are set, so these currently inherit the OS theme's values, but that inheritance itself has not been measured), real screen-reader software (only `setAccessibleName`/buddy wiring, not a live NVDA/Narrator pass), and remappable shortcuts (not applicable yet -- no gestures exist). Do not describe the WCAG 2.2 AA pass as complete.
- Added a system tray icon to `MainWindow`, the next component in Section 6's UI package order after the main window itself (approved next task 1, first slice). A Show/Quit context menu and click-to-toggle visibility, wired to plain window-lifecycle calls (`show`/`hide`/`raise_`/`activateWindow`/`QApplication.quit`) with no path into the runtime, orchestrator, or dispatcher -- see `docs/SECURITY.md`. Closing the window minimizes to tray only when `QSystemTrayIcon.isSystemTrayAvailable()` is true, and closes normally otherwise, so the window can never become unreachable on a system without a tray. Uses a standard Qt style icon as a placeholder (no branded VisionAI icon asset exists yet; real branding is Phase 8 release work). `isSystemTrayAvailable()` is always `False` under the offscreen platform the automated test suite runs under, so the headless tests exercise the real no-tray fallback path directly and use a monkeypatch only to exercise the tray-available path; the tray-available behavior was additionally live-verified on the real Windows desktop (tray actually available, icon actually visible, close-to-tray actually works) before documenting it.
- Added early confirmation-dialog plumbing for the next Phase 2 slice: `Runtime` now owns an injectable `ConfirmationService`, and `SerializedDispatcher.evaluate()` can perform a non-executing policy preflight for UI/orchestrator callers that need to know whether a confirmation prompt is required. Fixed the important safety detail before committing it: this preflight does not consume rate-limit quota, and `dispatch()` still re-evaluates policy before handler execution, so a stale or buggy preflight cannot authorize anything.

## Implemented but Not Fully Verified

- The latest confirmation-precheck slice has focused tests passing, but the full `scripts\verify.ps1` suite has not been rerun after that slice because the elevated full-suite run hit the platform usage-limit gate. The previous full-suite result is recorded below.

## In Progress

- Incremental migration from the previous JARVIS prototype: `app.open`, `browser.open`, `browser.search`, and `media.control` migrated; voice, gesture, and LLM behaviors remain unmigrated and untrusted.
- Deterministic text planning (`TextCommandPlanner`) now covers typed-text commands for every registered capability; voice/gesture input still has no adapter to feed it.
- Phase 2 desktop UI: a minimal main window exists and is tested, now with a Stop control, verified keyboard tab-order/focus behavior, and a tray icon; settings, onboarding, diagnostics, confirmation UI, contrast/scaling/screen-reader verification, and a real cancellation-capable (non-blocking) execution model are not built yet.

## Approved Next Tasks

1. Continue Phase 2: a tray icon now exists (Show/Quit, minimize-to-tray-when-available); settings, onboarding, diagnostics, and a real confirmation dialog for Risk 2+ capabilities (none are registered yet, but the UI should be ready before one is) are still needed.
2. Continue the WCAG 2.2 AA pass on `MainWindow`: keyboard focus order and no-trap navigation are now verified (see Implemented and Tested), but contrast, OS scaling, and a real screen-reader (NVDA/Narrator) pass are still outstanding -- do not claim accessibility compliance until those are checked too.
3. Wire voice/gesture input to `EventOrchestrator` (already event-driven and StateMachine-integrated, so no orchestrator changes should be needed -- only a new adapter that publishes real `TranscriptEvent`/`GestureEvent`s) so `system.stop` can interrupt real long-running operations.
4. Move `MainWindow`'s command execution off the blocking `asyncio.run()` call on the GUI thread (e.g. an event-loop integration like `qasync`, or a worker thread) so the new Stop button has something real to cancel -- this should land before task 3 introduces genuinely long-running voice/vision operations, since a blocked GUI thread cannot process a Stop click while a long operation runs.

## Known Defects

- Existing `../jarvis` prototype is still untrusted reference material, but its previously documented concrete OS command injection path has been locally quarantined in this workspace. The quarantine is not part of the `visionai/` Git repository, so a separate `jarvis` copy or restore must not be assumed safe.
- Existing `../jarvis` docs claim production readiness without verification evidence.
- Existing `../jarvis` logs are very large and should be rotated or removed with user approval.
- Existing `../jarvis` venv is not runnable in this workspace.
- `WindowsLockStateAdapter`'s true locked-workstation path has not been manually verified (requires a human to lock the screen and observe the result); only the unlocked path has been confirmed live.
- Old `../jarvis` media control and pointer automation remain direct local actions outside the trusted `visionai` manifest/policy/dispatcher/audit path.

## Security Restrictions

- No arbitrary shell execution is implemented in the new `visionai` package.
- No raw audio or camera retention is enabled by default in the new settings.
- Prohibited capabilities cannot be registered in the new capability registry.
- Sensitive capabilities require permission, and sensitive/destructive requests require fresh confirmation.
- Policy can enforce per-capability rate limits.
- Dispatcher records policy denials and execution results to an audit sink.
- Browser URL helpers reject unsafe schemes, unallowlisted hosts, private/local hosts, embedded credentials, control characters, and empty searches.
- Permission and audit persistence reject malformed local files rather than accepting corrupted state.
- Windows lock-state adapter is conservative: unknown state blocks mutating actions.
- Previous prototype code must not be treated as policy-compliant until migrated and tested.
- Further old-prototype migration must pass `docs/MIGRATION_QUARANTINE.md` gates.
- `system.help` and `system.capabilities` are read-only registry introspection only.
- `system.stop` requests cooperative cancellation only; it does not terminate processes or threads directly.
- `app.open` launches by exact executable name with `shell=False`, never a shell string; its allowlist (`notepad`, `calculator`, `paint`) deliberately excludes any general-purpose command surface (shell, terminal, task manager).
- `browser.open` and `browser.search` validate through `UrlPolicy` and allowlisted HTTPS hosts before the browser opener is called.
- `media.control` only maps allowlisted action names to fixed media keys and remains behind manifest, policy, dispatcher, rate-limit, and audit controls.
- The old `../jarvis` prototype must remain outside the trusted runtime even after local quarantine; only `visionai/` capabilities registered by manifest are trusted.

## Required Decisions

- None outstanding. (Resolved: `../jarvis` was locally quarantined; the next major phase was decided as Phase 2, desktop UI.)

## Verification Commands

```bash
cd visionai
.\scripts\verify.ps1
```

## Last Verification Result

Latest focused verification after confirmation-precheck changes:

- `pytest tests\unit\test_dispatcher.py tests\unit\test_policy.py tests\unit\test_runtime.py tests\unit\test_event_orchestrator.py tests\unit\test_main_window.py`: 33 passed

Most recent full local verification before that final precheck slice:

- Python: 3.12.10
- Ruff: passed
- mypy: passed for 36 source files
- pytest: 158 passed, 94% coverage (headless, via `tests/conftest.py`'s automatic `QT_QPA_PLATFORM=offscreen`)
- Bandit: passed
- pip-audit: no known vulnerabilities found

## Last Updated

2026-08-26
