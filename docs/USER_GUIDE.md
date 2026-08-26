# User Guide

VisionAI is not ready for end-user operation yet. It does not accept voice or gesture input, and does not execute browser, file, shutdown, or media actions.

The only working functionality is a console entry point that runs one policy-gated capability at a time:

```bash
visionai system.time
visionai system.date --format iso
visionai system.battery
visionai system.health
visionai app.open --app notepad
```

`app.open` accepts `notepad`, `calculator`, or `paint` -- any other value is rejected before anything opens. There is no wake word, no orchestrator, and no way to invoke these from voice or gesture input yet.

Use the previous prototype only as untrusted reference material during migration.
