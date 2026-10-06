"""Pairing codes and per-device tokens. A paired device can make Claude run tools: treat it so."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

from claudio_vibecode import paths

CODE_TTL = 300  # seconds a pairing code (the QR) stays valid
_ATTEMPTS = 10  # pairing tries per minute per client


def remote_dir() -> Path:
    return paths.state_dir()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mod_token() -> str:
    """Secret the mod and the CLI use to talk to the hub (a browser page can never send it)."""
    path = remote_dir() / "mod-token"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()


class Devices:
    def __init__(self, directory: Path | None = None) -> None:
        self._file = (directory or remote_dir()) / "devices.json"
        self._lock = threading.Lock()
        self._codes: dict[str, float] = {}
        self._tries: dict[str, list[float]] = {}

    def _load(self) -> dict:
        try:
            return json.loads(self._file.read_text())
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self._file.write_text(json.dumps(data, indent=2))
        try:
            self._file.chmod(0o600)
        except OSError:
            pass

    def new_code(self) -> str:
        code = secrets.token_urlsafe(9)
        with self._lock:
            now = time.time()
            self._codes = {c: t for c, t in self._codes.items() if t > now}
            self._codes[code] = now + CODE_TTL
        return code

    def pair(self, code: str, name: str, client: str = "") -> str | None:
        """Swap a valid one-time code for a device token; None if the code is bad or spent."""
        with self._lock:
            now = time.time()
            tries = [t for t in self._tries.get(client, []) if t > now - 60]
            tries.append(now)
            self._tries[client] = tries
            if len(tries) > _ATTEMPTS:
                return None
            expiry = self._codes.pop(code, 0)
            if expiry < now:
                return None
            token = secrets.token_urlsafe(32)
            data = self._load()
            data[_hash(token)] = {"name": (name or "phone")[:40], "created": now, "last": now}
            self._save(data)
            return token

    def check(self, token: str | None) -> bool:
        if not token:
            return False
        key = _hash(token)
        with self._lock:
            data = self._load()
            if key not in data:
                return False
            if time.time() - data[key].get("last", 0) > 60:  # don't rewrite the file every call
                data[key]["last"] = time.time()
                self._save(data)
            return True

    def listing(self) -> list[dict]:
        with self._lock:
            return [
                {"id": k[:8], "name": v["name"], "created": v["created"], "last": v["last"]}
                for k, v in self._load().items()
            ]

    def revoke(self, ident: str) -> int:
        """Remove devices whose id or name matches; returns how many."""
        with self._lock:
            data = self._load()
            gone = [k for k, v in data.items() if k.startswith(ident) or v["name"] == ident]
            for k in gone:
                del data[k]
            self._save(data)
            return len(gone)
