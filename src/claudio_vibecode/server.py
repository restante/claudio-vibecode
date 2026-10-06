"""The hub's HTTP server (standard library only): phone routes, mod routes, admin routes."""

from __future__ import annotations

import hmac
import json
import os
import socketserver
import sys
import threading
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from claudio_vibecode import auth, qr, voicekey
from claudio_vibecode import hub as hubmod

COOKIE = "ct"
IDLE_STOP = float(os.environ.get("CLAUDIO_VIBECODE_IDLE_HOURS", "8")) * 3600
LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"  # on Windows it lets a second hub steal the port

    def server_bind(self) -> None:
        # HTTPServer.server_bind() asks DNS for this host's name, which can stall for a minute on
        # some networks (seen on macOS CI). Nothing here needs the name.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = str(self.server_address[0]), self.server_address[1]

    def __init__(self, address: tuple[str, int], directory=None) -> None:
        super().__init__(address, Handler)
        self.hub = hubmod.Hub()
        self.devices = auth.Devices(directory)
        self.mod_token = auth.mod_token()
        self.base_url = ""  # what the QR points at; set by the launcher
        self.started = time.time()


def _page() -> bytes:
    return resources.files("claudio_vibecode").joinpath("web/index.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server: Server
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # quiet
        pass

    # ---- helpers ----
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: object, extra: dict | None = None) -> None:
        self._send(status, json.dumps(data).encode(), "application/json", extra)

    def _raw(self, limit: int = 1_000_000) -> bytes:
        length = min(int(self.headers.get("Content-Length") or 0), limit)
        return self.rfile.read(length) if length else b""

    def _body(self, raw: bytes | None = None) -> dict:
        raw = self._raw() if raw is None else raw
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _is_mod(self) -> bool:
        given = self.headers.get("X-Claudio-Mod", "")
        local = self.client_address[0] in LOOPBACK
        return local and hmac.compare_digest(given, self.server.mod_token)

    def _is_device(self, write: bool) -> bool:
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = jar[COOKIE].value if COOKIE in jar else None
        if not self.server.devices.check(token):
            return False
        if write:
            # A page on another site cannot send this header without a CORS preflight we refuse.
            if self.headers.get("X-Claudio") != "1":
                return False
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return False
        self.server.hub.touch_phone()
        return True

    def _deny(self) -> None:
        self._json(401, {"error": "not paired"})

    # ---- routes ----
    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        path = url.path
        if path in ("/", "/w", "/index.html"):
            return self._send(200, _page(), "text/html; charset=utf-8")
        if path == "/manifest.webmanifest":
            manifest = {
                "name": "Claudio vibecode", "short_name": "Claudio", "start_url": "/",
                "display": "standalone", "background_color": "#0f1115", "theme_color": "#0f1115",
            }  # fmt: skip
            return self._json(200, manifest)
        if path == "/pair":  # desktop page with a proper QR; this machine only
            if self.client_address[0] not in LOOPBACK:
                return self._json(403, {"error": "open this page on the computer"})
            return self._pair_page()
        if path == "/api/state":
            if not self._is_device(False):
                return self._deny()
            return self._json(200, self.server.hub.snapshot())
        if path.startswith("/api/audio/"):
            if not self._is_device(False):
                return self._deny()
            wav = self.server.hub.clip(path.rsplit("/", 1)[1])
            if wav is None:
                return self._json(404, {"error": "gone"})
            return self._send(200, wav, "audio/wav")
        if path == "/api/mod/listeners" and self._is_mod():
            hub = self.server.hub
            return self._json(200, {"listening": hub.listening(), "local": hub.local_sound})
        if path == "/api/stream":
            if not self._is_device(False):
                return self._deny()
            return self._stream()
        if path == "/api/mod/poll" and self._is_mod():
            session = query.get("session", [""])[0]
            wait = min(float(query.get("wait", ["0"])[0]), 25.0)
            return self._json(200, self.server.hub.poll(session, wait))
        if path.startswith("/api/mod/approval/") and self._is_mod():
            ident = path.rsplit("/", 1)[1]
            wait = min(float(query.get("wait", ["0"])[0]), 25.0)
            return self._json(200, {"status": self.server.hub.wait_approval(ident, wait)})
        if path == "/api/admin/devices" and self._is_mod():
            return self._json(200, self.server.devices.listing())
        if path == "/api/admin/status" and self._is_mod():
            return self._json(200, self._status())
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        path = url.path
        hub = self.server.hub
        if path == "/api/mod/audio":  # raw WAV from the player; not JSON
            if not self._is_mod():
                return self._json(403, {"error": "forbidden"})
            wav = self._raw(16_000_000)
            session = parse_qs(url.query).get("session", [""])[0]
            return self._json(200, {"id": hub.add_clip(session, wav)})
        body = self._body()
        if path == "/api/pair":
            token = self.server.devices.pair(
                str(body.get("code", "")), str(body.get("name", "")), self.client_address[0]
            )
            if not token:
                return self._json(403, {"error": "this code is wrong or has expired"})
            cookie = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000"
            if self.server.base_url.startswith("https://"):
                cookie += "; Secure"
            return self._json(200, {"ok": True}, {"Set-Cookie": cookie})
        if path.startswith("/api/mod/") or path.startswith("/api/admin/"):
            if not self._is_mod():
                return self._json(403, {"error": "forbidden"})
            return self._mod_post(path, body)
        if not self._is_device(True):
            return self._deny()
        session = str(body.get("session", ""))
        if path == "/api/say":
            text = str(body.get("text", "")).strip()
            if not text or not hub.push_command(session, {"type": "prompt", "text": text[:8000]}):
                return self._json(409, {"error": "that session is not connected"})
            return self._json(200, {"ok": True})
        if path == "/api/draft":  # the phone edited the text box: mirror it into the prompt box
            text = str(body.get("text", ""))[:4000]
            ok = hub.push_command(session, {"type": "setdraft", "text": text})
            hub.set_draft(session, text)
            return self._json(200 if ok else 409, {"ok": ok})
        if path == "/api/submit":
            command = {"type": "submit", "text": str(body.get("text", ""))[:8000]}
            ok = hub.push_command(session, command)
            if ok:
                hub.set_draft(session, "")  # the box empties; without this the old text comes back
            return self._json(200 if ok else 409, {"ok": ok})
        if path == "/api/clear":
            ok = hub.push_command(session, {"type": "setdraft", "text": ""})
            hub.set_draft(session, "")
            return self._json(200 if ok else 409, {"ok": ok})
        if path == "/api/mute":
            muted = bool(body.get("on"))
            ok = hub.push_command(session, {"type": "mute", "on": muted})
            hub.hold_mute(session)
            hub.set_muted(session, muted)
            return self._json(200 if ok else 409, {"ok": ok})
        if path == "/api/localsound":
            hub.set_local_sound(bool(body.get("on")))
            return self._json(200, {"local": hub.local_sound})
        if path == "/api/listen":
            hub.listen(bool(body.get("on")))
            return self._json(200, {"listening": hub.listening()})
        if path == "/api/cancel":
            ok = hub.push_command(session, {"type": "cancel"})
            return self._json(200 if ok else 409, {"ok": ok})
        if path == "/api/approve":
            result = hub.decide(
                str(body.get("id", "")), bool(body.get("allow")), bool(body.get("confirm"))
            )
            return self._json(409 if result == "confirm" else 200, {"result": result})
        if path == "/api/away":
            hub.set_away(bool(body.get("on")))
            return self._json(200, {"away": hub.away})
        if path == "/api/voice":
            info = hub.sessions.get(session, {})
            ok, why = voicekey.hold(
                body.get("action") == "down",
                voicekey.app_for(info.get("term", "")),
                info.get("pid") or None,
            )
            print(
                f"voice {body.get('action')} session={session} pid={info.get('pid')} ok={ok} {why}",
                flush=True,
            )
            return self._json(200 if ok else 501, {"ok": ok, "error": why})
        self._json(404, {"error": "not found"})

    def _mod_post(self, path: str, body: dict) -> None:
        hub = self.server.hub
        session = str(body.get("session", ""))
        if path == "/api/mod/register":
            hub.register(
                session,
                str(body.get("name", "")),
                str(body.get("term", "")),
                str(body.get("cwd", "")),
                int(body.get("pid") or 0),
            )
            return self._json(200, {"ok": True})
        if path == "/api/mod/draft":
            hub.set_draft(session, str(body.get("text", "")))
            return self._json(200, {"ok": True})
        if path == "/api/mod/unregister":
            hub.unregister(session)
            return self._json(200, {"ok": True})
        if path == "/api/mod/event":
            kind = str(body.get("kind", "info"))
            if body.get("status"):
                hub.set_status(session, str(body["status"]))
            if body.get("text") is not None or kind != "status":
                hub.add_event(session, kind, str(body.get("text", "")),
                              summary=str(body.get("summary", "")))  # fmt: skip
            return self._json(200, {"ok": True})
        if path == "/api/mod/approval":
            approval = hub.create_approval(session, str(body.get("tool", "")), body.get("input"))
            return self._json(200, {"id": approval["id"], "risky": approval["risky"]})
        if path == "/api/mod/approval-expire":
            hub.expire_approval(str(body.get("id", "")))
            return self._json(200, {"ok": True})
        if path == "/api/admin/pair":
            code = self.server.devices.new_code()
            base = self.server.base_url
            return self._json(200, {"code": code, "url": f"{base}/?pair={code}"})
        if path == "/api/admin/revoke":
            return self._json(200, {"revoked": self.server.devices.revoke(str(body.get("id", "")))})
        if path == "/api/admin/away":
            hub.set_away(bool(body.get("on")))
            return self._json(200, {"away": hub.away})
        if path == "/api/admin/shutdown":
            self._json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._json(404, {"error": "not found"})

    def _status(self) -> dict:
        hub = self.server.hub
        snap = hub.snapshot()
        return {
            "url": self.server.base_url,
            "away": hub.away,
            "sessions": [s["name"] for s in snap["sessions"] if s["online"]],
            "devices": len(self.server.devices.listing()),
            "uptime": int(time.time() - self.server.started),
        }

    def _pair_page(self) -> None:
        code = self.server.devices.new_code()
        link = f"{self.server.base_url}/?pair={code}"
        html = (
            "<!doctype html><meta charset=utf-8><title>Pair a phone</title>"
            "<body style='font:16px system-ui;text-align:center;padding:2rem'>"
            "<h1>Scan with your phone</h1>"
            f"<div style='max-width:340px;margin:auto'>{qr.svg(link)}</div>"
            "<p>Same Wi-Fi as this computer. The code works once and expires in 5 minutes.</p>"
            f"<p><small>{link}</small></p>"
        )
        self._send(200, html.encode(), "text/html; charset=utf-8")

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        hub = self.server.hub
        version = -1
        try:
            while True:
                if version != hub.version:
                    snap = hub.snapshot()
                    version = snap["version"]
                    self.wfile.write(f"data: {json.dumps(snap)}\n\n".encode())
                else:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
                hub.touch_phone()
                hub.wait_change(version, 15)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def serve(host: str, port: int, base_url: str, mic: bool = False) -> None:
    """Run the hub until it is shut down or idles out."""
    server = Server((host, port))
    server.base_url = base_url
    server.hub.mic = mic

    def watchdog() -> None:
        while True:
            time.sleep(60)
            last = max(server.hub.phone_seen, server.hub.mod_seen, server.started)
            if time.time() - last > IDLE_STOP:
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
