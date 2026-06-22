# Phase 9 Final Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the completed fraud-sentinel demo against the PRD definition of done and publish final go/no-go evidence.

**Architecture:** Phase 9 does not add new product behavior. It runs the documented verification commands, records exact evidence in `IMPLEMENTATION_STATUS.md`, and keeps generated data, benchmark outputs, and dashboard artifacts out of Git.

**Tech Stack:** Python 3.12+, DuckDB, Typer, Pydantic, Jinja2, NetworkX, Streamlit, Plotly, pytest, Ruff, shell scripts, Makefile.

## Global Constraints

- Treat `PRD.md` as the source of truth.
- Follow `AGENTS.md`.
- Implement phases in PRD order.
- Keep fraud detection deterministic and rule-based.
- Do not send raw transaction data to external models or APIs.
- Use synthetic or approved anonymized data only.
- Label outputs as suspicious indicators requiring human review, not confirmed fraud.
- Preserve run provenance, configuration hashes, source fingerprints, and stage timings.
- Do not generate one Markdown file per raw transaction.
- Keep dashboard graph rendering bounded by configuration.
- Never weaken or delete valid tests just to make the suite pass.
- Do not commit generated large data or artifacts.

---

## File Structure

- Modify `IMPLEMENTATION_STATUS.md`: update Phase 9 status, exact command evidence, benchmark evidence or limitation, known limitations, and final go/no-go.
- Create `docs/superpowers/plans/2026-06-23-phase-9-final-verification.md`: final verification checklist and evidence map.
- Do not modify deterministic detection code unless a verification failure exposes a real defect.

## Task 1: Preflight And Scope Confirmation

**Files:**
- Read: `PRD.md`
- Read: `AGENTS.md`
- Read: `IMPLEMENTATION_STATUS.md`
- Read: `README.md`
- Read: `Makefile`
- Read: `scripts/benchmark.sh`
- Read: `scripts/demo_setup.sh`
- Read: `scripts/demo_run.sh`
- Read: `scripts/demo_monitor_delta.sh`
- Read: `config/pipeline.yaml`
- Read: `config/rules.yaml`
- Read: `config/okf.yaml`
- Read: `config/dashboard.yaml`
- Read: `src/fraud_demo/`
- Read: `dashboard/`
- Read: `tests/`
- Read: `docs/superpowers/specs/2026-06-23-phase-8-performance-hardening-design.md`
- Read: `docs/superpowers/plans/2026-06-23-phase-8-performance-hardening.md`

**Interfaces:**
- Consumes: local `main` at merge commit `6ea631d`.
- Produces: isolated branch `codex/phase-9-final-verification`.

- [ ] **Step 1: Confirm branch and commit**

Run:

```bash
git status -sb
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git log -1 --oneline
```

Expected: local `main` starts at `6ea631d Merge pull request #7 from khalilhimura/codex/phase-8-performance-hardening`; unrelated untracked files remain unstaged.

- [ ] **Step 2: Review Phase 9 acceptance criteria**

Run:

```bash
sed -n '1720,1905p' PRD.md
```

Expected: Phase 9 requires `make lint`, `make test`, `make demo-data`, `make run-demo`, `make validate-okf`, benchmark evidence, known limitations, and exact demo commands.

## Task 2: Core Verification Gates

**Files:**
- Read: full source, dashboard, scripts, tests, and config tree.
- Modify: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Consumes: `.venv/bin/python -m fraud_demo`
- Produces: fresh verification evidence for tests, lint, demo artifacts, OKF validation, monitoring, scans, and benchmark reports.

