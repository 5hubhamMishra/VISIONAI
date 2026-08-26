# Security

## Threat Model

VisionAI processes local voice, camera, keyboard, and pointer input. Relevant threats include replayed audio, nearby speakers, malicious webpage audio, prompt or indirect injection, malicious URLs, event floods, unauthorized local users, compromised dependencies, secret leakage, and misuse of microphone or camera access.

## Phase 0 Controls

- Deny-by-default foundation: no executable capabilities are registered yet.
- Typed contracts reject control characters, oversized text, invalid confidence values, and malformed mappings.
- Event bus is bounded to provide backpressure; closing it is guaranteed to be observed by consumers (via a separate close signal) even if the bounded queue is full at that moment, after draining any already-queued events.
- Raw media retention defaults to disabled.
- Log redaction covers common key-value secret patterns.
- Capability registry rejects prohibited capabilities and duplicate IDs.
- Policy rejects unknown arguments, unsupported platforms, missing permissions, missing fresh confirmations, and mutating actions while the screen is locked.
- Confirmation service binds approval to the exact action request, expires it quickly, and consumes it after one use.
- Fixed-window rate limiting can be attached to policy evaluation and is safe under concurrent access from multiple recognition threads.
- Serialized dispatcher refuses denied requests before handler lookup and records denials/results to audit history, always using the registered capability's manifest risk level rather than the caller-supplied request field, so a request cannot understate its own severity in the audit trail.
- URL policy rejects non-HTTPS schemes by default, unallowlisted hosts, private/local hosts, embedded credentials, control characters, empty searches, and oversized searches.
- JSON permission and audit storage reject malformed local state.
- Lock-state policy input is isolated behind an adapter boundary. The Windows wrapper checks whether the interactive desktop can be opened (`OpenInputDesktop`), which fails while the workstation is locked or a secure desktop such as a UAC prompt is active, and treats any check failure or unreachable desktop as locked.

## Remaining Risks

- The previous `../jarvis` prototype contains direct system execution, browser opening, media control, and pointer automation. It should not be run as a trusted VisionAI build.
- The Windows lock-state wrapper has been verified against a live *unlocked* session (correctly reports unlocked, no crash) and against mocked locked/failure branches in unit tests. Its behavior against a genuinely *locked* workstation has not been manually verified, since that requires a human to lock the screen and observe the result — do not treat the locked-state path as field-tested until that manual check has been done.
- No real capability handlers with side effects exist yet; only read-only system info capabilities are wired to the dispatcher.
