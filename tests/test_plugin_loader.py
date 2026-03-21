from pathlib import Path
import types

from core.plugin_loader import PluginLoader
from modules.base import BasePlugin


class ValidPlugin(BasePlugin):
    async def run(self) -> None:
        return None


class AnotherValidPlugin(BasePlugin):
    async def run(self) -> None:
        return None


class NotAPlugin:
    pass


async def dummy_send_ipc(*_args, **_kwargs):
    return None


def test_loader_discovers_and_instantiates_only_baseplugin_subclasses(monkeypatch):
    files = [
        Path("/tmp/modules/__init__.py"),
        Path("/tmp/modules/base.py"),
        Path("/tmp/modules/good.py"),
    ]

    def fake_glob(_self, _pattern):
        return files

    module = types.SimpleNamespace(ValidPlugin=ValidPlugin, NotAPlugin=NotAPlugin)

    def fake_import_module(name):
        assert name == "modules.good"
        return module

    monkeypatch.setattr("core.plugin_loader.pathlib.Path.glob", fake_glob)
    monkeypatch.setattr("core.plugin_loader.importlib.import_module", fake_import_module)

    loader = PluginLoader(config={"ok": True}, send_ipc_func=dummy_send_ipc)
    plugins = loader.load_plugins()

    assert len(plugins) == 1
    assert isinstance(plugins[0], ValidPlugin)


def test_loader_continues_if_one_module_import_fails(monkeypatch):
    files = [
        Path("/tmp/modules/broken.py"),
        Path("/tmp/modules/good.py"),
    ]

    def fake_glob(_self, _pattern):
        return files

    good_module = types.SimpleNamespace(AnotherValidPlugin=AnotherValidPlugin)

    def fake_import_module(name):
        if name == "modules.broken":
            raise RuntimeError("boom")
        if name == "modules.good":
            return good_module
        raise AssertionError(f"Unexpected module: {name}")

    monkeypatch.setattr("core.plugin_loader.pathlib.Path.glob", fake_glob)
    monkeypatch.setattr("core.plugin_loader.importlib.import_module", fake_import_module)

    loader = PluginLoader(config={}, send_ipc_func=dummy_send_ipc)
    plugins = loader.load_plugins()

    assert len(plugins) == 1
    assert isinstance(plugins[0], AnotherValidPlugin)
