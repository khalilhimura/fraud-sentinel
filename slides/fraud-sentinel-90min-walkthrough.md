# Fraud Sentinel 90-Minute Project Walkthrough

NotebookLM source deck for generating actual slides.

Duration: 1 hour 30 minutes
Target deck length: 36 slides
Audience: product, engineering, risk, compliance, and AI strategy stakeholders
Tone: credible, practical, evidence-backed, and demo-ready
Core story: Fraud Sentinel turns large transaction CSVs into explainable mule-account alerts, bounded network views, and a portable OKF knowledge graph. Codex acts as the engineering agent; deterministic code performs the fraud analysis.

## Source Base

Local project sources:

- `PRD.md`
- `agentic_ai_fraud_detection_okf_prd.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENTS.md`
- `config/rules.yaml`
- `config/pipeline.yaml`
- `config/okf.yaml`
- `config/dashboard.yaml`
- `papers/2604.08649v1.pdf`

External evidence used:

- FBI IC3 2024 Annual Report: https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf
- FTC 2024 fraud loss release: https://www.ftc.gov/news-events/news/press-releases/2025/03/new-ftc-data-show-big-jump-reported-losses-fraud-125-billion-2024
- UK Finance Annual Fraud Report 2025: https://www.ukfinance.org.uk/policy-and-guidance/reports-and-publications/annual-fraud-report-2025
- Nasdaq Verafin 2024 Global Financial Crime Report: https://www.nasdaq.com/global-financial-crime-report
- PRAGMA paper: https://arxiv.org/abs/2604.08649
- PRAGMA HTML version: https://arxiv.org/html/2604.08649v1
- SEFraud KDD 2024 paper: https://arxiv.org/abs/2406.11389
- Lloyds/IBM graph-based mule-account research coverage: https://www.itpro.com/technology/lloyds-bank-touts-quantum-potential-in-anti-fraud-activities
- Google Cloud OKF announcement: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/

---

# Slide 1: Fraud Sentinel

Time: 2 minutes

Purpose:

- Establish the project in one sentence.

Visual direction:

- Title slide with a clean transaction-network background.
- Show three labels: "Detect", "Explain", "Export".

Slide copy:

- Fraud Sentinel
- Agentic AI mule-account fraud detection with an OKF knowledge graph
- 90-minute project walkthrough

Speaker notes:

Fraud Sentinel is a local, deterministic fraud-analysis demo. It processes banking transaction CSVs, detects suspicious mule-account patterns, presents an analyst dashboard, and exports investigation knowledge as a portable Open Knowledge Format bundle.

---

# Slide 2: What This Walkthrough Covers

Time: 2 minutes

Purpose:

- Tell the audience what kind of presentation this is.

Visual direction:

- Five-step journey from problem to roadmap.

Slide copy:

- Why mule-account detection matters now
- What PRAGMA teaches us about financial event data
- How Fraud Sentinel turns raw transaction data into evidence
- Why OKF makes the investigation portable
- What is built, what is planned, and how the demo should run

Speaker notes:

This is a project walkthrough, not a claim that the whole pipeline is production-complete today. The repo is currently Phase 1 complete: scaffold, config, CLI surface, dashboard shell, tests, and implementation plan are in place. The presentation explains the full PRD vision while being honest about current implementation status.

---

# Slide 3: The Fraud Problem Is Getting Larger

Time: 3 minutes

Purpose:

- Quantify the urgency using recent external sources.

Visual direction:

- Four metric tiles with source labels.

Slide copy:

- FBI IC3: reported 2024 internet crime losses reached USD 16.6B, up 33% from 2023.
- FTC: consumers reported USD 12.5B in fraud losses in 2024; investment scams led at USD 5.7B.
- Nasdaq Verafin: estimated USD 3.1T in illicit funds flowed through the global financial system in 2023.
- UK Finance: fraud remains a system-wide threat requiring layered defenses across banks, telecoms, technology platforms, and public agencies.

