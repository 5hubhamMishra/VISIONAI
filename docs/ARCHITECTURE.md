# Architecture

VisionAI is being rebuilt around an explicit safety-first pipeline:

Input adapters -> bounded event bus -> recognition services -> intent orchestrator -> typed action plan -> policy and permission engine -> confirmation gate -> serialized action dispatcher -> platform capability adapter -> result event -> UI, TTS, and audit history.

## Components (Phase 0 foundation + Phase 1 safety + first Phase 4 capabilities)

- `visionai.core.events`: typed contracts for inputs, transcripts, gestures, intents, action plans, confirmations, permission decisions, audit events, and error events.
- `visionai.core.state`: explicit assistant state machine. Safe under concurrent access from multiple recognition threads (voice, gesture): `transition()`/`cancel()`/`on_transition()` are serialized by a lock, with listener callbacks notified outside it so a listener cannot deadlock or block other threads.
- `visionai.core.event_bus`: bounded asynchronous queue with close semantics. Closing signals over a separate `asyncio.Event` rather than a sentinel value competing for queue space, so the signal cannot be lost even if the queue is full; consumers still drain any already-queued events before observing closure.
- `visionai.core.cancellation`: cooperative cancellation token wrapping `threading.Event`.
- `visionai.config.settings`: environment-backed settings with conservative defaults.
- `visionai.observability.logging`: redacted structured logging. The redaction filter is attached to every configured handler (not the root logger, whose own filters do not gate records from named child loggers) and redacts the fully substituted message so secrets passed as lazy `%`-style arguments are still caught.
- `visionai.observability.audit`: in-memory and JSON Lines audit sinks used by tests and early UI integration. Both reject an entire malformed log/entry rather than silently using a partial view, consistent with the permission store.
- `visionai.capabilities`: reviewed capability manifests and registry. Prohibited capabilities cannot be registered.
- `visionai.capabilities.system_info`: read-only capabilities -- `system.time`, `system.date`, `system.battery`, `system.health` -- with battery/CPU/memory probes backed by `psutil` and injectable for testing.
- `visionai.capabilities.meta`: read-only registry introspection -- `system.capabilities` and `system.help` -- for the initial safe help/capability-list surface.
- `visionai.capabilities.applications`: `app.open`, the first migrated behavior with a real side effect. Opens one allowlisted desktop application by exact executable name with `shell=False`; the allowlist deliberately excludes any general-purpose command surface (shell, terminal, task manager). See `docs/MIGRATION_QUARANTINE.md`.
- `visionai.capabilities.browser`: reversible browser capabilities -- `browser.open` and `browser.search` -- built from fixed site/search allowlists and `UrlPolicy` normalization before any browser opener is called.
- `visionai.capabilities.dispatcher`: serialized handler dispatch after policy approval, with audit output. Audit records for both denials and successes use the registered capability's manifest risk level, never the caller-supplied request field, so a request cannot understate its own severity in the audit trail.
- `visionai.policy`: deterministic policy, persistent permission storage, rate limiting (thread-safe), URL validation helpers (deny-by-default: an empty host allowlist denies every host, not just non-private ones), and confirmation checks before any dispatcher can execute a request.
- `visionai.platform`: platform-state adapter boundary with static test adapter and Windows lock-state wrapper. The Windows wrapper checks whether the interactive input desktop can be opened (fails while the workstation is locked or a secure desktop such as a UAC prompt is active); any check failure or unreachable desktop is treated as locked.
- `visionai.runtime`: assembles the registry, policy engine, rate limiter, audit sink, and dispatcher into a single `Runtime` for the console entry point.
- `visionai.app`: console entry point (`visionai` script) that dispatches one capability through the full policy + dispatcher path.

## Migration Rule

The old prototype remains in `../jarvis` and is not part of the trusted VisionAI runtime. Features should migrate only after their contracts, policy checks, tests, and documentation exist in this package. See `docs/MIGRATION_QUARANTINE.md`.
