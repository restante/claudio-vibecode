"""In-memory state of the remote: sessions, transcript, queued commands, audio clips."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

MAX_EVENTS = 200
SNAPSHOT_EVENTS = 80
TEXT_LIMIT = 3000
STALE_AFTER = 30  # seconds without a poll before a session shows as offline
LISTEN_TTL = 120  # Listen survives a phone that sleeps or reloads for this long

# Attachments from the phone are saved in the session's project folder, so Claude can open them
# without asking for permission. The folder ignores itself in git.
UPLOAD_DIR = ".claudio-uploads"
UPLOAD_TTL = 24 * 3600
MAX_UPLOAD = 20_000_000
MAX_SESSION_BYTES = 100_000_000
UPLOAD_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt", ".md", ".json", ".csv", ".log",
    ".yaml", ".yml", ".xml", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".py", ".swift",
    ".kt", ".java", ".go", ".rs", ".rb", ".sh", ".sql", ".toml", ".ini", ".diff", ".patch",
}  # fmt: skip


class UploadError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def safe_name(name: str) -> str:
    """The file name only: no folders, and only characters that are safe in a path."""
    base = re.split(r"[\\/]", name)[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return (base or "file")[-80:]


def session_title(pid: int) -> str:
    """The name you gave the session (/rename), which Claude keeps in `sessions/<pid>.json`."""
    from claudio_vibecode import paths, voicekey

    for candidate in voicekey.ancestors(pid) or ([pid] if pid else []):
        try:
            data = json.loads((paths.claude_dir() / "sessions" / f"{candidate}.json").read_text())
        except (OSError, ValueError):
            continue
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name.strip():
            return name.strip()
    return ""


def tts_muted(session: str) -> bool | None:
    """Whether claudio-tts has this session muted; None if claudio-tts does not say."""
    try:
        from claudio_tts import sessionstate
    except ImportError:  # an older claudio-tts
        return None
    value = sessionstate.read(session).get("muted")
    return value if isinstance(value, bool) else None


def _clip(text: str) -> str:
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "\n[...]"


class Hub:
    mic = False  # set by the server when the page is served over https (Tailscale)

    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.version = 0
        self.sessions: dict[str, dict] = {}
        self.events: deque[dict] = deque(maxlen=MAX_EVENTS)
        self.commands: dict[str, deque[dict]] = {}
        self.phone_seen = 0.0
        self.mod_seen = 0.0
        self._seq = 0
        self.clips: dict[str, bytes] = {}
        self.clip_meta: deque[dict] = deque(maxlen=60)
        self.listen_until = 0.0
        self.mute_hold: dict[str, float] = {}  # session -> until: a phone mute is on its way
        self.local_sound = (
            True  # whether the computer's own speakers also play while a phone listens
        )
        self.uploads: dict[str, dict] = {}  # id -> {session, path, name, size, ts}

    def _bump(self) -> None:
        self.version += 1
        self.cv.notify_all()

    # ---- sessions (mod side) ----
    def register(
        self, session: str, name: str, term: str = "", cwd: str = "", pid: int = 0
    ) -> None:
        with self.cv:
            old = self.sessions.get(session, {})
            self.sessions[session] = {
                "id": session,
                "name": name or session[:8],
                "term": term,
                "cwd": cwd,
                "pid": pid,
                "status": old.get("status", "idle"),
                "last": old.get("last", 0),
                "draft": old.get("draft", ""),
                "muted": old.get("muted"),
                "seen": time.time(),
            }
            self.commands.setdefault(session, deque())
            self._bump()

    def unregister(self, session: str) -> None:
        with self.cv:
            self.sessions.pop(session, None)
            self.commands.pop(session, None)
            self._bump()

    def set_draft(self, session: str, text: str) -> None:
        """What is typed (or dictated) in this session's prompt box right now."""
        with self.cv:
            if session in self.sessions and self.sessions[session].get("draft") != text[:4000]:
                self.sessions[session]["draft"] = text[:4000]
                self._bump()

    def set_muted(self, session: str, muted: bool) -> None:
        with self.cv:
            if session in self.sessions and self.sessions[session].get("muted") != muted:
                self.sessions[session]["muted"] = muted
                self._bump()

    def set_status(self, session: str, status: str) -> None:
        with self.cv:
            if session in self.sessions and self.sessions[session]["status"] != status:
                self.sessions[session]["status"] = status
                self._bump()

    def add_event(self, session: str, kind: str, text: str = "", **extra: object) -> dict:
        with self.cv:
            self._seq += 1
            event = {
                "seq": self._seq,
                "session": session,
                "kind": kind,
                "text": _clip(text),
                "ts": time.time(),
                **extra,
            }
            self.events.append(event)
            if session in self.sessions:
                self.sessions[session]["last"] = event["ts"]
            self._bump()
            return event

    # ---- attachments (phone -> project folder) ----
    def add_upload(self, session: str, name: str, data: bytes) -> dict:
        with self.cv:
            info = dict(self.sessions.get(session) or {})
        if not info:
            raise UploadError(409, "that session is not connected")
        cwd = Path(info.get("cwd") or "")
        if not info.get("cwd") or not cwd.is_dir():
            raise UploadError(409, "the session's folder is not available")
        clean = safe_name(name)
        if Path(clean).suffix.lower() not in UPLOAD_EXTENSIONS:
            raise UploadError(415, "that kind of file is not accepted")
        if not data:
            raise UploadError(400, "the file is empty")
        if len(data) > MAX_UPLOAD:
            raise UploadError(413, "the file is too large")
        self.cleanup_uploads()
        with self.cv:
            used = sum(u["size"] for u in self.uploads.values() if u["session"] == session)
        if used + len(data) > MAX_SESSION_BYTES:
            raise UploadError(413, "too many attachments for this session; try again later")
        folder = cwd / UPLOAD_DIR
        folder.mkdir(exist_ok=True)
        ignore = folder / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        ident = uuid.uuid4().hex[:8]
        path = folder / f"{ident}-{clean}"
        if path.resolve().parent != folder.resolve():
            raise UploadError(400, "bad file name")
        path.write_bytes(data)
        with self.cv:
            self.uploads[ident] = {
                "session": session,
                "path": str(path),
                "name": clean,
                "size": len(data),
                "ts": time.time(),
            }
        return {"id": ident, "name": clean, "size": len(data)}

    def resolve_uploads(self, session: str, ids: object) -> list[dict]:
        """Saved files for ids this session was given. The phone never names a path."""
        found: list[dict] = []
        if not isinstance(ids, list):
            return found
        with self.cv:
            for ident in ids[:8]:
                item = self.uploads.get(str(ident))
                if item and item["session"] == session and Path(item["path"]).is_file():
                    found.append({"name": item["name"], "path": item["path"]})
        return found

    def cleanup_uploads(self) -> None:
        """Delete attachments older than a day, and a project folder left with nothing in it."""
        cutoff = time.time() - UPLOAD_TTL
        with self.cv:
            old = [i for i, u in self.uploads.items() if u["ts"] < cutoff]
            gone = [self.uploads.pop(i) for i in old]
        for item in gone:
            path = Path(item["path"])
            path.unlink(missing_ok=True)
            folder = path.parent
            try:
                if folder.name == UPLOAD_DIR and [p.name for p in folder.iterdir()] == [
                    ".gitignore"
                ]:
                    (folder / ".gitignore").unlink()
                    folder.rmdir()
            except OSError:
                pass

    # ---- commands (phone -> mod) ----
    def push_command(self, session: str, command: dict) -> bool:
        with self.cv:
            if session not in self.sessions:
                return False
            self.commands.setdefault(session, deque()).append(command)
            self.cv.notify_all()
            return True

    def poll(self, session: str, wait: float = 0.0) -> dict:
        """Mod side: queued commands for this session."""
        deadline = time.time() + wait
        with self.cv:
            self.mod_seen = time.time()
            if session not in self.sessions:
                return self._poll_reply([], known=False)
            self.sessions[session]["seen"] = self.mod_seen
            self._sync_muted(session)
            while True:
                queue = self.commands.get(session)
                if queue:
                    commands = list(queue)
                    queue.clear()
                    return self._poll_reply(commands)
                left = deadline - time.time()
                if left <= 0:
                    return self._poll_reply([])
                self.cv.wait(min(left, 1.0))

    def hold_mute(self, session: str) -> None:
        self.mute_hold[session] = time.time() + 8

    def _sync_muted(self, session: str) -> None:
        if time.time() < self.mute_hold.get(session, 0):
            return  # the phone just asked; claudio-tts has not caught up yet
        muted = tts_muted(session)
        if self.sessions[session].get("muted") != muted:
            self.sessions[session]["muted"] = muted
            self._bump()

    def _poll_reply(self, commands: list[dict], known: bool = True) -> dict:
        return {"commands": commands, "known": known}

    # ---- audio to the phone ----
    def add_clip(self, session: str, wav: bytes) -> str:
        with self.cv:
            ident = uuid.uuid4().hex[:12]
            self.clips[ident] = wav
            self.clip_meta.append({"id": ident, "session": session, "ts": time.time()})
            live = {m["id"] for m in self.clip_meta}
            for old in [i for i in self.clips if i not in live]:
                del self.clips[old]
            self._bump()
            return ident

    def clip(self, ident: str) -> bytes | None:
        with self.cv:
            return self.clips.get(ident)

    def listen(self, on: bool) -> None:
        with self.cv:
            was = self.listening()
            self.listen_until = time.time() + LISTEN_TTL if on else 0.0
            if was != self.listening():
                self._bump()

    def set_local_sound(self, on: bool) -> None:
        with self.cv:
            self.local_sound = on
            self._bump()

    def listening(self) -> bool:
        return time.time() < self.listen_until

    # ---- phone side views ----
    def touch_phone(self) -> None:
        self.phone_seen = time.time()

    def snapshot(self) -> dict:
        with self.cv:
            now = time.time()
            sessions = [
                {
                    **s,
                    "name": (session_title(s["pid"]) if s.get("pid") else "") or s["name"],
                    "online": now - s["seen"] < STALE_AFTER,
                }
                for s in self.sessions.values()
                if now - s["seen"] < 6 * 3600
            ]
            return {
                "version": self.version,
                "listening": self.listening(),
                "local": self.local_sound,
                "mic": self.mic,
                "audio": [m for m in self.clip_meta if now - m["ts"] < 120],
                "sessions": sessions,
                "events": list(self.events)[-SNAPSHOT_EVENTS:],
            }

    def wait_change(self, version: int, wait: float) -> int:
        deadline = time.time() + wait
        with self.cv:
            while self.version == version:
                left = deadline - time.time()
                if left <= 0:
                    break
                self.cv.wait(left)
            return self.version
