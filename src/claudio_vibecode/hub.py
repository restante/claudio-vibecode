"""In-memory state of the remote: sessions, transcript, queued commands, pending approvals."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import deque

MAX_EVENTS = 200
SNAPSHOT_EVENTS = 80
TEXT_LIMIT = 3000
STALE_AFTER = 30  # seconds without a poll before a session shows as offline
APPROVAL_TTL = 180
LISTEN_TTL = 120  # Listen survives a phone that sleeps or reloads for this long
PHONE_RECENT = 300  # a phone counts as "there" for this long after its last request


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


RISKY_BASH = re.compile(
    r"\b(rm|sudo|su|dd|mkfs|chmod|chown|curl|wget|nc|ssh|scp|rsync|kill|killall|pkill|"
    r"git\s+(push|reset|clean|checkout\s+--|branch\s+-D)|npm\s+publish|docker|brew|pip|npm\s+i)\b"
    r"|[|;&]\s*(sh|bash|zsh)\b|>\s*/|\|\s*sh\b|`|\$\("
)


def is_risky(tool: str, tool_input: object, cwd: str = "") -> bool:
    """True when approving from a phone should need a second confirm."""
    data = tool_input if isinstance(tool_input, dict) else {}
    if tool == "Bash":
        return bool(RISKY_BASH.search(str(data.get("command", ""))))
    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        path = str(data.get("file_path", ""))
        return not path or (bool(cwd) and not _inside(path, cwd))
    if tool.startswith("mcp__") or tool in {"WebFetch", "Task", "Agent"}:
        return True
    return False


def _inside(path: str, folder: str) -> bool:
    norm = lambda p: os.path.normcase(os.path.normpath(p))  # noqa: E731 - Windows: case, slashes
    root = norm(folder)
    return norm(path) == root or norm(path).startswith(root.rstrip("\\/") + os.sep)


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
    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.version = 0
        self.sessions: dict[str, dict] = {}
        self.events: deque[dict] = deque(maxlen=MAX_EVENTS)
        self.commands: dict[str, deque[dict]] = {}
        self.approvals: dict[str, dict] = {}
        self.away = False
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

    # ---- commands (phone -> mod) ----
    def push_command(self, session: str, command: dict) -> bool:
        with self.cv:
            if session not in self.sessions:
                return False
            self.commands.setdefault(session, deque()).append(command)
            self.cv.notify_all()
            return True

    def poll(self, session: str, wait: float = 0.0) -> dict:
        """Mod side: queued commands for this session, plus the away/phone flags."""
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
        phone = time.time() - self.phone_seen < PHONE_RECENT
        return {"commands": commands, "away": self.away, "phone": phone, "known": known}

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

    # ---- approvals ----
    def create_approval(self, session: str, tool: str, tool_input: object) -> dict:
        with self.cv:
            cwd = self.sessions.get(session, {}).get("cwd", "")
            approval = {
                "id": uuid.uuid4().hex[:12],
                "session": session,
                "tool": tool,
                "input": tool_input,
                "risky": is_risky(tool, tool_input, cwd),
                "status": "pending",
                "ts": time.time(),
            }
            self.approvals[approval["id"]] = approval
            self._bump()
        self.add_event(
            session, "approval", f"{tool}: {_describe(tool_input)}", approval=approval["id"]
        )
        return approval

    def decide(self, ident: str, allow: bool, confirm: bool = False) -> str:
        """Phone side. Returns 'ok', 'gone' or 'confirm' (risky: tap again to confirm)."""
        with self.cv:
            approval = self.approvals.get(ident)
            if not approval or approval["status"] != "pending":
                return "gone"
            if allow and approval["risky"] and not confirm:
                return "confirm"
            approval["status"] = "allow" if allow else "deny"
            self._bump()
        self.add_event(
            approval["session"], "info", f"{'Approved' if allow else 'Denied'}: {approval['tool']}"
        )
        return "ok"

    def expire_approval(self, ident: str) -> None:
        with self.cv:
            approval = self.approvals.get(ident)
            if approval and approval["status"] == "pending":
                approval["status"] = "expired"
                self._bump()

    def wait_approval(self, ident: str, wait: float) -> str:
        deadline = time.time() + wait
        with self.cv:
            while True:
                approval = self.approvals.get(ident)
                if not approval:
                    return "gone"
                if approval["status"] != "pending":
                    return approval["status"]
                if time.time() - approval["ts"] > APPROVAL_TTL:
                    approval["status"] = "expired"
                    self._bump()
                    return "expired"
                left = deadline - time.time()
                if left <= 0:
                    return "pending"
                self.cv.wait(min(left, 1.0))

    # ---- phone side views ----
    def touch_phone(self) -> None:
        self.phone_seen = time.time()

    def set_away(self, on: bool) -> None:
        with self.cv:
            self.away = on
            self._bump()

    def snapshot(self) -> dict:
        with self.cv:
            now = time.time()
            for ident in [i for i, a in self.approvals.items() if now - a["ts"] > 3600]:
                del self.approvals[ident]
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
                "away": self.away,
                "listening": self.listening(),
                "local": self.local_sound,
                "audio": [m for m in self.clip_meta if now - m["ts"] < 120],
                "sessions": sessions,
                "events": list(self.events)[-SNAPSHOT_EVENTS:],
                "approvals": [a for a in self.approvals.values() if a["status"] == "pending"],
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


def _describe(tool_input: object) -> str:
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "url", "pattern", "description"):
            if key in tool_input:
                return str(tool_input[key])[:600]
    return str(tool_input)[:600]
