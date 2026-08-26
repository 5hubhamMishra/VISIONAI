# Project State

## Current Phase

Phase 1 safety foundation locally verified; Phase 4 capability migration is
underway through narrow, policy-gated slices.

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
- Migrated media behavior into the trusted runtime as `media.control`, a Risk 1 (Reversible) capability that accepts only fixed media actions (`play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`) and maps them to allowlisted media keys through an injectable key presser. Its real `default_key_presser` calls `pyautogui`, which was not declared as a project dependency -- every test injects a fake key presser, so `media.control` would have failed at runtime with "pyautogui is not installed" on a standard `pip install -r requirements/dev.txt`, undetected by the test suite. Added `pyautogui` to `requirements/base.txt`/`pyproject.toml`, then verified the real path live: toggled the mute key on and immediately off through both the raw function and the actual CLI (`visionai media.control --media-action mute` twice in a row), restoring the original state -- deliberately not testing `volume_up`/`volume_down`/`play_pause` for real, since those aren't cleanly self-reversing the way a mute toggle is.
- Added the two remaining Section 13 initial safe capabilities that don't require an orchestrator: `system.capabilities` (lists every registered capability by ID and description) and `system.help` (summarizes current functionality and the registered count). Both are pure registry introspection, Risk 0 (Read-only). "Stop current operation" is still deferred -- there is no orchestrator or in-flight operation yet for it to stop.
- Locally quarantined the old `../jarvis` prototype execution path in this workspace: app parsing now rejects injection-shaped text instead of partially matching it, unknown app/site names no longer fall back to raw spoken text, app launch uses `subprocess.Popen([cmd], shell=False)`, command-surface apps are blocked, web opens are host/scheme allowlisted, search query encoding uses `quote_plus`, mutating system commands are hard-blocked, and touched debug prints are ASCII-safe on the Windows console. These source edits are outside the `visionai/` Git repository and therefore are not pushed to `5hubhamMishra/VISIONAI`; this document records the local hardening step.

## Implemented but Not Fully Verified

- None outstanding at this time.

## In Progress

- Incremental migration from the previous JARVIS prototype: `app.open`, `browser.open`, `browser.search`, and `media.control` migrated; voice, gesture, and LLM behaviors remain unmigrated and untrusted.

## Approved Next Tasks

1. Decide whether to disable or quarantine unsafe direct execution paths in the old `../jarvis` prototype itself (distinct from the new package, which never imports from it).
2. Decide which prototype feature to migrate next (voice input, gesture input, LLM response planning, or something else).
3. Add "stop current operation" once a real orchestrator/state machine wiring exists for it to interrupt.

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
- `app.open` launches by exact executable name with `shell=False`, never a shell string; its allowlist (`notepad`, `calculator`, `paint`) deliberately excludes any general-purpose command surface (shell, terminal, task manager).
- `browser.open` and `browser.search` validate through `UrlPolicy` and allowlisted HTTPS hosts before the browser opener is called.
- `media.control` only maps allowlisted action names to fixed media keys and remains behind manifest, policy, dispatcher, rate-limit, and audit controls.
- The old `../jarvis` prototype must remain outside the trusted runtime even after local quarantine; only `visionai/` capabilities registered by manifest are trusted.

## Required Decisions

- Decide whether the old `../jarvis` prototype itself needs its unsafe execution paths disabled/quarantined, given it is not imported by and has no effect on the new `visionai` package.
- Decide which prototype feature to migrate next.

## Verification Commands

```bash
cd visionai
.\scripts\verify.ps1
```

## Last Verification Result

- Python: 3.12.10
- Ruff: passed
- mypy: passed for 31 source files
- pytest: 118 passed, 92% coverage
- Bandit: passed
- pip-audit: no known vulnerabilities found

## Last Updated

2026-08-26
