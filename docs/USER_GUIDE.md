# User Guide

VisionAI is not ready for end-user operation yet. Real voice input and recognized gestures can each trigger only the small command map below; they do not provide arbitrary system control.

There are two ways to run a command today: a console entry point, and a minimal desktop window (the first Phase 2 UI slice). Both drive the exact same policy-gated capabilities -- neither has any execution authority the other lacks.

The console entry point runs one policy-gated capability at a time:

```bash
visionai system.time
visionai system.date --format iso
visionai system.battery
visionai system.health
visionai system.capabilities
visionai system.clear_history
visionai system.help
visionai system.stop
visionai app.open --app notepad
visionai browser.open --site github
visionai browser.search --query "VisionAI local assistant"
visionai media.control --media-action play_pause
visionai --list-microphones
visionai --text "open notepad"
visionai --text "what time is it"
visionai --wake-word-text "visionai open notepad"
visionai --wake-word-listen
visionai --gesture-frames 15
visionai --gesture-listen
```

`--text` plans and runs one typed command through the same deterministic phrase matching, allowlists, and policy/dispatcher path as the explicit commands above -- it does not add any new capability, just an alternate way to invoke the existing ones. Anything that doesn't match a reviewed phrase, or whose slot isn't allowlisted, is treated as non-executable conversation and nothing runs.

`app.open` accepts `notepad`, `calculator`, or `paint` -- any other value is rejected before anything opens. The gesture command map invokes only the safe entries listed below through the same planner and policy path as typed commands.

A wake-word gate and listening loop (`visionai.orchestration.WakeWordGate`, `WakeWordVoiceRunner`, and `WakeWordListeningLoop`) strip a configured trigger word (default `"visionai"`, editable in desktop Settings) from an utterance and publish only matching commands. `--wake-word-listen` now drives this loop with the real microphone and STT provider (see below); the desktop window does not have this surface yet.

`browser.open` accepts `youtube`, `instagram`, `twitter`, `facebook`, `github`, `reddit`, or `netflix`. `browser.search` opens an encoded Google search URL; empty queries, control characters, and non-allowlisted hosts are rejected before anything opens.

`media.control` accepts `play_pause`, `next`, `previous`, `volume_up`, `volume_down`, or `mute`.

`--list-microphones` lists real audio input devices by index, name, and input-channel count. It does not record audio, run speech-to-text, or dispatch any command.

`--wake-word-text` accepts one already-transcribed utterance, applies the saved wake word, and sends only a matching command through the normal orchestrator and policy path. It does not provide speech-to-text or continuous microphone capture.

`--wake-word-listen` continuously records short chunks (4 seconds each) from the real microphone, transcribes each with the local `faster-whisper` provider, and sends only wake-word-matching commands through the normal orchestrator and policy path -- press `Ctrl+C` to stop; it reports `"Stopped. Accepted N command(s)."` and prints any dispatched action's result. It requires the `voice` extra installed. This is the smallest real continuous-listening implementation: fixed-length chunks, no voice-activity detection or streaming transcription, so a command must fit inside one chunk and `Ctrl+C` can take up to one chunk's length to take effect.

`--gesture-frames N` opens the real webcam and captures up to N frames, reporting the first confirmed gesture (held steady for a moment, the same temporal voting `GestureCaptureLoop` uses) or `"No gesture detected."` if none is confirmed within N frames. It requires the `vision` extra installed and a hand held close to and centered on the camera; a small N (a dozen or so) is normally enough.

`--gesture-listen` continuously watches for gestures over the real webcam until `Ctrl+C` (or an `open_palm` gesture, which stops it on its own), reporting `"Stopped. Confirmed N gesture(s)."` and printing any dispatched action's result. See the gesture cheat sheet below for what each pose does.

## Gesture cheat sheet

Use the same hand and hold each pose briefly:

| Gesture | Easy name | Planned command |
| --- | --- | --- |
| Open palm | Stop hand | Stop listening or cancel the current operation |
| Closed fist | Listen hand | Start voice command mode |
| Thumbs up | Yes hand | Open Notepad |
| Peace sign | Two hand | Show help |
| Index finger up | Point hand | Tell the time |
| Two fingers plus thumb | Volume hand | Turn volume up |

The classifier recognizes these fixed poses. Five of them route a mapped command
through the planner and policy engine; open palm also ends `--gesture-listen`'s
continuous loop on its own. Closed fist instead starts real push-to-talk voice
capture (`"Voice command listening started..."`) -- hold it, speak your command,
then show an open palm to send it (`"Voice command sent."`) through the same
planner and policy path. Mouse movement, scrolling, clicking, and other side
effects remain disabled until each action has its own policy-gated capability.

Real microphone capture uses the local `faster-whisper` provider when `MicrophonePushToTalk` is created without a custom transcriber. The default is the `base.en` model on CPU with int8 computation; set `VISIONAI_STT_MODEL_SIZE`, `VISIONAI_STT_DEVICE`, or `VISIONAI_STT_COMPUTE_TYPE` before starting VisionAI to change it. The model downloads from Hugging Face on first transcription and stays local afterward.

`system.stop` requests cooperative cancellation of the current operation. Until voice, vision, and long-running orchestration are wired in, it usually reports that no operation is running.

`system.clear_history` clears the local audit history, but it is a sensitive action: it requires both a stored permission grant and a fresh confirmation before it runs. The desktop window can ask for those prompts; the direct console command is mainly useful to prove policy denies it when the gates are missing.

## Desktop window

```bash
visionai-ui
```

Opens a minimal window: a command input, a Run button, a Stop button, Diagnostics and Settings buttons, a result area, an audit history list, and a tray icon. Type any of the same commands shown above (e.g. `open notepad`, `what time is it`) and press Enter or click Run. This is not the full application window described for later phases, but every command it runs goes through the same `TextCommandPlanner`, policy engine, and dispatcher as the console, so nothing typed into the window can do anything the console commands above cannot already do.

The first time the window opens, a one-time welcome dialog explains the safety model (read-only actions run immediately, sensitive actions ask for permission once, actions with side effects ask for confirmation each time). It does not appear again after that.

The Stop button requests cooperative cancellation and stays clickable even while a command is running, unlike the command input and Run button. Since the registered commands currently complete quickly, clicking it while nothing is running just reports that no operation is active.

The Diagnostics button shows a read-only status summary: app/library versions, registered capability count, tray availability, current state, and which input subsystems are still disconnected.

The Settings button lets you change the log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`), choose an enumerated microphone device, and edit the wake word. Choices are saved locally; log-level changes apply immediately. Invalid wake words are rejected. If microphone enumeration is unavailable, the default microphone remains available. `log_dir`/`data_dir` remain environment-only (see `.env.example`) since changing a storage path at runtime isn't supported. Settings cannot grant permissions or enable raw audio/camera retention.

If a command requires confirmation, the window asks before executing it. Choosing No cancels the pending request; choosing Yes sends the bound confirmation back through the orchestrator and dispatcher. If a command also or instead requires permission, the window asks to grant that first ("Grant permission") -- granting can still be followed by a separate confirmation prompt if the same command needs both. `clear history` is the first built-in command that exercises both prompts.

The window also has a system tray icon (a placeholder icon for now, not final branding). Left-clicking it shows or hides the window; right-clicking opens a menu with "Show VisionAI" and "Quit". Closing the window (the title bar's close button) minimizes it to the tray instead of exiting, so VisionAI keeps running in the background -- use the tray menu's "Quit" to actually exit.

Use the previous prototype only as untrusted reference material during migration.
