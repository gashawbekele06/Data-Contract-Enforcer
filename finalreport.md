# Data Contract Enforcer — Final Report
**TRP Week 7 · Bitol Open Data Contract Standard v3.0.0 · Tier 1**  
**Author:** gashawbekele06  
**Report Date:** 2026-04-02  
**Dashboard:** http://localhost:3000

---

## Section 1 — Enforcer Report (Auto-Generated)

> **⚙️ AUTO-GENERATED** — The following report was produced by `contracts/report_generator.py`  
> and is embedded verbatim from `enforcer_report/report_data.json` (generated 2026-04-02T19:43:46Z).  
> It is not hand-written. All numbers are sourced directly from the live validation pipeline.

---

### 1.1 Data Health Score

**Score: 100 / 100 — Healthy**

> 100/100 — Healthy: all major checks passing with no critical violations.

### 1.2 Validation Summary

| Metric | Value |
|--------|-------|
| Total Contract Checks Run | 266 |
| Passed | 266 |
| Failed | 0 |
| Warned | 0 |
| Reports Analyzed | 44 |
| Datasets Covered | 6 |

**Formula:** `Health Score = (passed / total × 100) − (critical_violations × 20)`, clamped [0, 100]  
→ `(266/266 × 100) − (0 × 20) = 100`

### 1.3 Violations This Week

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 0 |

**Most significant violation:**

| Field | Value |
|-------|-------|
| `check_id` | `ai_extensions.embedding_drift` |
| `violation_id` | `5692f759-471e-40f6-9202-d2fcd224acdb` |
| `severity` | HIGH |
| `system` | `week3-document-refinery-extractions` |
| `field` | `extracted_facts[*].text` |
| `message` | Embedding drift FAIL: 0.9534 (threshold=0.15) |
| `detected_at` | 2026-04-02T18:41:17Z |

### 1.4 Schema Changes Detected

| Contract | Column | Change Type | Compatible | Required Action |
|----------|--------|-------------|------------|-----------------|
| `week3-document-refinery-extractions` | `processing_time_ms` | `range_tightened` | **NO — BREAKING** | Migration plan required |
| `week3-document-refinery-extractions` | `processing_time_ms` | `range_tightened` | **NO — BREAKING** | Migration plan required |
| `week3-document-refinery-extractions` | `processing_time_ms` | `range_widened` | Yes — COMPATIBLE | None required |

### 1.5 AI System Risk Assessment (Overall: AMBER)

| Check | Raw Value | Status |
|-------|-----------|--------|
| Embedding Drift Score | 1.0170 (threshold = 0.15) | **FAIL** |
| Prompt Input Violation Rate | 0.0000 (0 / 60 records) | PASS |
| LLM Output Violation Rate | 0.0000 (0 / 50 outputs, trend=stable) | PASS |
| Trace Schema | 0 run_type violations, 0 token mismatches / 50 traces | PASS |

### 1.6 Recommended Actions

**[Priority 1 — HIGH]**  
Fix field `extracted_facts[*].text` in contract `week3-document-refinery-extractions`:  
Embedding drift FAIL: 0.9534 (threshold=0.15).  
Locate change in the extraction pipeline and revert, or update contract clause `ai_extensions.embedding_drift`.

**[Priority 2 — HIGH]**  
Investigate embedding drift in `extracted_facts[*].text`.  
Re-run `contracts/ai_extensions.py --set-baseline` after confirming the distribution shift is intentional.  
Affected pipeline: `week3-document-extraction-pipeline`

---

## Section 2 — Violation Deep-Dive

### 2.1 The Failing Check

The most significant violation in this reporting period is a **semantic contract breach** in the Week 3 Document Refinery pipeline — embedding drift detected on field `extracted_facts[*].text`.

```
check_id  : ai_extensions.embedding_drift
contract  : week3-document-refinery-extractions
field     : extracted_facts[*].text
actual    : drift_score = 0.9534
expected  : drift_score < 0.15  (contract clause: ai_extensions.embedding_drift)
severity  : HIGH
status    : FAIL
```

The check evaluates whether the cosine distance between current text embeddings and the stored baseline (in `schema_snapshots/baselines.json`) exceeds the contractual threshold of 0.15. A score of 0.9534 represents a **near-total semantic shift** — the extracted text content has moved to a completely different region of the embedding space.

This is a violation that traditional schema validators cannot detect: the field type is still `string`, the format is still valid, but the **semantic contract** — that extracted facts remain topically coherent with the baseline — is broken.

### 2.2 Lineage Traversal

The Data Contract Enforcer ran a 4-step attribution pipeline against this violation:

