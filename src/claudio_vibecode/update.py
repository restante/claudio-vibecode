"""Check GitHub for a newer release and, only when asked, install it."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from claudio_vibecode import __version__, ctl, paths

REPO = "restante/claudio-vibecode"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_SECONDS = 24 * 3600
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
MANUAL = f"curl -fsSL {RAW}/install.sh | bash   (Windows: irm {RAW}/install.ps1 | iex)"


def parse_version(text: str) -> tuple[int, ...] | None:
    """`v0.4.0` or `0.4.0` -> (0, 4, 0); None if it is not a plain dotted number."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(p) for p in match.group(1).split(".")) if match else None


def is_newer(latest: str, current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return a is not None and b is not None and a > b


def _cache_file() -> Path:
    return paths.state_dir() / "update-check.json"


def _fetch() -> dict | None:
    request = urllib.request.Request(
        API, headers={"Accept": "application/vnd.github+json", "User-Agent": "claudio-vibecode"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed https URL
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or parse_version(tag) is None:
        return None
    return {"tag": tag, "url": data.get("html_url", ""), "notes": data.get("body") or ""}


def latest_release(use_cache: bool = True) -> dict | None:
    """The newest release ({tag, url, notes}), cached for 24 h; None when unknown (offline)."""
    cache = _cache_file()
    if use_cache:
        try:
            saved = json.loads(cache.read_text())
            if time.time() - saved["checked"] < CACHE_SECONDS:
                return saved["release"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    release = _fetch()
    try:
        cache.write_text(json.dumps({"checked": time.time(), "release": release}))
    except OSError:
        pass
    return release


def _uv() -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (Path.home() / ".local" / "bin" / "uv", Path.home() / ".cargo" / "bin" / "uv"):
        for path in (candidate, candidate.with_suffix(".exe")):
            if path.exists():
                return str(path)
    return None


def install(tag: str) -> int:
    """Install release `tag` into this environment and refresh the mod. Returns an exit code."""
    uv = _uv()
    if uv is None:
        print("error: `uv` was not found, so I can't update in place.", file=sys.stderr)
        print(f"Re-run the installer instead:\n  {MANUAL}", file=sys.stderr)
        return 1
    was_running = ctl.running() is not None
    ctl.stop()  # on Windows a running hub locks the files being replaced
    spec = f"claudio-vibecode @ git+https://github.com/{REPO}@{tag}"
    done = subprocess.run([uv, "pip", "install", "-q", "--python", sys.executable, spec])
    restart = [sys.executable, "-m", "claudio_vibecode", "start"]
    if done.returncode != 0:
        print("error: the update failed; your current version is unchanged.", file=sys.stderr)
        print(f"Try the installer:\n  {MANUAL}", file=sys.stderr)
        if was_running:
            subprocess.run(restart, check=False)
        return 1
    # Run the NEW code to copy the mod, not the modules this process already loaded.
    done = subprocess.run(
        [sys.executable, "-m", "claudio_vibecode", "install-mod", "--python", sys.executable]
    )
    if was_running:
        subprocess.run(restart, check=False)
    return done.returncode


def run(check: bool, yes: bool, quiet: bool) -> int:
    release = latest_release(use_cache=quiet or check)
    if release is None:
        if not quiet:
            print("Could not reach GitHub to look for updates.")
        return 0
    newer = is_newer(release["tag"])
    if quiet:
        if newer:
            tag = release["tag"].lstrip("v")
            print(f"claudio-vibecode {tag} is available (you have {__version__})")
        return 10 if newer else 0
    if not newer:
        print(f"claudio-vibecode {__version__} is up to date.")
        return 0
    print(f"claudio-vibecode {release['tag'].lstrip('v')} is available (you have {__version__}).")
    if release["url"]:
        print(f"Release notes: {release['url']}")
    if not yes:
        print("Run `claudio-vibecode update --yes` (or /vibe update in Claude Code) to install it.")
        return 10 if check else 0
    code = install(release["tag"])
    if code == 0:
        print(
            f"Updated {__version__} -> {release['tag'].lstrip('v')}. Restart open Claude sessions."
        )
    return code
