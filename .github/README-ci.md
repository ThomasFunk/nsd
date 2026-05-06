# CI Runner Setup (Wayland Smoke)

This document explains how to run the optional `wayland` test marker from
`.github/workflows/ci.yml`.

## Overview

- Default CI job (`tests`) runs on `ubuntu-latest`.
- Optional Wayland smoke job (`wayland-smoke`) runs only when manually triggered
  with `run_wayland=true`.
- The smoke job expects a self-hosted runner with labels:
  - `self-hosted`
  - `linux`
  - `wayland`

## Self-hosted runner requirements

Install on the runner host:

- Python 3.13+
- `labwc` available in `PATH`
- A working Wayland session for the runner user

Note: the `wayland-smoke` job intentionally uses `python3` from the runner
system instead of `actions/setup-python`. This avoids platform/image mismatch
issues on self-hosted distributions (for example Debian 13).

Recommended package check:

```bash
which labwc
python3 --version
```

## Environment expectations

The `wayland` smoke test in `tests/test_labwc_bridge.py` skips automatically when:

- `WAYLAND_DISPLAY` is not set, or
- `labwc` binary is missing, or
- `labwc --reconfigure` cannot be executed in the current session.

To make the smoke test actually run (not skip), ensure the runner process has access
to the active Wayland session environment (`WAYLAND_DISPLAY`, and if needed `XDG_RUNTIME_DIR`).

## Troubleshooting

- Symptom: test is skipped with "WAYLAND_DISPLAY is not set"
  - Cause: runner process does not inherit Wayland session variables.
  - Fix: start the runner from the same user session, or export `WAYLAND_DISPLAY`
    and `XDG_RUNTIME_DIR` for the runner service context.

- Symptom: test is skipped with "labwc binary not found in PATH"
  - Cause: `labwc` is not installed or not visible in runner PATH.
  - Fix: install `labwc` and verify with `which labwc` in the runner environment.

- Symptom: test is skipped with "labwc reconfigure not available in this session"
  - Cause: command cannot reach an active labwc-managed Wayland session.
  - Fix: ensure the runner user owns the active session and has matching runtime
    environment variables.

- Symptom: workflow stays pending on `wayland-smoke`
  - Cause: no self-hosted runner matches labels `self-hosted`, `linux`, `wayland`.
  - Fix: add the `wayland` label to the intended runner in repository settings.

## Manual workflow trigger

In GitHub Actions:

1. Open the `CI` workflow.
2. Click `Run workflow`.
3. Set `run_wayland` to `true`.
4. Start the run.

The `wayland-smoke` job is intentionally separate so regular PR CI remains stable
without GUI/session dependencies.
