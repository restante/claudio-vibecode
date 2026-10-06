"""Where claudio-vibecode keeps its files. It shares claudio-tts's install root (one venv)."""

from __future__ import annotations

from pathlib import Path

from claudio_tts import paths as tts_paths

data_dir = tts_paths.data_dir
claude_dir = tts_paths.claude_dir


def state_dir() -> Path:
    path = data_dir() / "vibecode"
    path.mkdir(parents=True, exist_ok=True)
    return path


def mod_source() -> Path:
    """The Claude mod shipped inside this package."""
    return Path(__file__).parent / "mod"
