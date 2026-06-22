# fraud-sentinel: PRAGMA Paper Alignment and Gap Analysis

**Project:** `fraud-sentinel`<br>
**Target:** MVP fraud and mule-account investigation system<br>
**Compared document:** *PRAGMA: Revolut Foundation Model* (arXiv:2604.08649v1, 9 April 2026)<br>
**Current product specification:** Agentic AI mule-account fraud detection MVP with OKF knowledge graph, dashboard, and micro-batch monitoring

---

## 1. Executive conclusion

The current `fraud-sentinel` specification does **not implement PRAGMA**. It implements a deterministic, network-aware fraud investigation product around transaction CSV data. Its strongest overlap with the paper is at the **application and operational layers**: banking events, account context, fraud detection, privacy, reproducible data pipelines, and evaluation-oriented synthetic data.

The current MVP intentionally excludes the paper's core contribution: a pre-trained financial foundation model. It has no key-value-time tokenizer, no Profile State/Event/History Transformer encoders, no masked-model pre-training, no embedding probes, no LoRA fine-tuning, and no multi-task model evaluation.

This distinction is important because the paper itself reports that PRAGMA underperforms a network-aware anti-money-laundering baseline by **47.1% on F0.5**, attributing the gap to PRAGMA processing user histories in isolation rather than modelling cross-record network relationships. `fraud-sentinel` already implements the relational layer that PRAGMA lacks: transfer edges, shared-device/IP relationships, cycles, connected clusters, and graph investigation.

The recommended direction is therefore **hybrid**, not replacement:

```text
PRAGMA-style account/event embedding
        +
fraud-sentinel graph and rule features
        +
calibrated fraud classifier
        ->
explainable alert, OKF graph, dashboard, and monitoring
```

For the current MVP, retain deterministic rule and graph scoring. Add a small PRAGMA-compatible representation layer only after the MVP is stable and labelled data is available.

---

## 2. What the PRAGMA paper implements

PRAGMA is an encoder-only financial foundation model for heterogeneous, irregular banking histories. Its principal components are:

1. A record represents a user history up to an **evaluation point**, plus contextual profile state.
2. Multiple event sources are combined, including transactions, app activity, trading, and communications.
3. Every field is represented as a **key-value-time** item.
4. Numerical values use learned percentile buckets; categorical values use single tokens; free text uses BPE-style subword tokens.
5. Time is represented with log-transformed elapsed time and calendar-cycle features.
6. A hierarchical model uses a Profile State Encoder, an Event Encoder, and a History Encoder.
7. The model is pre-trained with masked modelling over individual tokens, entire events, and semantic keys.
8. The frozen model can provide embeddings for a linear probe, or be adapted using LoRA.
9. The paper evaluates one backbone across fraud, credit scoring, communication engagement, product recommendation, recurrent transactions, and lifetime value.
10. Training uses specialised storage, event-count sharding, dynamic token-budget batching, sequence packing, variable-length attention, and truncation.

The research corpus contains 26 million user records from 111 countries, 24 billion events, and 207 billion tokens. Model sizes range from 10 million to 1 billion parameters.

---

## 3. What the current fraud-sentinel MVP implements

The existing specification implements:

- CSV ingestion, validation, normalisation, deduplication, and rejected-row quarantine.
- One-million-row local processing using DuckDB and Parquet.
- Account-level handcrafted fraud features.
- Configurable and explainable weighted fraud rules.
- Network features and bounded graph analysis.
- Detection of fan-in, fan-out, rapid pass-through, shared devices/IPs, cross-border funnels, new-account bursts, layering chains, and short cycles.
- Suspicious clusters based on transfer and shared-access relationships.
- Typed analytical graph artifacts.
- OKF v0.1 knowledge bundle generation and validation.
- Obsidian compatibility.
- Streamlit fraud dashboard.
- File-based micro-batch monitoring.
- Privacy, pseudonymisation, provenance, and audit artifacts.
- Synthetic labelled scenarios for acceptance testing.