```
Step 1 — Registry Blast Radius Query
  Query: contract_registry/subscriptions.yaml for breaking_fields containing extracted_facts[].text
  Result: week3-document-refinery-extractions → week7-ai-contract-extension
          breaking_reason: "Text content is embedded for semantic drift detection.
                           Structural changes shift the embedding centroid and may
                           falsely trigger drift alerts."

Step 2 — Lineage BFS Enrichment
  Starting node : week3-document-refinery-extractions
  BFS traversal : week3 → week7-ai-contract-extension (depth = 1)
  Contamination : 1 direct consumer, 0 further downstream hops confirmed in graph

Step 3 — Git Blame Attribution
  Target        : outputs/week3/extractions.jsonl
  Result        : No single commit identified as root cause.
                  The drift is a gradual distribution shift across many records,
                  not a single-record format violation traceable to one commit.
                  Attribution: undetermined (requires investigation of extraction model
                  version changes or input document set changes)

Step 4 — Violation Log Write
  violation_id : 5692f759-471e-40f6-9202-d2fcd224acdb
  Written to   : violation_log/violations.jsonl
```

**Why blame could not be fully resolved:**  
Embedding drift is a statistical violation, not a point violation. There is no single commit that "introduced" the bad record — the entire distribution of `extracted_facts[*].text` values has shifted. The most likely causes are: (a) a change in the upstream extraction model (from one Claude checkpoint to another), (b) a change in the input document corpus, or (c) a change in the text chunking or fact-extraction prompt. All three would shift the embedding centroid without changing the field type or format.

### 2.3 Blast Radius

| Dimension | Value |
|-----------|-------|
| Registry subscribers (direct) | `week7-ai-contract-extension` |
| Contamination depth | 1 hop |
| Validation mode | AUDIT (violation is logged, pipeline not blocked) |
| Estimated records affected | All `extracted_facts[*].text` values in outputs/week3/extractions.jsonl (200 sampled) |
| Blast radius source | `registry` |

**Subscriber detail:**

| Subscriber | Team | Mode | Breaking Reason |
|------------|------|------|-----------------|
| `week7-ai-contract-extension` | week7-team | AUDIT | Text content is embedded for semantic drift detection. Structural changes shift the embedding centroid and trigger false drift alerts. |

**Impact assessment:** Because the subscription is in `AUDIT` mode, the pipeline continues to run. However, all embedding drift baselines stored in `schema_snapshots/baselines.json` are now stale, and any future drift comparisons will measure against a corrupted baseline — meaning the problem silently compounds over time.

---

## Section 3 — AI Contract Extension Results

`contracts/ai_extensions.py` implements four AI-specific contract checks that extend beyond what standard schema validators can enforce. Results from the most recent run (2026-04-02T19:32:30Z):

### 3.1 Embedding Drift

| Parameter | Value |
|-----------|-------|
| Algorithm | Cosine distance between mean of 200 sampled embeddings and stored centroid |
| Sample size | 200 records |
| Baseline stored at | `schema_snapshots/baselines.json` |
| **Drift score** | **1.0170** |
| **Threshold** | **0.15** |
| **Status** | **FAIL** |
| Margin exceeded by | 6.78× the threshold |

> **Triggered: FAIL**

A score of 1.0170 on a cosine distance scale [0, 2] means the current text embedding centroid is nearly orthogonal to the baseline — the content has shifted as far semantically as it is possible to shift while still being in the same embedding space. This is a categorical data distribution change, not noise.

**Violation logged:** `ai_extensions.embedding_drift` — HIGH severity.

### 3.2 Prompt Input Validation

| Parameter | Value |
|-----------|-------|
| Records checked | 60 |
| Valid | 60 |
| Invalid | 0 |
| **Violation rate** | **0.0000 (0.00%)** |
| Quarantine path | None |
| **Status** | **PASS** |

> **No WARN or FAIL triggered.**

All 60 prompt input records conform to the prompt schema contract — required fields present, no malformed structures, no injection patterns detected.

### 3.3 LLM Output Schema Validation

| Parameter | Value |
|-----------|-------|
| Contract validated against | `week2-digital-courtroom` (verdict records) |
| Total outputs checked | 50 |
| Schema violations | 0 |
| **Violation rate** | **0.0000 (0.00%)** |
| Baseline violation rate | 0.0000 |
| Trend | stable |
| **Status** | **PASS** |

> **No WARN or FAIL triggered.**

All 50 LLM-generated verdict records conform to the Bitol contract schema — `overall_verdict` is within the `{PASS, FAIL, WARN}` enum, `scores` are integers in range [1, 5], and `confidence` is a float in [0.0, 1.0].

### 3.4 Trace Schema Validation (LangSmith)

| Parameter | Value |
|-----------|-------|
| Traces checked | 50 |
| `run_type` violations | 0 (all within `{llm, chain, tool, retriever, embedding}`) |
| Token count mismatches | 0 (`total_tokens = prompt_tokens + completion_tokens` holds for all) |
| **Status** | **PASS** |

