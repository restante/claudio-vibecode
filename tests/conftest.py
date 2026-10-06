import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Each test gets its own data and Claude dirs, and never touches real audio or music apps."""
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CLAUDIO_TTS_FAKE_PLAYER", str(tmp_path / "played.log"))
    monkeypatch.setenv("AUDIO_DUCK_ENABLED", "false")
    return tmp_path
