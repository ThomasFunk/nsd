__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/05/08"

"""NDE XML config assembler plugin.

Builds a full labwc ``rc.xml`` from ``~/.config/nde/config.xml`` and custom
``<load .../>`` directives that reference XML part files.
"""

import asyncio
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from modules.base import BasePlugin

LOAD_TAG = "load"
MERGE_KEY_ATTRS = ("name", "key", "button", "id", "device", "action")


class NdeConfigAssemblerPlugin(BasePlugin):
    """Assemble and validate labwc config from NDE XML blocks."""

    def __init__(self, config: Any, send_ipc_func: Any) -> None:
        """Initialize plugin settings from config.

        Parameters
        ----------
        config : Any
            Configuration provider.
        send_ipc_func : Any
            Async IPC send callback.
        """
        super().__init__(config, send_ipc_func)
        nde_cfg = self.config.get("nde_config") or {}

        default_base = Path.home() / ".config" / "nde"
        self.base_dir = Path(str(nde_cfg.get("base_dir", default_base))).expanduser()
        self.main_file = Path(
            str(nde_cfg.get("main_file", self.base_dir / "config.xml"))
        ).expanduser()
        self.output_file = Path(
            str(nde_cfg.get("output_file", Path.home() / ".config" / "labwc" / "rc.xml"))
        ).expanduser()
        self.backup = bool(nde_cfg.get("backup", True))
        self.strict_validation = bool(nde_cfg.get("strict_validation", True))

    def register_handlers(self, daemon: Any) -> None:
        """Register ``nde.reconfigure`` command handler.

        Parameters
        ----------
        daemon : Any
            Daemon instance exposing ``register_command_handler``.

        Returns
        -------
        None
        """
        daemon.register_command_handler("nde.reconfigure", self.handle_reconfigure)

    async def run(self) -> None:
        """Keep plugin task alive.

        Returns
        -------
        None
        """
        self.log.info("NDE config assembler active")
        while True:
            await asyncio.sleep(3600)

    async def handle_reconfigure(self, _payload: dict[str, Any]) -> dict[str, Any]:
        """Assemble, validate, and write ``rc.xml``.

        On success, emits a result broadcast and internal event that can be used
        by other plugins (for example labwc bridge) to trigger reconfigure.

        Parameters
        ----------
        _payload : dict[str, Any]
            Unused request payload.

        Returns
        -------
        dict[str, Any]
            Result payload with ``ok`` and metadata/error details.
        """
        try:
            result = await asyncio.to_thread(self._assemble_and_write)
            await self.send_ipc(
                {
                    "src": "nsd.nde_config_assembler",
                    "type": "broadcast",
                    "action": "nde.reconfigure_result",
                    "payload": result,
                }
            )
            await self.send_ipc(
                {
                    "src": "nsd.nde_config_assembler",
                    "type": "event",
                    "action": "reconfigure_requested",
                    "payload": {
                        "source": "nde.reconfigure",
                        "output_file": result.get("output_file", ""),
                    },
                }
            )
            return result
        except Exception as exc:
            result = {
                "ok": False,
                "error_code": "assemble_failed",
                "message": str(exc),
            }
            await self.send_ipc(
                {
                    "src": "nsd.nde_config_assembler",
                    "type": "broadcast",
                    "action": "nde.reconfigure_result",
                    "payload": result,
                }
            )
            return result

    def _assemble_and_write(self) -> dict[str, Any]:
        """Build and write the final labwc ``rc.xml``.

        Returns
        -------
        dict[str, Any]
            Success metadata.
        """
        loaded_files: set[Path] = set()
        stack: list[Path] = []

        main_path = self._resolve_main_path()
        root = self._load_xml(main_path, stack, loaded_files)
        if root.tag != "labwc_config":
            raise ValueError("Main config root must be <labwc_config>")

        root = self._merge_top_level_blocks(root)
        if self.strict_validation:
            self._validate_compiled_tree(root)

        self._write_xml(root)
        return {
            "ok": True,
            "source_count": len(loaded_files),
            "output_file": str(self.output_file),
        }

    def _resolve_main_path(self) -> Path:
        """Resolve and validate the main config path under base dir."""
        base = self.base_dir.resolve()
        if self.main_file.is_absolute():
            candidate = self.main_file.resolve()
        else:
            candidate = (base / self.main_file).resolve()
        if not self._is_under_base(candidate):
            raise ValueError(f"Main config path outside base dir: {candidate}")
        if not candidate.exists():
            raise FileNotFoundError(f"Main config not found: {candidate}")
        return candidate

    def _load_xml(self, file_path: Path, stack: list[Path], loaded_files: set[Path]) -> ET.Element:
        """Load one XML file and resolve nested load directives.

        Parameters
        ----------
        file_path : Path
            XML file to parse.
        stack : list[Path]
            Active include chain for cycle detection.
        loaded_files : set[Path]
            Set of all files loaded during assembly.

        Returns
        -------
        ET.Element
            Parsed and load-expanded root element.
        """
        resolved = file_path.resolve()
        if resolved in stack:
            cycle = " -> ".join([str(p) for p in [*stack, resolved]])
            raise ValueError(f"Load cycle detected: {cycle}")

        stack.append(resolved)
        loaded_files.add(resolved)
        try:
            root = ET.parse(resolved).getroot()
            self._expand_loads(root, resolved.parent, stack, loaded_files)
            return root
        finally:
            stack.pop()

    def _expand_loads(
        self,
        element: ET.Element,
        current_dir: Path,
        stack: list[Path],
        loaded_files: set[Path],
    ) -> None:
        """Resolve ``<load .../>`` tags recursively inside one element."""
        children = list(element)
        idx = 0
        while idx < len(children):
            child = children[idx]
            if child.tag == LOAD_TAG:
                ref = self._extract_load_ref(child)
                include_path = self._resolve_load_path(ref, current_dir)
                included_root = self._load_xml(include_path, stack, loaded_files)

                replacements = self._included_as_replacements(element, included_root)
                element.remove(child)
                for offset, repl in enumerate(replacements):
                    element.insert(idx + offset, repl)

                children = list(element)
                idx += len(replacements)
                continue

            self._expand_loads(child, current_dir, stack, loaded_files)
            idx += 1

    def _extract_load_ref(self, load_elem: ET.Element) -> str:
        """Extract include reference from one load element."""
        ref = (
            load_elem.attrib.get("path")
            or load_elem.attrib.get("file")
            or load_elem.attrib.get("href")
            or (load_elem.text or "").strip()
        )
        if not ref:
            raise ValueError("<load> must specify path/file/href or text path")
        return ref

    def _resolve_load_path(self, ref: str, current_dir: Path) -> Path:
        """Resolve and validate a load reference under base dir."""
        rel = Path(ref)
        if rel.is_absolute():
            raise ValueError(f"Absolute load path is not allowed: {ref}")

        candidate = (current_dir / rel).resolve()
        if not self._is_under_base(candidate):
            raise ValueError(f"Load path outside base dir: {ref}")
        if not candidate.exists():
            raise FileNotFoundError(f"Loaded file not found: {candidate}")
        return candidate

    def _included_as_replacements(self, parent: ET.Element, included_root: ET.Element) -> list[ET.Element]:
        """Convert one included root into replacement nodes."""
        if included_root.tag == "labwc_config":
            return [self._clone_elem(c) for c in list(included_root)]

        # Support nested includes inside blocks: when a keyboard block loads
        # another keyboard block, inject children instead of creating nested blocks.
        if parent.tag != "labwc_config" and included_root.tag == parent.tag:
            return [self._clone_elem(c) for c in list(included_root)]

        return [self._clone_elem(included_root)]

    def _merge_top_level_blocks(self, root: ET.Element) -> ET.Element:
        """Merge duplicate top-level blocks under ``labwc_config``."""
        merged_root = ET.Element("labwc_config")
        for child in list(root):
            existing = next((c for c in list(merged_root) if c.tag == child.tag), None)
            if existing is None:
                merged_root.append(self._clone_elem(child))
                continue
            self._merge_element(existing, child)
        return merged_root

    def _merge_element(self, target: ET.Element, incoming: ET.Element) -> None:
        """Deep-merge one XML element into another."""
        for k, v in incoming.attrib.items():
            target.attrib[k] = v

        if incoming.text and incoming.text.strip():
            target.text = incoming.text

        for incoming_child in list(incoming):
            match = self._find_merge_candidate(target, incoming_child)
            if match is None:
                target.append(self._clone_elem(incoming_child))
            else:
                self._merge_element(match, incoming_child)

    def _find_merge_candidate(self, target: ET.Element, incoming_child: ET.Element) -> ET.Element | None:
        """Find matching child for key-based merge."""
        key_attr = next((a for a in MERGE_KEY_ATTRS if a in incoming_child.attrib), None)
        if key_attr is None:
            return None

        key_value = incoming_child.attrib.get(key_attr)
        for candidate in list(target):
            if candidate.tag != incoming_child.tag:
                continue
            if candidate.attrib.get(key_attr) == key_value:
                return candidate
        return None

    def _validate_compiled_tree(self, root: ET.Element) -> None:
        """Validate compiled XML structure."""
        if root.tag != "labwc_config":
            raise ValueError("Compiled root must be <labwc_config>")

        seen: set[str] = set()
        for child in list(root):
            if child.tag == LOAD_TAG:
                raise ValueError("Compiled XML must not contain <load> elements")
            if child.tag in seen:
                raise ValueError(f"Duplicate top-level block after merge: <{child.tag}>")
            seen.add(child.tag)

    def _write_xml(self, root: ET.Element) -> None:
        """Write compiled XML atomically to output file."""
        output = self.output_file.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)

        if self.backup and output.exists():
            backup_path = output.with_suffix(output.suffix + ".bak")
            shutil.copy2(output, backup_path)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        xml_str = ET.tostring(root, encoding="unicode")
        payload = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{xml_str}\n"

        fd, tmp_name = tempfile.mkstemp(prefix="rc.", suffix=".tmp", dir=str(output.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, output)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _is_under_base(self, path: Path) -> bool:
        """Return whether path is within configured base dir."""
        base = self.base_dir.resolve()
        try:
            path.resolve().relative_to(base)
            return True
        except ValueError:
            return False

    @staticmethod
    def _clone_elem(elem: ET.Element) -> ET.Element:
        """Deep-clone XML element."""
        return ET.fromstring(ET.tostring(elem, encoding="unicode"))