> **No WARN or FAIL triggered.**

### 3.5 Summary

| Check | Status | Triggered |
|-------|--------|-----------|
| Embedding Drift (drift=1.0170, threshold=0.15) | **FAIL** | **YES — HIGH violation logged** |
| Prompt Input Validation (0/60 invalid) | PASS | No |
| LLM Output Schema (0/50 violations, stable trend) | PASS | No |
| Trace Schema (0 run_type, 0 token mismatches) | PASS | No |
| **Overall AI Status** | **AMBER** | |

The single open signal is the embedding drift. All structured schema checks are clean.

---

## Section 4 — Schema Evolution Case Study

### 4.1 Context

The `SchemaEvolutionAnalyzer` diffs consecutive schema snapshots stored in `schema_snapshots/week3-document-refinery-extractions/` to detect breaking changes before they reach downstream consumers. This case study uses the confirmed breaking change from 2026-03-31.

### 4.2 The Snapshots Compared

| | Snapshot A (Baseline) | Snapshot B (Breaking) |
|---|---|---|
| File | `20260331_224716.yaml` | `20260331_225113_breaking.yaml` |
| Captured | 2026-03-31T22:47:16Z | 2026-03-31T22:51:13Z |
| Contract | `week3-document-refinery-extractions` | same |

### 4.3 The Diff

```
Field         : processing_time_ms
Change type   : range_tightened
Old constraint: minimum = 1,     maximum = None  (unbounded above)
New constraint: minimum = 1000,  maximum = 60000
```

In plain English: the previous contract allowed any positive integer millisecond value (minimum 1 ms). The new snapshot tightens this to a range of 1,000 ms – 60,000 ms, meaning any extraction completing in under one second (which many fast extractions do) would now **fail validation**.

### 4.4 Compatibility Verdict

```
compatibility_verdict : BACKWARD_INCOMPATIBLE
breaking_changes      : 1
compatible_changes    : 0
change_type taxonomy  : range_tightened  (from Confluent Schema Evolution Taxonomy)
risk_level            : HIGH
```

From the 11-type Schema Evolution Taxonomy implemented in `contracts/schema_analyzer.py`:

| Change Type | Definition | Backward Compatible? |
|-------------|------------|---------------------|
| `range_widened` | Constraint relaxed — producers gain more valid values | ✅ Yes |
| **`range_tightened`** | **Constraint narrowed — existing producers may produce values now invalid** | **❌ No** |

`range_tightened` is backward incompatible because existing producers that were writing valid data (e.g., `processing_time_ms = 250`) will now produce **FAIL** results without any code change on their end. The contract moved under them.

### 4.5 Auto-Generated Migration Impact Report

```
BREAKING: Field 'processing_time_ms' range tightened
          (min=1, max=None → min=1000, max=60000)

Migration Checklist:
  [ ] range_tightened on 'processing_time_ms': Tighter range may break
      existing producers. Migration plan required.
  [ ] Run full validation suite on all downstream consumers
  [ ] Update blast radius report and notify affected teams
  [ ] Tag release with BREAKING_CHANGE label

Rollback Plan:
  1. Revert the producer commit identified in the blame chain.
  2. Re-run ContractGenerator to restore previous schema snapshot.
  3. Re-run ValidationRunner to confirm baseline is restored.
  4. Notify all downstream consumers that rollback is complete.

Blast Radius Note:
  Run contracts/attributor.py with the identified FAIL check_ids
  to generate a full blast radius report.
```

### 4.6 Resolution

A subsequent snapshot (`20260402_184117.yaml`) shows `range_widened` — the range was restored to `min=1, max=None`, making the change backward compatible again. The full compatibility verdict for that transition is `FULL_COMPATIBLE`. This demonstrates the SchemaEvolutionAnalyzer's ability to detect both the breaking introduction and the safe rollback.

---

## Section 5 — What Would Break Next

### 5.1 Highest-Risk Interface: `week3-document-refinery-extractions → week4-brownfield-cartographer` on `extracted_facts[].confidence`

Of all seven registered inter-system interfaces in the contract registry, this is the single interface most likely to **fail silently in production**.

### 5.2 Why This Interface

**The contract clause at risk:**

```yaml
# generated_contracts/week3_extractions.yaml, lines 51–56
confidence:
  type: number
  minimum: 0.0
  maximum: 1.0
  required: true
  description: BREAKING CHANGE if scale changed to 0-100
```

**The registry subscription (ENFORCE mode):**

```yaml
contract_id  : week3-document-refinery-extractions
subscriber_id: week4-brownfield-cartographer
validation_mode: ENFORCE
breaking_fields:
  - field: extracted_facts[].confidence
    reason: "Used for lineage node confidence weighting and ranking.
             Scale change from 0.0–1.0 to 0–100 silently corrupts all
             threshold checks (e.g., nodes with confidence 87 pass a
             threshold of 0.5 instead of failing it)."
```

