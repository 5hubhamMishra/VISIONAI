# VisionAI

VisionAI is a local-first Windows desktop assistant that accepts voice
commands, hand gestures, and keyboard/pointer input. It interprets requests,
applies deterministic safety and permission rules, executes only registered
capabilities, and returns clear visual and spoken feedback.

## Status

VisionAI has a safety foundation and a desktop/console runtime for system
information, help, cancellation, allowlisted apps and websites, browser
search, and media controls. Webcam gestures and local speech transcription
are connected; real voice accuracy and broader gesture benchmarks remain
unverified. Phase 6 adds optional AI answers and reviewed command suggestions
with human confirmation, plus OS keychain storage and desktop Settings key
controls. It is a development build, not a production release. See
[docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) for the current phase, verified
functionality, and next steps.

## Priorities

User safety, correctness, privacy, reliability, and accessibility take
precedence over feature count. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
and [docs/SECURITY.md](docs/SECURITY.md) for the design rationale.

## Requirements

- Windows 10/11
- Python 3.12

Linux and macOS are not currently supported or tested.

## Setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for environment setup,
dependency installation, and verification commands.

## Documentation

- [Autonomous cycle report](docs/AUTONOMOUS_HOUR_2026-09-05.md) — changes, checks, timing, and remaining work
- [Phone remote control](docs/REMOTE_CONTROL.md) — one-time pairing and connection check

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components and data flow
- [docs/SECURITY.md](docs/SECURITY.md) — threat model and controls
- [docs/TESTING.md](docs/TESTING.md) — test strategy and verified results
- [docs/ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md) — Python setup and repair steps
- [docs/MIGRATION_QUARANTINE.md](docs/MIGRATION_QUARANTINE.md) — rules for old prototype migration
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — end-user guide
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — contributor setup
- [docs/DECISIONS/](docs/DECISIONS/) — architectural decision records
- [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) — release history

## License

MIT — see [LICENSE](LICENSE).
