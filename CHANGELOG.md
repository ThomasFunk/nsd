# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog.

## [Unreleased]

### Changed

- Improved inline documentation in core modules with English docstrings and comments:
	- `core/config.py`
	- `core/plugin_loader.py`
	- `core/server.py`
- Improved inline documentation in plugin and entrypoint modules:
	- `modules/base.py`
	- `modules/automount.py`
	- `modules/notifications.py`
	- `nsd.py`
- Updated `README.md` to match current nsd architecture, setup, run workflow, configuration behavior, and IPC examples.
- Translated `Roadmap.md` to English while preserving milestones and checkbox states.

## [0.1.0] - 2026-03-21

### Added

- Initial nsd project structure with core, modules, and tools directories.
- Async Unix Domain Socket daemon core (`/tmp/nsd.sock` default).
- Dynamic plugin loading from `modules/` for classes inheriting `BasePlugin`.
- Initial plugin implementations for automount and DBus notifications.
- CLI helper tool `tools/nsd-send/nsd-send.py` for manual IPC message testing.
- Workspace and XDG-aware TOML configuration loading with defaults.

### Changed

- Added `-d/--debug` to `nsd.py`.
- Centralized logging with named loggers across core and plugin modules.

### Fixed

- Resolved daemon/server initialization mismatch by wiring `NightshadeDaemon` to `ConfigManager`.

### Removed

- No removals in this release.

### Documentation

- Updated roadmap status for completed Phase 1 items (configuration, IPC server, plugin loader, logging).

