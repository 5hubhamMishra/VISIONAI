# Migration Quarantine

The previous `../jarvis` prototype is reference material only. It must not be treated as trusted VisionAI runtime code until each migrated behavior passes the gates below.

## Quarantine Rules

- Do not import from `../jarvis` into `visionai`.
- Do not run old direct-action modules as part of the VisionAI app.
- Do not migrate a capability until it has a manifest, typed parameters, policy tests, audit behavior, and dispatcher coverage.
- Do not migrate arbitrary launch, shell, file mutation, send, purchase, install, or shutdown behavior in early phases.
- Do not describe migrated code as implemented and tested until automated tests have passed.

## Required Migration Steps

1. Identify one safe behavior from the prototype.
2. Write or update the capability manifest.
3. Add policy and validation tests for unknown fields, wrong types, malformed input, rate limits, permissions, confirmations, and audit behavior.
4. Implement the handler behind the serialized dispatcher.
5. Run the full verification suite.
6. Update `docs/PROJECT_STATE.md`, `docs/SECURITY.md`, and user-facing documentation.

## Current Status

No old prototype capability has been migrated into the trusted `visionai` runtime.