The specification explicitly states that the MVP will **not train a machine-learning model** and adopts rule-based scoring as an architecture decision.

---

## 4. Coverage matrix

Legend:

- **Covered:** substantively implemented by the current specification.
- **Partial:** related data or product capability exists, but not in the paper's form.
- **Not covered:** absent from the current specification.
- **Complementary:** outside PRAGMA's core design but directly addresses one of its limitations.

| PRAGMA capability | fraud-sentinel coverage | Current implementation | Required change |
|---|---|---|---|
| Banking fraud use case | Covered | Mule-account and suspicious-network detection | Retain |
| Event timestamp and sequence order | Partial | Transaction timestamps and rolling windows | Build per-account ordered histories and evaluation-point snapshots |
| Multi-source event histories | Not covered | Transaction CSV only | Add canonical events for app, communication, trading, card, transfer, and product activity |
| Static profile state | Partial | Optional account opening date, KYC risk, country, account type | Add profile-state snapshot schema, balance quantiles, tenure, service/product state, and lifelong milestones |
| Pseudonymised data | Covered | HMAC pseudonymisation and synthetic/anonymised-data requirements | Retain and extend to model-training datasets |
| Key-value-time data representation | Not covered | Fixed transaction columns and handcrafted SQL features | Add generic event/key/value/time schema and serializer |
| Numerical percentile tokenisation | Not covered | Raw numeric columns and aggregate features | Learn train-only quantile boundaries and persist tokenizer artifacts |
| Categorical tokenisation | Not covered | Normalised strings | Add categorical vocabulary, unknown handling, and field-level type registry |
| BPE text tokenisation | Not covered | Description excluded from OKF and unused by scoring | Add controlled free-text tokenisation with privacy filters |
| Log elapsed-time encoding | Not covered | Windowed counts and hold-time proxy | Add per-event log-seconds-to-latest-event and lifelong-event distances |
| Calendar-cycle features | Partial | Night-activity ratio | Add hour/day-of-week/day-of-month periodic embeddings |
| Profile State Encoder | Not covered | No neural model | Implement bidirectional Transformer branch |
| Event Encoder | Not covered | No neural model | Implement per-event bidirectional Transformer branch |
| History Encoder | Not covered | No neural model | Implement cross-event Transformer over profile and event representations |
| PRAGMA-S/M/L model family | Not covered | No parameterised model family | Start with PRAGMA-S-compatible configuration; add M/L only after validation |
| Masked token modelling | Not covered | No self-supervised training | Add token, event, and key-level masking objective |
| Frozen embedding extraction | Not covered | No embeddings | Persist account/evaluation-point embeddings with model version |
| Linear embedding probe | Not covered | Rule score only | Add logistic-regression probe with temporal train/validation/test splits |
| LoRA fine-tuning | Not covered | No model adaptation | Add parameter-efficient fine-tuning for fraud labels |
| Precision and recall evaluation | Partial | Synthetic seed-detection rate only | Add precision, recall, PR-AUC, F0.5, calibration, and threshold analysis |
| Multi-task downstream evaluation | Not covered | Fraud only | Add the paper's other five tasks and task-specific labels/heads |
| Event-count sharding | Not covered | Parquet artifacts, but not model-training shards | Partition records by event-count bands |
| Dynamic token-budget batching | Not covered | DuckDB batch analytics only | Implement training dataloader with a fixed token budget |
| Sequence packing/varlen attention | Not covered | No GPU sequence model | Add packed event buffers and variable-length attention kernels |
| Context truncation | Partial | Bounded dashboard graph, not sequence context | Add event, profile, and history context limits with recency retention |
| GPU pre-training infrastructure | Not covered | Local CPU-oriented MVP | Add PyTorch distributed training, bf16, checkpoints, metrics, and GPU environment |
| Optional pre-trained text encoder | Not covered | No text embeddings | Add only as an opt-in experiment after structural model baseline |
| Relational AML graph features | Complementary / strong | Transfer graph, shared devices/IPs, cycles, clusters, centrality | Preserve; this addresses PRAGMA's documented AML weakness |
| Analyst investigation interface | Covered beyond paper | Dashboard, OKF, Obsidian, alerts, runbooks | Retain as product layer |
| Continuous monitoring | Covered beyond paper | Micro-batch ingestion and alert-state changes | Extend with model and tokenizer version monitoring |
| Reproducibility metadata | Covered beyond paper | Source/config hashes, commit, run manifest | Extend with dataset split, checkpoint, tokenizer, and adapter hashes |

