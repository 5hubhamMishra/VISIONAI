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

One old prototype behavior has been migrated into the trusted `visionai` runtime, following all six steps above:

- **`app.open`** (open an allowlisted desktop application), migrated from `../jarvis/actions/executor.py`'s app-launch logic as reference material only. The old code used `subprocess.Popen(cmd, shell=True)` against a broad app list that included a shell (`cmd`, `powershell`), a terminal, and Task Manager. The new capability deliberately excludes anything that is itself a general-purpose command surface, uses exact executable names with `shell=False`, and is Risk 1 (Reversible) per Section 9 of the master prompt -- see `src/visionai/capabilities/applications.py`.

No other old prototype capability (voice, gesture, media control, browser, LLM) has been migrated.
