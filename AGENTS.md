# Agent Operating Rules

This repository follows `PRD.md` as the source of truth for the Agentic AI mule-account fraud detection demo.

## Core Rules

- Implement phases in PRD order.
- Record progress, assumptions, verification output, and blockers in `IMPLEMENTATION_STATUS.md`.
- Use Python 3.12 or later with DuckDB, Typer, Pydantic, Jinja2, NetworkX, Streamlit, Plotly, and pytest unless a later documented decision changes the stack.
- Keep fraud detection deterministic and rule-based.
- Do not send raw transaction data to external models or APIs.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, and stage timings.
- Do not generate one Markdown file per raw transaction.
- Keep dashboard graph rendering bounded by configuration.
- Never weaken or delete valid tests just to make the suite pass.

## Phase Discipline

- Phase 0: repository assessment and implementation plan.
- Phase 1: project scaffold, config models, CLI skeleton, logging, Makefile, and basic tests.
- Phase 2 and later: implement only after Phase 1 verification is passing.

