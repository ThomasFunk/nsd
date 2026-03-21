#!/usr/bin/env python3

"""Entry point for the Nightshade Daemon (nsd)."""

__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"
__version__ = "0.4.0"

import asyncio
import argparse
import logging
from core.config import ConfigManager
from core.server import NightshadeDaemon
from core.plugin_loader import PluginLoader

log = logging.getLogger("nsd")

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for daemon startup."""
    parser = argparse.ArgumentParser(description="Nightshade Daemon (NSD) - Lightweight system integration daemon")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main(debug: bool) -> None:
    """Initialize logging, load config, and run daemon + plugins."""
    # 1. Initialize logging early so config load messages are captured.
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
        datefmt='%H:%M:%S',
    )

    # 2. Load config and apply configured log level (unless debug is forced).
    cfg = ConfigManager()
    if not debug:
        configured_log_level = str(cfg.get("global", "log_level") or "info").upper()
        logging.getLogger().setLevel(getattr(logging, configured_log_level, logging.INFO))

    # 3. Initialize IPC server.
    daemon = NightshadeDaemon(cfg)
    
    # 4. Load plugins and inject broadcast callback.
    loader = PluginLoader(cfg, daemon.broadcast)
    plugins = loader.load_plugins()

    for plugin in plugins:
        register_handlers = getattr(plugin, "register_handlers", None)
        if callable(register_handlers):
            register_handlers(daemon)

    # 5. Start daemon and all loaded plugin tasks.
    tasks = [daemon.run()]
    for plugin in plugins:
        tasks.append(plugin.run())

    log.info("Starting %d tasks...", len(tasks))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    """Run daemon with graceful shutdown on Ctrl+C."""
    args = parse_args()
    try:
        asyncio.run(main(args.debug))
    except KeyboardInterrupt:
        logging.info("NSD is shutting down...")