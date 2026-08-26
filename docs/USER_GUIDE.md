# User Guide

VisionAI is not ready for end-user operation yet. It does not accept voice or gesture input, and does not execute file, shutdown, or any other system-mutating actions beyond the specific commands below.

The only working functionality is a console entry point that runs one policy-gated capability at a time:

```bash
visionai system.time
visionai system.date --format iso
visionai system.battery
visionai system.health
visionai system.capabilities
visionai system.help
visionai system.stop
visionai app.open --app notepad
visionai browser.open --site github
visionai browser.search --query "VisionAI local assistant"
visionai media.control --media-action play_pause
visionai --text "open notepad"
visionai --text "what time is it"
```

`--text` plans and runs one typed command through the same deterministic phrase matching, allowlists, and policy/dispatcher path as the explicit commands above -- it does not add any new capability, just an alternate way to invoke the existing ones. Anything that doesn't match a reviewed phrase, or whose slot isn't allowlisted, is treated as non-executable conversation and nothing runs.

`app.open` accepts `notepad`, `calculator`, or `paint` -- any other value is rejected before anything opens. There is no wake word, no orchestrator, and no way to invoke these from voice or gesture input yet.

`browser.open` accepts `youtube`, `instagram`, `twitter`, `facebook`, `github`, `reddit`, or `netflix`. `browser.search` opens an encoded Google search URL; empty queries, control characters, and non-allowlisted hosts are rejected before anything opens.

`media.control` accepts `play_pause`, `next`, `previous`, `volume_up`, `volume_down`, or `mute`.

`system.stop` requests cooperative cancellation of the current operation. Until voice, vision, and long-running orchestration are wired in, it usually reports that no operation is running.

Use the previous prototype only as untrusted reference material during migration.
