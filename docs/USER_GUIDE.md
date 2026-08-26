# User Guide

VisionAI is not ready for end-user operation yet. It does not accept voice or gesture input, and does not execute file, shutdown, or any other system-mutating actions beyond the specific commands below.

There are two ways to run a command today: a console entry point, and a minimal desktop window (the first Phase 2 UI slice). Both drive the exact same policy-gated capabilities -- neither has any execution authority the other lacks.

The console entry point runs one policy-gated capability at a time:

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

## Desktop window

```bash
visionai-ui
```

Opens a minimal window: a command input, a Run button, a Stop button, Diagnostics and Settings buttons, a result area, an audit history list, and a tray icon. Type any of the same commands shown above (e.g. `open notepad`, `what time is it`) and press Enter or click Run. This is not the full application window described for later phases -- there is no onboarding or editable settings UI yet -- but every command it runs goes through the same `TextCommandPlanner`, policy engine, and dispatcher as the console, so nothing typed into the window can do anything the console commands above cannot already do.

The Stop button requests cooperative cancellation and stays clickable even while a command is running, unlike the command input and Run button. Since the registered commands currently complete quickly, clicking it while nothing is running just reports that no operation is active.

The Diagnostics button shows a read-only status summary: app/library versions, registered capability count, tray availability, current state, and which input subsystems are still disconnected.

The Settings button shows a read-only summary of the currently loaded settings, including log level and data/log paths. It does not change configuration, grant permissions, or enable raw audio/camera retention.

If a future command requires confirmation, the window asks before executing it. Choosing No cancels the pending request; choosing Yes sends the bound confirmation back through the orchestrator and dispatcher. If a command also or instead requires permission, the window asks to grant that first ("Grant permission") -- granting can still be followed by a separate confirmation prompt if the same command needs both. No registered command currently requires either prompt yet, but both UI paths are in place.

The window also has a system tray icon (a placeholder icon for now, not final branding). Left-clicking it shows or hides the window; right-clicking opens a menu with "Show VisionAI" and "Quit". Closing the window (the title bar's close button) minimizes it to the tray instead of exiting, so VisionAI keeps running in the background -- use the tray menu's "Quit" to actually exit.

Use the previous prototype only as untrusted reference material during migration.
