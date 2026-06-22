# Fraud Sentinel

## Keynote, Current PRD/Specification, and PRAGMA Coverage Analysis

| Field | Value |
|---|---|
| Project | `fraud-sentinel` |
| Product stage | MVP / research demonstrator |
| Assessment date | 22 June 2026 |
| Documents assessed | Current consolidated PRD and technical specification; PRAGMA: Revolut Foundation Model; SCxSC MyFintech Week 2025 keynote |
| Assessment purpose | Determine keynote coverage, identify implementation gaps, and assess state-of-the-art/frontier positioning |

## 1. Executive conclusion

The SC keynote describes an **end-to-end anti-scam ecosystem**: upstream scam-content discovery, investor verification, deepfake and social-engineering detection, payment and mule-account tracing, cross-agency intelligence, rapid disruption, public warnings, education, enforcement, and cross-border cooperation.

The current `fraud-sentinel` PRD is narrower. It is a strong, explainable **mule-account transaction intelligence MVP** built around CSV processing, deterministic rules, a transfer and shared-identifier graph, an OKF knowledge bundle, Obsidian, a dashboard, and micro-batch monitoring.

PRAGMA adds a different capability: learned representations of long, multi-source banking event histories. It is potentially useful for account-level fraud and behavioural anomaly detection, but it does not cover public scam content, deepfakes, platform surveillance, regulatory watchlists, intervention, or cross-institution relational AML. Its own paper shows a major AML weakness when records are analysed in isolation rather than with a network-aware model.

Therefore:

- The current MVP covers the **mule/payment-analysis lane** of the keynote well.
- It covers only about **one-third of the keynote's wider capability surface**.
- PRAGMA improves behavioural modelling but does not close most of the keynote gaps.
- The current implementation is **modern and frontier-aware, but not state of the art**.
- A credible frontier direction is a hybrid of sequence foundation-model embeddings, temporal network analytics, multi-institution privacy-preserving collaboration, multimodal scam intelligence, and a real-time intervention loop.

## 2. Terminology

- **State of the art (SOTA):** demonstrated best or near-best performance on a comparable benchmark using transparent metrics and strong baselines.
- **Frontier development:** a leading-edge research or engineering direction that may not yet be mature, reproducible, or superior on every benchmark.
- **OSINT:** open-source intelligence gathered from publicly accessible sources such as websites, advertisements, social media, public registers, and alert lists.
- **Temporal graph:** a graph whose nodes, edges, and attributes change over time.
- **PETs:** privacy-enhancing technologies that enable analysis or collaboration while limiting disclosure of sensitive data.
- **CAL:** collaborative analysis and learning across organisations without relying solely on institution-level silos.

## 3. What the keynote requires

The keynote's capability model can be organised into five layers.

### 3.1 Threat and channel intelligence

- Investment scams operating through social and messaging platforms.
- Digital ecosystems involving e-wallets, blockchain infrastructure, and online trading.
- AI-generated impersonation and deepfake content.
- Psychological manipulation, including urgency and fear of missing out.
- Unlicensed firms, misleading promotions, finfluencers, and fraudulent advertisements.

### 3.2 Detection and verification

- Web crawling and surveillance.
- AI-assisted scam detection and monitoring.
- Investor checks before funds are transferred.
- Alert-list and regulator intelligence.
- Cross-border intelligence exchange.

### 3.3 Payment and network intelligence

- Online payment tracing.
- Mule-account identification.
- Network and cluster analysis.
- Cross-institution and cross-border flow analysis.

### 3.4 Disruption and enforcement

- Rapid reporting and coordinated response.
- Blocking pages, accounts, and content.
- Freezing or suspending suspicious transfers.
- Evidence preservation and case escalation.
- Enforcement actions and asset recovery.

### 3.5 Awareness and learning

- Public alerts on new scam methods.
- Investor education and practical guidance.
- Feedback from analyst dispositions and confirmed outcomes.
- Continuous updating as scam methods evolve.

