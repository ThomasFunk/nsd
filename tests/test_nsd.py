import logging
import sys

import pytest

import nsd


class FakeConfig:
    def __init__(self, log_level: str = "warning"):
        self.log_level = log_level

    def get(self, section, key=None):
        if section == "global" and key == "log_level":
            return self.log_level
        return None


class FakeDaemon:
    def __init__(self, config):
        self.config = config

    async def run(self):
        return None

    async def broadcast(self, *_args, **_kwargs):
        return None


class FakePlugin:
    async def run(self):
        return None


def test_parse_args_debug_true(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["nsd.py", "-d"])
    args = nsd.parse_args()
    assert args.debug is True


def test_parse_args_debug_false(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["nsd.py"])
    args = nsd.parse_args()
    assert args.debug is False


@pytest.mark.asyncio
async def test_main_non_debug_applies_config_log_level_and_wires_tasks(monkeypatch):
    created = {}
    gather_calls = []
    basic_levels = []
    root_levels = []

    def fake_basic_config(**kwargs):
        basic_levels.append(kwargs.get("level"))

    root_logger = logging.getLogger()
    original_set_level = root_logger.setLevel

    def set_level_spy(level):
        root_levels.append(level)
        return original_set_level(level)

    class FakeLoader:
        def __init__(self, config, send_ipc_func):
            created["loader_config"] = config
            created["send_ipc_func"] = send_ipc_func

        def load_plugins(self):
            return [FakePlugin()]

    async def fake_gather(*tasks):
        gather_calls.append(tasks)
        for task in tasks:
            await task

    monkeypatch.setattr(nsd.logging, "basicConfig", fake_basic_config)
    monkeypatch.setattr(root_logger, "setLevel", set_level_spy)
    monkeypatch.setattr(nsd, "ConfigManager", lambda: FakeConfig("warning"))
    monkeypatch.setattr(nsd, "NightshadeDaemon", FakeDaemon)
    monkeypatch.setattr(nsd, "PluginLoader", FakeLoader)
    monkeypatch.setattr(nsd.asyncio, "gather", fake_gather)

    await nsd.main(debug=False)

    assert basic_levels == [logging.INFO]
    assert root_levels == [logging.WARNING]
    assert callable(created["send_ipc_func"])
    assert len(gather_calls) == 1
    assert len(gather_calls[0]) == 2


@pytest.mark.asyncio
async def test_main_debug_forces_debug_level_without_config_override(monkeypatch):
    basic_levels = []
    root_setlevel_called = []

    def fake_basic_config(**kwargs):
        basic_levels.append(kwargs.get("level"))

    root_logger = logging.getLogger()

    def set_level_spy(_level):
        root_setlevel_called.append(True)

    class FakeLoader:
        def __init__(self, _config, _send_ipc_func):
            pass

        def load_plugins(self):
            return []

    async def fake_gather(*tasks):
        for task in tasks:
            await task

    monkeypatch.setattr(nsd.logging, "basicConfig", fake_basic_config)
    monkeypatch.setattr(root_logger, "setLevel", set_level_spy)
    monkeypatch.setattr(nsd, "ConfigManager", lambda: FakeConfig("error"))
    monkeypatch.setattr(nsd, "NightshadeDaemon", FakeDaemon)
    monkeypatch.setattr(nsd, "PluginLoader", FakeLoader)
    monkeypatch.setattr(nsd.asyncio, "gather", fake_gather)

    await nsd.main(debug=True)

    assert basic_levels == [logging.DEBUG]
    assert root_setlevel_called == []
