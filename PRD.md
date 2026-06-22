# Product Requirements Document and Technical Specification

## Agentic AI Mule-Account Fraud Detection Demo with an OKF Knowledge Graph

| Field | Value |
|---|---|
| Document status | Implementation-ready MVP specification |
| Version | 1.0 |
| Date | 2026-06-22 |
| Primary implementation agent | OpenAI Codex |
| Demo duration | 2 hours |
| Target complexity | 5–7 out of 10 |
| Input scale | Approximately 1,000,000 banking transaction rows in CSV format |
| Primary outputs | Fraud dashboard, OKF v0.1 knowledge bundle, Obsidian-compatible graph, alerts and evidence artifacts |
| Intended environment | Local development machine or controlled demo environment |

> **Instruction to Codex:** Treat this document as the source of truth for the MVP. Implement in the stated phase order, preserve all safety and data-handling constraints, run tests after each phase, and record progress in `IMPLEMENTATION_STATUS.md`. Make reasonable implementation decisions without waiting for clarification unless a missing credential or inaccessible file makes progress impossible.

---

## 1. Executive Summary

Build a demo system that processes approximately one million banking transactions from CSV files and detects suspicious activity associated with potential mule accounts. The system must:

1. Ingest, validate, normalize, and profile transaction data.
2. Compute transparent account-level and network-level fraud indicators.
3. Assign explainable risk scores using configurable rules.
4. Identify suspicious account clusters and fund-flow relationships.
5. Generate a portable knowledge graph as an **Open Knowledge Format (OKF) v0.1 bundle**.
6. Allow the OKF bundle to be opened directly as an Obsidian vault.
7. Provide a Streamlit dashboard for investigation and repeat monitoring.
8. Demonstrate Codex acting as an engineering agent that plans, implements, tests, debugs, and documents the workflow.

The large language model must **not** inspect or classify one million rows directly. Deterministic code using Python and DuckDB performs all bulk processing. Codex is the development agent; optional runtime narrative generation may only receive anonymized aggregate data and must be disabled by default.

The system identifies **suspicious indicators**, not confirmed fraud. Human review remains mandatory before any operational decision.

---

## 2. Product Vision

Provide a credible, visually compelling demonstration of how an agentic coding workflow can accelerate the creation of a fraud-analysis system while preserving explainability, portability, and analyst control.

The demo should tell this story:

> “Codex acts as an engineering coworker. It builds and validates a deterministic fraud pipeline, surfaces suspicious account networks, packages the findings as a portable OKF knowledge graph, and creates an analyst dashboard. The AI assists the analyst; it does not make an unreviewed fraud determination.”

---

## 3. Definitions

| Term | Meaning |
|---|---|
| Agentic AI | An AI system that can plan work, use tools, inspect results, and iterate toward a goal. |
| Mule account | An account suspected of receiving, holding, or forwarding illicit funds on behalf of another party. |
| Knowledge graph | A network of entities and relationships, such as accounts connected by transfers, shared devices, alerts, and risk signals. |
| OKF | Open Knowledge Format: a portable directory of Markdown concept documents with YAML frontmatter and standard Markdown links. |
| Concept | One unit of knowledge represented by one Markdown file in an OKF bundle. |
| Concept ID | The path of a concept file within the bundle, excluding the `.md` suffix. |
| ETL | Extract, Transform, Load: reading source data, cleaning or transforming it, and writing usable outputs. |
| Fan-in | Many source accounts transferring into one receiving account. |
| Fan-out | One account transferring to many downstream accounts. |
| Pass-through | Funds entering an account and leaving again within a short period. |
| Entity resolution | Matching records that refer to the same real-world account, customer, device, or other entity. The MVP uses exact normalized identifiers only. |
| Micro-batch monitoring | Repeatedly processing newly arrived files rather than operating a true real-time stream. |
| Pseudonymization | Replacing sensitive identifiers with stable masked values so relationships remain analyzable without exposing original identifiers. |

---

## 4. Problem Statement

Fraud analysts often begin with large transaction tables that are difficult to investigate manually. Suspicious behavior is frequently visible only when multiple signals are combined:

- Many unrelated accounts pay into the same account.
- Funds are transferred onward soon after receipt.
- Several accounts share devices or IP addresses.
- A small number of accounts act as hubs in a larger transfer network.
- Activity changes sharply after an account is opened or after a dormant period.

A flat CSV does not present these relationships clearly. A graph and dashboard can reduce investigation time, but building the ingestion, feature engineering, graph export, monitoring, and analyst interface usually requires substantial engineering effort.

This product demonstrates how Codex can accelerate that engineering work while the final detection logic remains deterministic, testable, and explainable.

---

## 5. Goals

### 5.1 Product goals

1. Process a one-million-row CSV reliably on a typical developer workstation.
2. Detect several intentionally injected mule-like scenarios in synthetic data.
3. Produce explainable account risk scores and alert evidence.
4. Build a filtered, analyst-usable account relationship graph.
5. Export fraud knowledge in a conformant OKF v0.1 bundle.
6. Open the same bundle in Obsidian without proprietary plugins.
7. Present an interactive dashboard for investigation.
8. Support repeatable file-based monitoring runs.
9. Demonstrate an auditable Codex engineering workflow.

### 5.2 Success metrics

| Metric | MVP target |
|---|---:|
| Raw transactions processed | At least 1,000,000 rows |
| Pipeline completion time | Target ≤ 5 minutes on 8 CPU cores, 16 GB RAM, SSD; hard demo limit ≤ 10 minutes |
| Peak memory | Target ≤ 8 GB |
| Injected mule accounts detected | ≥ 90% of accounts explicitly marked as synthetic fraud seeds |
| OKF hard conformance errors | 0 |
| Internal broken-link warnings | 0 for generated concepts |
| Dashboard initial page load from prepared artifacts | Target ≤ 3 seconds |
| Core pipeline test coverage | Target ≥ 80% for ingestion, scoring, graph, and OKF modules |
| High/critical alerts with evidence explanation | 100% |
| Raw transaction notes generated in OKF | 0 by default |

Performance targets are demo targets, not production service-level agreements.

---

## 6. Non-Goals

The MVP will not:

1. Serve as a production anti-money-laundering or transaction-monitoring platform.
2. Make autonomous account-blocking, reporting, or customer-action decisions.
3. Claim that a flagged account is confirmed fraudulent.
4. Implement full legal or regulatory compliance workflows.
5. Train a machine-learning model.
6. Perform fuzzy identity matching across people or organizations.
7. Trace the true provenance of each monetary unit through commingled balances.
8. Export one Markdown note per raw transaction.
9. Render the complete one-million-row transfer graph in a browser.
10. Require a graph database, cloud warehouse, or proprietary knowledge platform.
11. Require a runtime LLM or external API call to complete the core pipeline.
12. Provide true real-time streaming in the MVP.

---

## 7. Product Principles

1. **Deterministic before generative:** calculations, rules, joins, graph edges, and alerts are produced by code.
2. **Explainability by default:** every score is traceable to rules and feature values.
3. **Human review required:** the output is an investigation aid.
4. **Portable knowledge:** OKF is the canonical knowledge output; Obsidian is one consumer.
5. **Scale-aware:** raw data stays in columnar files or DuckDB, not in Markdown.
6. **Privacy-aware:** no unapproved raw personally identifiable information enters generated notes or external services.
7. **Reproducible:** every run records data fingerprint, configuration hash, code version, and timestamps.
8. **Demo reliability over novelty:** the live presentation uses prepared fallbacks and bounded workloads.

---

## 8. Target Users and User Stories

### 8.1 Fraud analyst

**Story:** As a fraud analyst, I need a prioritized alert queue and clear evidence so I can decide which accounts require deeper review.

Acceptance conditions:

- Alerts are sortable by score, severity, amount, and recency.
- Selecting an account shows rule hits, counterparties, activity timeline, and graph neighborhood.
- Every alert links to its OKF concept.

### 8.2 Compliance reviewer

