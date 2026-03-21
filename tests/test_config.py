from pathlib import Path
import uuid

from core.config import ConfigManager


def _unique_name() -> str:
    return f"test-{uuid.uuid4().hex}.toml"


def test_loads_xdg_config_when_local_missing(monkeypatch, tmp_path):
    config_name = _unique_name()
    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    xdg_config = xdg_home / "lns" / config_name
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text('[global]\nsocket_path = "/tmp/from-xdg.sock"\n', encoding="utf-8")

    cfg = ConfigManager(config_name=config_name)

    assert cfg.config_path == xdg_config
    assert cfg.get("global", "socket_path") == "/tmp/from-xdg.sock"


def test_local_config_takes_precedence_over_xdg(monkeypatch, tmp_path):
    config_name = _unique_name()
    project_root = Path(__file__).resolve().parents[1]
    local_config = project_root / config_name

    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    xdg_config = xdg_home / "lns" / config_name
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text('[global]\nsocket_path = "/tmp/from-xdg.sock"\n', encoding="utf-8")

    local_config.write_text('[global]\nsocket_path = "/tmp/from-local.sock"\n', encoding="utf-8")
    try:
        cfg = ConfigManager(config_name=config_name)
        assert cfg.config_path == local_config
        assert cfg.get("global", "socket_path") == "/tmp/from-local.sock"
    finally:
        local_config.unlink(missing_ok=True)


def test_invalid_toml_keeps_defaults(monkeypatch, tmp_path):
    config_name = _unique_name()
    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    xdg_config = xdg_home / "lns" / config_name
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text('[global\nsocket_path = "/tmp/broken.sock"\n', encoding="utf-8")

    cfg = ConfigManager(config_name=config_name)

    assert cfg.get("global", "socket_path") == "/tmp/nsd.sock"
    assert cfg.get("modules", "automount") is True


def test_get_returns_section_or_single_value(monkeypatch, tmp_path):
    config_name = _unique_name()
    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    xdg_config = xdg_home / "lns" / config_name
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text('[automount]\nmount_path = "/mnt/custom"\n', encoding="utf-8")

    cfg = ConfigManager(config_name=config_name)

    automount_section = cfg.get("automount")
    assert isinstance(automount_section, dict)
    assert automount_section["mount_path"] == "/mnt/custom"
    assert cfg.get("automount", "mount_path") == "/mnt/custom"
