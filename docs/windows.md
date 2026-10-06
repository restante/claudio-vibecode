# Windows (beta)

claudio-vibecode runs on Windows 10 and 11 but has so far been verified only by automated tests on Windows
runners, not on a real PC. Please open an issue with the output of `claudio-vibecode doctor` if something is off.

- The first time, **Windows Defender Firewall asks** whether `python.exe` may talk on the network. Allow it on
  **Private networks** only, or your phone cannot reach the page.
- **Hold to talk** sends a real Space key press and first brings your terminal window forward (it walks up from
  Claude's process to the window that owns it). If Claude Code runs as administrator, Windows blocks key presses
  from a normal program: start Claude Code normally.
- Windows Terminal, PowerShell and cmd all work. Keep the screen unlocked for Hold to talk.
- `claudio-vibecode status` shows the address and whether the voice button is ready.
- Run `& "$env:LOCALAPPDATA\claudio-tts\venv\Scripts\python.exe" -m claudio_vibecode doctor` to check the install.