**Story:** As a compliance reviewer, I need an auditable explanation of why an alert was generated.

Acceptance conditions:

- Each alert records the pipeline run and rule configuration used.
- Evidence values are displayed next to thresholds.
- Language says “suspicious” or “requires review,” not “confirmed fraud.”

### 8.3 Data engineer

**Story:** As a data engineer, I need a repeatable pipeline that handles malformed rows, duplicate files, and reruns safely.

Acceptance conditions:

- The CLI validates required columns.
- Invalid rows are quarantined with reasons.
- Duplicate transactions and already processed files are handled idempotently.
- Outputs are partitioned or versioned by run ID.

### 8.4 Demo presenter

**Story:** As a presenter, I need a controlled two-hour flow that visibly demonstrates Codex contribution without depending on fragile live generation.

Acceptance conditions:

- A completed fallback branch and prepared artifacts exist.
- A live Codex task can add or change one rule, test it, and regenerate outputs.
- A new CSV batch can be processed to show continuous monitoring.

---

## 9. Demo Scope and Presentation Strategy

This is a two-hour showcase, not a requirement to build the entire system live in two hours.

### 9.1 Recommended preparation

- Prebuild approximately 70–80% of the implementation.
- Pre-generate the one-million-row synthetic dataset.
- Pre-run the full pipeline and preserve successful artifacts.
- Prepare a smaller 25,000-row development sample for live changes.
- Keep a completed Git branch as a fallback.

### 9.2 Suggested two-hour agenda

| Time | Segment |
|---:|---|
| 0–10 min | Problem, architecture, safety boundaries, and OKF rationale |
| 10–25 min | Codex inspects the repository and implements or modifies one bounded feature |
| 25–45 min | CSV ingestion, validation, profiling, and data-quality report |
| 45–70 min | Fraud features, transparent scoring, and injected scenario results |
| 70–90 min | Graph construction and OKF bundle generation |
| 90–110 min | Dashboard investigation: alert queue, account detail, and network explorer |
| 110–120 min | New batch ingestion, new alert, updated OKF graph, limitations, and next steps |

### 9.3 Preferred live Codex task

Choose one:

- Add a `shared_device` rule and unit tests.
- Change a threshold in `rules.yaml`, explain the impact, and regenerate alerts.
- Add an OKF validation check.
- Add a dashboard filter for a selected signal.

Do not rely on Codex to build the entire system during the presentation.

---

## 10. Functional Scope

### 10.1 MVP capabilities

1. Synthetic data generation when no user dataset is available.
2. CSV schema validation and normalization.
3. Data-quality profiling.
4. DuckDB-backed feature engineering.
5. Rule-based account scoring.
6. Suspicious account-to-account transfer aggregation.
7. Shared device and IP analysis when fields are present.
8. Connected-component clustering on the suspicious subgraph.
9. Alert generation with evidence.
10. OKF v0.1 bundle export and validation.
11. Obsidian-compatible standard Markdown links.
12. Streamlit dashboard.
13. File-based repeat monitoring.
14. Run manifests, logs, and reproducibility metadata.

### 10.2 Optional stretch capabilities

- An investigation chat agent that queries only processed summaries.
- LLM-generated narratives from anonymized aggregates.
- Incremental recomputation for only affected accounts.
- Community detection beyond connected components.
- Static OKF HTML visualization.
- Neo4j or another graph database consumer.
- Case management fields and analyst dispositions.

Stretch work must not delay the MVP.

---

## 11. Recommended Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.12 | Broad data, CLI, testing, and dashboard ecosystem |
| Bulk data engine | DuckDB | Efficient local CSV and Parquet processing using SQL |
| Persistent analytical store | DuckDB database file plus Parquet artifacts | Reproducible and easy to inspect |
| CLI | Typer | Clear commands and help output |
| Configuration | YAML plus Pydantic validation | Human-editable, typed configuration |
| Markdown templates | Jinja2 | Deterministic OKF note generation |
| Graph analysis | NetworkX on a filtered suspicious graph | Simple connected components and centrality for demo scale |
| Dashboard | Streamlit | Fast local data application development |
| Charts | Plotly | Interactive timelines and graph rendering |
| Testing | pytest | Unit, integration, and acceptance tests |
| File monitoring | Manual command first; `watchfiles` optional | Bounded micro-batch monitoring |
| Packaging | `pyproject.toml` | Standard dependency and tooling configuration |
| Task automation | Makefile | Stable demo commands |

Avoid adding an orchestration framework, distributed compute engine, graph database, or frontend framework unless the documented MVP cannot be met without it.

---

## 12. High-Level Architecture

```text
CSV files
   │
   ▼
Ingestion and schema validation
   │
   ├── rejected_rows.parquet
   └── normalized_transactions.parquet / DuckDB tables
   │
   ▼
Data profiling and run manifest
   │
   ▼
Account feature engineering
   │
   ▼
Rule engine and explainable risk scores
   │
   ├── account_features.parquet
   ├── account_risk.parquet
   └── alerts.parquet
   │
   ▼
Suspicious graph construction
   │
   ├── graph_nodes.parquet
   ├── graph_edges.parquet
   └── clusters.parquet
   │
   ▼
OKF exporter and validator
   │
   ├── artifacts/okf_bundle/
   ├── okf_manifest.json
   └── okf_validation_report.json
   │
   ├──────────────────────────┐
   ▼                          ▼
Obsidian                   Streamlit dashboard
```

### 12.1 Design decision: two graph representations

The system maintains two complementary graph representations:

1. **OKF-native graph:** standard Markdown links between concept documents, suitable for humans, agents, Git, Obsidian, and generic OKF consumers.
2. **Typed analytical graph:** `graph_nodes.parquet` and `graph_edges.parquet`, suitable for filtering, graph algorithms, dashboards, amounts, counts, and timestamps.

OKF links are intentionally portable and usually untyped. Typed financial relationships remain available in structured analytical artifacts and may also be represented as optional producer-defined frontmatter.

---

## 13. Input Data Contract

### 13.1 Required transaction columns

| Column | Type after normalization | Description |
|---|---|---|
| `transaction_id` | string | Unique transaction identifier |
| `event_timestamp` | timestamp with timezone | Transaction event time |
| `sender_account_id` | string | Source account identifier |
| `receiver_account_id` | string | Destination account identifier |
| `amount` | decimal(18,2) | Positive transfer amount |
| `currency` | string | ISO-style currency code, such as MYR |

### 13.2 Recommended columns

| Column | Type | Description |
|---|---|---|
| `transaction_type` | string | Transfer, cash deposit, withdrawal, card payment, etc. |
| `channel` | string | Mobile, web, ATM, branch, API, etc. |
| `sender_bank_id` | string | Sending institution identifier |
| `receiver_bank_id` | string | Receiving institution identifier |
| `sender_country` | string | Source country code |
| `receiver_country` | string | Destination country code |
| `device_id` | string | Device identifier, when available |
| `ip_address` | string | Network address, when available and approved |
| `merchant_category` | string | Optional merchant category |
| `description` | string | Optional transaction text; excluded from OKF by default |
| `sender_account_opened_at` | timestamp | Optional source account opening time |
| `receiver_account_opened_at` | timestamp | Optional destination account opening time |
| `is_synthetic_fraud_seed` | boolean | Synthetic-only evaluation label |
| `synthetic_scenario` | string | Synthetic-only scenario name |

### 13.3 Data normalization rules

1. Trim whitespace from identifiers and categorical fields.
2. Normalize blank strings to null.
3. Parse timestamps to UTC internally.
4. Display local time in `Asia/Kuala_Lumpur` where needed.
5. Reject rows with missing required identifiers, invalid timestamp, or non-positive amount.
6. Normalize currency and country codes to uppercase.
7. Deduplicate on `transaction_id`, keeping the first valid occurrence and logging duplicates.
8. Preserve original row number and source filename for traceability.
9. Do not silently coerce unparseable amounts or timestamps.
10. Calculate a SHA-256 fingerprint for every source file.

