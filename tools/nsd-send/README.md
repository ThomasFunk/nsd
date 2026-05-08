How to test with it
Once `nsd.py` is running, you can simulate different scenarios in a second terminal:

A. Send a simple command:

```Bash
python3 nsd-send.py --action reload
```

B. Simulate a notification (broadcast to all tools):

```Bash
python3 nsd-send.py --type broadcast --action notify --payload '{"title": "Test", "msg": "Hello from the console"}'
```

C. Send a full JSON packet (raw):

```Bash
python3 nsd-send.py --raw '{"src": "manual", "type": "command", "action": "mount", "payload": {"dev": "/dev/sdb1"}}'
```

3. Pro tip for development
You can make the script executable and symlink it to `/usr/local/bin/nsd-send`.
Then you can run `nsd-send --action reload` from anywhere.

```Bash
chmod +x nsd-send.py
```

Optional:

```Bash
sudo ln -s $(pwd)/nsd-send.py /usr/local/bin/nsd-send
```

That completes your test setup. You now have the daemon, plugin structure, automount module and the CLI tool.