Source cues:

- FBI IC3 2024 Annual Report
- FTC 2025 release on 2024 fraud losses
- Nasdaq Verafin 2024 Global Financial Crime Report
- UK Finance Annual Fraud Report 2025

Speaker notes:

The value proposition starts with scale. Fraud is not a back-office nuisance; it is a material economic, operational, and trust problem. The rise is not just more reports. Sources like the FTC note that more people who report fraud are reporting actual financial loss. That is a signal that fraud tactics are becoming more effective.

---

# Slide 4: Mule Accounts Are the Hidden Payment Rail

Time: 3 minutes

Purpose:

- Define the core fraud typology.

Visual direction:

- Flow diagram: victim accounts -> mule receiver -> fan-out accounts -> cash-out or cross-border exits.

Slide copy:

- A mule account receives, holds, or forwards illicit funds.
- The account may look normal until it suddenly becomes part of a fraud chain.
- Detection depends on relationships: fan-in, rapid pass-through, shared devices, short cycles, and cross-border funnels.
- The goal is not to prove fraud automatically. The goal is to produce reviewable evidence fast.

Source cues:

- PRD section: Definitions, Problem Statement, Rule-Based Risk Scoring
- Nasdaq Verafin: money mule activity is one of the top concerns for anti-financial-crime professionals.
- Lloyds/IBM coverage: mule detection requires analyzing complex transaction networks.

Speaker notes:

A mule account is difficult because it can be opened legitimately and then repurposed. A single transaction may not look suspicious. The pattern emerges when many accounts point to one receiver, funds leave quickly, access points are shared, or money moves through short chains. That is why this project emphasizes graph structure and evidence, not just row-level scoring.

---

# Slide 5: Why Flat Tables Fail Analysts

Time: 3 minutes

Purpose:

- Show the operational pain the product solves.

Visual direction:

- Left: raw CSV table.
- Right: small network with highlighted mule account, triggered rules, and alert links.

Slide copy:

- Analysts often start with large transaction tables.
- Suspicious behavior is distributed across accounts, devices, timestamps, and counterparties.
- SQL can find aggregates, but it does not naturally create an investigation narrative.
- Fraud Sentinel turns raw rows into prioritized, explainable, linked evidence.

Speaker notes:

The PRD is very explicit about the problem: a flat CSV does not present relationships clearly. Analysts need to move from "show me a million rows" to "show me the 30 accounts, 10 links, and 4 rules that explain why this case deserves review."

---

# Slide 6: Product Thesis

Time: 2.5 minutes

Purpose:

- State the central argument of the project.

Visual direction:

- One sentence in large type with three supporting pillars.

Slide copy:

Fraud Sentinel is valuable because it combines:

- Deterministic bulk processing for scale
- Explainable rules and graph features for analyst trust
- Portable OKF knowledge output for reuse across humans, agents, and tools

Speaker notes:

The thesis is intentionally not "let an LLM classify transactions." The system keeps row-level processing in deterministic Python and DuckDB. Codex is the development agent. The fraud output is evidence for a human reviewer.

---

# Slide 7: PRAGMA In One Slide

Time: 2.5 minutes

Purpose:

- Introduce the PRAGMA paper and why it belongs in this project.

Visual direction:

- PRAGMA as a foundation-model layer over multi-source banking events.

Slide copy:

- PRAGMA is a Revolut/NVIDIA family of encoder-style foundation models for banking event sequences.
- It pre-trains on heterogeneous event histories using masked modelling.
- It supports downstream tasks including fraud detection, credit scoring, lifetime value, recurrent transactions, communications, and product recommendation.
- It reports relative improvements only because absolute production metrics are commercially sensitive.

Source cues:

- PRAGMA: Revolut Foundation Model, arXiv:2604.08649

Speaker notes:

PRAGMA is relevant because it is not a generic chat model pasted onto bank data. It is designed around the structure of banking events: typed fields, values, timestamps, profile state, and long histories. It validates the premise that financial event streams are rich enough to support transferable representations.