### 13.4 Invalid row handling

Write invalid records to:

```text
artifacts/runs/<run_id>/rejected_rows.parquet
```

Required fields:

```text
source_file
source_row_number
rejection_code
rejection_message
raw_values_json
```

Redact or omit sensitive free-text values in `raw_values_json` when configured.

### 13.5 Optional supporting account file

The MVP may also accept `accounts.csv` with:

```text
account_id
customer_id
account_opened_at
account_type
kyc_risk_level
home_country
status
```

The pipeline must still run when this file is absent. Rules requiring account age or KYC data are automatically disabled and reported as unavailable.

---

## 14. Synthetic Dataset Generator

When no appropriate dataset is supplied, implement a seeded generator capable of producing 1,000,000 rows.

### 14.1 Generator requirements

- Reproducible random seed.
- Configurable row count, account count, date range, and currency.
- Majority normal behavior with varied transaction patterns.
- Explicit injection of suspicious scenarios.
- Evaluation labels stored only in synthetic data.
- Output CSV plus scenario manifest.

### 14.2 Required injected scenarios

| Scenario | Pattern |
|---|---|
| `fan_in_mule` | Many distinct accounts transfer to one receiver in a short period |
| `rapid_pass_through` | The receiver forwards most received value shortly afterward |
| `layering_chain` | Funds move through a short sequence of accounts |
| `shared_device_ring` | Multiple suspicious accounts use the same device or IP |
| `cross_border_funnel` | Domestic inbound transfers are followed by cross-border outbound transfers |
| `new_account_burst` | Recently opened account has an abrupt transaction burst |
| `short_cycle` | Funds circulate back to an earlier account in a short directed cycle |

The generator must not be presented as guidance for evading detection. It exists only to test defensive analytics.

---

## 15. Feature Engineering Specification

Features are calculated per account as of the maximum transaction timestamp in the run. Store `snapshot_timestamp` with every feature row.

### 15.1 Core account features

| Feature | Definition |
|---|---|
| `incoming_count_24h` | Incoming transaction count in the last 24 hours |
| `outgoing_count_24h` | Outgoing transaction count in the last 24 hours |
| `incoming_amount_24h` | Total incoming amount in the last 24 hours |
| `outgoing_amount_24h` | Total outgoing amount in the last 24 hours |
| `unique_senders_7d` | Distinct source accounts in the last 7 days |
| `unique_receivers_7d` | Distinct destination accounts in the last 7 days |
| `incoming_amount_7d` | Total incoming amount in the last 7 days |
| `outgoing_amount_7d` | Total outgoing amount in the last 7 days |
| `pass_through_ratio_7d` | `outgoing_amount_7d / max(incoming_amount_7d, epsilon)`, capped for display at 2.0 |
| `hold_time_proxy_minutes` | Median daily interval between first inbound and first subsequent outbound transaction, using only positive intervals ≤ 24 hours |
| `cross_border_out_ratio_7d` | Outbound cross-border count divided by all outbound count in the last 7 days |
| `night_activity_ratio_7d` | Transactions between configurable local hours divided by all transactions in the last 7 days |
| `round_amount_ratio_7d` | Share of transactions divisible by a configurable amount increment |
| `shared_device_account_count_30d` | Distinct accounts using the same device in the last 30 days; maximum over devices used by the account |
| `shared_ip_account_count_30d` | Distinct accounts using the same IP in the last 30 days; maximum over IPs used by the account |
| `account_age_days` | Days between account opening and snapshot, when available |
| `active_days_30d` | Distinct days with activity in the last 30 days |
| `counterparty_concentration_7d` | Largest counterparty amount share in the last 7 days |
| `reciprocal_transfer_ratio_7d` | Share of counterparties with transfers in both directions |

### 15.2 Hold-time limitation

`hold_time_proxy_minutes` is an investigative proxy, not proof that specific incoming funds funded a particular outgoing transaction. The dashboard and OKF notes must label it as a proxy.

### 15.3 Network features on suspicious subgraph

Compute only after pre-filtering candidate accounts and relevant edges:

- In-degree and out-degree.
- Weighted in-degree and out-degree by transaction amount.
- Connected-component ID.
- Component account count.
- Component transaction amount.
- Optional PageRank or betweenness centrality for the top bounded graph.
- Short cycle indicator for cycles up to a configurable maximum length.

Do not run expensive centrality over the complete transaction graph.

---

## 16. Rule-Based Risk Scoring

Rules are configured in `config/rules.yaml`. No detection threshold may be hard-coded in Python unless it is a parser or safety default.

### 16.1 Baseline rules

| Rule ID | Description | Default weight | Illustrative condition |
|---|---|---:|---|
| `high_fan_in` | Many unique senders pay one account | 20 | `unique_senders_7d >= 10` |
| `rapid_pass_through` | Most incoming value is moved out quickly | 25 | `pass_through_ratio_7d >= 0.80` and `hold_time_proxy_minutes <= 120` |
| `high_velocity` | Unusually high transaction count in 24 hours | 15 | `incoming_count_24h + outgoing_count_24h >= 30` |
| `high_fan_out` | One account pays many downstream accounts | 10 | `unique_receivers_7d >= 10` |
| `shared_access_point` | Device or IP is shared across many accounts | 15 | device or IP account count ≥ configured threshold |
| `cross_border_funnel` | High cross-border outbound share after significant inbound activity | 10 | inbound threshold met and `cross_border_out_ratio_7d >= 0.50` |
| `new_account_burst` | Recently opened account has high recent activity | 15 | `account_age_days <= 30` and velocity threshold met |
| `short_cycle` | Account participates in a short directed transfer cycle | 20 | cycle indicator is true |

### 16.2 Risk score

```text
raw_score = sum(weight for every triggered rule)
risk_score = min(raw_score, 100)
```

Default severity bands:

| Score | Level |
|---:|---|
| 0–24 | Low |
| 25–49 | Medium |
| 50–74 | High |
| 75–100 | Critical |

### 16.3 Missing data behavior

- A rule whose required fields are unavailable is marked `not_evaluated`.
- `not_evaluated` contributes zero points.
- Alert explanations list unavailable rules separately from non-triggered rules.
- The pipeline must not replace missing evidence with invented values.

### 16.4 Explainability requirements

Every triggered rule stores:

```text
rule_id
rule_version
weight
feature_values_json
thresholds_json
human_explanation
```

Example explanation:

> “Rapid pass-through triggered because the seven-day pass-through ratio was 0.91, above the 0.80 threshold, and the hold-time proxy was 47 minutes, below the 120-minute threshold.”

---

## 17. Alert Specification

### 17.1 Alert generation

Generate an alert when:

- `risk_score >= alert_min_score`, default 50; or
- a configured mandatory rule triggers; or
- a suspicious cluster exceeds a configured cluster threshold.

### 17.2 Alert schema

```text
alert_id
run_id
account_id
risk_score
risk_level
alert_status
triggered_rule_ids
triggered_rule_count
explanation
first_activity_at
last_activity_at
incoming_amount_7d
outgoing_amount_7d
unique_senders_7d
unique_receivers_7d
hold_time_proxy_minutes
cluster_id
source_data_fingerprint
rules_config_hash
created_at
okf_concept_id
```

Default `alert_status` is `new`. The MVP may support `reviewed`, `dismissed`, and `escalated` as optional analyst fields stored separately from regenerated analytics.

### 17.3 Alert identity

Use a stable format:

```text
ALERT_<run_id>_<masked_account_id>
```

For incremental monitoring, optionally use a stable account alert plus alert-event history. Do not block the MVP on case-management design.

---

## 18. Fraud Knowledge Graph Model

### 18.1 Node types

| Node type | Purpose |
|---|---|
| Account | Primary investigated entity |
| Alert | Explainable detection event |
| Cluster | Suspicious connected component or network |
| Fraud Signal | Definition of a rule or behavior |
| Device | Shared access point, when approved |
| IP Address | Shared access point, masked by default |
| Pipeline Run | Reproducibility and provenance |
| Dataset | Source dataset description |
| Metric | Definition of a derived feature |
| Runbook | Analyst investigation guidance |

