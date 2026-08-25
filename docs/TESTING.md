# Testing

## Strategy

Phase 0 tests cover core contracts and invariants:

- Invalid transcript text has no downstream side effect.
- Gesture confidence is normalized.
- Action arguments are immutable after validation.
- Confirmation requests must expire in the future.
- State transitions are explicit and reject unapproved jumps.
- Event bus publishes in order and rejects publish after close.
- Logs redact common secret patterns.
- Capability manifests reject duplicate and prohibited registrations.
- Policy rejects unknown arguments, wrong argument types, missing permissions, missing confirmations, unrelated confirmations, and locked-screen mutations.
- Confirmation requests are exact-match, expiring, and single-use.
- Rate limiting blocks requests after the configured fixed-window limit and resets after the window.
- URL validation covers allowlisted HTTPS URLs, unsafe schemes, unallowlisted hosts, private/local hosts, embedded credentials, encoded searches, and empty searches.
- Dispatcher tests cover handler execution, audit records, policy denial before handler execution, and missing handlers.
- Permission persistence tests cover grants, revocations, malformed JSON, and invalid entries.
- Audit persistence tests cover JSON Lines round-trip and malformed log rejection.
- Lock-state tests cover conservative defaults, policy-context construction from adapters, Windows wrapper failure handling, and injected successful session lookup.
- Security input tests cover unknown fields from model output, control characters in intent slots, prompt-injection strings that remain data, and malformed model plans with extra tool fields.

## Verified Results

Verified locally on Windows with Python 3.12.10 using `scripts\verify.ps1`:

- Ruff: passed
- mypy: passed for 25 source files
- pytest: 53 passed
- Coverage: 86%
- Bandit: passed
- pip-audit: no known vulnerabilities found

## CI Coverage

`.github/workflows/ci.yml` runs Ruff, mypy, pytest with coverage, Bandit, and pip-audit on Windows with Python 3.12. Hosted CI has not run because no remote repository is configured in this workspace.

## Planned Coverage

Phase 1 should still add runtime-backed Windows lock-state tests after Python is repaired.
