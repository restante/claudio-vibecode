# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Remote control for Claude Code from a phone browser. A Python hub serves a plain-HTML page on the LAN. A Claude Code "mod" (TypeScript hooks) forwards session events to the hub and carries out what the phone asks for.

## Commands

```bash
bash install.sh --dev          # link the mod + install the package editable into claudio-tts's venv
pytest -q                      # all tests
pytest tests/test_vibecode.py -k <name>   # one test
ruff check . && ruff format --check .     # lint + format (line length 100)
claude plugin validate src/claudio_vibecode/mod && claude plugin test src/claudio_vibecode/mod   # mod checks
claudio-vibecode doctor | status          # diagnostics (paste both in bug reports)
```

CI runs ruff and pytest on Linux, macOS and Windows, plus a hub smoke test (install-mod, start, qr, status, stop, uninstall-mod). `claudio-tts` is installed from git (`CLAUDIO_TTS_REF` picks the ref).

## Architecture

- **Mod** (`src/claudio_vibecode/mod/hooks/register.ts`): runs inside Claude Code. Handles `/vibe` commands and forwards events to the hub over loopback. It calls the Python package with `python -m claudio_vibecode <cmd>`. `install-mod` sets `CLAUDIO_VIBECODE_PYTHON` so the mod finds the right interpreter. All OS-specific work stays in Python.
- **Hub** (`hub.py`): in-memory state only: sessions, transcript events, queued phone commands, pending approvals. Also holds the risky-command regex that forces a second tap.
- **Server** (`server.py`): stdlib `ThreadingHTTPServer` with three route groups: phone routes (cookie token), mod routes (`X-Claudio-Mod` header), admin routes (loopback only). Stops itself after 8 idle hours.
- **Control** (`ctl.py`, `cli.py`): start/stop the hub, pairing and QR, and talking to a running hub. `hub.json` in the state dir records the running hub.
- **Auth** (`auth.py`): one-time pairing code (5 min) swapped for a per-device token, stored hashed.
- **Voice key** (`voicekey.py`): "Hold to talk" presses Claude Code's voice key in the front window (needs Accessibility on macOS, `xdotool` on Linux).
- **Audio** (`audiolink.py`): registered as the `claudio_tts.sinks` entry point `phone` in `pyproject.toml`. Turns each sentence into a WAV clip for the hub.
- **Phone page** (`web/index.html`): single file, no build step, no external requests.
- **Paths** (`paths.py`): reuses claudio-tts's data and Claude config dirs, so both packages share one venv and install root.

Env vars: `CLAUDIO_VIBECODE_PORT`, `CLAUDIO_VIBECODE_IDLE_HOURS`, `CLAUDIO_TTS_HOME`, `CLAUDE_CONFIG_DIR`.

## Rules to keep

- Standard library only for HTTP. Do not add dependencies without a reason.
- Every route needs a token except the static page and `/pair`, which answers on the computer only.
- Off by default. Anything that lets the phone make Claude act needs a paired device and must be documented.
- `HTTPServer.server_bind` is overridden to skip the DNS lookup (it stalled on some networks). Keep that.
- Windows differs: `allow_reuse_address` is off there (it lets a second hub steal the port). Tests read child output as UTF-8 bytes.
- Update `CHANGELOG.md` for user-visible changes.
