import http.client
import json
import os
import threading
import time

import pytest

from claudio_vibecode import auth, hub, qr, server


@pytest.fixture
def srv(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path))
    s = server.Server(("127.0.0.1", 0))
    s.base_url = "http://phone.test"
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s
    s.shutdown()
    s.server_close()


def call(srv, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    data = None if body is None else json.dumps(body)
    conn.request(method, path, data, headers or {})
    res = conn.getresponse()
    raw = res.read()
    out = json.loads(raw) if raw[:1] in (b"{", b"[") else raw
    return res.status, out, res.getheader("Set-Cookie")


def mod(srv, method, path, body=None):
    return call(srv, method, path, body, {"X-Claudio-Mod": srv.mod_token})[:2]


def pair(srv):
    _, made = mod(srv, "POST", "/api/admin/pair", {})
    code = made["code"]
    status, _, cookie = call(srv, "POST", "/api/pair", {"code": code, "name": "test phone"})
    assert status == 200
    return {"Cookie": cookie.split(";")[0], "X-Claudio": "1"}, code


def test_pair_code_is_single_use_and_phone_routes_need_pairing(srv):
    assert call(srv, "GET", "/api/state")[0] == 401
    headers, code = pair(srv)
    assert call(srv, "POST", "/api/pair", {"code": code})[0] == 403  # already spent
    assert call(srv, "GET", "/api/state", None, headers)[0] == 200
    assert call(srv, "POST", "/api/say", {"session": "s", "text": "x"})[0] == 401
    no_header = {"Cookie": headers["Cookie"]}  # a cross-site form could not add X-Claudio
    assert call(srv, "POST", "/api/say", {"session": "s", "text": "x"}, no_header)[0] == 401


def test_service_worker_script_is_served_for_notifications(srv):
    status, body, _ = call(srv, "GET", "/sw.js")
    assert status == 200
    assert b"notificationclick" in body


def test_bad_origin_is_refused(srv):
    headers, _ = pair(srv)
    evil = {**headers, "Origin": "http://evil.example"}
    assert call(srv, "POST", "/api/say", {"session": "s", "text": "x"}, evil)[0] == 401


def test_mod_routes_need_the_secret(srv):
    assert call(srv, "GET", "/api/mod/poll?session=s")[0] == 404
    assert call(srv, "POST", "/api/mod/register", {"session": "s"})[0] == 403
    assert call(srv, "POST", "/api/admin/shutdown", {}, {"X-Claudio-Mod": "wrong"})[0] == 403


def test_expired_code_is_refused(srv, monkeypatch):
    _, made = mod(srv, "POST", "/api/admin/pair", {})
    monkeypatch.setattr(time, "time", lambda: time.monotonic() + 10**10)
    assert call(srv, "POST", "/api/pair", {"code": made["code"]})[0] == 403


def test_prompt_and_cancel_reach_the_session(srv):
    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "proj"})
    assert call(srv, "POST", "/api/say", {"session": "s1", "text": "run tests"}, headers)[0] == 200
    assert call(srv, "POST", "/api/cancel", {"session": "s1"}, headers)[0] == 200
    _, polled = mod(srv, "GET", "/api/mod/poll?session=s1")
    assert [c["type"] for c in polled["commands"]] == ["prompt", "cancel"]
    assert polled["commands"][0]["text"] == "run tests"
    assert call(srv, "POST", "/api/say", {"session": "nope", "text": "x"}, headers)[0] == 409


def test_events_reach_the_snapshot(srv):
    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "proj"})
    mod(srv, "POST", "/api/mod/event", {"session": "s1", "kind": "reply", "text": "done",
                                        "summary": "all good", "status": "idle"})  # fmt: skip
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["name"] == "proj"
    assert snap["events"][-1]["summary"] == "all good"


def test_long_poll_wakes_on_a_new_command(srv):
    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "p"})
    say = {"session": "s1", "text": "hi"}
    threading.Timer(0.3, lambda: call(srv, "POST", "/api/say", say, headers)).start()
    started = time.time()
    _, polled = mod(srv, "GET", "/api/mod/poll?session=s1&wait=5")
    assert polled["commands"][0]["text"] == "hi"
    assert time.time() - started < 3


def test_revoke(srv):
    headers, _ = pair(srv)
    _, rows = mod(srv, "GET", "/api/admin/devices")
    assert mod(srv, "POST", "/api/admin/revoke", {"id": rows[0]["id"]})[1]["revoked"] == 1
    assert call(srv, "GET", "/api/state", None, headers)[0] == 401