---

# Slide 8: PRAGMA's Data Setting

Time: 2.5 minutes

Purpose:

- Explain the scale and shape of PRAGMA's source data.

Visual direction:

- Layered stack: profile state + event history + evaluation point.

Slide copy:

- Record-level histories: one observation is a pseudonymized user history at an evaluation point.
- Sources include transactions, app events, trading activity, and communications.
- Profile state adds context such as plan, region, balance quantile, and account milestones.
- Reported pre-training corpus: 26M user records, 111 countries, 24B events, 207B tokens.

Source cues:

- PRAGMA paper, dataset section

Speaker notes:

The key idea is that financial behavior is not just a stream of transfers. It is a heterogeneous timeline. Transaction amount, direction, device, app behavior, communication, profile state, and timing all matter. Fraud Sentinel is smaller and deterministic, but it shares the same respect for event structure.

---

# Slide 9: Why A Plain Text LLM Is Not Enough

Time: 2.5 minutes

Purpose:

- Connect PRAGMA's critique to Fraud Sentinel's architecture.

Visual direction:

- Compare text serialization with structured event encoding.

Slide copy:

- Turning records into plain text inflates sequence length.
- Field names and delimiters become noisy tokens.
- Numeric values lose magnitude and ordering when split into digit fragments.
- Banking histories are long, irregular, and privacy-constrained.
- Fraud Sentinel keeps bulk processing structured and local.

Source cues:

- PRAGMA paper, introduction and tokenisation discussion

Speaker notes:

This is also why the PRD forbids sending one million transaction rows into a model. The model is not the data engine. The project uses deterministic processing for the pipeline, then creates summarized evidence and knowledge artifacts that humans and agents can inspect.

---

# Slide 10: PRAGMA's Key-Value-Time Representation

Time: 2.5 minutes

Purpose:

- Explain the paper's core representation idea.

Visual direction:

- A transaction row decomposed into key, value, and time tokens.

Slide copy:

- Semantic type: what field means, such as amount, channel, direction, product.
- Value: numerical, categorical, or text-specific encoding.
- Time: elapsed time plus calendar patterns like hour, day of week, and day of month.
- Profile state is encoded similarly to events.

Source cues:

- PRAGMA paper, tokenisation section

Speaker notes:

This matters for fraud because many useful signals are temporal and contextual. "Amount 1000" means less without knowing direction, channel, time since last event, country, device, and account age. Fraud Sentinel expresses the same idea through engineered features rather than a foundation model.

---

# Slide 11: PRAGMA Architecture

Time: 3 minutes

Purpose:

- Show how the model separates and fuses profile and event information.

Visual direction:

- Three-block model: Profile State Encoder, Event Encoder, History Encoder.

Slide copy:

- Encoder-only Transformer family: 10M, 100M, and 1B parameter variants.
- Profile State Encoder processes contextual attributes and lifelong milestones.
- Event Encoder processes each event independently.
- History Encoder fuses profile and event embeddings into a record-level representation.
- Downstream use: frozen embedding probes or LoRA fine-tuning.

Source cues:

- PRAGMA paper, model architecture section

Speaker notes:

PRAGMA chooses encoder-only because the target is discriminative prediction, not open-ended generation. That is aligned with fraud detection: the goal is a reliable signal and explanation, not fluent freeform text.

---

# Slide 12: PRAGMA Training And Adaptation

Time: 2.5 minutes

Purpose:

- Explain what makes PRAGMA reusable.

Visual direction:

- Pre-train once, adapt many times.

Slide copy:

- Pre-training objective: masked modelling over event tokens, whole events, and semantic types.
- Adaptation mode 1: freeze the backbone and train a lightweight probe.
- Adaptation mode 2: LoRA fine-tuning updates about 2-4% of parameters.
- Engineering choices include sequence packing, dynamic batching, truncation, and H100-scale training.

Source cues:

- PRAGMA paper, training and evaluation protocol sections

