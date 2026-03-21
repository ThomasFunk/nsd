So testest du damit
Sobald dein nsd.py läuft, kannst du in einem zweiten Terminal verschiedene Szenarien simulieren:

A. Ein einfaches Kommando senden:

```Bash
python3 nsd-send.py --action reload
```

B. Eine Benachrichtigung simulieren (Broadcast an alle Tools):

```Bash
python3 nsd-send.py --type broadcast --action notify --payload '{"title": "Test", "msg": "Hallo von der Konsole"}'
```

C. Ein komplettes JSON-Paket (Raw):

```Bash
python3 nsd-send.py --raw '{"src": "manual", "type": "command", "action": "mount", "payload": {"dev": "/dev/sdb1"}}'
```

3. Profi-Tipp für die Entwicklung
Du kannst das Skript ausführbar machen und nach /usr/local/bin/nsd-send verlinken. 
Dann kannst du von überall einfach nsd-send --action reload tippen.

```Bash
chmod +x nsd-send.py
```

Optional:

```Bash
sudo ln -s $(pwd)/nsd-send.py /usr/local/bin/nsd-send
```

Damit steht dein Test-Setup! Du hast den Daemon, die Plugin-Struktur, das Automount-Modul, 
die Copilot-Instructions und nun das CLI-Tool.