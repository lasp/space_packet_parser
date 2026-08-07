"""Tests for scripts/check_codecov_yaml.py."""

import importlib.util
import io
from pathlib import Path
from urllib import error

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_codecov_yaml.py"
SPEC = importlib.util.spec_from_file_location("check_codecov_yaml", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class _FakeResponse:
    """Minimal context manager for urllib responses."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_validate_codecov_yaml_posts_to_expected_endpoint(tmp_path, monkeypatch, capsys):
    file_path = tmp_path / "codecov.yml"
    file_path.write_text("coverage:\n  status: off\n")
    captured: dict[str, object] = {}

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["data"] = req.data
        captured["timeout"] = timeout
        return _FakeResponse(b"Valid!")

    monkeypatch.setattr(MODULE.request, "urlopen", _fake_urlopen)

    assert MODULE.validate_codecov_yaml(file_path) == 0
    assert captured == {
        "url": "https://codecov.io/validate",
        "method": "POST",
        "data": file_path.read_bytes(),
        "timeout": MODULE.NETWORK_TIMEOUT_SECONDS,
    }
    output = capsys.readouterr()
    assert "is valid." in output.out
    assert output.err == ""


def test_validate_codecov_yaml_http_error(tmp_path, monkeypatch, capsys):
    file_path = tmp_path / "codecov.yml"
    file_path.write_text("bad: yaml\n")

    def _raise_http_error(*_args, **_kwargs):
        raise error.HTTPError(
            url=MODULE.CODECOV_VALIDATE_URL,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"Invalid YAML"),
        )

    monkeypatch.setattr(MODULE.request, "urlopen", _raise_http_error)

    assert MODULE.validate_codecov_yaml(file_path) == 1
    output = capsys.readouterr()
    assert "validation failed with HTTP 400" in output.err
    assert "Invalid YAML" in output.err


def test_validate_codecov_yaml_network_error(tmp_path, monkeypatch, capsys):
    file_path = tmp_path / "codecov.yml"
    file_path.write_text("coverage: {}\n")

    def _raise_url_error(*_args, **_kwargs):
        raise error.URLError("network down")

    monkeypatch.setattr(MODULE.request, "urlopen", _raise_url_error)

    assert MODULE.validate_codecov_yaml(file_path) == 1
    output = capsys.readouterr()
    assert "Unable to reach Codecov validation endpoint" in output.err


def test_validate_codecov_yaml_file_read_error(tmp_path, capsys):
    missing_path = tmp_path / "missing-codecov.yml"

    assert MODULE.validate_codecov_yaml(missing_path) == 1
    output = capsys.readouterr()
    assert f"Unable to read {missing_path}" in output.err