### 5.3 Why It Fails Silently

This is the most dangerous class of data contract violation: a **type-preserving scale change**.

If an extraction model starts returning confidence as a percentage (0–100) instead of a fraction (0.0–1.0):

1. **The field is still a number.** Type validation passes.
2. **The value is still within JSON schema constraints** — if Week 3's schema is ever updated to remove the `maximum: 1.0` clause, range validation also passes.
3. **Week 4 receives the data without error.** No exception is raised. No pipeline alert fires.
4. **The lineage graph is silently corrupted.** Every node with `confidence = 87` passes a threshold filter of `> 0.5` (it should have been `0.87`, which also passes — but a node with confidence `12` should have failed the filter at `0.12`, and instead reads as `12.0` and passes massively).
5. **Blame attribution becomes impossible.** Because no validation check failed at ingest time, there is no violation record, no timestamp, no commit to blame. By the time the corruption is noticed downstream (if ever), hundreds of lineage graphs will have been built on wrong confidence weights.

### 5.4 Why It Is More Dangerous Than the Embedding Drift

The currently open embedding drift violation (Section 2) **was caught** — it triggered a FAIL, a violation record was written, and a recommended action was generated. The system worked.

The confidence scale inversion would **not be caught** by the existing checks under one realistic scenario: if the Week 3 contract's `maximum: 1.0` constraint is removed (or was never present on a new field variant), and the Week 4 consumer does not independently validate the range before using the value as a threshold weight. The data would flow through all validation layers and corrupt the lineage graph silently.

### 5.5 The Signal That Is Already Present

The embedding drift score of **1.0170** on `extracted_facts[*].text` tells us that the Week 3 Document Refinery pipeline is **actively changing** — its output distribution has shifted significantly. A pipeline in active flux is more likely to introduce a confidence scale change as a side effect of a model upgrade or prompt change. The risk is not theoretical; the precursor signal is already in the violation log.

### 5.6 Recommended Pre-emptive Action

1. Add an explicit range check to the Week 4 contract (`week4_lineage_snapshots.yaml`) that validates incoming `confidence` values are `≤ 1.0` before accepting them into the lineage graph.
2. Escalate the `week3 → week4` subscription from `ENFORCE` to a monitored alert: any new Week 3 snapshot where the `confidence` column's observed max exceeds `1.0` should block the pipeline immediately.
3. Investigate and resolve the embedding drift (Section 2) — the same pipeline change that caused the text distribution to shift may be the precursor to a confidence scale change.

---

## Appendix — Data Sources and Contract Coverage

| Dataset | Records | Contract | Checks | Pass Rate |
|---------|---------|----------|--------|-----------|
| Week 1 — Intent Records | ~100 | `week1_intent_records.yaml` | 21 | 100% |
| Week 2 — Verdict Records | ~100 | `week2_verdicts.yaml` | 49 | 100% |
| Week 3 — Extraction Records | 200 | `week3_extractions.yaml` | 41 | 100% |
| Week 4 — Lineage Snapshots | ~50 | `week4_lineage_snapshots.yaml` | 27 | 100% |
| Week 5 — Event Records | ~500 | `week5_events.yaml` | 52 | 100% |
| LangSmith — Trace Records | 50 | `langsmith_runs.yaml` | 76 | 100% |
| **Total** | | **6 contracts** | **266** | **100%** |

## Appendix — Contract Registry (7 Subscriptions)

| Producer | Consumer | Mode | Breaking Fields |
|----------|----------|------|-----------------|
| week1-intent-code-correlator | week2-digital-courtroom | ENFORCE | `code_refs`, `intent_id` |
| week3-document-refinery-extractions | week4-brownfield-cartographer | ENFORCE | `extracted_facts[].confidence`, `doc_id`, `entities[].type` |
| week3-document-refinery-extractions | week7-ai-contract-extension | AUDIT | `extracted_facts[].confidence`, `extracted_facts[].text` |
| week4-brownfield-cartographer | week7-violation-attributor | ENFORCE | `nodes`, `edges`, `nodes[].node_id`, `git_commit` |
| week5-event-sourcing-platform | week7-schema-contract | ENFORCE | `event_type`, `payload`, `sequence_number`, `recorded_at` |
| langsmith-traces | week7-ai-contract-extension | AUDIT | `run_type`, `total_tokens`, `start_time` |
| week2-digital-courtroom | week7-ai-contract-extension | ENFORCE | `overall_verdict`, `scores`, `confidence` |

---

*Report generated: 2026-04-02 | Data Contract Enforcer v1.0.0 | Bitol Open Data Contract Standard v3.0.0 | Tier 1 Trust Boundary*