---

## 5. Areas already aligned with the paper

### 5.1 Financial-event domain

Both systems operate on banking events and seek discriminative fraud signals from user/account histories. The existing transaction schema already includes several fields useful for a PRAGMA-style event representation: timestamp, type, channel, amount, currency, device, country, merchant category, and description.

### 5.2 Profile context, at a limited level

The optional account file and transaction fields provide account opening time, KYC risk, home country, account type, and status. These correspond conceptually to PRAGMA's profile state, but the MVP uses them as explicit rule inputs rather than tokens in a dedicated encoder.

### 5.3 Time and sequence awareness

The MVP calculates rolling windows, activity velocity, pass-through ratios, hold-time proxies, and recency. This captures selected temporal patterns but does not learn representations of full irregular histories.

### 5.4 Privacy and provenance

The current specification is stronger operationally than the paper description in several areas: pseudonymisation options, PII exclusion, source fingerprints, configuration hashes, code commits, generated-artifact validation, and audit-friendly run manifests.

### 5.5 Fraud and AML network structure

The strongest alignment is indirect. The paper's AML study concludes that isolated record embeddings are insufficient where cross-record relationships matter. `fraud-sentinel` explicitly models those relationships and therefore supplies the missing network context.

---

## 6. Areas that are fundamentally different

### 6.1 Handcrafted rule engine versus learned representation

`fraud-sentinel` converts raw transactions into manually selected aggregate features and weighted rules. PRAGMA seeks to reduce the need for such feature engineering by learning reusable embeddings directly from heterogeneous histories.

These approaches are not mutually exclusive:

- Rules provide transparency, fast delivery, and reliable demo behaviour.
- Learned embeddings may capture patterns that rules miss, but require labelled data, compute, model governance, and stronger evaluation.

### 6.2 Transaction graph versus per-user sequence encoder

`fraud-sentinel` treats accounts as nodes and transfers/shared access as edges. PRAGMA treats each user's history independently. For mule-account and AML use cases, the graph representation is essential and should not be removed.

### 6.3 Product system versus research backbone

The current specification includes alert management artifacts, knowledge export, dashboarding, monitoring, privacy controls, and analyst explanations. The paper focuses on model representation and experiments, not an end-user monitoring product.

---

## 7. Critical reading of the paper for fraud-sentinel

### Strengths

- The key-value-time representation is more suitable for financial records than naïvely converting structured rows to text.
- The hierarchical encoder separates within-event, cross-event, and profile-state reasoning.
- Masked self-supervision can exploit large unlabelled banking histories.
- Frozen probes offer a fast method to test representation usefulness.
- LoRA lowers task-specific training cost.
- The profile-state ablation is highly relevant: adding profile context substantially improved external-fraud precision and recall in the reported relative comparison.

### Limitations relevant to implementation

- The underlying banking corpus, task datasets, production baselines, and absolute performance values are proprietary.
- The paper reports relative results, so exact target metrics cannot be independently reconstructed.
- The paper does not provide enough public information to guarantee byte-for-byte or metric-for-metric replication of the internal system.
- The AML result is negative: a linear probe on PRAGMA-L embeddings performs markedly worse than the network-aware baseline.
- The paper's core model is account-history-centric and does not solve relational mule-network detection on its own.
- The full training scale is far beyond the current MVP: 24 billion events versus 1 million transaction rows.