Speaker notes:

The important lesson is not that Fraud Sentinel should train a billion-parameter model. The lesson is that banking event data has reusable structure. For this MVP, we capture that structure with transparent features, rules, and graph artifacts.

---

# Slide 13: PRAGMA Results To Carry Forward

Time: 2.5 minutes

Purpose:

- Present the paper's most useful result signals.

Visual direction:

- Relative uplift chart with a disclaimer: "relative only, not absolute production metrics."

Slide copy:

- External fraud: reported relative gains of +16.7% precision and +64.7% recall versus internal task-specific baselines.
- Credit scoring: +130.2% PR-AUC.
- Communication engagement: +79.4% PR-AUC.
- Product recommendation: +40.5% mAP.
- Profile state was especially useful for fraud and credit tasks.

Source cues:

- PRAGMA paper, main results and profile-state ablation sections

Speaker notes:

The numbers are relative improvements, not absolute accuracy. That distinction matters. The business takeaway is still strong: general financial event representations can outperform isolated task models, especially where signals are sparse and distributed across a user's history.

---

# Slide 14: The PRAGMA Limitation That Validates This Project

Time: 2 minutes

Purpose:

- Show why Fraud Sentinel's graph layer is not optional.

Visual direction:

- Split screen: "record history" versus "network relationships".

Slide copy:

- PRAGMA underperformed on the AML case study relative to a network-aware baseline.
- The paper attributes the gap to cross-record relational structure.
- Mule-account detection is inherently relational.
- Fraud Sentinel is designed around the missing layer: account-to-account flows, shared access points, clusters, and evidence graphs.

Source cues:

- PRAGMA paper, AML limitation section

Speaker notes:

This is the intellectual bridge. PRAGMA proves that financial event representations are powerful, but it also says AML-style tasks need cross-record network structure. Fraud Sentinel takes that limit seriously by making the graph a first-class product surface.

---

# Slide 15: From PRAGMA To Fraud Sentinel

Time: 2 minutes

Purpose:

- Translate paper insights into product choices.

Visual direction:

- Mapping table: PRAGMA insight -> Fraud Sentinel design.

Slide copy:

- Heterogeneous event histories -> structured CSV contract and feature windows.
- Temporal signals -> velocity, hold-time proxy, night activity, account age.
- Profile state matters -> optional account file and missing-data reporting.
- Relational AML gap -> typed graph artifacts and bounded network explorer.
- Privacy constraints -> local processing, pseudonymization, no raw data sent to models.

Speaker notes:

The project is not trying to clone PRAGMA. It uses PRAGMA as a strategic reference, then builds an MVP that is explainable, local, deterministic, and demo-reliable.

---

# Slide 16: Safety Boundary

Time: 2 minutes

Purpose:

- Set governance expectations.

Visual direction:

- Boundary line: "suspicious indicator" on one side, "confirmed fraud" crossed out on the other.

Slide copy:

- The system identifies suspicious indicators for human review.
- It does not confirm fraud.
- It does not block accounts or make customer decisions.
- It does not require a runtime LLM.
- It uses synthetic or approved anonymized data only.

Source cues:

- `AGENTS.md`
- `PRD.md`, Safety Boundary and Non-Goals

Speaker notes:

This is not a legal compliance system and not a production AML engine. The trust strategy is to be precise about what the demo does and does not do. Every analyst-facing output should say that human review is required.

---

# Slide 17: Who Uses It

Time: 2.5 minutes

Purpose:

- Show the project is designed around concrete users.

Visual direction:

- Three personas with their core questions.

Slide copy:

- Fraud analyst: "Which alerts should I review first, and why?"
- Compliance reviewer: "Can I audit the evidence and configuration?"
- Data engineer: "Can I rerun the pipeline safely and reproduce outputs?"
- Demo presenter: "Can I show Codex contribution without relying on fragile live generation?"

Source cues:

- `PRD.md`, Target Users and User Stories

Speaker notes:

The project works because each persona has a clear workflow. The analyst gets priority and evidence. Compliance gets provenance. The engineer gets repeatability. The presenter gets a controlled demonstration path.

---

# Slide 18: Current Repo Status

Time: 2 minutes

Purpose:

- Avoid overstating implementation status.

Visual direction:

- Phase tracker with Phase 0 and 1 checked, later phases planned.

Slide copy:

- Phase 0: repository assessment complete.
- Phase 1: scaffold complete.
- Present today: package metadata, config, CLI skeleton, tests, dashboard shell, operating rules, PRD, and status doc.
- Not yet implemented: synthetic generation, ingestion, scoring, graph, OKF export, dashboard artifacts, monitoring, and performance hardening.

Source cues:

- `IMPLEMENTATION_STATUS.md`
- `README.md`

Speaker notes:

This slide is useful for credibility. The deck describes the project vision and implementation roadmap, but it also marks exactly where the repo is today. That makes the next phases easier to fund, staff, and verify.

---

# Slide 19: Data Contract

Time: 2.5 minutes

Purpose:

- Make the input shape concrete.

Visual direction:

- Required columns in a compact schema table.

Slide copy:

Required transaction fields:

- `transaction_id`
- `event_timestamp`
- `sender_account_id`
- `receiver_account_id`
- `amount`
- `currency`

Recommended fields:

- device, IP, channel, bank, country, transaction type, account opened date, synthetic labels

Speaker notes:

The minimum viable data model is intentionally simple: who sent money to whom, when, how much, and in what currency. Optional fields enable stronger rules, especially shared-device, shared-IP, cross-border, account-age, and channel-based signals.

---

# Slide 20: Synthetic Data Strategy

Time: 2.5 minutes

Purpose:

- Explain how the demo can be validated without real bank data.

Visual direction:

- Seven suspicious scenario cards.

Slide copy:

Injected scenarios:

- `fan_in_mule`
- `rapid_pass_through`
- `layering_chain`
- `shared_device_ring`
- `cross_border_funnel`
- `new_account_burst`
- `short_cycle`

Speaker notes:

Synthetic data is not a throwaway demo convenience. It is how we prove detection coverage without exposing sensitive data. The PRD target is to detect at least 90% of explicitly marked synthetic fraud seed accounts.

---

# Slide 21: Pipeline Architecture

Time: 3 minutes

Purpose:

- Walk through the end-to-end system.

Visual direction:

- Vertical flow diagram from CSV to dashboard and OKF.

Slide copy:

1. CSV ingestion and validation
2. Normalized transactions and rejected rows
3. Data profiling and run manifest
4. Account feature engineering
5. Rule engine and explainable scores
6. Suspicious graph construction
7. OKF export and validation
8. Obsidian and Streamlit dashboard consumption

Speaker notes:

The system is built around prepared artifacts. Dashboard pages should not read the one-million-row CSV on load. The pipeline writes Parquet, JSON, logs, and OKF Markdown. The dashboard reads those artifacts.

---

# Slide 22: Feature Engineering

Time: 2.5 minutes

Purpose:

- Explain how suspicious behavior is transformed into measurable evidence.

Visual direction:

- Feature families arranged by time, counterparty, access point, and network.

Slide copy:

Feature families:

- Velocity: transaction counts and amounts over 24 hours and 7 days.
- Counterparty structure: unique senders, unique receivers, concentration.
- Movement behavior: pass-through ratio and hold-time proxy.
- Access sharing: shared device and shared IP counts.
- Context: account age, country, channel, night activity.
- Network: degree, connected component, cycle indicators.

Speaker notes:

The most important design choice is that every alert has evidence. A score is not enough. The analyst needs observed values, thresholds, triggered rules, and unavailable rules.

---

# Slide 23: Rule-Based Scoring

Time: 2.5 minutes

Purpose:

- Show how risk becomes explainable.

Visual direction:

- Rule weights stacked into a capped score.

Slide copy:

Baseline rules:

- High fan-in: 20
- Rapid pass-through: 25
- High velocity: 15
- High fan-out: 10
- Shared access point: 15
- Cross-border funnel: 10
- New account burst: 15
- Short cycle: 20

Score = sum triggered weights, capped at 100.

Speaker notes:

No detection threshold is supposed to be hard-coded in Python. Rules and thresholds live in `config/rules.yaml`. That makes tuning visible and auditable.

---

# Slide 24: Alert Evidence

Time: 2.5 minutes

Purpose:

- Show the analyst-facing output.

Visual direction:

- Mock alert card with score, evidence table, rule explanations, and OKF link.

Slide copy:

Each alert records:

- account ID, score, severity, and triggered rules
- evidence values next to thresholds
- run ID, data fingerprint, rules config hash
- related account, cluster, signal, and OKF concept
- human-review disclaimer

Speaker notes:

This is where explainability becomes operational. A compliance reviewer can see what rule fired, what threshold was used, what data run generated it, and where the linked concept lives.

---

# Slide 25: Graph And Clusters

Time: 3 minutes

Purpose:

- Explain why the graph is central, not decorative.

Visual direction:

- Suspicious subgraph around one critical account.

Slide copy:

Graph node types:

- Account, Alert, Cluster, Fraud Signal, Device, IP, Run, Dataset, Metric, Runbook

Typed analytical edges:

- transferred to, triggered signal, has alert, member of cluster, used device, used IP, generated in run, derived from dataset

Speaker notes:

The project keeps two graph representations. The analytical graph is structured Parquet with typed edges and numeric attributes. The OKF graph is Markdown links for humans, Obsidian, Git, and agents.

---

# Slide 26: OKF Knowledge Bundle

Time: 2.5 minutes

Purpose:

- Introduce OKF as the canonical knowledge output.

Visual direction:

- Folder tree of `artifacts/okf_bundle/`.

Slide copy:

OKF output:

- Markdown files with YAML frontmatter
- Standard relative Markdown links
- Root `index.md`, subdirectory indexes, and `log.md`
- Concepts for accounts, alerts, clusters, signals, devices, IPs, runs, datasets, metrics, and runbooks
- No one-file-per-transaction explosion

Source cues:

- Google Cloud OKF announcement
- `PRD.md`, Open Knowledge Format Requirements

Speaker notes:

OKF is a format, not a platform. It gives the investigation a portable shape: readable by humans, parseable by agents, usable in Git, and openable in tools like Obsidian.

---

# Slide 27: Why OKF Matters For Agents

Time: 2.5 minutes

Purpose:

- Connect OKF to the agentic AI value proposition.

Visual direction:

- Same knowledge bundle consumed by analyst, Codex, Obsidian, and a future retrieval agent.

Slide copy:

- A reusable knowledge layer prevents each tool from rebuilding context.
- Markdown and YAML keep evidence inspectable.
- Links preserve the investigation graph.
- `log.md` preserves run history.
- Future agents can reason over curated summaries instead of raw transaction rows.

Source cues:

- Google Cloud: OKF is vendor-neutral, agent- and human-friendly, and based on Markdown plus YAML frontmatter.

Speaker notes:

This is where the project becomes more than a dashboard. The OKF bundle is an investigation memory. It can be searched, versioned, reviewed, shared, and used as context by future AI systems without exposing raw transaction tables.

---

# Slide 28: Dashboard Overview

Time: 2.5 minutes

Purpose:

- Preview the six Streamlit pages from the PRD.

Visual direction:

- Dashboard sitemap.

Slide copy:

Required pages:

- Executive Overview
- Alert Queue
- Account Investigation
- Network Explorer
- OKF Knowledge Bundle
- Monitoring

Speaker notes:

The current dashboard is a shell, planned for Phase 6. The PRD is very specific about the intended pages and controls. That specificity is useful because it makes the dashboard build measurable.

---

# Slide 29: Analyst Investigation Flow