Raw transactions are not graph nodes in the default OKF bundle. Transaction evidence remains in Parquet and in aggregated edge attributes.

### 18.2 Typed analytical edge types

| Edge type | Source → target | Meaning |
|---|---|---|
| `TRANSFERRED_TO` | Account → Account | Aggregated transaction flow |
| `TRIGGERED_SIGNAL` | Account → Fraud Signal | Account met a rule condition |
| `HAS_ALERT` | Account → Alert | Alert belongs to account |
| `MEMBER_OF_CLUSTER` | Account → Cluster | Account belongs to suspicious component |
| `USED_DEVICE` | Account → Device | Account used a device |
| `USED_IP` | Account → IP Address | Account used an IP address |
| `GENERATED_IN_RUN` | Alert → Pipeline Run | Provenance relationship |
| `DERIVED_FROM_DATASET` | Pipeline Run → Dataset | Input relationship |
| `USES_METRIC` | Fraud Signal → Metric | Rule depends on metric |
| `GUIDED_BY_RUNBOOK` | Alert → Runbook | Suggested investigation process |

### 18.3 Aggregated transfer edge schema

```text
source_node_id
target_node_id
edge_type
transaction_count
total_amount
currency
first_seen_at
last_seen_at
sample_transaction_ids_json
risk_relevance_score
run_id
properties_json
```

Limit `sample_transaction_ids_json` to a small configurable number. Do not store every transaction ID in Markdown.

### 18.4 Graph filtering

For dashboard and OKF export, include:

- All high and critical accounts.
- Configurable one-hop counterparties.
- Optional two-hop accounts only when the graph remains below limits.
- Top transfer edges by risk relevance or amount.
- Devices and IPs linked to suspicious accounts only.

Default graph limits:

```yaml
max_account_nodes: 500
max_context_accounts: 500
max_cluster_nodes: 100
max_device_nodes: 200
max_ip_nodes: 200
max_edges: 5000
max_counterparties_per_account: 30
```

---

## 19. Open Knowledge Format Requirements

The canonical knowledge output is an **OKF v0.1 Draft** bundle.

### 19.1 Core OKF rules

1. The bundle is a directory tree of UTF-8 Markdown files.
2. Every non-reserved `.md` concept file starts with parseable YAML frontmatter.
3. Every concept frontmatter contains a non-empty `type` field.
4. `index.md` and `log.md` are reserved filenames and are not ordinary concepts.
5. Standard Markdown links express relationships.
6. Relative links and bundle-relative absolute links are valid. The MVP defaults to standard relative links for direct Obsidian compatibility.
7. `index.md` supports progressive navigation.
8. `log.md` records date-grouped changes using `YYYY-MM-DD` headings.
9. Unknown fields and unknown concept types are allowed.
10. Broken links are soft validation warnings, although generated links must resolve in the MVP.
11. External claims should include a `# Citations` section.

### 19.2 Root index version declaration

The bundle root `index.md` may use the OKF version declaration permitted by the specification:

```markdown
---
okf_version: "0.1"
---

# Mule Account Fraud Knowledge Bundle

- [Accounts](accounts/) - High-risk accounts and selected counterparties.
- [Alerts](alerts/) - Explainable fraud alerts.
- [Clusters](clusters/) - Suspicious account networks.
- [Signals](signals/) - Risk-rule definitions.
- [Runs](runs/) - Pipeline run provenance.
```

Subdirectory `index.md` files should contain navigation content and no frontmatter.

### 19.3 OKF bundle structure

```text
artifacts/okf_bundle/
├── index.md
├── log.md
├── accounts/
│   ├── index.md
│   └── <account_id>.md
├── alerts/
│   ├── index.md
│   └── <alert_id>.md
├── clusters/
│   ├── index.md
│   └── <cluster_id>.md
├── signals/
│   ├── index.md
│   └── <rule_id>.md
├── devices/
│   ├── index.md
│   └── <masked_device_id>.md
├── ips/
│   ├── index.md
│   └── <masked_ip_id>.md
├── metrics/
│   ├── index.md
│   └── <metric_id>.md
├── runs/
│   ├── index.md
│   └── <run_id>.md
├── datasets/
│   ├── index.md
│   └── transactions.md
├── runbooks/
│   ├── index.md
│   └── mule_account_investigation.md
└── references/
    ├── index.md
    └── okf_spec.md
```

### 19.4 Concept type vocabulary

OKF does not prescribe a central taxonomy. This producer uses descriptive types:

```text
Fraud Account
Fraud Alert
Fraud Cluster
Fraud Signal
Fraud Device
Fraud IP Address
Fraud Metric
Fraud Pipeline Run
Fraud Dataset
Fraud Runbook
Reference
```

### 19.5 Required producer fields

In addition to OKF’s required `type`, this implementation requires the following fields for generated fraud concepts where applicable:

```yaml
title: Human-readable title
description: One-sentence summary
tags: [fraud, ...]
timestamp: ISO-8601 timestamp
run_id: Pipeline run identifier
producer: fraud-agentic-demo
producer_version: Application version
```

Recommended provenance fields:

```yaml
source_data_fingerprint: SHA-256
rules_config_hash: SHA-256
code_commit: Git commit SHA or "uncommitted"
resource: fraud-demo://<entity-type>/<entity-id>
```

### 19.6 Producer-defined typed relation extension

OKF links in the body remain mandatory for graph portability. The producer may also include a `relations` frontmatter extension:

```yaml
relations:
  - predicate: transferred_to
    target_concept_id: accounts/ACC888
    transaction_count: 12
    total_amount: 50000.00
    currency: MYR
  - predicate: triggered_signal
    target_concept_id: signals/rapid_pass_through
```

Consumers must not depend exclusively on this extension. Equivalent standard Markdown links must appear in the body.

### 19.7 Account concept example

```markdown
---
type: Fraud Account
title: Account ACC123
description: Critical-risk account with high fan-in and rapid pass-through indicators.
resource: fraud-demo://account/ACC123
tags: [fraud, mule-account, critical-risk]
timestamp: 2026-06-22T10:00:00+08:00
run_id: RUN_20260622_100000
account_id: ACC123
risk_score: 85
risk_level: Critical
source_data_fingerprint: <sha256>
rules_config_hash: <sha256>
relations:
  - predicate: triggered_signal
    target_concept_id: signals/rapid_pass_through
  - predicate: member_of_cluster
    target_concept_id: clusters/CLUSTER_001
---

# Account ACC123

## Risk summary

This account is classified as **Critical** with a risk score of **85**. This is an investigative indicator, not a confirmed fraud determination.

## Triggered signals

- [Rapid pass-through](../signals/rapid_pass_through.md)
- [High fan-in](../signals/high_fan_in.md)

## Evidence

| Metric | Account value | Rule threshold |
|---|---:|---:|
| Unique senders, 7 days | 31 | 10 |
| Pass-through ratio, 7 days | 0.91 | 0.80 |
| Hold-time proxy | 47 minutes | 120 minutes maximum |

## Connected accounts

Received funds from:

- [Account ACC045](ACC045.md)
- [Account ACC077](ACC077.md)

Sent funds to:

- [Account ACC888](ACC888.md)
- [Account ACC901](ACC901.md)

## Related concepts

- [Alert ALERT_RUN_20260622_100000_ACC123](../alerts/ALERT_RUN_20260622_100000_ACC123.md)
- [Cluster CLUSTER_001](../clusters/CLUSTER_001.md)
- [Mule-account investigation runbook](../runbooks/mule_account_investigation.md)
```

### 19.8 Alert concept required sections

Every alert concept must contain:

1. Risk summary.
2. Triggered rule explanations.
3. Evidence table with observed values and thresholds.
4. Related account and cluster links.
5. Suggested human review steps.
6. Provenance section.
7. Clear statement that the alert is not a confirmed fraud judgment.

