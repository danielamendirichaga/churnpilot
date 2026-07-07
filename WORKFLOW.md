# WORKFLOW — churnpilot

A single-agent, config-driven churn/retention analysis tool: the AI does judgment and
explanation; deterministic, tested Python does all compute. This file is the process;
`AGENTS.md` is how the code works.

---

## Persistence & Memory

Each session starts fresh, so files on disk are the project's memory. Three files carry
state across sessions:

- **AGENTS.md** — how the project works: architecture rules, conventions, key-file map,
  commands, gotchas. Auto-loads every session (as `CLAUDE.md` / `AGENTS.md`), so it primes
  the agent. The most important file — keep it current.
- **STATUS.md** — where things stand: done, in progress, next, and anything needed to
  resume cleanly.
- **CHANGELOG.md** — append-only history of what changed and when.

**Definition of Done (DoD):** a slice isn't done until you've updated `STATUS.md`,
`CHANGELOG.md`, and its GitHub issue (closed or checked off). Update `AGENTS.md` too
whenever a convention, architecture rule, key file, or gotcha changes.

## Session start — Orient

Before touching anything:

1. Read **AGENTS.md** — how the project works.
2. Read **STATUS.md** — where things stand.
3. Open the **active GitHub issue** — what you're working on now.

## 1) Setup

- Create the project directory and GitHub repo; connect it to Claude (MCP or CLI).
- Scaffold with `uv`:
  - `uv venv --python 3.11 .venv`
  - `pyproject.toml` with `[project.scripts]`: `churnpilot = "churnpilot.cli:app"`
  - `churnpilot/` package (`config.py`, `source.py`, `cli.py`) + `tests/`
  - Core deps: `typer`, `pandas`, `numpy`, `pyarrow`, `scikit-learn`,
    `matplotlib`/`plotly`, `streamlit`. Dev deps: `pytest`, `ruff` (+ `mypy` for types).
- Create `AGENTS.md`, `STATUS.md`, `CHANGELOG.md` from the templates below.
- Verify: `.venv/bin/pytest -q` runs and `churnpilot --help` prints.

## 2) Planning

### 2.1) Idea
- Capture the raw idea.
- `/grill-with-docs` — pressure-test the idea against the reference docs.
- Domain modeling — define core entities and vocabulary
  (**Customer, Cohort, Score, Model, Policy, Offer, DriftReport**).

### 2.2) Spec — one layered PRD
- `/to-prd` produces: `context.md` (background + constraints), ADRs (e.g. "agent never
  computes numbers"; "single-agent"; "time-aware split default"), user stories (become the
  acceptance criteria in Eval), and a **slice breakdown** (every requirement anchored to
  one slice).
- Structure the PRD in three parts:
  1. **Deterministic ML engine** — acceptance = *unit/integration* tests.
  2. **Contract / interface** (load-bearing) — CLI signatures, `churn.yaml` schema, output
     shapes, and what the agent may/may not do.
  3. **Agent behavior** — guardrails + interaction; acceptance = *behavioral/E2E* checks.
- Output: `PRD.md`, every requirement anchored to a slice.

### 2.3) Slices
- `/to-issue` — one GitHub issue per slice, so work can be managed and checked off.

### 2.4) Design direction (charts, report & dashboard)
Do this when you reach the visual slices (build steps 7–8), not up front.

- Write a mini visual spec: report/dashboard look and feel, must-show charts (gain/lift
  curve, PSI-over-time, policy trade-off), and what to avoid.
- Define chart design tokens — palette, chart style, number formatting — using the
  **`dataviz` skill**.
- Build on Streamlit's built-in components + the single tested `charts.py`.
- Lock taste on **one chart** (the gain/lift chart) before styling the rest.

## 3) Build

- Orient (AGENTS → STATUS → issue), then work one slice at a time, smallest viable first.
- Build order: `config`+`init`+`generate` → `validate` → `profile` → `metrics` →
  `split` → `train` → `compare` → `evaluate` → `simulate-policy` → `charts`+`report` →
  `monitor` → package → `app`+`dashboard` (v1.1).
- For visual slices, build the first chart per the locked design direction and confirm
  taste before scaling to the rest.
- On finishing each slice, apply the **DoD**.
- Build ⇄ Eval is a cycle — run the checks below before moving on.

## 4) Eval / Test (by layer)

Run in order; a slice passes only when its layers are green:

1. **Static** — `ruff format .`, `ruff check .`, `mypy churnpilot` (if used).
2. **Unit** — `pytest` on isolated logic (metrics, validators, policy math).
3. **Integration** — `pytest` on modules together (a CLI command end-to-end on synthetic
   data).
4. **Behavioral / E2E** — run the real CLI flow against the slice's user stories; for the
   agent layer, behavioral checks ("proposes before deciding? catches the leakage feature?").
5. **Manual smoke** — run the command / open `report.html` / click through the dashboard.

Fix and re-run until green. Apply the DoD on notable changes.

## 5) Launch / Release

- **Package** — `uv build` → an installable wheel; confirm `pip install .` +
  `churnpilot --help` in a clean venv.
- **Tag a GitHub release** (semver) with notes from `CHANGELOG.md`.
- *(Optional)* Publish to **PyPI** so `pip install churnpilot` works for anyone.
- *(Optional)* Deploy the dashboard to **Streamlit Community Cloud** for a live demo link.
- Smoke-test the installed tool / live dashboard.
- Mark the release in `STATUS.md` and `CHANGELOG.md`.

---

## Templates

### `AGENTS.md`

```markdown
# AGENTS — churnpilot

## Architecture & conventions
- Split: agent does judgment/explanation; deterministic, tested Python does ALL compute. Never compute in the prompt.
- Single-agent (Claude drives the CLI). Human-in-the-loop: propose, don't decide.
- Config-driven: everything reads churn.yaml — no hardcoded column names.
- charts.py is the single source of truth for visuals (report + dashboard reuse it).
- Determinism: seed everything; same inputs → same outputs.

## Key files (map)
- churn.yaml        — user config (data source + columns)
- churnpilot/config.py, source.py, validate.py, metrics.py, model.py, policy.py, monitor.py, charts.py, report.py, app.py, cli.py
- tests/            — green tests behind every step

## Commands
- setup:     uv venv --python 3.11 .venv && uv pip install --python .venv -e ".[dev]"
- data:      churnpilot generate --out data/sample.parquet
- run:       churnpilot <command>   (validate | profile | split | train | evaluate | simulate-policy | monitor | report)
- dashboard: streamlit run churnpilot/app.py
- test:      .venv/bin/pytest -q
- lint/fmt:  ruff check .   /   ruff format .
- build:     uv build

## Gotchas
- scikit-learn only in model/policy paths; tested core must import without it.
- Time-aware split by date_col is the default — random split is opt-in and wrong for cohorts.
- Leakage: never feed cancellation-flow / exit-survey fields as features.
```

### `STATUS.md`

```markdown
# Status — churnpilot (updated <date>)

## Done
-

## In progress
-

## Next up
-

## Blockers / open questions
-
```

### `CHANGELOG.md` entry format

```markdown
## <YYYY-MM-DD> — <slice / change name>
- <what changed, one line per item> (#<issue>)
```