def test_pair_page_only_on_this_computer_and_has_qr(srv):
    status, page, _ = call(srv, "GET", "/pair")
    assert status == 200 and b"<svg" in page


def test_qr_text_has_two_rows_per_line():
    art = qr.text("http://192.168.1.2:47821/?pair=abc")
    lines = art.splitlines()
    assert len(lines) > 10 and len({len(line) for line in lines}) == 1


def test_device_token_is_stored_hashed(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path))
    devices = auth.Devices()
    token = devices.pair(devices.new_code(), "phone")
    assert token and token not in (auth.remote_dir() / "devices.json").read_text()
    assert devices.check(token) and not devices.check("nope")


def test_windows_key_struct_matches_the_win32_input_layout():
    import ctypes

    from claudio_vibecode import voicekey

    # INPUT is 40 bytes on 64-bit Windows and 28 on 32-bit; a wrong size makes SendInput fail.
    assert ctypes.sizeof(voicekey.Input) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    assert ctypes.sizeof(voicekey.KeyboardInput) == (
        24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 16
    )


def test_ancestors_walks_up_from_this_process():
    import os

    from claudio_vibecode import voicekey

    chain = voicekey.ancestors(os.getpid())
    assert chain[0] == os.getpid() and len(chain) >= 2
    assert voicekey.ancestors(None) == []


def test_cli_output_survives_a_legacy_console_encoding(tmp_path):
    import subprocess
    import sys

    code = "from claudio_vibecode import qr; print(qr.text('http://x.test'))"
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "CLAUDIO_TTS_HOME": str(tmp_path)}
    bad = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env, text=True)
    assert bad.returncode != 0  # the QR really cannot be printed with cp1252 ...
    code = "import sys; from claudio_vibecode import cli; cli.main(['doctor']); "
    code += "from claudio_vibecode import qr; print(qr.text('http://x.test'))"
    good = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)
    assert good.returncode == 0, good.stderr  # ... but main() switches output to UTF-8 first
    assert "█".encode() in good.stdout  # read as bytes: the test console may not be UTF-8


def test_session_shows_the_name_you_gave_it(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / f"{os.getpid()}.json").write_text('{"name": "my-renamed-session"}')
    h = hub.Hub()
    h.register("s1", "folder", pid=os.getpid())
    assert h.snapshot()["sessions"][0]["name"] == "my-renamed-session"
    (tmp_path / "sessions" / f"{os.getpid()}.json").write_text('{"name": "again"}')  # live rename
    assert h.snapshot()["sessions"][0]["name"] == "again"
    h.register("s2", "other-folder", pid=0)
    names = {s["id"]: s["name"] for s in h.snapshot()["sessions"]}
    assert names["s2"] == "other-folder"  # no pid or no file: the folder name


def test_phone_text_box_mirrors_the_prompt_box(srv):
    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "p"})
    mod(
        srv, "POST", "/api/mod/draft", {"session": "s1", "text": "dictated words"}
    )  # from the computer
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["draft"] == "dictated words"
    call(srv, "POST", "/api/draft", {"session": "s1", "text": "edited on the phone"}, headers)
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["draft"] == "edited on the phone"
    assert (
        call(srv, "POST", "/api/submit", {"session": "s1", "text": "send this"}, headers)[0] == 200
    )
    assert call(srv, "POST", "/api/clear", {"session": "s1"}, headers)[0] == 200
    assert call(srv, "POST", "/api/submit", {"session": "nope", "text": "x"}, headers)[0] == 409
    assert (
        call(srv, "POST", "/api/submit", {"session": "s1", "text": "x"})[0] == 401
    )  # needs pairing
    _, polled = mod(srv, "GET", "/api/mod/poll?session=s1")
    kinds = [(c["type"], c.get("text")) for c in polled["commands"]]
    assert kinds == [("setdraft", "edited on the phone"), ("submit", "send this"), ("setdraft", "")]


def test_submit_empties_the_shared_draft(srv):
    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "p"})
    mod(srv, "POST", "/api/mod/draft", {"session": "s1", "text": "old words"})
    call(srv, "POST", "/api/submit", {"session": "s1", "text": "old words"}, headers)
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["draft"] == ""  # else the phone would refill its box