- [ ] **Step 1: Run automated tests**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
.venv/bin/ruff check .
```

Expected: all checks pass.

- [ ] **Step 3: Run smoke benchmark**

Run:

```bash
make benchmark-smoke
```

Expected: `/private/tmp/fraud-sentinel-benchmark-smoke-report.json` is written and row, alert, amount, and OKF checks pass.

- [ ] **Step 4: Run full demo-data and run-demo path**

Run:

```bash
make demo-data
make run-demo
```

Expected: `data/raw/transactions_1m.csv` is generated locally, `RUN_DEMO` completes, and prepared dashboard/OKF artifacts are refreshed without committing generated outputs.

- [ ] **Step 5: Validate OKF bundle**

Run:

```bash
.venv/bin/python -m fraud_demo validate-okf --bundle artifacts/okf_bundle
```

Expected: OKF validation exits 0 with zero hard errors.

- [ ] **Step 6: Run monitoring delta smoke**

Run:

```bash
make demo-monitor
```

Expected: `RUN_MONITOR_DEMO` completes, monitoring summary and alert-change artifacts are written, and OKF remains valid.

- [ ] **Step 7: Run full benchmark if practical**

Run if hardware/time allows:

```bash
make benchmark
```

Expected: `benchmark_report.json` records a one-million-row run with reconciliation checks passing. If not practical, record the reason and preserve smoke benchmark evidence.

## Task 3: Safety And Artifact Readiness Checks

**Files:**
- Read: `src/`
- Read: `dashboard/`
- Read: `scripts/`
- Read: `tests/`
- Read: repository status and ignored generated paths.

**Interfaces:**
- Produces: safety scan evidence for external calls, dashboard raw-CSV boundary, human-review language, and clean PR scope.

- [ ] **Step 1: Scan for external model/API calls**

Run:

```bash
rg -n "requests|httpx|openai|anthropic|api_key|http://|https://" src dashboard scripts tests Makefile pyproject.toml README.md
```

Expected: no production external model/API calls. Any documentation-only matches must be explicitly reviewed.

- [ ] **Step 2: Scan dashboard raw CSV reads**

Run:

```bash
rg -n "read_csv" dashboard src/fraud_demo tests/test_dashboard.py scripts
```

Expected: dashboard page render code does not read raw CSV; production CSV reads remain limited to ingestion or explicit synthetic demo preparation.

- [ ] **Step 3: Scan human-review language**

Run:

```bash
rg -n "confirmed fraud|proves fraud|fraudster|human review|suspicious" README.md IMPLEMENTATION_STATUS.md src dashboard tests
```

Expected: user-facing conclusions remain framed as suspicious indicators requiring human review, not confirmed fraud.

- [ ] **Step 4: Confirm generated data and secrets are not in PR scope**

Run:

```bash
git status -sb
git diff --stat
git diff --check
```

Expected: staged/committed scope is limited to Phase 9 plan and status documentation; generated data, artifacts, secrets, and unrelated slide directories remain uncommitted.

## Task 4: Status Update And Publish

**Files:**
- Modify: `IMPLEMENTATION_STATUS.md`
- Commit: `docs/superpowers/plans/2026-06-23-phase-9-final-verification.md`
- Commit: `IMPLEMENTATION_STATUS.md`

**Interfaces:**
- Produces: final Phase 9 status and GitHub PR merged to `main`.

- [ ] **Step 1: Update implementation status**

Record:

```text
Phase 9 final verification command results, benchmark report or limitation, fallback regeneration commands, dashboard artifact readiness, safety scans, known limitations, and final go/no-go.
```

- [ ] **Step 2: Commit Phase 9 documentation**

Run:

```bash
git add docs/superpowers/plans/2026-06-23-phase-9-final-verification.md IMPLEMENTATION_STATUS.md
git commit -m "docs: record phase 9 final verification"
```

- [ ] **Step 3: Push, open PR, merge, and verify main**

Run:

```bash
git push -u origin codex/phase-9-final-verification
gh pr create --base main --head codex/phase-9-final-verification --title "[codex] phase 9 final verification" --body-file /tmp/fraud-sentinel-phase-9-pr.md
gh pr merge --merge --delete-branch
git switch main
git pull --ff-only
git log -1 --oneline
git status -sb
```

Expected: PR is merged to `main`; local `main` is fast-forwarded to the merge commit and has no Phase 9 tracked diff.