Time: 2.5 minutes

Purpose:

- Show how a user moves through the product.

Visual direction:

- Click path: alert queue -> account detail -> graph neighborhood -> OKF concept -> runbook.

Slide copy:

Investigation path:

1. Filter high and critical alerts.
2. Select an account.
3. Review triggered rule evidence.
4. Inspect counterparties and timeline.
5. Open network neighborhood.
6. Follow OKF links to alert, cluster, signal, run, and runbook.

Speaker notes:

This is the main product experience. The analyst should never be forced to infer why a score exists. The interface should always connect score, evidence, network, provenance, and next review steps.

---

# Slide 30: Network Explorer

Time: 2.5 minutes

Purpose:

- Make graph constraints explicit.

Visual direction:

- Graph view with controls around it: depth, min amount, risk level, node type.

Slide copy:

The network explorer must be bounded:

- one-hop or two-hop depth
- minimum edge amount
- minimum transaction count
- risk-level filter
- node-type filter
- configurable node and edge limits

Speaker notes:

The PRD explicitly says not to render the complete raw graph. That is a product design choice and a performance control. Show the relevant graph, not the whole universe.

---

# Slide 31: Monitoring Loop

Time: 2.5 minutes

Purpose:

- Show how the MVP supports repeated runs.

Visual direction:

- Micro-batch loop around `data/incoming/transactions_*.csv`.

Slide copy:

Monitoring means file-based micro-batches:

- discover new CSV files
- skip already processed file hashes unless forced
- validate and append transactions
- recompute snapshot features
- compare current and prior alerts
- update analytical artifacts and OKF `log.md`

Speaker notes:

This is not real-time streaming. The MVP uses repeatable micro-batches so the demo remains controlled and explainable. Full snapshot recomputation is acceptable for the MVP; incremental recomputation is a stretch goal.

---

# Slide 32: Demo Run And Codex Role

Time: 2.5 minutes

Purpose:

- Explain how the project should be presented live.

Visual direction:

- Timeline: setup, bounded Codex change, tests, sample run, full-run artifacts, dashboard, OKF, monitoring delta.

Slide copy:

Recommended live Codex task:

- Add a shared-device rule and tests, or
- Change a threshold and explain impact, or
- Add an OKF validation check, or
- Add a dashboard filter.

Demo principle:

- Prebuild the full path.
- Live-code one bounded change.
- Keep fallback artifacts ready.

Speaker notes:

The PRD's demo guidance is strong: do not rely on Codex to build the whole system live. Show Codex as an engineering coworker working within a tested system.

---

# Slide 33: Evidence That This Direction Is Market-Relevant

Time: 3 minutes

Purpose:

- Connect the project to current market and case-study evidence.

Visual direction:

- Three evidence cards: scale, graph, explainability.

Slide copy:

- Scale: FBI, FTC, UK Finance, and Nasdaq all point to fraud and financial crime as large, evolving, and economically material.
- Graph: Lloyds and IBM explored graph-based anomaly detection for mule-account analysis using anonymized transaction data.
- Explainability: SEFraud reports deployment at ICBC, emphasizing graph-based fraud detection with explanations aligned to expert business understanding.
- Industry need: Nasdaq reports expected growth in AI/ML spend for financial crime prevention.

Source cues:

- FBI IC3 2024 Annual Report
- FTC fraud loss release
- UK Finance Annual Fraud Report 2025
- Nasdaq Verafin 2024 Global Financial Crime Report
- SEFraud KDD 2024 paper
- ITPro coverage of Lloyds/IBM research

Speaker notes:

The project is well timed because the problem is not only high volume; it is networked, fast-moving, and expensive to investigate manually. The outside evidence supports three bets: better data engineering, better graph analysis, and better explainability.

---

# Slide 34: Differentiated Value

Time: 2.5 minutes

Purpose:

- Make the project memorable.

Visual direction:

- Four-part value stack.

Slide copy:

Fraud Sentinel differentiates on:

