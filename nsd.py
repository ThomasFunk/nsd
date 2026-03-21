#!/usr/bin/env python3

__author__ = 'Thomas Funk'
__coauthors__ = 'Github Copilot & Gemini'
__date__ = "2026/03/21"
__version__ = "0.1.0"

import asyncio
import argparse
import logging
from core.config import ConfigManager
from core.server import NightshadeDaemon  # Unser Socket-Server von vorhin
from core.plugin_loader import PluginLoader

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nightshade Daemon (NSD) - Ein leichtgewichtiger Daemon für Systemintegration")
    parser.add_argument("-d", "--debug", action="store_true", help="Aktiviert Debug-Logging")
    return parser.parse_args()


async def main(debug: bool) -> None:
    cfg = ConfigManager()
    configured_log_level = str(cfg.get("global", "log_level") or "info").upper()
    log_level = logging.DEBUG if debug else getattr(logging, configured_log_level, logging.INFO)
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # 1. Config laden
    # 2. Daemon (IPC Server) initialisieren
    daemon = NightshadeDaemon(cfg)
    
    # 3. Plugins laden
    loader = PluginLoader(cfg, daemon.broadcast) # Übergibt die Broadcast-Funktion
    plugins = loader.load_plugins()

    # 4. Alles zusammen starten
    tasks = [daemon.run()] # Der IPC-Server
    for plugin in plugins:
        tasks.append(plugin.run()) # Jedes geladene Plugin

    logging.info(f"Starte {len(tasks)} Tasks...")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args.debug))
    except KeyboardInterrupt:
        logging.info("NSD wird beendet...")