# Architecture

VisionAI is being rebuilt around an explicit safety-first pipeline:

Input adapters -> bounded event bus -> recognition services -> intent orchestrator -> typed action plan -> policy and permission engine -> confirmation gate -> serialized action dispatcher -> platform capability adapter -> result event -> UI, TTS, and audit history.

## Phase 0 Components

- `visionai.core.events`: typed contracts for inputs, transcripts, gestures, intents, action plans, confirmations, permission decisions, audit events, and error events.
- `visionai.core.state`: explicit assistant state machine.
- `visionai.core.event_bus`: bounded asynchronous queue with close semantics.
- `visionai.config.settings`: environment-backed settings with conservative defaults.
- `visionai.observability.logging`: redacted structured logging setup.
- `visionai.capabilities`: reviewed capability manifests and registry. Prohibited capabilities cannot be registered.
- `visionai.capabilities.dispatcher`: serialized handler dispatch after policy approval, with audit output.
- `visionai.policy`: deterministic policy, persistent permission storage, rate limiting, URL validation helpers, and confirmation checks before any dispatcher can execute a request.
- `visionai.observability.audit`: in-memory and JSON Lines audit sinks used by tests and early UI integration.
- `visionai.platform`: platform-state adapter boundary with static test adapter and Windows lock-state wrapper. Unknown state is treated as locked.

## Migration Rule

The old prototype remains in `../jarvis` and is not part of the trusted VisionAI runtime. Features should migrate only after their contracts, policy checks, tests, and documentation exist in this package.