Accordingly, `fraud-sentinel` can implement a faithful open re-creation of the architecture and training recipe, but it cannot verify the paper's proprietary results without comparable data, labels, baselines, and undisclosed implementation details.

---

## 8. Recommended target architecture

### 8.1 MVP architecture: retain current specification

```text
CSV transactions
  -> deterministic validation and profiling
  -> account and graph features
  -> configurable rule score
  -> alerts and clusters
  -> OKF knowledge bundle
  -> dashboard and monitoring
```

This remains the correct architecture for a two-hour showcase.

### 8.2 Post-MVP PRAGMA-lite architecture

```text
Canonical event/profile store
  -> key-value-time tokenizer
  -> PRAGMA-S-style encoder
  -> frozen account embeddings
  -> linear fraud probe

Account embeddings
  + existing rule features
  + existing graph features
  -> hybrid calibrated classifier
  -> current alert/OKF/dashboard pipeline
```

### 8.3 Full research architecture

```text
Multi-source banking histories
  -> scalable tokenizer and sharded training corpus
  -> PRAGMA-S / PRAGMA-M / PRAGMA-L pre-training
  -> frozen probes and LoRA adapters for six downstream tasks
  -> scale, profile, text, and adaptation ablations
  -> relational extension for AML
```

---

## 9. Gap analysis to implement the paper in full

### Gap A: Project identity and repository naming

The current document still uses names such as `fraud-agentic-demo`, `fraud_demo`, `fraud-demo://`, and `producer: fraud-agentic-demo`.

Required replacements:

| Current | Required |
|---|---|
| Repository | `fraud-sentinel/` |
| Python package | `fraud_sentinel` |
| Module commands | `python -m fraud_sentinel ...` |
| OKF producer | `fraud-sentinel` |
| Resource URI | `fraud-sentinel://...` |
| Dashboard title | `Fraud Sentinel` |
| Bundle name | `Fraud Sentinel Knowledge Graph` |

### Gap B: Canonical event and profile-state data model

Required work:

- Introduce `entities`, `evaluation_points`, `events`, `event_fields`, `profile_state`, `lifelong_events`, and `labels` datasets.
- Represent each model record as all permitted events before an evaluation point plus profile state at that point.
- Prevent future-event leakage.
- Support variable schemas per event source.
- Add source-specific field registries and privacy allowlists.

Definition of done:

- A deterministic builder produces account-history records from CSV/Parquet.
- Every record has an evaluation point, ordered events, profile state, and optional downstream label.
- Temporal leakage tests pass.

### Gap C: Multi-source data

Required sources for faithful scope:

- Transfers and card/payment events.
- Account funding/top-ups.
- App/navigation events.
- Communication events.
- Trading/investment events.
- Product/account-state events.

For an open implementation, synthetic equivalents are acceptable, but a transactions-only corpus is not a full implementation of the paper.

### Gap D: Tokenizer

Required modules:

```text
src/fraud_sentinel/modeling/tokenizer/
  schema_registry.py
  key_vocab.py
  numeric_buckets.py
  categorical_vocab.py
  text_bpe.py
  temporal.py
  serializer.py
  artifacts.py
```

Requirements:

- One token per semantic key.
- Train-only percentile buckets for each numerical field, including a zero bucket.
- Cardinality-based categorical versus text classification, with controlled manual overrides.
- BPE-style tokenizer for text fields and `[UNK]` handling.
- Log-transformed time distance.
- Periodic hour, weekday, and day-of-month features.
- Persisted, versioned tokenizer artifact.

### Gap E: PRAGMA model architecture

Required PyTorch modules:

```text
ProfileStateEncoder
EventEncoder
HistoryEncoder
MaskedModelHead
RecordEmbeddingHead
TaskHead
```

Start with a PRAGMA-S-compatible target:

- Approximately 10 million parameters.
- `d_model = 192`.
- `d_ffn = 768`.
- Profile/Event/History depths of 1/5/2.
- 3 attention heads.
- GELU, pre-norm, dropout 0.1.
- `[USR]` and `[EVT]` tokens.
- RoPE for temporal coordinates.

