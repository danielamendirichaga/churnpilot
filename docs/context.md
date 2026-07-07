# churnpilot — Context

Background and constraints for the PRD. Full design detail: `DESIGN_BRIEF.md`.

## Problem

Churn/retention analysis is judgment-heavy but easy to get *wrong-but-confident*: a model
that looks great in-sample quietly collapses in production (leakage, drift, an unstable
score). Teams need not just a prediction, but a *trustworthy* end-to-end analysis — and the
slow parts (interpreting metrics, spotting leakage, choosing a model, simulating a retention
policy, watching for drift) are exactly where an AI copilot helps most.

## The one idea

The AI agent does **judgment and explanation**; a deterministic, unit-tested Python CLI does
**all compute**; typed artifacts with lineage are the **contract** between them. Single-agent,
human-in-the-loop. (Re-versioned from the prior work pattern into churn.)

## Goals

1. **Portfolio piece** for **Data Scientist / Research Scientist / Applied Scientist** roles —
   defensible line-by-line in an interview.
2. **Deeply learn** the agent + tested-CLI + typed-artifacts pattern by building it end-to-end.

## Target users

- **Primary:** a data scientist comfortable in a terminal, pointing the tool at a customer
  table (their own DB, or the bundled synthetic data).
- **Reviewer:** an interviewer / hiring manager evaluating the repo and its README/report.

## Constraints

- **Single-agent**, human-in-the-loop (propose, don't decide). No multi-agent orchestration.
- **Terminal CLI**, print-to-screen; **config-driven** (`churn.yaml`), installable (`pip`).
- **Deterministic**: seed everything; same inputs → same outputs.
- **Clean-room + synthetic only**: no real customer data / PII in the repo. Data is generated.
- **The tested core imports only numpy/pandas** — never sklearn/xgboost.
- **Four principles** (from credit-lab): DS-leads · compute in tested code not the prompt ·
  working-result enforcement · multi-entry.
- Stack: Python 3.11, `uv`, `typer`, scikit-learn, xgboost, imbalanced-learn, pydantic,
  matplotlib/plotly, streamlit; pytest/ruff/mypy.

## Non-goals

- **Not** general AutoML — one problem shape (binary churn), reusable across datasets.
- **Not** a production ML platform — medium contract tier, no schema-governance/versioning infra.
- **Not** multi-agent.
- **Uplift/causal modeling and seasonality are v2**, not v1.
- Not a non-technical, no-code product — the user is a DS.

## Success criteria

- A newcomer clones the repo, runs the quickstart, gets **green tests**, generates synthetic
  data, and runs the full v1 loop (`generate → … → simulate-policy → report → monitor`) to a
  coherent result.
- Every number is produced by tested code; every persisted step emits a typed, lineage-bearing
  artifact.
- The agent can drive the pipeline end-to-end, flagging the planted leakage feature and the
  wrong (`random`) split, and proposing a retention policy — while the DS stays in charge.
- The author can defend every design decision (see `ADRs.md`) in an interview.
