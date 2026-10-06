import json
from pathlib import Path

import pytest
import tomllib

from claudio_vibecode import __version__, update

ROOT = Path(__file__).parent.parent


def test_version_compare():
    assert update.is_newer("v0.4.1", "0.4.0")
    assert update.is_newer("1.0.0", "0.9.9")
    assert not update.is_newer("v0.4.0", "0.4.0")
    assert not update.is_newer("v0.3.9", "0.4.0")
    assert not update.is_newer("nightly", "0.4.0")


def test_versions_stay_in_step():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    plugin = json.loads((ROOT / "src/claudio_vibecode/mod/.claude-plugin/plugin.json").read_text())[
        "version"
    ]
    assert pyproject == plugin == __version__


@pytest.fixture
def release(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path))
    calls = {"fetch": 0, "install": []}

    def fake_fetch():
        calls["fetch"] += 1
        return {"tag": "v9.0.0", "url": "https://example/rel", "notes": ""}

    monkeypatch.setattr(update, "_fetch", fake_fetch)
    monkeypatch.setattr(update, "install", lambda tag: calls["install"].append(tag) or 0)
    return calls


def test_check_is_cached_for_a_day(release, capsys):
    assert update.run(check=True, yes=False, quiet=False) == 10
    assert update.run(check=True, yes=False, quiet=True) == 10
    assert release["fetch"] == 1
    assert "9.0.0 is available" in capsys.readouterr().out


def test_nothing_installs_without_yes(release):
    assert update.run(check=False, yes=False, quiet=False) == 0
    assert release["install"] == []


def test_yes_installs_the_release_tag(release):
    assert update.run(check=False, yes=True, quiet=False) == 0
    assert release["install"] == ["v9.0.0"]


def test_quiet_is_silent_when_current(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path))
    monkeypatch.setattr(
        update, "_fetch", lambda: {"tag": f"v{__version__}", "url": "", "notes": ""}
    )
    assert update.run(check=False, yes=False, quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_offline_is_silent_when_quiet(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDIO_TTS_HOME", str(tmp_path))
    monkeypatch.setattr(update, "_fetch", lambda: None)
    assert update.run(check=False, yes=False, quiet=True) == 0
    assert capsys.readouterr().out == ""
