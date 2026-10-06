"""The `claudio-vibecode` command line. The Claude mod is a thin shim over it."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path

from claudio_vibecode import DEFAULT_PORT, __version__, auth, ctl, paths, server, update, voicekey


def cmd_serve(a: argparse.Namespace) -> int:
    server.serve(a.host, a.port, a.url)
    return 0


def cmd_start(a: argparse.Namespace) -> int:
    info = ctl.start()
    print(f"Vibecode is on: {info['url']}")
    print("Pair a phone with: claudio-vibecode qr")
    return 0


def cmd_stop(a: argparse.Namespace) -> int:
    print("Vibecode is off." if ctl.stop() else "Vibecode was not running.")
    return 0


def cmd_info(a: argparse.Namespace) -> int:  # for the mod
    info = ctl.running()
    reply = {
        "running": bool(info),
        "port": info["port"] if info else 0,
        "token": auth.mod_token() if info else "",
        "pid": os.getppid(),  # the Claude process that ran this; its parents own the window
    }
    print(json.dumps(reply))
    return 0 if info else 1


def cmd_qr(a: argparse.Namespace) -> int:
    print(ctl.pairing(invert=a.invert, open_browser=not a.no_browser))
    return 0


def _need_hub() -> dict | None:
    info = ctl.running()
    if not info:
        print("Vibecode is off. Turn it on with: claudio-vibecode start")
    return info


def cmd_status(a: argparse.Namespace) -> int:
    info = _need_hub()
    if not info:
        return 1
    status = ctl._call("/api/admin/status")
    print(f"Vibecode is on: {status['url']}")
    print(f"Paired phones: {status['devices']}   Away mode: {'on' if status['away'] else 'off'}")
    print(f"Sessions connected: {', '.join(status['sessions']) or 'none'}")
    tail = ctl._tailscale()
    if tail:
        print(f"Tailscale address (encrypted, works away from home): http://{tail}:{info['port']}")
    ok, why = voicekey.available()
    print("Voice button: ready" if ok else f"Voice button: {why}")
    return 0


def cmd_devices(a: argparse.Namespace) -> int:
    if not _need_hub():
        return 1
    rows = ctl._call("/api/admin/devices")
    for row in rows:
        print(f"{row['id']}  {row['name']}")
    print(f"{len(rows)} paired. Remove one with: claudio-vibecode revoke <id or name>")
    return 0


def cmd_revoke(a: argparse.Namespace) -> int:
    if not _need_hub():
        return 1
    print(f"Removed {ctl._call('/api/admin/revoke', {'id': a.value})['revoked']} device(s).")
    return 0


def cmd_away(a: argparse.Namespace) -> int:
    if not _need_hub():
        return 1
    on = a.value == "on"
    ctl._call("/api/admin/away", {"on": on})
    print(f"Away mode {'on: tool approvals go to your phone' if on else 'off'}.")
    return 0


def cmd_update(a: argparse.Namespace) -> int:
    return update.run(check=a.check, yes=a.yes, quiet=a.quiet)


def cmd_doctor(a: argparse.Namespace) -> int:
    failed = False

    def check(ok: bool, label: str, hint: str = "") -> None:
        nonlocal failed
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + (f"  ({hint})" if hint and not ok else ""))
        failed = failed or not ok

    print(f"claudio-vibecode {__version__}")
    try:
        import claudio_tts

        check(True, f"claudio-tts {claudio_tts.__version__} installed")
    except ImportError:
        check(False, "claudio-tts installed", "https://github.com/restante/claudio-tts")
    ok, why = voicekey.available()
    check(ok, "voice button (keyboard access)", why)
    print(f"  info  hub is {'on' if ctl.running() else 'off (it is off until you type /vibe)'}")
    mod = paths.claude_dir() / "mods" / "claudio-vibecode"
    check(mod.exists(), f"mod installed at {mod}", "run: claudio-vibecode install-mod")
    print("All good." if not failed else "Some checks failed.")
    return 1 if failed else 0


def cmd_install_mod(a: argparse.Namespace) -> int:
    from claudio_tts import install_mod

    result = install_mod.install(
        a.python or sys.executable,
        claude_dir=Path(a.claude_dir) if a.claude_dir else None,
        link=a.link,
        source=paths.mod_source(),
        name="claudio-vibecode",
        python_var="CLAUDIO_VIBECODE_PYTHON",
    )
    print(f"Mod {'linked' if result['linked'] else 'installed'} at {result['mod']}")
    return 0


def cmd_uninstall_mod(a: argparse.Namespace) -> int:
    from claudio_tts import install_mod

    result = install_mod.uninstall(
        claude_dir=Path(a.claude_dir) if a.claude_dir else None,
        name="claudio-vibecode",
        python_var="CLAUDIO_VIBECODE_PYTHON",
    )
    print(f"Removed {result['mod']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claudio-vibecode", description="Run Claude Code from your phone."
    )
    parser.add_argument("--version", action="version", version=f"claudio-vibecode {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("_serve")
    p.add_argument("--host", default="0.0.0.0")  # noqa: S104 - the phone is on the LAN
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--url", default="")
    p.set_defaults(func=cmd_serve)

    sub.add_parser("start", help="start the hub").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the hub and close the port").set_defaults(func=cmd_stop)
    sub.add_parser("info").set_defaults(func=cmd_info)
    p = sub.add_parser("qr", help="show a QR code to pair a phone")
    p.add_argument("--invert", action="store_true", help="flip colours for a light terminal")
    p.add_argument("--no-browser", action="store_true", help="do not open the desktop page")
    p.set_defaults(func=cmd_qr)
    sub.add_parser("status", help="address, paired phones, sessions").set_defaults(func=cmd_status)
    sub.add_parser("devices", help="list paired phones").set_defaults(func=cmd_devices)
    p = sub.add_parser("revoke", help="remove a paired phone")
    p.add_argument("value", help="device id or name")
    p.set_defaults(func=cmd_revoke)
    p = sub.add_parser("away", help="send tool permission asks to the phone")
    p.add_argument("value", choices=["on", "off"])
    p.set_defaults(func=cmd_away)

    p = sub.add_parser("update", help="look for a newer release; install it with --yes")
    p.add_argument("--check", action="store_true", help="only look (exit 10 if newer exists)")
    p.add_argument("--yes", action="store_true", help="install the newer release")
    p.add_argument("--quiet", action="store_true", help="one line if newer, silent otherwise")
    p.set_defaults(func=cmd_update)

    sub.add_parser("doctor", help="check the installation").set_defaults(func=cmd_doctor)
    p = sub.add_parser("install-mod", help="install the Claude mod and register it")
    p.add_argument("--python")
    p.add_argument("--claude-dir")
    p.add_argument("--link", action="store_true", help="symlink instead of copy (development)")
    p.set_defaults(func=cmd_install_mod)
    p = sub.add_parser("uninstall-mod", help="remove the Claude mod")
    p.add_argument("--claude-dir")
    p.set_defaults(func=cmd_uninstall_mod)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252: the QR needs UTF-8
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (urllib.error.URLError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