- Local-first reproducibility: no mandatory cloud service or runtime LLM.
- Explainability: every alert traces to configured thresholds and evidence.
- Portability: OKF exports can be opened, versioned, and reused.
- Agentic workflow: Codex accelerates engineering while deterministic code handles data.

Speaker notes:

Many fraud demos over-index on either black-box AI or dashboard visuals. Fraud Sentinel's sharper story is that it joins engineering automation, explainable analytics, and portable knowledge.

---

# Slide 35: Risks, Mitigations, And Roadmap

Time: 3 minutes

Purpose:

- Be candid about what can go wrong and what comes next.

Visual direction:

- Risk-to-mitigation table plus phase roadmap.

Slide copy:

Key risks:

- Graph too dense -> enforce limits and suspicious-subgraph filtering.
- False positives -> expose thresholds, evidence, and tuning.
- Missing optional fields -> mark rules as `not_evaluated`.
- Sensitive data leakage -> synthetic data, masking, field allowlists, privacy tests.
- Live demo failure -> use sample run and prepared artifacts.

Next phases:

- Phase 2: synthetic generator and ingestion
- Phase 3: features and scoring
- Phase 4: graph and clusters
- Phase 5: OKF exporter and validator
- Phase 6-9: dashboard, monitoring, performance, final verification

Speaker notes:

The roadmap is already in the PRD. The most important next step is Phase 2: build the generator and ingestion pipeline, validate on a small deterministic fixture, then scale toward one million rows.

---

# Slide 36: Closing Ask

Time: 1.5 minutes

Purpose:

- End with a concrete decision point.

Visual direction:

- Three next-step buttons or cards.

Slide copy:

Recommended next steps:

1. Approve Phase 2 implementation: synthetic generator and ingestion.
2. Preserve the PRAGMA-informed design boundary: structured local processing first, optional model work later.
3. Use the 90-minute walkthrough as the narrative spine for demo, roadmap, and stakeholder alignment.

Speaker notes:

The project is compelling because it is realistic. It does not promise magic classification. It promises an inspectable path from raw transactions to evidence, graphs, dashboard workflows, and reusable knowledge.

---

# Appendix: NotebookLM Generation Prompt

Use this prompt when importing the markdown into NotebookLM:

Generate a professional 90-minute slide presentation from this source deck. Preserve the 36-slide structure and timing. Use the "Slide copy" as visible slide content, use "Speaker notes" for presenter notes, and use "Visual direction" to choose diagrams or layouts. Keep the deck credible and practical. Do not claim the full pipeline is implemented today; clearly distinguish the current Phase 1 repo status from the PRD roadmap. Include source citations in speaker notes or final reference slides.

---

# Appendix: Core References

- Fraud Sentinel PRD: `PRD.md`
- Fraud Sentinel implementation status: `IMPLEMENTATION_STATUS.md`
- Fraud Sentinel operating rules: `AGENTS.md`
- PRAGMA paper in repo: `papers/2604.08649v1.pdf`
- PRAGMA arXiv page: https://arxiv.org/abs/2604.08649
- PRAGMA HTML page: https://arxiv.org/html/2604.08649v1
- FBI IC3 2024 Annual Report: https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf
- FTC 2024 fraud loss release: https://www.ftc.gov/news-events/news/press-releases/2025/03/new-ftc-data-show-big-jump-reported-losses-fraud-125-billion-2024
- UK Finance Annual Fraud Report 2025: https://www.ukfinance.org.uk/policy-and-guidance/reports-and-publications/annual-fraud-report-2025
- Nasdaq Verafin 2024 Global Financial Crime Report: https://www.nasdaq.com/global-financial-crime-report
- SEFraud KDD 2024: https://arxiv.org/abs/2406.11389
- Lloyds/IBM mule-account graph research coverage: https://www.itpro.com/technology/lloyds-bank-touts-quantum-potential-in-anti-fraud-activities
- Google Cloud OKF announcement: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/
