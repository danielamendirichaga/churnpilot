# churnpilot

Config-driven churn/retention analysis. Deterministic, tested Python does all the
compute; an AI agent (Claude) drives the CLI and explains the results. Single-agent,
human-in-the-loop, terminal + Streamlit.

- **`WORKFLOW.md`** — the process (setup → plan → build → eval → launch).
- **`AGENTS.md`** — how the code works (architecture, key files, commands, gotchas).
- **`STATUS.md`** — where things stand right now.

## Quickstart (once the environment is set up)

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/churnpilot version
```

## Status

Setup complete. Implementation begins with build slice 1 (config + generate).
See `STATUS.md`.