### 19.9 Cluster concept required sections

Every cluster concept must contain:

1. Cluster size and total observed value.
2. Key accounts ranked by risk or network relevance.
3. Main signals.
4. Concise graph interpretation.
5. Related alerts.
6. Limitations of the inference.

### 19.10 Export limits

Do not create one concept per raw transaction. Default limits:

```yaml
max_accounts: 500
max_alerts: 500
max_clusters: 100
max_devices: 200
max_ips: 200
max_counterparties_per_account: 30
max_sample_transactions_per_alert: 20
```

---

## 20. OKF Validation Specification

Implement `src/fraud_demo/okf_validator.py`.

### 20.1 Hard errors

The validator fails the command when:

- A non-reserved Markdown file lacks YAML frontmatter.
- YAML cannot be parsed.
- A concept lacks a non-empty `type`.
- A concept ID is duplicated.
- A Markdown file is not valid UTF-8.
- A reserved `index.md` or `log.md` violates the required reserved-file structure.
- A generated concept path escapes the bundle root.

### 20.2 Warnings

The validator warns when:

- A recommended field such as `title` or `description` is missing.
- A timestamp is not ISO 8601.
- A generated internal link is broken.
- A `relations` target does not exist.
- A concept exceeds a configurable file-size limit.
- A privacy scanner detects a disallowed field or pattern.
- A directory lacks `index.md`.
- A generated external factual claim lacks a citation section.

### 20.3 Validation report

Write:

```text
artifacts/runs/<run_id>/okf_validation_report.json
```

Schema:

```json
{
  "okf_version": "0.1",
  "bundle_path": "artifacts/okf_bundle",
  "valid": true,
  "concept_count": 0,
  "link_count": 0,
  "hard_errors": [],
  "warnings": [],
  "validated_at": "ISO-8601"
}
```

---

## 21. Obsidian Compatibility

The generated OKF directory must open directly as an Obsidian vault.

Requirements:

1. Use standard Markdown links, not Obsidian-only Wikilinks, as the canonical link form.
2. Use relative link paths by default.
3. Use safe filenames containing letters, numbers, underscores, and hyphens.
4. Avoid spaces where possible; otherwise URL-encode Markdown link destinations.
5. Do not require community plugins.
6. Do not depend on Obsidian-specific block references.
7. Use frontmatter tags so Obsidian can filter concepts.
8. Keep `.obsidian/` configuration optional and excluded from the core conformance tests.

Obsidian is a viewer and editor for the same OKF files; it is not the canonical storage format.

---

## 22. Dashboard Requirements

Implement a local Streamlit application reading prepared Parquet and JSON artifacts.

### 22.1 Page 1: Executive Overview

Display:

- Total valid transactions.
- Rejected rows.
- Total distinct accounts.
- High and critical alert counts.
- Suspicious transfer amount.
- Number of suspicious clusters.
- Current run ID and data fingerprint.
- Risk-level distribution.
- Alerts over time.
- Top suspicious accounts.
- Top triggered rules.

### 22.2 Page 2: Alert Queue

Filters:

- Date range.
- Risk level.
- Minimum score.
- Rule triggered.
- Country.
- Bank.
- Channel.
- Cluster.

Columns:

```text
alert_id
account_id
risk_score
risk_level
triggered_rules
incoming_amount_7d
outgoing_amount_7d
unique_senders_7d
unique_receivers_7d
hold_time_proxy_minutes
cluster_id
created_at
```

Support CSV download of the filtered view.

### 22.3 Page 3: Account Investigation

For a selected account, show:

- Risk score and severity.
- Rule-by-rule evidence.
- Incoming and outgoing summaries.
- Activity timeline.
- Top counterparties.
- Shared devices or IPs, when approved.
- Selected transactions as evidence.
- Cluster membership.
- Link or displayed path to the corresponding OKF concept.
- Disclaimer that the output requires human review.

### 22.4 Page 4: Network Explorer

Show a bounded graph around a selected account or cluster.

Controls:

- One-hop or two-hop depth.
- Minimum edge amount.
- Minimum transaction count.
- Risk-level filter.
- Node-type filter.

Visual encoding:

- Account node size by risk score or degree.
- Edge thickness by amount or count.
- Hover details with amounts, counts, and timestamps.

Never attempt to render the complete raw graph. Enforce configurable node and edge limits.

### 22.5 Page 5: OKF Knowledge Bundle

Display:

- OKF version.
- Concept count by type.
- Internal link count.
- Validation status.
- Validation warnings.
- Most-linked concepts.
- Bundle path.
- Selected concept Markdown preview.
- Instructions for opening the bundle in Obsidian.

### 22.6 Page 6: Monitoring

Display:

- Last successful run.
- Source files processed.
- New transactions since prior run.
- New and changed alerts.
- Accounts whose severity increased.
- OKF concepts added or updated.
- Pipeline stage timings.
- Failed or quarantined files.

### 22.7 Dashboard performance

- Use `st.cache_data` for prepared artifacts.
- Avoid loading the raw CSV on page render.
- Read Parquet or DuckDB views.
- Limit network data before sending it to the browser.

---

## 23. Continuous Monitoring

Continuous monitoring in the MVP means file-based micro-batch processing.

### 23.1 Input convention

```text
data/incoming/transactions_*.csv
```

### 23.2 State management

Maintain a `processed_files` table:

```text
file_path
file_sha256
first_seen_at
processed_at
run_id
row_count
status
error_message
```

### 23.3 Idempotency

- Skip a file whose hash has already completed successfully unless `--force` is supplied.
- Deduplicate transaction IDs across files.
- A failed file can be retried.
- Re-running OKF export for the same analytical state must be deterministic except for declared timestamps.

### 23.4 MVP monitoring strategy

1. Discover unprocessed CSV files.
2. Validate and append valid transactions.
3. Recompute the current account snapshot.
4. Re-score accounts.
5. Compare current and prior alerts.
6. Update analytical artifacts.
7. Regenerate changed OKF concepts and indexes.
8. Append the OKF `log.md`.
9. Refresh dashboard artifacts.

Full snapshot recomputation is acceptable for the MVP. Recomputing only impacted accounts is a stretch goal.

### 23.5 Alert change categories

```text
new
severity_increased
severity_decreased
unchanged
resolved_below_threshold
```

Do not delete prior run concepts silently. Preserve run history and record deprecations or status changes.

---

## 24. Agentic AI and Codex Responsibilities

### 24.1 Codex is responsible for

- Inspecting the repository.
- Producing an implementation plan.
- Scaffolding modules and configuration.
- Writing deterministic processing code.
- Running commands and tests.
- Diagnosing and correcting errors.
- Generating documentation.
- Maintaining progress status.
- Producing a clear final implementation summary.

### 24.2 Codex is not responsible for

- Making an unreviewed fraud judgment.
- Sending raw financial data to an external model.
- Inventing missing fields or evidence.
- Replacing deterministic data processing with prompts.
- weakening tests to make failures disappear.
- Changing the required stack without documenting the reason.

### 24.3 Optional runtime narrative generation

If implemented, it must:

- Be disabled by default.
- Accept only pseudonymized, aggregated alert summaries.
- Never receive the raw transaction CSV.
- Store the exact input summary and model output for audit.
- Mark generated text as AI-assisted.
- Use a deterministic template fallback.

The MVP is complete without runtime narrative generation.

---

## 25. Command-Line Interface

Implement these commands with Typer.

```bash
# Generate reproducible synthetic data
python -m fraud_demo generate-data \
  --rows 1000000 \
  --output data/raw/transactions_1m.csv \
  --seed 42

# Validate and profile a source file
python -m fraud_demo profile \
  --input data/raw/transactions_1m.csv

# Run the complete pipeline
python -m fraud_demo run \
  --input data/raw/transactions_1m.csv \
  --run-id RUN_20260622_100000

# Validate an existing OKF bundle
python -m fraud_demo validate-okf \
  --bundle artifacts/okf_bundle

# Process new files from the incoming directory
python -m fraud_demo monitor \
  --inbox data/incoming

# Start the dashboard
streamlit run dashboard/app.py
```

