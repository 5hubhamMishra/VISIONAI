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
- Cancellation tests cover token signalling, raising, active-operation tracking, active cancellation, no-active-operation behavior, and ignoring stale operation tokens.
- Capability manifests reject duplicate and prohibited registrations.
- Policy rejects unknown arguments, wrong argument types, missing permissions, missing confirmations, unrelated confirmations, and locked-screen mutations.
- Confirmation requests are exact-match, expiring, and single-use.
- Rate limiting blocks requests after the configured fixed-window limit and resets after the window.
- URL validation covers allowlisted HTTPS URLs, unsafe schemes, unallowlisted hosts, private/local hosts, embedded credentials, encoded searches, and empty searches.
- Dispatcher tests cover handler execution, audit records, policy denial before handler execution, and missing handlers.
- Permission persistence tests cover grants, revocations, malformed JSON, and invalid entries.
- Audit persistence tests cover JSON Lines round-trip and malformed log rejection.
- Lock-state tests cover conservative defaults, policy-context construction from adapters, Windows wrapper failure handling, injected successful session lookup, and a live smoke test against the real `OpenInputDesktop`/`CloseDesktop` Windows API calls (confirms no crash and a correct result on an unlocked session; does not confirm the genuinely-locked path, which needs a human to lock the screen -- see `docs/PROJECT_STATE.md` Known Defects).
- Security input tests cover unknown fields from model output, control characters in intent slots, prompt-injection strings that remain data, and malformed model plans with extra tool fields.
- Concurrency regression tests reproduce and then verify the fix for three races found during review: `FixedWindowRateLimiter` (100 threads racing through a barrier must not exceed the configured limit), `StateMachine` (50 threads racing a transition must yield exactly one success and an unbroken history chain, reproduced with `sys.setswitchinterval` tightened to widen the race window), and `EventBus.close()` (closing a completely full queue must not deadlock a consumer waiting in `next_event()`).
- Logging redaction tests exercise the actual filter against realistic `LogRecord`s, not only the pure `redact_message()` helper: lazy `%s`-style arguments, dict-style arguments, and messages with no secret at all, plus a test that `configure_logging()` attaches the filter to installed handlers (not just the root logger).
- System info capability tests cover `system.time`, `system.date`, `system.battery` (including the "no battery detected" fallback), and `system.health`, both as isolated handlers with injected fakes and end to end through `build_runtime()`'s real dispatcher and policy path.
- `app.open` tests cover manifest risk classification, an injected fake launcher for the success/case-insensitivity/OS-error paths (so no real process spawns), policy rejection of unknown/missing arguments and rate-limit exhaustion, and two things verified with the *real* `default_launcher`: the denial path for an unallowlisted app (safe, since nothing launches), and a genuine end-to-end run through the CLI that actually opened Notepad as a live process (confirmed via `Get-Process`) before it was closed.
- `system.capabilities`/`system.help`/`system.stop` tests cover manifest risk classification, listing sorted by ID, the empty-registry case, cooperative cancellation behavior, locked-screen availability, and end to end through `build_runtime()` -- including that the listing correctly includes itself.
- Browser capability tests cover `browser.open` and `browser.search`: allowlisted site normalization, unknown-site rejection, URL policy failure before opener execution, encoded search queries, empty/control-character query rejection, runtime dispatch/audit, CLI invocation, and policy rejection of missing/unknown arguments.
- Media capability tests cover `media.control`: manifest risk classification, allowlisted key mapping, unknown-action rejection before keypress, key-presser failure handling, runtime dispatch/audit, CLI invocation, and policy rejection of missing/unknown arguments -- all via an injected fake key presser, since automated verification must not send live keyboard input. The real `pyautogui`-based path was found missing from the project's declared dependencies (added to `requirements/base.txt`), then verified once, live: the mute key toggled on and immediately off, through both the raw function and the actual CLI, confirming no crash and a correctly self-reversing result.

## Verified Results

Verified locally on Windows with Python 3.12.10 using `scripts\verify.ps1`:

- Ruff: passed
- mypy: passed for 31 source files
- pytest: 126 passed
- Coverage: 92%
- Bandit: passed
- pip-audit: no known vulnerabilities found

## CI Coverage

`.github/workflows/ci.yml` runs Ruff, mypy, pytest with coverage, Bandit, and pip-audit on Windows with Python 3.12, on every push to `main` and every pull request. Hosted CI is live at https://github.com/5hubhamMishra/VISIONAI/actions and has passed on every commit pushed so far.
