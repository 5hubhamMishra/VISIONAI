# Release Notes

## 0.1.0

- Started Phase 0 foundation.
- Added neutral VisionAI package structure, docs, typed contracts, state machine, event bus, logging redaction, and unit tests.
- Added initial Phase 1 capability registry, policy engine, confirmation service, and related unit tests.
- Added Phase 1 rate limiter, URL policy helper, serialized dispatcher, audit sink, and related unit tests.
- Added Phase 1 JSON permission store, JSON Lines audit sink, lock-state adapter boundary, private/local URL host blocking, and security input tests.
- Added URL IDN/redirect/host-confusion tests, confirmation replay/expiry edge tests, prompt-injection data tests, and a conservative Windows lock-state adapter wrapper.
- Added CI workflow, local verification scripts, and migration quarantine documentation.
- Initialized Git repository on `main` and added Python environment repair documentation.
- Installed Python 3.12.10, created `.venv312`, updated vulnerable dependency pins, and verified the local suite.
- Added the first real, dispatcher-wired capabilities: `system.time`, `system.date`, `system.battery`, `system.health`, all read-only.
- Pushed the repository to https://github.com/5hubhamMishra/VISIONAI; hosted CI is live and has passed on every commit so far.
- Found and fixed seven defects surfaced by a full security/correctness review of the safety-critical modules, each with a regression test: `UrlPolicy` failed open on an empty host allowlist; `WindowsLockStateAdapter` never actually detected lock state (it checked session membership, not lock status); `SerializedDispatcher` audited denials using the caller-supplied risk level instead of the manifest's; `FixedWindowRateLimiter` and `StateMachine` both mutated shared state with no lock, reproducible as real races under concurrent access; `EventBus.close()` could deadlock a consumer if the queue was full at close time; and log redaction did not work at all as wired (attached to the wrong logger) and could crash message rendering even when fixed to attach correctly.
- Migrated the first capability from `../jarvis` per `docs/MIGRATION_QUARANTINE.md`: `app.open`, opening one allowlisted desktop application (`notepad`, `calculator`, `paint`) by exact executable name with `shell=False`, deliberately excluding anything from the old prototype's broader app list that is itself a command surface (`cmd`, `powershell`, Task Manager). Verified live end to end, including a real Notepad launch and clean shutdown.
- Added `system.capabilities` and `system.help`, the two remaining Section 13 initial safe capabilities that don't need an orchestrator; "stop current operation" is still deferred until one exists.
- Documented a concrete, traceable OS command injection path in `../jarvis` (found while reviewing `brain/intent_parser.py`): unrecognized app/site names fall back to the raw spoken word instead of being rejected, and that value reaches `subprocess.Popen(cmd, shell=True)` unvalidated.
- Locally quarantined that old `../jarvis` app/web/system execution path in this workspace. The source edits are outside the `visionai/` Git repository, so the trusted repo records the hardening but still treats the old prototype as untrusted reference material.
- Migrated safe browser/search behavior into the trusted runtime as `browser.open` and `browser.search`, both reversible and allowlist-backed. Site names map to fixed HTTPS URLs, search queries are encoded through `UrlPolicy`, and tests inject the browser opener so verification never launches a real browser.