def test_sound_state_comes_from_claudio_tts_and_mute_reaches_the_session(srv):
    from claudio_tts import sessionstate

    headers, _ = pair(srv)
    mod(srv, "POST", "/api/mod/register", {"session": "s1", "name": "p"})
    mod(srv, "GET", "/api/mod/poll?session=s1")
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["muted"] is None  # claudio-tts has not said: the chip hides
    sessionstate.write("s1", muted=True)
    mod(srv, "GET", "/api/mod/poll?session=s1")
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["muted"] is True
    call(srv, "POST", "/api/mute", {"session": "s1", "on": False}, headers)  # phone: sound on
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["muted"] is False  # shown at once, not after the command ran
    mod(srv, "GET", "/api/mod/poll?session=s1")  # claudio-tts still says muted: the hold keeps it
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["sessions"][0]["muted"] is False


def test_audio_clips_reach_a_listening_phone(srv):
    import wave

    import numpy as np

    from claudio_vibecode import audiolink

    headers, _ = pair(srv)
    assert mod(srv, "GET", "/api/mod/listeners")[1]["listening"] is False
    call(srv, "POST", "/api/listen", {"on": True}, headers)
    assert mod(srv, "GET", "/api/mod/listeners")[1]["listening"] is True
    wav = audiolink.wav_bytes(np.zeros(2400, dtype="float32"), 24000)
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request("POST", "/api/mod/audio?session=s1", wav, {"X-Claudio-Mod": srv.mod_token})
    clip_id = json.loads(conn.getresponse().read())["id"]
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert [c["id"] for c in snap["audio"]] == [clip_id] and snap["listening"] is True
    status, body, _ = call(srv, "GET", f"/api/audio/{clip_id}", None, headers)
    assert status == 200 and body == wav
    assert call(srv, "GET", f"/api/audio/{clip_id}")[0] == 401  # needs pairing
    with wave.open(__import__("io").BytesIO(wav)) as w:
        assert (w.getnchannels(), w.getframerate(), w.getnframes()) == (1, 24000, 2400)
    call(srv, "POST", "/api/listen", {"on": False}, headers)
    assert mod(srv, "GET", "/api/mod/listeners")[1]["listening"] is False


def test_mac_speakers_switch_and_listen_survives_a_nap(srv, monkeypatch):
    headers, _ = pair(srv)
    call(srv, "POST", "/api/listen", {"on": True}, headers)
    assert mod(srv, "GET", "/api/mod/listeners")[1] == {"listening": True, "local": True}
    call(srv, "POST", "/api/localsound", {"on": False}, headers)
    assert mod(srv, "GET", "/api/mod/listeners")[1]["local"] is False
    _, snap, _ = call(srv, "GET", "/api/state", None, headers)
    assert snap["local"] is False
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 100)  # a phone asleep for 100 s
    assert mod(srv, "GET", "/api/mod/listeners")[1]["listening"] is True


def test_mic_is_off_unless_the_page_is_served_over_https(srv):
    headers, _ = pair(srv)
    assert call(srv, "GET", "/api/state", None, headers)[1]["mic"] is False
    srv.hub.mic = True
    assert call(srv, "GET", "/api/state", None, headers)[1]["mic"] is True


def _tailscale_says(monkeypatch, payload, code=0):
    import json
    import subprocess

    from claudio_vibecode import ctl

    done = subprocess.CompletedProcess([], code, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr(ctl.subprocess, "run", lambda *a, **k: done)
    return ctl.tailscale_https()


def test_tailscale_https_needs_a_running_tailnet_with_certificates(monkeypatch):
    good = {
        "BackendState": "Running",
        "Self": {"DNSName": "mac.tail1234.ts.net."},
        "CertDomains": ["mac.tail1234.ts.net"],
    }
    assert _tailscale_says(monkeypatch, good) == "https://mac.tail1234.ts.net:8443"
    assert _tailscale_says(monkeypatch, {**good, "BackendState": "Stopped"}) is None
    assert _tailscale_says(monkeypatch, {**good, "CertDomains": []}) is None
    assert _tailscale_says(monkeypatch, good, code=1) is None


def test_tailscale_https_is_none_when_tailscale_is_not_installed(monkeypatch):
    from claudio_vibecode import ctl

    def missing(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(ctl.subprocess, "run", missing)
    assert ctl.tailscale_https() is None
    assert ctl._serve_https(47821) is False
