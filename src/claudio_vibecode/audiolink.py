"""The phone as an extra claudio-tts output: each sentence becomes a short WAV clip for the hub.

claudio-tts finds this through the `claudio_tts.sinks` entry point (see pyproject.toml).
"""

from __future__ import annotations

import io
import json
import queue
import sys
import threading
import urllib.error
import urllib.request
import wave

import numpy as np

from claudio_vibecode import auth


def _hub():
    from claudio_vibecode import ctl  # imported late: ctl pulls in the whole server

    return ctl.running()


def _request(info: dict, path: str, data: bytes | None = None, timeout: float = 5):
    request = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}{path}",
        data=data,
        headers={"X-Claudio-Mod": auth.mod_token(), "Content-Type": "application/octet-stream"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback
        return response.read()


def wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    """Mono float32 in [-1, 1] -> a 16-bit WAV file."""
    pcm = (np.clip(samples.reshape(-1), -1.0, 1.0) * 32767).astype("<i2")
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def listener_state(info: dict | None = None) -> dict | None:
    """{"listening", "local"} from the hub, or None when it is not running."""
    info = info or _hub()
    if not info:
        return None
    try:
        return json.loads(_request(info, "/api/mod/listeners"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def phone_listening() -> bool:
    """True when the hub is up and a phone page has Listen switched on."""
    state = listener_state()
    return bool(state and state.get("listening"))


class PhoneSink:
    """Posts clips to the hub from its own thread so a slow network never stalls the speakers."""

    def __init__(self, info: dict, session: str, local: bool = True) -> None:
        self.info = info
        self.session = session
        self.local = local  # whether the computer's speakers should play as well
        self.q: queue.Queue = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @classmethod
    def open(cls, session: str) -> PhoneSink | None:
        info = _hub()
        state = listener_state(info)
        if not info or not state or not state.get("listening"):
            return None
        return cls(info, session, bool(state.get("local", True)))

    def _run(self) -> None:
        while (clip := self.q.get()) is not None:
            try:
                _request(self.info, f"/api/mod/audio?session={self.session}", clip, timeout=15)
            except (urllib.error.URLError, OSError) as error:
                print(f"claudio-vibecode: phone audio failed: {error}", file=sys.stderr)

    name = "phone"

    def put(self, samples: np.ndarray, rate: int) -> None:
        self.q.put(wav_bytes(samples, rate))

    def close(self) -> None:
        self.q.put(None)
        self.thread.join(timeout=20)


def open_sink(session: str) -> PhoneSink | None:
    """claudio-tts calls this once per utterance; None when no phone is listening."""
    return PhoneSink.open(session)


open_sink.description = "your phone, while Listen is on in the claudio-vibecode page"  # type: ignore[attr-defined]
