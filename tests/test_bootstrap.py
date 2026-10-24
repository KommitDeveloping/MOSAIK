from mosaik import bootstrap


def test_required_when_libraries_are_missing(monkeypatch):
    monkeypatch.setattr(bootstrap, "deps_ready", lambda: False)
    assert bootstrap.setup_state() == "required"


def test_ready_outside_a_virtualenv(monkeypatch):
    monkeypatch.setattr(bootstrap, "deps_ready", lambda: True)
    monkeypatch.setattr(bootstrap, "_in_virtualenv", lambda: False)
    assert bootstrap.setup_state() == "ready"


def test_optional_is_attempted_once_inside_a_virtualenv(monkeypatch):
    monkeypatch.setattr(bootstrap, "deps_ready", lambda: True)
    monkeypatch.setattr(bootstrap, "_in_virtualenv", lambda: True)
    monkeypatch.setattr(bootstrap, "optional_ready", lambda: False)
    monkeypatch.delenv(bootstrap.ENV_RELAUNCHED, raising=False)
    assert bootstrap.setup_state() == "optional"
    bootstrap._marker().write_text("1")
    assert bootstrap.setup_state() == "ready"


def test_no_private_environment_yet():
    assert bootstrap.find_ready_python() is None


def test_install_failure_is_reported(monkeypatch):
    import pytest

    from mosaik.config import SetupError

    monkeypatch.setattr(bootstrap, "_in_virtualenv", lambda: True)
    monkeypatch.setattr(bootstrap, "_run_logged", lambda cmd, log: 1)
    with pytest.raises(SetupError):
        bootstrap.install_environment(lambda line: None)