### 25.1 Required command behavior

- Print stage progress and elapsed time.
- Return non-zero exit code on hard failure.
- Write structured logs.
- Never overwrite a successful run without explicit force.
- Display output paths on completion.

---

## 26. Repository Structure

```text
fraud-agentic-demo/
├── AGENTS.md
├── README.md
├── PRD.md
├── IMPLEMENTATION_STATUS.md
├── pyproject.toml
├── Makefile
├── .env.example
├── .gitignore
├── config/
│   ├── rules.yaml
│   ├── pipeline.yaml
│   ├── okf.yaml
│   └── dashboard.yaml
├── data/
│   ├── raw/
│   ├── incoming/
│   ├── samples/
│   └── .gitkeep
├── src/
│   └── fraud_demo/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── logging.py
│       ├── generate_data.py
│       ├── ingest.py
│       ├── profile.py
│       ├── features.py
│       ├── scoring.py
│       ├── graph_builder.py
│       ├── clusters.py
│       ├── alerts.py
│       ├── okf_exporter.py
│       ├── okf_validator.py
│       ├── monitoring.py
│       ├── manifests.py
│       ├── privacy.py
│       └── templates/
│           ├── account.md.j2
│           ├── alert.md.j2
│           ├── cluster.md.j2
│           ├── signal.md.j2
│           ├── run.md.j2
│           └── runbook.md.j2
├── dashboard/
│   ├── app.py
│   ├── common.py
│   └── pages/
│       ├── 1_Overview.py
│       ├── 2_Alerts.py
│       ├── 3_Account_Investigation.py
│       ├── 4_Network_Explorer.py
│       ├── 5_OKF_Knowledge_Bundle.py
│       └── 6_Monitoring.py
├── tests/
│   ├── fixtures/
│   ├── test_config.py
│   ├── test_ingest.py
│   ├── test_features.py
│   ├── test_scoring.py
│   ├── test_graph_builder.py
│   ├── test_alerts.py
│   ├── test_okf_exporter.py
│   ├── test_okf_validator.py
│   ├── test_monitoring.py
│   └── test_end_to_end.py
├── artifacts/
│   ├── okf_bundle/
│   └── runs/
└── scripts/
    ├── demo_setup.sh
    ├── demo_run.sh
    └── benchmark.sh
```

Large generated CSV, Parquet, DuckDB, and OKF output files should be ignored by Git unless a small sample is intentionally committed.

---

## 27. Configuration Specifications

### 27.1 Example `config/rules.yaml`

```yaml
version: "1.0"
alert_min_score: 50
severity_bands:
  low: [0, 24]
  medium: [25, 49]
  high: [50, 74]
  critical: [75, 100]

rules:
  high_fan_in:
    enabled: true
    weight: 20
    description: Many unique senders transferred to one account.
    required_features: [unique_senders_7d]
    thresholds:
      unique_senders_7d: 10

  rapid_pass_through:
    enabled: true
    weight: 25
    description: Most incoming value was moved out within a short interval.
    required_features: [pass_through_ratio_7d, hold_time_proxy_minutes]
    thresholds:
      pass_through_ratio_7d: 0.80
      hold_time_proxy_minutes_max: 120

  high_velocity:
    enabled: true
    weight: 15
    description: Transaction count was high within 24 hours.
    required_features: [incoming_count_24h, outgoing_count_24h]
    thresholds:
      total_count_24h: 30

  high_fan_out:
    enabled: true
    weight: 10
    description: Funds were sent to many distinct downstream accounts.
    required_features: [unique_receivers_7d]
    thresholds:
      unique_receivers_7d: 10

  shared_access_point:
    enabled: true
    weight: 15
    description: The account shared a device or IP with multiple accounts.
    required_features: [shared_device_account_count_30d, shared_ip_account_count_30d]
    thresholds:
      shared_accounts: 4

  cross_border_funnel:
    enabled: true
    weight: 10
    description: Significant incoming activity was followed by cross-border outgoing transfers.
    required_features: [incoming_amount_7d, cross_border_out_ratio_7d]
    thresholds:
      incoming_amount_7d: 10000
      cross_border_out_ratio_7d: 0.50

  new_account_burst:
    enabled: true
    weight: 15
    description: A recently opened account showed abrupt high activity.
    required_features: [account_age_days, incoming_count_24h, outgoing_count_24h]
    thresholds:
      account_age_days_max: 30
      total_count_24h: 20

  short_cycle:
    enabled: true
    weight: 20
    description: The account participated in a short directed transfer cycle.
    required_features: [short_cycle_flag]
    thresholds:
      max_cycle_length: 5
```

### 27.2 Example `config/okf.yaml`

```yaml
version: "0.1"
bundle_name: Mule Account Fraud Knowledge Graph
output_dir: artifacts/okf_bundle
link_style: relative
include_root_version_frontmatter: true
generate_index_files: true
generate_log_files: true
include_typed_relations_extension: true

export_limits:
  max_accounts: 500
  max_alerts: 500
  max_clusters: 100
  max_devices: 200
  max_ips: 200
  max_counterparties_per_account: 30
  max_sample_transactions_per_alert: 20

privacy:
  pseudonymize_account_ids: false
  pseudonymize_device_ids: true
  pseudonymize_ip_addresses: true
  include_transaction_descriptions: false
  include_customer_pii: false

concept_types:
  account: Fraud Account
  alert: Fraud Alert
  cluster: Fraud Cluster
  signal: Fraud Signal
  device: Fraud Device
  ip: Fraud IP Address
  metric: Fraud Metric
  run: Fraud Pipeline Run
  dataset: Fraud Dataset
  runbook: Fraud Runbook
```

---

## 28. Output Artifacts

Each run writes under:

```text
artifacts/runs/<run_id>/
```

Required outputs:

```text
run_manifest.json
data_quality_report.json
normalized_transactions.parquet
rejected_rows.parquet
account_features.parquet
account_risk.parquet
rule_evidence.parquet
alerts.parquet
graph_nodes.parquet
graph_edges.parquet
clusters.parquet
alert_changes.parquet
okf_manifest.json
okf_validation_report.json
pipeline.log
```

The canonical latest OKF bundle may be written to `artifacts/okf_bundle/`, while the run manifest records the exact run used to generate it.

### 28.1 Run manifest

Required fields:

```json
{
  "run_id": "RUN_20260622_100000",
  "status": "success",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "source_files": [],
  "source_data_fingerprint": "sha256",
  "valid_row_count": 1000000,
  "rejected_row_count": 0,
  "distinct_account_count": 0,
  "alert_count": 0,
  "cluster_count": 0,
  "rules_config_hash": "sha256",
  "pipeline_config_hash": "sha256",
  "code_commit": "git-sha-or-uncommitted",
  "stage_timings_seconds": {},
  "artifact_paths": {}
}
```

---

## 29. Detailed Functional Requirements

