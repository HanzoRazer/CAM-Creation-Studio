"""CLI dispatch, help, and version (CS-007)."""

import json

import pytest

from cam_creation_studio.cli.main import main


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("generate", "validate", "parse", "preview", "feeds", "version"):
        assert cmd in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "camstudio" in capsys.readouterr().out


def test_version_command_human(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.startswith("camstudio ")


def test_version_command_json(capsys):
    assert main(["version", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "camstudio"
    assert payload["version"]


def test_version_fallback_is_marked_when_uninstalled(monkeypatch):
    # When distribution metadata is missing (a bare source tree), the version
    # is a clearly non-authoritative marker, not a real-looking release number.
    import importlib.metadata as md

    from cam_creation_studio.cli.commands import version as version_cmd

    def _not_found(_dist):
        raise md.PackageNotFoundError

    monkeypatch.setattr(md, "version", _not_found)
    v = version_cmd.get_version()
    assert v == version_cmd._FALLBACK
    assert "+source" in v  # obviously not an installed release


def test_no_command_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_unknown_command_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["frobnicate"])
    assert exc.value.code == 2
