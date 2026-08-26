# Security

## Threat Model

VisionAI processes local voice, camera, keyboard, and pointer input. Relevant threats include replayed audio, nearby speakers, malicious webpage audio, prompt or indirect injection, malicious URLs, event floods, unauthorized local users, compromised dependencies, secret leakage, and misuse of microphone or camera access.

## Phase 0 Controls

- Deny-by-default foundation: every capability must be explicitly registered with a manifest before it is reachable, and the one capability with a real side effect (`app.open`) uses an exact-executable allowlist rather than trusting caller-supplied input.
- The application state machine is safe under concurrent access from multiple recognition threads (voice, gesture): transitions are serialized so only one of several racing callers can ever succeed, and the audit trail cannot be corrupted by interleaved transitions.
- Typed contracts reject control characters, oversized text, invalid confidence values, and malformed mappings.
- Event bus is bounded to provide backpressure; closing it is guaranteed to be observed by consumers (via a separate close signal) even if the bounded queue is full at that moment, after draining any already-queued events.
- Raw media retention defaults to disabled.
- Log redaction covers common key-value secret patterns, including secrets passed as lazy %-style logging arguments rather than baked into the message template; the filter is attached to every configured handler so it applies to all named application loggers, not only the root logger.
- Capability registry rejects prohibited capabilities and duplicate IDs.
- `system.help` and `system.capabilities` are read-only registry introspection only; they do not execute shell commands, inspect files, or call external services.
- `system.stop` only requests cooperative cancellation through `OperationController`; it never kills processes or threads directly and is safe to call when no operation is active.
- Policy rejects unknown arguments, unsupported platforms, missing permissions, missing fresh confirmations, and mutating actions while the screen is locked.
- Confirmation service binds approval to the exact action request, expires it quickly, and consumes it after one use.
- Fixed-window rate limiting can be attached to policy evaluation and is safe under concurrent access from multiple recognition threads.
- Serialized dispatcher refuses denied requests before handler lookup and records denials/results to audit history, always using the registered capability's manifest risk level rather than the caller-supplied request field, so a request cannot understate its own severity in the audit trail.
- URL policy rejects non-HTTPS schemes by default, unallowlisted hosts, private/local hosts, embedded credentials, control characters, empty searches, and oversized searches.
- JSON permission and audit storage reject malformed local state.
- Lock-state policy input is isolated behind an adapter boundary. The Windows wrapper checks whether the interactive desktop can be opened (`OpenInputDesktop`), which fails while the workstation is locked or a secure desktop such as a UAC prompt is active, and treats any check failure or unreachable desktop as locked.
- `app.open` opens one allowlisted desktop application by its exact executable name with `shell=False` -- never a shell string, never user-supplied text. The allowlist (`notepad`, `calculator`, `paint`) deliberately excludes anything that is itself a general-purpose command surface (a shell, a terminal, Task Manager), since exposing one of those would let an "open an app" capability be used to reach arbitrary further execution.
- `browser.open` and `browser.search` are reversible browser capabilities. They do not accept arbitrary URLs: site names map to a fixed allowlist, search queries are encoded by `UrlPolicy`, only HTTPS allowlisted hosts are permitted, and the browser opener is called only after policy normalization succeeds.
- `media.control` accepts only fixed media actions (`play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`) and maps them to allowlisted media keys; tests inject the key presser so automated verification never sends live keyboard input. The real `pyautogui`-based key presser is dependency-declared but not exercised by automated verification.
- `TextCommandPlanner` is deterministic (no LLM, no arbitrary phrase interpretation) and is explicitly not itself a security boundary: it only ever emits an `ActionRequest` for a capability already registered in the runtime, using slot values already checked against the same allowlists (`ALLOWED_APPLICATIONS`, `ALLOWED_SITES`, `ALLOWED_MEDIA_ACTIONS`) the capability handlers themselves enforce, and every request it produces still passes through the same policy engine and dispatcher as one invoked directly. Text that doesn't match a reviewed phrase, or whose slot fails allowlist/character checks, becomes non-executable conversation data -- confirmed for the exact injection shape found in `../jarvis` ("open calc & powershell" produces no action).

## Remaining Risks

- The previous `../jarvis` prototype is still not a trusted VisionAI build. Its concrete app-launch injection path was locally quarantined in this workspace, but those source edits live outside the `visionai/` Git repository and are not evidence that any other copy of the prototype is safe. Media control and pointer automation also remain direct local actions outside the manifest/policy/dispatcher/audit path.
- The Windows lock-state wrapper has been verified against a live *unlocked* session (correctly reports unlocked, no crash) and against mocked locked/failure branches in unit tests. Its behavior against a genuinely *locked* workstation has not been manually verified, since that requires a human to lock the screen and observe the result -- do not treat the locked-state path as field-tested until that manual check has been done.
- `app.open`, `browser.open`, `browser.search`, and `media.control` are the only capabilities with real side effects wired to the dispatcher; everything else currently wired is read-only.