| ID | Requirement |
|---|---|
| FR-001 | The system shall ingest one or more transaction CSV files. |
| FR-002 | The system shall validate required columns and normalized types. |
| FR-003 | The system shall quarantine invalid rows with explicit reasons. |
| FR-004 | The system shall deduplicate transactions by ID. |
| FR-005 | The system shall produce a data-quality report. |
| FR-006 | The system shall calculate account features for configured time windows. |
| FR-007 | The system shall evaluate configurable fraud rules. |
| FR-008 | The system shall create an evidence record for every triggered rule. |
| FR-009 | The system shall assign a capped risk score and severity. |
| FR-010 | The system shall generate alerts at the configured threshold. |
| FR-011 | The system shall aggregate suspicious account-to-account edges. |
| FR-012 | The system shall identify connected suspicious clusters. |
| FR-013 | The system shall generate structured graph node and edge artifacts. |
| FR-014 | The system shall export an OKF v0.1 knowledge bundle. |
| FR-015 | The system shall validate OKF hard conformance rules. |
| FR-016 | The OKF bundle shall use standard Markdown links. |
| FR-017 | The OKF bundle shall open as an Obsidian vault. |
| FR-018 | The system shall generate root and subdirectory indexes. |
| FR-019 | The system shall append run changes to `log.md`. |
| FR-020 | The dashboard shall provide overview, alerts, account, graph, OKF, and monitoring pages. |
| FR-021 | The dashboard shall not read the one-million-row CSV on normal page loads. |
| FR-022 | The system shall support repeat processing of new files. |
| FR-023 | The system shall track processed files by hash. |
| FR-024 | The system shall compare alert states across runs. |
| FR-025 | The system shall record source, config, and code provenance. |
| FR-026 | The system shall support synthetic data generation with fraud scenarios. |
| FR-027 | Every analyst-facing alert shall state that human review is required. |
| FR-028 | Raw PII and transaction descriptions shall be excluded from OKF by default. |
| FR-029 | The system shall run without any runtime LLM call. |
| FR-030 | The CLI shall return non-zero status on hard errors. |

---

## 30. Non-Functional Requirements

### 30.1 Performance

- Process 1,000,000 rows within the stated demo target.
- Use SQL pushdown and Parquet rather than loading all rows into Python objects.
- Bound graph algorithms and browser payloads.

### 30.2 Reliability

- Commands are idempotent where practical.
- Successful run outputs are not silently overwritten.
- Partial failures preserve logs and error details.
- The demo has cached fallback artifacts.

### 30.3 Maintainability

- Functions have typed signatures.
- Configuration is validated.
- Rule evaluation is separated from feature computation.
- OKF templates are separated from exporter logic.
- Avoid a single monolithic pipeline file.

### 30.4 Explainability

- Every score is reproducible from stored evidence.
- Every threshold comes from versioned configuration.
- Narrative text is deterministic by default.

### 30.5 Portability

- Run locally on macOS, Linux, or Windows where dependencies support it.
- Use plain files, DuckDB, Parquet, Markdown, YAML, and JSON.
- Avoid mandatory cloud services.

### 30.6 Accessibility

- Dashboard labels must not rely only on color.
- Tables must provide text severity labels.
- Graph hover information must repeat key values in text panels.

---

## 31. Security, Privacy, and Governance

1. Use synthetic or approved anonymized data for the demo.
2. Never commit real banking data, secrets, or unmasked PII.
3. Keep `.env`, raw data, and generated sensitive artifacts out of Git.
4. Default to masking device and IP identifiers.
5. Provide an HMAC-based stable pseudonymization option for account IDs.
6. Keep the HMAC secret outside the repository.
7. Do not send row-level data to Codex prompts or runtime external APIs.
8. Exclude free-text transaction descriptions from OKF by default.
9. Record whether data was synthetic, anonymized, or real-approved in the run manifest.
10. Include an analyst disclaimer in dashboard and alert concepts.
11. Use least-privilege file permissions in a real environment.
12. Treat the demo’s rules as illustrative, not regulatory policy.

### 31.1 Pseudonymization format

When enabled:

```text
ACC_<first 12 hex characters of HMAC-SHA256(secret, original_id)>
```

Keep a mapping only when explicitly required and store it outside generated artifacts.

---

## 32. Logging and Observability

Use structured logs with:

```text
timestamp
level
run_id
stage
event
message
row_count
elapsed_seconds
error_type
```

Required stage timings:

```text
ingest
validate
profile
feature_engineering
scoring
graph_build
clustering
alert_generation
okf_export
okf_validate
artifact_finalize
```

The monitoring dashboard reads summarized stage timings from the run manifest.

---

## 33. Testing Strategy

### 33.1 Unit tests

- CSV type parsing.
- Missing required column behavior.
- Invalid amount and timestamp rejection.
- Deduplication.
- Each fraud feature on a small deterministic fixture.
- Each rule at below, equal, and above threshold.
- Risk-score cap and severity bands.
- Graph edge aggregation.
- Cluster membership.
- Jinja template escaping.
- OKF frontmatter generation.
- OKF link generation.
- Reserved filename handling.
- Privacy masking.

### 33.2 Integration tests

- End-to-end run on a small fixture.
- Synthetic scenario detection.
- Run manifest completeness.
- Dashboard artifact availability.
- OKF bundle validation.
- Monitoring rerun with one new file.
- Duplicate file hash handling.

### 33.3 Performance test

Use `scripts/benchmark.sh` to:

1. Generate or locate 1,000,000 rows.
2. Run the pipeline with timing.
3. Record peak memory where available.
4. Validate row reconciliation.
5. Validate OKF bundle.
6. Write `benchmark_report.json`.

The one-million-row benchmark is not part of the default unit test suite.

### 33.4 Reconciliation assertions

```text
raw_rows = valid_rows + rejected_rows + duplicate_rows_removed
sum_valid_amount ≈ sum_normalized_amount
all alerts reference existing account risk rows
all exported alert concepts reference existing account concepts
all generated internal Markdown links resolve
all high and critical alerts have rule evidence
```

---

## 34. Acceptance Criteria and Definition of Done

The MVP is complete only when all of the following are true:

### Data pipeline

- [ ] A one-million-row CSV completes successfully within the demo hard limit.
- [ ] Required schema failures produce clear errors.
- [ ] Invalid rows are quarantined.
- [ ] Transaction and amount reconciliation checks pass.
- [ ] All required Parquet and JSON artifacts are generated.

### Detection

- [ ] All baseline rules are configurable.
- [ ] Each triggered rule has stored evidence.
- [ ] Synthetic scenario capture target is met or deviations are documented.
- [ ] Alert language avoids declaring confirmed fraud.

### Graph

- [ ] Structured nodes and typed edges are generated.
- [ ] Suspicious clusters are identified.
- [ ] Graph size limits are enforced.
- [ ] Dashboard graph shows a selected account or cluster without browser overload.

### OKF

- [ ] Every concept file has parseable frontmatter and non-empty `type`.
- [ ] Reserved files follow OKF structure.
- [ ] Standard Markdown links are used.
- [ ] Generated internal links resolve.
- [ ] Root `index.md`, subdirectory indexes, and `log.md` exist.
- [ ] `okf_validation_report.json` contains zero hard errors.
- [ ] The bundle opens in Obsidian and graph links are visible.
- [ ] No raw one-million-transaction note explosion occurs.

### Dashboard

- [ ] All six required pages run.
- [ ] Filters work on prepared artifacts.
- [ ] Account investigation shows evidence and linked concepts.
- [ ] Monitoring shows run differences.

### Engineering quality

- [ ] Core automated tests pass.
- [ ] `README.md` includes setup and demo instructions.
- [ ] `IMPLEMENTATION_STATUS.md` accurately reflects completed work.
- [ ] No secrets or raw data are committed.
- [ ] A fallback demo run and artifacts are available.

---

## 35. Implementation Plan for Codex

### Phase 0: Repository assessment

1. Read `PRD.md` and `AGENTS.md`.
2. Inspect existing files and dependencies.
3. Write a concise implementation plan to `IMPLEMENTATION_STATUS.md`.
4. Identify assumptions and blockers.
5. Do not change product scope during this phase.

### Phase 1: Project scaffold

Deliver:

- `pyproject.toml`
- CLI skeleton
- configuration models
- logging
- Makefile
- basic tests

Validation:

```bash
python -m fraud_demo --help
pytest -q
```

### Phase 2: Synthetic generator and ingestion

Deliver:

- Reproducible data generator.
- CSV validator.
- DuckDB schema.
- normalized and rejected outputs.
- data-quality report.

Validate on 10,000 rows before 1,000,000 rows.

### Phase 3: Features and scoring

Deliver:

- Account features.
- rule configuration.
- evidence records.
- account risk and alert outputs.

Add threshold boundary tests.

### Phase 4: Graph and clusters

Deliver:

- Filtered node and edge tables.
- connected components.
- bounded cycle indicator.
- cluster summaries.

