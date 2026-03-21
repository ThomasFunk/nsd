# nsd


Currently it's a work in progress and will change frequently.

## Features

## Installation

### 1) System dependencies
You need at least:
- Python 3.11+
- `venv` + `pip`


Examples (optional):

```bash
# Debian/Ubuntu
sudo apt install python3 python3-venv python3-pip

# Arch
sudo pacman -S python python-pip

# Fedora
sudo dnf install python3 python3-pip
```

### 2) Virtual environment and Python packages

```bash
cd ~/workset/nsd
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Run

```bash
./venv/bin/python nsd.py
```

Optional with detailed logs:

```bash
./venv/bin/python nsd.py --debug
```

Important config options in `nsd.toml`:

## Development

Local development workflow:

```bash
cd ~/workset/nsd
source venv/bin/activate
pip install -r requirements.txt
python nsd.py --debug
```

Useful checks:

```bash
python -m py_compile nsd.py
python -c "import pywayland; print('deps ok')"
```

## Troubleshooting


## Quick Check

```bash
./venv/bin/python -V
./venv/bin/python -c "import pywayland; print('ok')"
```