## 4. Coverage matrix

Status meanings:

- **Strong:** directly designed and acceptance-tested.
- **Partial:** some relevant data or architecture exists, but the keynote outcome is not delivered.
- **Absent:** outside the current implementation.

| Keynote capability | Current PRD/specification | PRAGMA paper | Combined assessment |
|---|---|---|---|
| Mule-account and fund-flow detection | Strong | Partial | Strong analytical core, but not an operational response system |
| Fan-in, fan-out, rapid pass-through, layering, cycles | Strong | Partial | Strong for a synthetic MVP |
| Shared devices and IPs | Strong | Partial through profile/event fields | Good single-dataset entity linkage |
| Cross-border payments | Partial: ratio and funnel rules | Partial: multi-country event histories | Missing cross-institution and jurisdiction-level coordination |
| E-wallet and blockchain/virtual-asset flows | Minimal or absent | Not explicitly implemented | Major gap |
| Social media and messaging channels | Absent | Absent; PRAGMA communications are bank/platform events, not scam conversations | Critical gap |
| Deepfake and AI impersonation | Absent | Absent | Critical gap |
| Psychological manipulation and FOMO | Absent | Absent | Critical gap |
| Web crawling and platform surveillance | Absent | Absent | Critical gap |
| OSINT and public-register enrichment | Absent | Absent | Critical gap |
| Finfluencer, advertising, and unlicensed-entity monitoring | Absent | Absent | Critical gap |
| Public pre-investment verification | Absent | Absent | Product gap |
| Investor Alert List and international alert feeds | Absent | Absent | Integration gap |
| Cross-institution network intelligence | Partial only within one imported dataset | Absent and identified as an AML limitation | Critical gap |
| True real-time detection | Absent; micro-batch only | Offline training/inference design | Critical operational gap |
| Freeze, block, takedown, and fund recovery | Explicitly outside MVP | Absent | Critical operational gap |
| Explainable account alerts | Strong | Partial; learned embeddings need an explanation layer | Strong baseline if model explanations are added |
| Evidence provenance and auditability | Partial to strong through manifests, OKF, and deterministic evidence | Limited to model/evaluation artefacts | Missing legal chain-of-custody and case controls |
| Learned behavioural representations | Explicit non-goal | Strong | Research gap in current implementation |
| Profile-state modelling | Limited optional attributes | Strong and shown to improve external-fraud results | High-value near-term gap |
| Human review | Strong principle | Not a product workflow | Covered at MVP level |
| Analyst feedback and model learning | Future enhancement | Downstream adaptation exists, but not an operational feedback loop | Important gap |
| Public education and scam awareness | Absent | Absent | Outside present product scope |
| Privacy within one organisation | Good MVP safeguards | Anonymised training data | Reasonable MVP base |
| Privacy-preserving multi-party collaboration | Absent | Absent | Frontier and regulatory gap |

## 5. What the current MVP does well

### 5.1 Explainable mule detection

The deterministic rules, stored evidence, account features, and bounded graph make the system suitable for analyst demonstration. Every high-risk result can be traced to thresholds and observed values.

### 5.2 Relational analysis

The account-transfer graph, shared-device/IP links, components, cycles, and clusters address a central AML requirement: suspicious behaviour is often relational rather than isolated to one account.

### 5.3 Portable investigation knowledge

The OKF knowledge bundle and typed Parquet graph separate human/agent knowledge from analytical computation. This is a useful product architecture for investigations, audit, and interoperability, although it is not itself a detection breakthrough.

### 5.4 Safe MVP boundary

Synthetic data, pseudonymisation, no autonomous blocking, no row-level LLM classification, and explicit human review are appropriate for a two-hour demo.

## 6. What PRAGMA contributes

PRAGMA provides capabilities missing from the current MVP:

- Multi-source banking event histories rather than only transaction rows.
- Explicit account/profile state.
- Key-value-time representation for mixed numerical, categorical, textual, and temporal fields.
- Self-supervised masked pre-training.
- Reusable account embeddings.
- Lightweight downstream adaptation through linear probes and LoRA.

These features could identify behavioural patterns that fixed rules do not anticipate.

However, PRAGMA does not provide:

- Scam-content or deepfake detection.
- Social media or web surveillance.
- A regulator/watchlist intelligence layer.
- Cross-institution graph context.
- Real-time intervention.
- Case management, blocking, freezing, or recovery.
- Public-facing investor verification.

For AML, PRAGMA's isolated-history representation is insufficient by itself. The target architecture should therefore combine PRAGMA-style representations with graph and rule features rather than replace the graph.

## 7. June 2026 SOTA/frontier assessment

### 7.1 Current component positioning

| Component | June 2026 position | Assessment |
|---|---|---|
| Configurable weighted fraud rules | Established baseline | Not SOTA; valuable for explanation and fallback |
| DuckDB/Parquet processing of one million rows | Good demo engineering | Not frontier scale |
| NetworkX on a bounded suspicious graph | Modern MVP baseline | Not temporal, distributed, or cross-institutional SOTA |
| OKF plus Obsidian investigation output | Emerging product/knowledge integration | Innovative packaging, not detection SOTA |
| Codex-assisted implementation | Modern software-engineering workflow | Not a fraud-science contribution |
| PRAGMA-style sequence foundation model | Frontier financial representation learning | Not implemented in MVP; not sufficient for relational AML |
| Hybrid sequence embeddings plus temporal graph | Frontier direction | Recommended research target |
| Privacy-preserving cross-institution learning | Frontier/advanced institutional direction | Missing |
| Real-time payment-network intervention | Advanced production capability | Missing |
| Multimodal social/deepfake scam intelligence | Frontier anti-scam direction | Missing |

### 7.2 Why the project cannot claim SOTA today

1. It has no trained model or benchmark comparison.
2. Its success target is recovery of injected synthetic scenarios, not performance against independent labelled fraud data.
3. It lacks true time-based validation, concept-drift testing, calibration, and adversarial evaluation.
4. It does not compare against gradient-boosting, anomaly-detection, temporal-graph, or graph-neural-network baselines.
5. It has no cross-institution or national payment-network view.
6. It does not measure intervention outcomes such as time to freeze, loss prevented, or funds recovered.
7. PRAGMA reports relative results against proprietary baselines and itself underperforms a network-aware AML baseline.

The defensible positioning is:

> `fraud-sentinel` is a modern, explainable, graph-centred mule-account MVP and a research platform for testing hybrid transaction intelligence. It is frontier-aware, but it is not yet a state-of-the-art fraud detection or national anti-scam system.

## 8. Immediate MVP gap closure

These changes improve keynote alignment without turning the two-hour demo into a national platform.

### 8.1 Complete project renaming

Replace all legacy names:

```text
fraud-agentic-demo  -> fraud-sentinel
fraud_demo          -> fraud_sentinel
fraud-demo://       -> fraud-sentinel://
```

### 8.2 Extend the canonical entity model

Add optional concepts and graph nodes:

```text
ScamCampaign
VictimReport
Channel
Platform
ContentItem
EvidenceAsset
URL
Domain
PhoneNumber
Wallet
Organisation
UnauthorizedEntity
AlertListEntry
Intervention
Case
AnalystDisposition
```

Representative relationships:

```text
VictimReport -MENTIONS-> Account
VictimReport -OBSERVED_ON-> Platform
ContentItem -USES_URL-> URL
ContentItem -IMPERSONATES-> Organisation
Account -RECEIVED_FUNDS_FROM-> Victim
Account -MEMBER_OF-> MuleCluster
AlertListEntry -IDENTIFIES-> UnauthorizedEntity
Intervention -TARGETS-> Account
EvidenceAsset -SUPPORTS-> Case
```

