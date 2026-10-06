"""Start and stop the hub, pair phones, and talk to a running hub (used by the CLI and the mod)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import psutil

from claudio_vibecode import DEFAULT_PORT, auth, paths, qr, voicekey


def _port() -> int:
    return int(os.environ.get("CLAUDIO_VIBECODE_PORT", DEFAULT_PORT))


def _info_file() -> Path:
    return auth.remote_dir() / "hub.json"


def lan_ip() -> str:
    """This machine's address on the local network (no packet is sent)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def running() -> dict | None:
    """The live hub's {pid, port, url}, or None."""
    try:
        info = json.loads(_info_file().read_text())
        proc = psutil.Process(info["pid"])
        if proc.is_running() and abs(proc.create_time() - info["created"]) < 2:
            return info
    except (OSError, ValueError, KeyError, psutil.Error):
        pass
    return None


def _call(path: str, body: dict | None = None, port: int | None = None, timeout: float = 5):
    info = running()
    port = port or (info["port"] if info else _port())
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={"X-Claudio-Mod": auth.mod_token(), "Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback
        return json.load(response)


def start() -> dict:
    info = running()
    if info:
        return info
    port = _port()
    host = "0.0.0.0"  # noqa: S104 - the phone is on the LAN; every route but /pair needs pairing
    url = f"http://{lan_ip()}:{port}"
    log = open(paths.state_dir() / "hub.log", "ab")  # noqa: SIM115 - handed to the child
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": log}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    child = subprocess.Popen(
        [sys.executable, "-m", "claudio_vibecode", "_serve", "--host", host,
         "--port", str(port), "--url", url],
        **kwargs,
    )  # fmt: skip
    info = {
        "pid": child.pid,
        "created": psutil.Process(child.pid).create_time(),
        "port": port,
        "url": url,
    }
    _info_file().write_text(json.dumps(info))
    for _ in range(50):  # wait up to 5 s for the port to answer
        try:
            _call("/api/admin/status", port=port, timeout=1)
            return info
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise SystemExit(f"the hub did not start; see {paths.state_dir() / 'hub.log'}")


def stop() -> bool:
    info = running()
    if not info:
        return False
    try:
        _call("/api/admin/shutdown", {}, timeout=3)
    except (urllib.error.URLError, OSError):
        try:
            psutil.Process(info["pid"]).terminate()
        except psutil.Error:
            pass
    voicekey.hold(False)
    _info_file().unlink(missing_ok=True)
    return True


def pairing(invert: bool = False, open_browser: bool = False) -> str:
    info = start()
    made = _call("/api/admin/pair", {})
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{info['port']}/pair")
    lines = [
        "Scan this with your phone camera (same Wi-Fi). One use, expires in 5 minutes.",
        "",
        qr.text(made["url"], invert=invert),
        "",
        made["url"],
    ]
    ok, why = voicekey.available()
    if not ok:
        lines += ["", f"Voice button: {why}"]
    return "\n".join(lines)


def _tailscale() -> str | None:
    try:
        done = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        return done.stdout.split()[0] if done.returncode == 0 and done.stdout.split() else None
    except (OSError, subprocess.SubprocessError):
        return None