Definition of done:

- Forward pass supports variable events and fields.
- Model returns token, event, and record embeddings.
- Parameter count and shape tests pass.

### Gap F: Self-supervised pre-training

Implement:

- Individual token masking at 15%.
- Whole-event masking at 10%.
- Semantic-key/value masking at 10%.
- Selected `[UNK]` corruption excluded from the reconstruction loss.
- Cross-entropy with label smoothing.
- Optional MSE reconstruction for frozen text embeddings.

Operational requirements:

- Deterministic seeds.
- Checkpoints and resumable training.
- Train/validation pre-training loss.
- Tokenizer and dataset fingerprints.
- Model-card artifact.

### Gap G: Efficient training data plane

Required work:

- LMDB or equivalent indexed profile-state store.
- Parquet event shards grouped by event-count bands.
- Dynamic batching under a token budget.
- Packed variable-length event attention.
- Event limit, profile-state token limit, and history limit.
- bf16 mixed precision.
- Multi-GPU distributed training for larger variants.
- Throughput, GPU memory, and padding-waste metrics.

The current DuckDB/Parquet pipeline is a useful starting point, but it is an analytics pipeline rather than a Transformer training data plane.

### Gap H: Downstream fraud adaptation

Implement two paths:

1. **Embedding probe:** frozen embeddings, standard scaling, logistic regression with L-BFGS.
2. **LoRA:** adapters on Q/K/V and feed-forward projections, with rank sweeps over 4, 8, and 16.

Fraud metrics:

- Precision.
- Recall.
- PR-AUC.
- F0.5 where precision is prioritised.
- Calibration error and reliability curve.
- False-positive rate at operating thresholds.
- Alert volume and analyst-capacity constraints.

### Gap I: Relational AML fusion

A strict PRAGMA implementation would reproduce its limitation. A useful `fraud-sentinel` implementation should go further.

Recommended progression:

1. Concatenate PRAGMA record embeddings with current graph/rule features and train a calibrated classifier.
2. Use PRAGMA embeddings as node features in a graph neural network or graph Transformer.
3. Add cross-account pre-training objectives such as linked-counterparty prediction, temporal edge prediction, or suspicious-subgraph contrastive learning.
4. Evaluate against the rule-only, graph-only, sequence-only, and hybrid variants.

This is the highest-value product extension because mule activity is inherently relational.

### Gap J: Multi-task paper scope

To implement the complete paper rather than only its fraud use case, add datasets, labels, heads, and metrics for:

- Credit scoring.
- Communication engagement.
- Product recommendation.
- Recurrent transaction prediction.
- Lifetime value.
- External fraud.
- AML as a limitation/comparison case.

This is outside the practical scope of the `fraud-sentinel` MVP and should be a separate research workstream.

### Gap K: Ablations and scale experiments

Required experiments:

- PRAGMA-S versus M versus L.
- Frozen embedding probe versus LoRA.
- LoRA versus task-specific training from scratch.
- Event-only versus event-plus-profile-state.
- Native text tokenizer versus frozen pre-trained text encoder.
- Sequence-only versus graph-only versus hybrid AML model.

Store experiment definitions and results as versioned artifacts and optionally publish them as OKF research concepts.

### Gap L: Model operations and governance

Add:

- Model registry and checkpoint lineage.
- Tokenizer versioning.
- Training-data and label lineage.
- Model cards.
- Bias and subgroup analysis.
- Drift monitoring for event distributions and embedding distributions.
- Champion/challenger deployment.
- Rollback and threshold-control procedures.
- Analyst-feedback loop and label-quality governance.
- Explainability for both sequence and graph features.

---

## 10. Prioritised roadmap

### Phase 0 - Rename and preserve MVP boundary

- Rename repository and product references to `fraud-sentinel`.
- Keep current rule/graph MVP acceptance criteria unchanged.
- Add this paper alignment document as a research roadmap, not an MVP blocker.