### 8.3 Add three synthetic intelligence inputs

```text
scam_reports.csv
external_alerts.csv
content_evidence.csv
```

The data should connect a scam advertisement or message to a phone/domain, beneficiary account, transaction path, mule cluster, alert, and recommended analyst action.

### 8.4 Add a pre-investment checker

Provide a dashboard search page for an organisation name, domain, phone number, wallet, or bank account. It should search the local OKF/graph bundle and return:

- matching alerts and reports;
- connected accounts and clusters;
- source and timestamp;
- evidence confidence;
- a warning that the result is not legal or investment advice.

Use synthetic or approved mock alert feeds for the demo.

### 8.5 Add intervention recommendations, not autonomous actions

Support workflow states such as:

```text
review_required
refer_to_fraud_team
request_payment_hold
request_account_freeze
request_platform_takedown
refer_to_regulator
closed_false_positive
closed_confirmed
```

No automated blocking or freezing should be performed in the MVP.

### 8.6 Add analyst feedback and operational metrics

Capture:

- analyst disposition;
- reason codes;
- confirmed/false-positive outcome;
- time to detect;
- time to triage;
- time from victim report to account alert;
- alert precision at a fixed analyst-review capacity.

## 9. Frontier implementation roadmap

### Phase 1: Hybrid behavioural and relational detection

- Implement PRAGMA-S-compatible event/profile datasets.
- Train or adapt a small sequence encoder.
- Build a temporal heterogeneous transaction graph.
- Compare rules, gradient boosting, sequence embeddings, graph model, and hybrid model.
- Calibrate a final ensemble while preserving rule evidence.

Target architecture:

```text
PRAGMA-style account embedding
+ temporal graph embedding
+ deterministic rule features
+ profile-state features
-> calibrated fraud classifier
-> explanation and evidence layer
```

### Phase 2: Cross-institution collaboration

- Design a multi-participant data contract.
- Add privacy-enhancing technologies, secure aggregation, or federated learning where appropriate.
- Support network-wide signals without centralising all raw customer data.
- Model data ownership, consent, access, retention, and regulatory controls.

### Phase 3: Multimodal scam intelligence

- Add web and public-source crawling under authorised policies.
- Ingest social posts, messages, advertisements, images, audio, video, domains, phone numbers, and wallets.
- Detect impersonation, urgency, financial promises, unlicensed claims, and recurring campaign templates.
- Add Content Credentials/C2PA provenance verification when available.
- Support Malay, English, Chinese, and Tamil evaluation.

### Phase 4: Real-time response loop

- Replace file micro-batches with event streaming.
- Implement incremental graph updates and low-latency scoring.
- Integrate authorised regulator, payment-network, and institutional APIs.
- Support human-approved holds, freezes, takedown referrals, victim notification, and recovery tracking.

### Phase 5: Robust evaluation and governance

- Use strict chronological train/validation/test splits.
- Test unseen fraud patterns and concept drift.
- Red-team graph, content, and sequence models.
- Measure precision, recall, PR-AUC, F0.5, calibration, false positives, analyst throughput, time to intervention, losses prevented, and funds recovered.
- Add model cards, data sheets, fairness review, explainability review, human override, immutable logs, and independent validation.

## 10. Final decision

For the two-hour MVP, retain the deterministic graph-centred scope and add only lightweight external-intelligence and case-linking features. Do not make PRAGMA training, deepfake detection, cross-institution learning, or intervention APIs MVP blockers.

For the research roadmap, prioritise the combination of:

```text
multi-source event representation
+ profile state
+ temporal cross-record graph
+ external scam intelligence
+ privacy-preserving collaboration
+ real-time human-approved intervention
```

That combination is substantially closer to the June 2026 frontier than either the current PRD or PRAGMA alone.
