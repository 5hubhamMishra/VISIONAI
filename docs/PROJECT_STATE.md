# Project State

## Current Phase

Phase 1 Safety foundation locally verified.

## Last Verified Commit

`3b321db` on `main`, pushed to https://github.com/5hubhamMishra/VISIONAI. Hosted CI ("VisionAI CI") passed on both `c7beb2e` (1m 59s) and `3b321db` (1m 3s).

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
- Phase 1 Windows lock-state adapter wrapper that treats API failures or unknown session state as locked
- CI workflow and local verification scripts for formatting, typing, tests, security scan, and dependency audit
- Migration quarantine documentation for the previous prototype
- Environment repair documentation for Python 3.12 and virtual environment recreation
- Phase 4 read-only system info capabilities (`system.time`, `system.date`, `system.battery`, `system.health`) with manifests and handlers
- Runtime assembly (`visionai.runtime.build_runtime`) wiring the registry, policy engine, rate limiter, audit sink, and dispatcher together
- Console entry point (`visionai.app.main`) that dispatches a read-only capability through the full policy + dispatcher path
- Battery and CPU/memory probes backed by `psutil`, injectable for testing, with a graceful "no battery detected" fallback on desktops/VMs without one

## Implemented but Not Fully Verified

- None outstanding at this time.

## In Progress

- Incremental migration from the previous JARVIS prototype into the VisionAI architecture remains blocked until policy gates are verified.

## Approved Next Tasks

1. Disable or quarantine unsafe direct execution paths in the old prototype before any migration into `visionai`.
2. Decide which safe prototype feature to migrate first behind the Phase 1 gates.
3. Add remaining Section 13 initial safe capabilities (help, capability list, stop current operation) once a real orchestrator/state machine wiring exists to stop.

## Known Defects

- Existing `../jarvis` prototype still contains direct OS/browser/media execution paths.
- Existing `../jarvis` docs claim production readiness without verification evidence.
- Existing `../jarvis` logs are very large and should be rotated or removed with user approval.
- Existing `../jarvis` venv is not runnable in this workspace.

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
- Old prototype migration is blocked by `docs/MIGRATION_QUARANTINE.md` gates.

## Required Decisions

- Decide which existing prototype features are worth migrating first after Phase 1 safety gates.

## Verification Commands

```bash
cd visionai
.\scripts\verify.ps1
```

## Last Verification Result

- Python: 3.12.10
- Ruff: passed
- mypy: passed for 27 source files
- pytest: 67 passed, 88% coverage
- Bandit: passed
- pip-audit: no known vulnerabilities found

## Last Updated

2026-08-26