### Phase 1 - MVP completion

- Complete ingestion, synthetic scenarios, rules, graph, OKF, dashboard, monitoring, tests, and one-million-row benchmark.
- Establish a rule-only and graph-aware baseline.

### Phase 2 - PRAGMA-lite feasibility

- Add canonical event/profile records.
- Implement tokenizer and PRAGMA-S model.
- Pre-train on a smaller approved or synthetic multi-source corpus.
- Extract embeddings and train a fraud linear probe.

Exit criterion:

- Embeddings outperform simple raw aggregate baselines on at least one time-separated fraud benchmark, or provide clear complementary lift when fused with graph features.

### Phase 3 - Hybrid fraud model

- Add LoRA fraud adaptation.
- Fuse sequence embeddings with graph and rule features.
- Calibrate scores and integrate them into the existing alert pipeline.
- Preserve deterministic evidence alongside learned-model scores.

Exit criterion:

- Hybrid model improves precision/recall or F0.5 over graph-only baseline at a fixed analyst alert capacity.

### Phase 4 - Scaled pre-training

- Implement event-count sharding, dynamic batching, sequence packing, bf16, and distributed training.
- Train S and M variants.
- Add reproducible experiment tracking and ablations.

### Phase 5 - Full paper research programme

- Add all six downstream tasks.
- Train S/M/L variants where data and compute permit.
- Reproduce reported ablation directions.
- Add optional text encoder experiment.
- Publish absolute internal metrics and baselines within the authorised environment.

### Phase 6 - Beyond-paper relational foundation model

- Add graph-aware pre-training or a hybrid sequence-graph encoder.
- Compare against network-aware AML baselines.
- Integrate relational embeddings into continuous monitoring.

---

## 11. Final assessment

### Current coverage

A qualitative assessment is:

- **Fraud product and operational shell:** approximately 65-75% aligned with what is needed to operationalise a fraud model.
- **PRAGMA data representation:** approximately 20-30% conceptually aligned.
- **PRAGMA model and training core:** approximately 0-10% implemented.
- **Full paper replication:** approximately 15-20% of the overall end-to-end capability, mostly in surrounding data, privacy, fraud-domain, and operational concerns rather than the foundation model itself.

These percentages are planning estimates, not measured engineering completion.

### Product recommendation

Do not redefine the MVP as a PRAGMA implementation. The current `fraud-sentinel` MVP is more suitable for the two-hour fraud demonstration and is better aligned with relational mule-account detection.

Treat PRAGMA as a post-MVP representation-learning workstream. The final target should combine:

- PRAGMA-style temporal account embeddings,
- existing deterministic fraud rules,
- existing network and graph features,
- calibrated supervised scoring,
- existing OKF knowledge output,
- existing dashboard and monitoring.

That hybrid design implements the paper's useful representation layer while directly addressing the paper's documented weakness on relational AML.

---

## 12. Source references by paper section/page

- Abstract and Figure 1: general-purpose multi-source banking foundation model and relative downstream gains, page 1.
- Introduction and contributions: multi-source events, profile state, key-value-time tokenisation, hierarchical encoder, masked modelling, LoRA, pages 2-3.
- Dataset and Figure 2: evaluation points, event history, profile state, 26M records, 24B events, 207B tokens, pages 3-4.
- Tokenisation and Figure 3: numeric, categorical, text, and temporal encoding, pages 4-5.
- Architecture and Figure 4/Table 1: Profile State, Event, and History encoders; 10M/100M/1B variants, pages 5-7.
- Training objective and adaptation: multi-level masking, probes, and LoRA, page 7.
- Training infrastructure: LMDB, Parquet sharding, dynamic batching, packing, truncation, and H100 compute, page 8.
- Downstream metrics and main results: pages 9-12.
- Profile-state and text-encoder ablations: pages 12-14.
- AML limitation and Table 9: page 15 in the PDF viewer's pagination sequence / paper page 14.
