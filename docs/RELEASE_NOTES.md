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