### Phase 5: OKF exporter and validator

Deliver:

- templates.
- bundle hierarchy.
- relative Markdown links.
- indexes and log.
- manifest and validation report.
- Obsidian smoke test instructions.

### Phase 6: Dashboard

Build pages in this order:

1. Overview.
2. Alerts.
3. Account Investigation.
4. Network Explorer.
5. OKF Knowledge Bundle.
6. Monitoring.

### Phase 7: Monitoring

Deliver:

- processed-file state.
- new-file command.
- alert comparison.
- OKF update log.

### Phase 8: Performance and demo hardening

- Run benchmark.
- Fix bottlenecks.
- Generate fallback artifacts.
- Add demo scripts.
- Finalize documentation.

### Phase 9: Final verification

Run:

```bash
make lint
make test
make demo-data
make run-demo
make validate-okf
```

Then update `IMPLEMENTATION_STATUS.md` with:

- Completed scope.
- Test results.
- benchmark result.
- Known limitations.
- Exact demo commands.

---

## 36. Makefile Targets

Required targets:

```makefile
setup           # Create environment and install dependencies
lint            # Run formatting and static checks
test            # Run unit and integration tests
demo-data       # Generate 1M-row synthetic dataset
sample-data     # Generate small development dataset
run-sample      # Run pipeline on development sample
run-demo        # Run pipeline on 1M-row dataset
validate-okf    # Validate generated OKF bundle
dashboard       # Start Streamlit
benchmark       # Run performance benchmark
clean-generated # Remove generated artifacts after confirmation
```

---

## 37. Demo Script

### Before presentation

1. Confirm environment and dependencies.
2. Run the sample pipeline.
3. Verify the fallback full-run artifacts.
4. Open Obsidian on `artifacts/okf_bundle/`.
5. Start Streamlit and verify all pages.
6. Put a prepared delta CSV in a staging folder.
7. Confirm the completed fallback branch is available.

### During presentation

1. Show the PRD and architecture.
2. Ask Codex to implement or modify one bounded feature.
3. Run focused tests.
4. Run the sample pipeline live.
5. Show the prevalidated one-million-row run manifest.
6. Investigate a critical account in the dashboard.
7. Open its OKF account note in Obsidian.
8. Traverse links to an alert, signal, cluster, and runbook.
9. Process the delta file.
10. Show the new or changed alert and updated `log.md`.

### Fallback behavior

If a live implementation or full run fails:

- Switch to the completed branch.
- Load prepared artifacts.
- Explain the failure honestly.
- Continue the investigation and monitoring demonstration.

---

## 38. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Live Codex task takes an unexpected path | Demo delay | Keep task bounded and maintain completed branch |
| One-million-row run is slower than expected | Demo delay | Pre-run artifacts; live-run smaller sample |
| Graph becomes too dense | Unusable visualization | Strict node, edge, hop, and counterparty limits |
| OKF vault contains too many files | Slow navigation | Export only high-risk concepts and bounded context |
| False positives appear excessive | Reduced credibility | Explain demo thresholds; show evidence; support tuning |
| Missing optional columns disable rules | Reduced feature set | Report `not_evaluated`; synthetic data includes full schema |
| LLM narrative invents facts | Misleading output | Deterministic templates by default; runtime LLM optional |
| Sensitive data leaks into notes | Privacy incident | Synthetic data, masking, field allowlist, privacy tests |
| Obsidian link incompatibility | Broken graph | Standard relative Markdown links and smoke test |
| OKF v0.1 changes | Rework | Pin target version and isolate exporter/validator logic |
| Users interpret alerts as confirmed fraud | Governance risk | Persistent disclaimer and human-review language |

---

## 39. Architecture Decisions

### ADR-001: Use DuckDB for bulk processing

**Decision:** Use DuckDB SQL for CSV scanning, transformation, aggregation, and Parquet output.

**Reason:** It handles the target scale locally without requiring distributed infrastructure.

### ADR-002: Keep the runtime LLM optional

**Decision:** The core pipeline has no runtime model dependency.

**Reason:** This reduces privacy, latency, cost, and reliability risks while preserving the Codex agentic development story.

### ADR-003: Use OKF as canonical knowledge output

**Decision:** The graph knowledge layer is an OKF v0.1 bundle, not an Obsidian-specific vault format.

**Reason:** OKF is plain Markdown plus YAML and standard links, allowing Obsidian, Git, agents, and other consumers to share the same artifacts.

### ADR-004: Maintain a typed analytical graph beside OKF

**Decision:** Store typed nodes and edges in Parquet.

**Reason:** OKF links are portable but do not prescribe typed edge semantics or numerical edge attributes.

### ADR-005: Export summaries, not raw transactions

**Decision:** Raw transaction rows remain in DuckDB or Parquet.

**Reason:** One million Markdown concepts would be slow, noisy, privacy-sensitive, and analytically unnecessary.

### ADR-006: Use standard relative Markdown links

**Decision:** Generate relative Markdown links by default.

**Reason:** Relative links are allowed by OKF and work directly in Obsidian while avoiding proprietary Wikilink syntax.

### ADR-007: Use rule-based scoring for the MVP

**Decision:** Use transparent weighted rules rather than a trained model.

**Reason:** The demo prioritizes explainability, speed of implementation, and reproducibility.

---

## 40. Future Enhancements

1. Label-driven supervised fraud model.
2. Analyst feedback and threshold tuning.
3. Entity resolution across customer, device, phone, and identity records.
4. Temporal graph algorithms.
5. Incremental account-only recomputation.
6. Graph database adapter.
7. Static OKF HTML visualizer.
8. Search and retrieval agent over the OKF bundle.
9. Case management and analyst disposition workflow.
10. Role-based access and audit logs.
11. Production orchestration using Prefect, Airflow, or cloud-native services.
12. Streaming ingestion and event-time windows.
13. Model risk management and fairness evaluation.
14. Regulatory reporting integration after legal and compliance review.

---

## 41. Codex Bootstrap Prompt

Use the following prompt at the start of a Codex session:

```text
Build the MVP described in PRD.md for the Agentic AI mule-account fraud detection demo.

Operating rules:
1. Treat PRD.md as the source of truth.
2. Read the repository before editing.
3. Create or update IMPLEMENTATION_STATUS.md with a phased plan.
4. Implement one phase at a time and run relevant tests after each phase.
5. Use Python 3.12, DuckDB, Typer, Pydantic, Jinja2, NetworkX, Streamlit, Plotly, and pytest unless the repository already has an equivalent approved dependency.
6. Do not send raw transaction data to an LLM or external API.
7. Keep fraud detection deterministic and rule-based.
8. Generate an OKF v0.1 bundle with YAML frontmatter and standard relative Markdown links.
9. Do not generate one file per raw transaction.
10. Keep the dashboard graph bounded.
11. Never weaken or delete a valid test merely to make the suite pass.
12. Use synthetic or anonymized data only.
13. Label outputs as suspicious indicators requiring human review, not confirmed fraud.
14. Preserve run provenance, configuration hashes, and source fingerprints.
15. If an assumption is needed, choose the simplest implementation consistent with the PRD and document it.

Begin with Phase 0 repository assessment. Then proceed through the implementation plan, stopping only for a genuine blocker such as a missing inaccessible file or credential.
```

---

## 42. Authoritative References

1. Google Cloud, “Introducing the Open Knowledge Format,” published 2026-06-13: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/
2. Open Knowledge Format v0.1 Draft specification: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
3. OKF reference repository and sample bundles: https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf
4. Obsidian internal link documentation: https://obsidian.md/help/links

---

## 43. Final Product Statement

The finished demo is a local, reproducible, explainable fraud-analysis workflow that processes one million transaction rows, identifies suspicious mule-account patterns, presents bounded graph investigations in a dashboard, and publishes the results as a portable OKF knowledge bundle that can be opened in Obsidian and consumed by other agents or tools.

The output supports investigation and continuous monitoring; it does not replace analyst judgment or constitute a confirmed fraud determination.
