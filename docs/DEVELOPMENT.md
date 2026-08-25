# Development

## Principles

- Keep migration incremental.
- Add tests with behavior changes.
- Treat external input as untrusted.
- Do not execute model output directly.
- Do not add operating-system actions until the capability registry and policy engine exist.

## Local Commands

If Python is not available, repair the environment first with
`docs/ENVIRONMENT_SETUP.md`.

```bash
python -m ruff check .
python -m mypy src
python -m pytest --cov=src/visionai --cov-report=term-missing
python -m bandit -q -r src
python -m pip_audit -r requirements/base.txt -r requirements/dev.txt
```

On Windows, run the bundled script once Python and dependencies are installed:

```powershell
.\scripts\verify.ps1
```

On POSIX shells:

```bash
./scripts/verify.sh
```

## Prototype Quarantine

The old `../jarvis` prototype is not trusted runtime code. See
`docs/MIGRATION_QUARANTINE.md` before migrating any behavior.
