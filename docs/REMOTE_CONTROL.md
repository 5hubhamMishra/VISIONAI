# Phone access to this project

Status on 2026-09-05: phone pairing and an end-to-end phone command are **not
verified**. Repository instructions are saved in `AGENTS.md`, so you do not
need to repeat the autonomous-work preference in a new project session.

## One-time connection

1. In the desktop Codex/ChatGPT app, open **Settings > Connections > Control
   this PC**, then **Set up** or **Add**.
2. Scan its QR code with your phone. Finish setup in the updated ChatGPT app
   using the same account and workspace; complete any authentication requested.
3. In **Remote** on the phone, select this PC, then this project/chat. The
   repository folder on this PC is `demo/visionai`.
4. Keep the desktop app running and the PC online and awake. Use the connection
   setting to keep it awake while plugged in, where available.

These steps follow [official Remote documentation](https://learn.chatgpt.com/docs/remote-connections).
The installed desktop-bundled CLI reports `0.137.0-alpha.4`; its remote-control
help exposes start/stop, but no pairing command. Desktop pairing is the route
documented here; starting a separate CLI daemon is not proof of phone pairing.

## Confirm it works

From the phone, ask this project chat to report the current Git commit. A
successful response from this PC verifies the path. Until then, do not mark
the connection complete. Authentication and scanning must occur on your phone.

The saved preference controls how an active session works. It does not create
an unattended schedule, and it does not bypass required platform approvals.
