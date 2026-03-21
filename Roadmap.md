# Roadmap: nsd (Nightshade Daemon)
Dieses Projekt ist der zentrale Service-Hub für das labwc-Nightshade Desktop-Environment.
Es arbeitet modular, kommuniziert über JSON-Pakete via Unix Domain Sockets und ist vollständig in Python 3 geschrieben.

# Phase 1: Core & Infrastruktur (Prio: Blockierend)
- [x] Konfigurations-System: ConfigManager implementieren:
    - [x] TOML-Support
    - [x] Defaults
    - [x] nsd commandline option -d|--debug
    - [x] Setzt XDG-Pfad = Lokaler Pfad ${workspaceFolder}/; Default: XDG-Pfad ~/.config/lns/

- [x] IPC-Server: Asyncio-basierter Unix Domain Socket Server (/tmp/nsd.sock).
- [x] Plugin-Loader: Dynamisches Laden von Modulen aus modules/, die von BasePlugin erben.
- [x] Logging: Zentralisierte Log-Ausgabe für alle Plugins und den Core.

# Phase 2: System-Services & Hardware (Prio: Hoch)
- [ ] Automount-Plugin:
    - [ ] Integration von pyudev für Hardware-Events.
    - [ ] Triggerung von udisksctl für passwortloses Mounten.
    - [ ] Broadcast von mounted/unmounted Events an den Socket.
- [ ] Polkit-Integration: Erstellen und Dokumentieren der .rules für privilegierte Aktionen ohne Passwort-Prompt.
- [ ] Desktop-Sync: Sicherstellen, dass ld-icons die Mount-Events sofort verarbeiten kann.

# Phase 3: Desktop-Integration (Prio: Mittel)
- [ ] Notification-Server:
    - [ ] Registrierung am DBus (org.freedesktop.Notifications).
    - [ ] Umwandlung von DBus-Signalen in nsd-JSON-Pakete für die Anzeige in SimpleWx.
- [ ] Labwc-Bridge:
    - [ ] Implementierung einer Schnittstelle zur Remotesteuerung von labwc (Fenster schließen, Workspace-Wechsel).
    - [ ] Überwachung von labwc-Statusänderungen.
- [ ] Hot-Corner-Relay: Empfang von Signalen aus h-corners und Ausführung der konfigurierten Befehle.

# Phase 4: Tools & Stabilisierung (Prio: Niedrig)
- [ ] nsd-send CLI: Kleines Python-Tool, um manuell JSON-Befehle an den Socket zu schicken (für Shell-Skripte).
- [ ] Hot-Reload: Implementierung von SIGHUP zum Neuladen der TOML-Konfiguration ohne Prozess-Neustart.
- [ ] Auto-Discovery: Plugins sollen zur Laufzeit erkennen, welche anderen LNS-Tools (wie wbar) gerade aktiv sind.