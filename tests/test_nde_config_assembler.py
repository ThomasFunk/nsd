import asyncio
from pathlib import Path
import xml.etree.ElementTree as ET

from modules.nde_config_assembler import NdeConfigAssemblerPlugin


class DummyConfig:
    def __init__(self, data):
        self._data = data

    def get(self, section, key=None):
        if key is None:
            return self._data.get(section)
        section_data = self._data.get(section, {})
        return section_data.get(key)


async def _dummy_send_ipc_collector(messages, msg, *_args, **_kwargs):
    messages.append(msg)


def _make_plugin(tmp_path: Path, collector: list[dict]):
    nde_base = tmp_path / "nde"
    out_path = tmp_path / "labwc" / "rc.xml"
    cfg = DummyConfig(
        {
            "nde_config": {
                "base_dir": str(nde_base),
                "main_file": str(nde_base / "config.xml"),
                "output_file": str(out_path),
                "backup": False,
                "strict_validation": True,
            }
        }
    )

    async def sender(msg, *_args, **_kwargs):
        await _dummy_send_ipc_collector(collector, msg)

    return NdeConfigAssemblerPlugin(cfg, sender), nde_base, out_path


def test_reconfigure_merges_duplicate_keyboard_blocks_and_nested_loads(tmp_path):
    messages: list[dict] = []
    plugin, nde_base, out_path = _make_plugin(tmp_path, messages)

    parts = nde_base / "parts"
    parts.mkdir(parents=True)

    (nde_base / "config.xml").write_text(
        """
<labwc_config>
  <keyboard>
    <keybind key=\"A\" action=\"default\"/>
  </keyboard>
  <load path=\"parts/keyboard_user.xml\"/>
</labwc_config>
""".strip(),
        encoding="utf-8",
    )

    (parts / "keyboard_user.xml").write_text(
        """
<keyboard>
  <keybind key=\"A\" action=\"override\"/>
  <load path=\"keyboard_more.xml\"/>
</keyboard>
""".strip(),
        encoding="utf-8",
    )

    (parts / "keyboard_more.xml").write_text(
        """
<keyboard>
  <keybind key=\"B\" action=\"extra\"/>
</keyboard>
""".strip(),
        encoding="utf-8",
    )

    result = asyncio.run(plugin.handle_reconfigure({}))

    assert result["ok"] is True
    assert out_path.exists()

    root = ET.parse(out_path).getroot()
    assert root.tag == "labwc_config"

    top_keyboard = [c for c in list(root) if c.tag == "keyboard"]
    assert len(top_keyboard) == 1

    keybinds = {kb.attrib.get("key"): kb.attrib.get("action") for kb in top_keyboard[0].findall("keybind")}
    assert keybinds["A"] == "override"
    assert keybinds["B"] == "extra"

    assert any(m.get("action") == "nde.reconfigure_result" for m in messages)
    assert any(m.get("action") == "reconfigure_requested" for m in messages)


def test_reconfigure_rejects_load_path_traversal(tmp_path):
    messages: list[dict] = []
    plugin, nde_base, _out_path = _make_plugin(tmp_path, messages)

    nde_base.mkdir(parents=True)
    (nde_base / "config.xml").write_text(
        """
<labwc_config>
  <load path="../outside.xml"/>
</labwc_config>
""".strip(),
        encoding="utf-8",
    )

    result = asyncio.run(plugin.handle_reconfigure({}))

    assert result["ok"] is False
    assert "outside base dir" in result["message"]


def test_reconfigure_rejects_load_cycles(tmp_path):
    messages: list[dict] = []
    plugin, nde_base, _out_path = _make_plugin(tmp_path, messages)

    parts = nde_base / "parts"
    parts.mkdir(parents=True)

    (nde_base / "config.xml").write_text(
        """
<labwc_config>
  <load path="parts/a.xml"/>
</labwc_config>
""".strip(),
        encoding="utf-8",
    )
    (parts / "a.xml").write_text(
        """
<keyboard>
  <load path="b.xml"/>
</keyboard>
""".strip(),
        encoding="utf-8",
    )
    (parts / "b.xml").write_text(
        """
<keyboard>
  <load path="a.xml"/>
</keyboard>
""".strip(),
        encoding="utf-8",
    )

    result = asyncio.run(plugin.handle_reconfigure({}))

    assert result["ok"] is False
    assert "Load cycle detected" in result["message"]
