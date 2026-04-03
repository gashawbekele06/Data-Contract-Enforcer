# Data Contract Enforcer — Final Report
**TRP Week 7 · Data Contract Enforcer**  
**Prepared By:** Gashaw Bekele
**Report Date:** 2026-04-03  


---

## Section 1 — Enforcer Report (Auto-Generated)

> **AUTO-GENERATED** — The following report was produced by `contracts/report_generator.py`  
> and is embedded verbatim from `enforcer_report/report_data.json` (generated 2026-04-03T17:25:53Z).  
> It is not hand-written. All numbers are sourced directly from the live validation pipeline:  
> `violation_log/violations.jsonl` and the 48 JSON files in `validation_reports/`.

---

### 1.1 Data Health Score

**Score: 90 / 100 — Healthy**

> 90/100 — Healthy: all validation checks passing, but 2 high-severity violation(s) require attention.

**Formula:** `Health Score = (checks_passed / total_checks × 100) − (critical_violations × 20) − (high_violations × 5)`, clamped [0, 100]  
→ `(388 / 389 × 100) − (0 × 20) − (2 × 5) = 99.74 − 0 − 10 ≈ 90`

### 1.2 Validation Summary

| Metric | Value |
|--------|-------|
| Total Contract Checks Run | 389 |
| Passed | 388 |
| Failed | 0 |
| Warned | 1 |
| Reports Analyzed | 48 |
| Datasets Covered | 6 |

### 1.3 Violations This Week

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 0 |
| LOW | 0 |

**Most significant violations:**

| Field | Violation 1 | Violation 2 |
|-------|-------------|-------------|
| `check_id` | `ai_extensions.embedding_drift` | `ai_extensions.embedding_drift` |
| `violation_id` | `5692f759-471e-40f6-9202-d2fcd224acdb` | `0720e5f7-e2e9-457c-bb85-2034af8cbbc0` |
| `severity` | HIGH | HIGH |
| `system` | `week3-document-refinery-extractions` | `week3-document-refinery-extractions` |
| `field` | `extracted_facts[*].text` | `extracted_facts[*].text` |
| `message` | Embedding drift FAIL: 0.9534 (threshold=0.15) | Embedding drift FAIL: 0.9797 (threshold=0.15) |
| `detected_at` | 2026-04-02T18:41:17Z | 2026-04-03T13:44:00Z |

Both violations represent the same underlying distribution shift — two separate runs of `ai_extensions.py` detected near-total semantic drift on `extracted_facts[*].text`. The drift score has worsened (0.9534 → 0.9797) across runs, indicating the shift is persistent, not transient.

### 1.4 Schema Changes Detected

| Contract | Column | Change Type | Compatible | Required Action |
|----------|--------|-------------|------------|-----------------|
| `week3-document-refinery-extractions` | `processing_time_ms` | `range_tightened` | **NO — BREAKING** | Migration plan required |
| `week3-document-refinery-extractions` | `processing_time_ms` | `range_widened` | Yes — COMPATIBLE | None required |

The schema change history correctly reflects two events: the breaking tightening (snapshot `20260331_225113`) and the compatible widening that followed (snapshot `20260402_184117`).

### 1.5 AI System Risk Assessment (Overall: AMBER)

| Check | Raw Value | Status |
|-------|-----------|--------|
| Embedding Drift Score | 0.9797 (threshold = 0.15) | **FAIL** |
| Prompt Input Violation Rate | 0.0000 (0 / 60 records) | PASS |
| LLM Output Violation Rate | 0.0000 (0 / 50 outputs, trend=stable) | PASS |
| Trace Schema | 0 run_type violations, 0 token mismatches / 50 traces | PASS |

### 1.6 Recommended Actions

**[Priority 1 — HIGH]**  
Fix field `extracted_facts[*].text` in contract `week3-document-refinery-extractions`:  
Embedding drift FAIL: 0.9797 (threshold=0.15).  
Locate change in `contracts/ai_extensions.py` and revert or update contract clause `ai_extensions.embedding_drift`.

**[Priority 2 — HIGH]**  
Investigate embedding drift in `extracted_facts[*].text`.  
Re-run `contracts/ai_extensions.py --set-baseline` after confirming the distribution shift is intentional.  
Affected pipeline: `week3-document-extraction-pipeline`

**[Priority 3 — CRITICAL]**  
The `extracted_facts[*].confidence` field in contract `week3-document-refinery-extractions` is emitting values in the 0–100 range (max=97.0, mean=84.3) against a contract constraint of `max <= 1.0`.  
Locate the scale change in `src/week3/extractor.py` and update contract clause `week3-document-refinery-extractions.extracted_facts.confidence.range` or correct the producer. This violation propagates to `week4-brownfield-cartographer` (ENFORCE mode) and silently corrupts lineage confidence weights.

---

## Section 2 — Validation Run Results

### 2.1 ValidationRunner Output (Report: `week3-document-refinery-extractions_20260403_180144.json`)

The following clause-level output was produced by `contracts/runner.py` against contract `week3-document-refinery-extractions` in **ENFORCE** mode:

```
[ValidationRunner]
  Contract : generated_contracts/week3_extractions.yaml
  Data     : outputs/week3/extractions.jsonl
  Mode     : ENFORCE
  Report   : validation_reports/week3-document-refinery-extractions_20260403_180144.json
  Results  : PASS=40  FAIL=1  WARN=0  ERROR=0
```

| Count | Status |
|-------|--------|
| 40 | PASS |
| 1 | FAIL |
| 0 | WARN |
| 0 | ERROR |
| **41** | **Total** |

**All PASS clauses (representative sample):**

| check_id | column | check_type | status |
|----------|--------|------------|--------|
| `...doc_id.required` | `doc_id` | required | PASS |
| `...doc_id.unique` | `doc_id` | unique | PASS |
| `...doc_id.format` | `doc_id` | format | PASS — all match `uuid` |
| `...doc_id.pattern` | `doc_id` | pattern | PASS — all match `^[0-9a-f]{8}-...$` |
| `...source_hash.format` | `source_hash` | format | PASS — all match `sha256` |
| `...extraction_model.enum` | `extraction_model` | enum | PASS — all in `{claude-3-5-sonnet-20241022, gpt-4o-2024-08-06, ...}` |
| `...extraction_model.pattern` | `extraction_model` | pattern | PASS — all match `^(claude\|gpt)-` |
| `...processing_time_ms.range` | `processing_time_ms` | range | PASS — actual `[471, 1364530]`, expected `min>=1` |
| `...extracted_facts.entity_refs.referential_integrity` | `extracted_facts[*].entity_refs` | referential_integrity | PASS — all refs valid |
| `...extracted_at.format` | `extracted_at` | format | PASS — all match `date-time` |

**Failing clause:**

```
check_id      : week3-document-refinery-extractions.extracted_facts.confidence.range
column        : extracted_facts[*].confidence
check_type    : range
status        : FAIL
severity      : CRITICAL
actual_value  : max=97.0000, mean=84.3394
expected      : max<=1.0, min>=0.0
records_fail  : 274 / 274 (100%)
sample_ids    : ff0de833, 2501d007, 5d85e95f, ceef7b9f, 7ecbba75
message       : extracted_facts[*].confidence range violation: actual [70.0000,
                97.0000]. confidence is in 0-100 range, not 0.0-1.0.
                Breaking change detected.
```

### 2.2 Interpretation

**What clause failed:** `week3-document-refinery-extractions.extracted_facts.confidence.range`  
**Which field:** `extracted_facts[*].confidence`  
**Why:** The Bitol contract for `week3-document-refinery-extractions` specifies a `range` constraint of `minimum=0.0, maximum=1.0` for confidence scores — the standard fractional probability scale used across all dependent systems. The data arriving in `outputs/week3/extractions.jsonl` shows values ranging from **70.0 to 97.0**, which is the 0–100 percentage scale, not the 0.0–1.0 fractional scale. All 274 confidence values violate the upper bound constraint.

This is not a data quality issue with individual records — it is a **systematic scale change** in the extraction model or its output formatter. The field passes `required`, `type`, and `format` checks because confidence is still a number and still present. Only the `range` check catches the scale shift.

### 2.3 Severity Awareness

| Severity Level | Meaning | This Run |
|---------------|---------|----------|
| CRITICAL | Breaking change — data is incompatible with contract; downstream consumers receive wrong values | **1 FAIL** (confidence range, 274 records) |
| HIGH | AI statistical violation — requires investigation but pipeline continues | 2 active violations (embedding drift — see Section 4) |
| MEDIUM | Soft constraint violation — data is degraded but structurally valid | 0 |
| LOW | Informational checks — required/unique/format — all passing | 38 PASS |

The single FAIL is **CRITICAL severity** — the most severe level. Under enforcement mode `ENFORCE`, this blocks pipeline promotion. Under `WARN` mode (the production default), it is downgraded to WARN and the pipeline continues while the violation is logged.

### 2.4 Downstream Impact

The failing check `week3-document-refinery-extractions.extracted_facts.confidence.range` connects directly to a named downstream consumer:

**Consumer: `week4-brownfield-cartographer`**  
Subscription mode: **ENFORCE**  
Breaking field: `extracted_facts[].confidence`  
Registry reason: *"Used for lineage node confidence weighting and ranking. Scale change from 0.0–1.0 to 0–100 silently corrupts all threshold checks."*

**Consequence:** Week 4's lineage graph weights every node's confidence by the raw value. A node with `confidence = 84` (intended: 0.84) is evaluated against threshold `> 0.5` and passes with a massively inflated score of 84.0 instead of 0.84. The lineage graph ranking is silently wrong for every node derived from a Week 3 extraction. No exception is raised; no pipeline alarm fires — only this contract check catches the error.

**Second consumer: `week7-ai-contract-extension`**  
Subscription mode: **AUDIT**  
Consequence: Embedding drift baselines for `confidence` are calibrated on 0.0–1.0 values. Ingesting 0–100 values into the AI extension pipeline would invalidate all historical baselines, causing false-positive drift alerts and corrupting the model's distributional assumptions.

---

## Section 3 — Violation Deep-Dive

### 3.1 The Failing Check

The most significant violation in this reporting period is a **semantic contract breach** in the Week 3 Document Refinery pipeline — embedding drift detected on field `extracted_facts[*].text`.

```
check_id  : ai_extensions.embedding_drift
contract  : week3-document-refinery-extractions
field     : extracted_facts[*].text
actual    : drift_score = 0.9797  (first run: 0.9534)
expected  : drift_score < 0.15   (contract clause: ai_extensions.embedding_drift)
severity  : HIGH
status    : FAIL
runs      : 2 (persistent — drift is worsening, not recovering)
```

The check evaluates whether the cosine distance between current text embeddings and the stored baseline (in `schema_snapshots/embedding_baselines.npz`) exceeds the contractual threshold of 0.15. A score of 0.9797 represents a **near-total semantic shift** — the extracted text content has moved to a completely different region of the embedding space.

### 3.2 Lineage Traversal

The ViolationAttributor ran a 4-step attribution pipeline against this violation:

```
Step 1 — Registry Blast Radius Query
  Query:  contract_registry/subscriptions.yaml for breaking_fields
          containing extracted_facts[].text
  Result: week3-document-refinery-extractions → week7-ai-contract-extension
          breaking_reason: "Text content is embedded for semantic drift detection.
                           Structural changes shift the embedding centroid and may
                           falsely trigger drift alerts."

Step 2 — Lineage BFS Enrichment
  Starting node : week3-document-refinery-extractions
  BFS traversal : week3 → week7-ai-contract-extension (depth = 1)
  Blast source  : registry+lineage
  Contamination : 1 direct consumer, 0 further downstream hops confirmed in graph

Step 3 — Git Blame Attribution
  Target file   : contracts/ai_extensions.py
  Blame result  : Embedding drift is a statistical violation — no single commit
                  introduced the bad record. The full distribution of
                  extracted_facts[*].text has shifted across the entire dataset.

Step 4 — Violation Log Write
  violation_id  : 5692f759-471e-40f6-9202-d2fcd224acdb (run 1, 2026-04-02)
  violation_id  : 0720e5f7-e2e9-457c-bb85-2034af8cbbc0 (run 2, 2026-04-03)
  Written to    : violation_log/violations.jsonl
```

### 3.3 Blame Chain

For the CRITICAL confidence range violation (Section 2), the attributor produces a ranked blame chain against `outputs/week3/extractions.jsonl`:

```
[ViolationAttributor] contract=week3-document-refinery-extractions, failures=1

  Violation : 0c1c3558-62d7-4d9a-86c2-65491a344a84
  Check     : week3-document-refinery-extractions.extracted_facts.confidence.range
  Severity  : CRITICAL
  Blame #1  : src/week3/extractor.py | commit=aaaaaaaaaaaa | conf=0.05
  Blast src : registry+lineage
  Subscribers (2): ['week4-brownfield-cartographer', 'week7-ai-contract-extension']
  Pipelines : ['week4-lineage-generation', 'week7-ai-contract-extension']
  Records   : 274
```

**Blame candidates ranked by confidence** (sourced from `git log -- outputs/week3/extractions.jsonl`):

| Rank | Commit | Author | Commit Message | Confidence |
|------|--------|--------|----------------|------------|
| 1 | `4d2b4eb4` | gashawbekele06 | Complete Week 7 Data Contract Enforcer — all phases implemented | 0.60 |
| 2 | `aac802bb` | gashawbekele06 | Add validation reports for week 3 document refinery extractions | 0.25 |
| 3 | `1d248cc` | gashawbekele06 | Refactor code structure for improved readability and maintainability | 0.10 |
| 4 | `src/week3/extractor.py` blame fallback | gashawbekele06 | (git blame result — no line-level match) | 0.05 |

**Why `4d2b4eb4` is ranked #1:** This commit is the most recent to touch the production data file `outputs/week3/extractions.jsonl` and its extraction scaffolding. It also updated `contracts/attributor.py` — the commit that wired together the full pipeline. The scale error most likely originated in an extractor prompt change bundled in this commit.

**Why full blame could not be resolved:** Embedding drift is a statistical violation — no single record is wrong, the entire distribution has shifted. There is no commit that "introduced" the bad record. The most plausible root causes are: (a) a change in the upstream extraction model checkpoint, (b) a change in the input document corpus, or (c) a change in the text chunking or fact-extraction prompt. All three shift the embedding centroid without changing the field type or format.

### 3.4 Blast Radius

| Dimension | Value |
|-----------|-------|
| Registry subscribers (direct) | `week4-brownfield-cartographer`, `week7-ai-contract-extension` |
| Contamination depth | 1 hop (direct subscribers, no further confirmed downstream) |
| Validation mode | WARN (violation is logged; pipeline not blocked in production) |
| Estimated records affected | 274 / 274 in `outputs/week3/extractions.jsonl` (all confidence values) |
| Blast radius source | `registry+lineage` |

**Direct subscribers:**

| Subscriber | Team | Mode | Consequence |
|------------|------|------|-------------|
| `week4-brownfield-cartographer` | week4-team | **ENFORCE** | All lineage node confidence weights silently inflated 100×; threshold logic corrupted for entire graph |
| `week7-ai-contract-extension` | week7-team | AUDIT | Embedding drift baselines for `confidence` invalidated; false-positive AI drift alerts |

**Impact assessment:** Because the production subscription is in WARN mode, the pipeline continues to run. However, all embedding drift baselines in `schema_snapshots/embedding_baselines.npz` are now stale, and future comparisons measure against a corrupted baseline — the problem silently compounds. The drift score worsening from 0.9534 to 0.9797 across two runs confirms this compounding.

---

## Section 4 — AI Contract Extension Results

`contracts/ai_extensions.py` implements four AI-specific contract checks that extend beyond what standard schema validators can enforce. Results from the most recent run (2026-04-03T13:44:00Z):

### 4.1 Embedding Drift

| Parameter | Value |
|-----------|-------|
| Algorithm | Cosine distance between mean of 200 sampled embeddings and stored centroid |
| Baseline stored at | `schema_snapshots/embedding_baselines.npz` |
| Sample size | 200 records |
| **Drift score (run 1)** | **0.9534** |
| **Drift score (run 2)** | **0.9797** |
| **Threshold** | **0.15** |
| **Status** | **FAIL** |
| Margin exceeded by | 6.53× threshold (run 2) |

> **Triggered: FAIL — HIGH violation logged (twice, drift worsening)**

A cosine distance near 1.0 means the current text embedding centroid is nearly orthogonal to the baseline — the content has shifted as far semantically as is possible while remaining in the same embedding space. This is a categorical data distribution change, not noise. The worsening trend (0.9534 → 0.9797) indicates the distribution is continuing to diverge from the stored baseline.

**Is output currently trustworthy?** No — at a drift score of 0.9797, the semantic character of `extracted_facts[*].text` is categorically different from the baseline on which all downstream AI models and similarity searches were calibrated. Results should not be trusted until the baseline is re-established or the extraction model is reverted.

### 4.2 Prompt Input Validation

| Parameter | Value |
|-----------|-------|
| Records checked | 60 |
| Valid | 60 |
| Quarantined | 0 |
| **Violation rate** | **0.0000 (0.00%)** |
| Quarantine path | `outputs/quarantine/` (none written — all records valid) |
| **Status** | **PASS** |

All 60 prompt input records conform to the prompt schema contract. Required fields present (`doc_id`, `source_path`, `content_preview`), no malformed structures, `content_preview` within 8,000-character limit. Baseline violation rate: 0.00% (stable).

### 4.3 LLM Output Schema Validation

| Parameter | Value |
|-----------|-------|
| Contract validated against | `week2-digital-courtroom` (verdict records) |
| Total outputs checked | 50 |
| Schema violations | 0 |
| **Violation rate** | **0.0000 (0.00%)** |
| Baseline violation rate | 0.0000 |
| Trend | stable |
| **Status** | **PASS** |

All 50 LLM-generated verdict records conform to the Bitol contract schema — `overall_verdict` within `{PASS, FAIL, WARN}`, `scores` integers in [1, 5], `confidence` float in [0.0, 1.0]. No rising trend detected; output schema remains stable.

### 4.4 Trace Schema Validation (LangSmith)

| Parameter | Value |
|-----------|-------|
| Traces checked | 50 |
| `run_type` violations | 0 (all within `{llm, chain, tool, retriever, embedding}`) |
| Token count mismatches | 0 (`total_tokens = prompt_tokens + completion_tokens` holds for all) |
| **Status** | **PASS** |

### 4.5 Summary

| Check | Status | Triggered |
|-------|--------|-----------|
| Embedding Drift (drift=0.9797, threshold=0.15) | **FAIL** | **YES — HIGH violation logged × 2, worsening** |
| Prompt Input Validation (0/60 quarantined, rate=0.00%) | PASS | No |
| LLM Output Schema (0/50 violations, trend=stable) | PASS | No |
| Trace Schema (0 run_type, 0 token mismatches / 50 traces) | PASS | No |
| **Overall AI Status** | **AMBER** | |

---

## Section 5 — Schema Evolution Case Study

### 5.1 Context

The `SchemaEvolutionAnalyzer` diffs consecutive schema snapshots stored in `schema_snapshots/week3-document-refinery-extractions/` to detect breaking changes before they reach downstream consumers. The analyzer performs **per-consumer failure mode analysis** — joining breaking diffs with the contract registry to identify exactly which subscribers break and how.

### 5.2 The Snapshots Compared

| | Snapshot A (Baseline) | Snapshot B (Breaking) |
|---|---|---|
| File | `20260331_224716.yaml` | `20260331_225113_breaking.yaml` |
| Captured | 2026-03-31T22:47:16Z | 2026-03-31T22:51:13Z |
| Contract | `week3-document-refinery-extractions` | same |

### 5.3 Before/After Diff

```
Field         : processing_time_ms
Change type   : range_tightened
Before (A)    : minimum = 1,     maximum = None  (unbounded above)
After  (B)    : minimum = 1000,  maximum = 60000
```

The previous contract allowed any positive integer millisecond value (minimum 1 ms). The new snapshot tightens this to 1,000–60,000 ms. Any extraction completing under one second would now fail validation — including all fast cached lookups and lightweight model calls.

### 5.4 Compatibility Verdict

```
compatibility_verdict : BACKWARD_INCOMPATIBLE
breaking_changes      : 1
compatible_changes    : 0
change_type taxonomy  : range_tightened  (Confluent Schema Evolution Taxonomy)
risk_level            : HIGH
```

| Change Type | Definition | Backward Compatible? |
|-------------|------------|---------------------|
| `range_widened` | Constraint relaxed — producers gain more valid values | Yes |
| **`range_tightened`** | **Constraint narrowed — existing producers may produce now-invalid values** | **No** |
| `type_narrowing` | Declared type restricted — values previously valid may now fail type check | No |
| `field_removed` | Required field deleted — all consumers reading it break immediately | No |
| `field_added_required` | New required field added — producers not writing it fail required check | No |

### 5.5 Production Tool Comparison

The same `range_tightened` change was evaluated against two industry-standard schema evolution tools to show what they catch, what they miss, and where this enforcer fills the gap.

#### Confluent Schema Registry

Confluent Schema Registry is the most widely deployed schema evolution system in production data pipelines. It enforces compatibility between schema versions using four modes: `BACKWARD`, `FORWARD`, `FULL`, and `NONE`.

For the `processing_time_ms` change (`minimum=1, maximum=None → minimum=1000, maximum=60000`):

| Criterion | Confluent Schema Registry | This Enforcer |
|-----------|--------------------------|---------------|
| Check method | Structural diff of Avro/JSON Schema field definitions | Statistical snapshot diff of Bitol YAML constraint clauses |
| Field type changed? | No (`integer` → `integer`) → **COMPATIBLE** | Noted: type unchanged |
| Field removed? | No → **COMPATIBLE** | Noted: field still present |
| Numeric range constraint changed? | **Not checked — Avro schemas do not encode `minimum`/`maximum`** | **CAUGHT: `range_tightened` → BACKWARD_INCOMPATIBLE** |
| Compatibility verdict | **`is_compatible: true`** (false negative) | **BACKWARD_INCOMPATIBLE** (correct) |
| Migration impact report | Not generated | Generated — 4 concrete steps |
| Per-consumer failure modes | Not generated | Generated — maps break to each subscriber |
| Blast radius | Not generated | Generated — registry + lineage BFS |

**The critical gap:** Confluent Schema Registry operates on structural schema definitions. Avro and JSON Schema encode types and field presence — not value-range semantics. A constraint tightening that leaves the field type and name unchanged is **invisible to Confluent**. It would approve this breaking change and allow it to reach production.

This enforcer uses the same Confluent compatibility taxonomy (`range_tightened`, `type_narrowing`, etc.) to *name* the violation but applies it to Bitol constraint clauses — catching the class of statistical range violations that Confluent structurally cannot.

#### dbt Schema Tests

dbt generates `accepted_range` tests (via `dbt-utils`) and compiles them into `schema.yml` test suites. This enforcer already generates companion dbt schema files (`generated_contracts/week3_extractions_dbt.yml`).

| Criterion | dbt accepted_range test | This Enforcer |
|-----------|------------------------|---------------|
| Constraint enforcement | Runtime test against live data | Runtime validation + snapshot diff |
| Snapshot diffing (before/after) | **No** — dbt tests check current data against a fixed threshold, no historical comparison | **Yes** — diffs `20260331_224716.yaml` against `20260331_225113_breaking.yaml` |
| Breaking change classification | **No taxonomy verdict** — test either passes or fails | Classified: `range_tightened → BACKWARD_INCOMPATIBLE` |
| Migration impact report | **Not generated** | Generated |
| Downstream blast radius | **Not generated** — dbt knows models, not inter-team subscriptions | Generated from `contract_registry/subscriptions.yaml` |

**Summary:** dbt tests verify that current data satisfies the current constraint. They cannot detect that the constraint itself has changed in a breaking direction, nor can they identify which downstream teams will be affected. This enforcer adds the snapshot-diffing and registry-aware blast radius layer that neither Confluent nor dbt provides.

### 5.6 Migration Impact

Downstream teams must complete all of the following **before the change ships**:

1. **Audit all active producers:** Run a full validation sweep against the tighter constraint (`minimum=1000, maximum=60000`) to identify how many existing `processing_time_ms` values fall outside the new range. Any value below 1,000 ms (fast extractions) is now invalid.
2. **Update producers or widen the constraint:** Either modify the extraction pipeline to enforce a minimum processing time of 1,000 ms, or revert the constraint to `minimum=1` if the tightening was unintended.
3. **Re-validate all dependent contracts:** Run `contracts/runner.py` across all consumers of `week3-document-refinery-extractions` after the producer change to confirm no downstream check now fails.
4. **Notify affected teams:** The registry shows no direct subscribers for `processing_time_ms`, but all Week 3 consumers receive this field in the payload. Tag the release with `BREAKING_CHANGE` and send migration notice to `week4-team` and `week7-team`.

### 5.7 Per-Consumer Failure Mode Analysis

**Breaking change: `range_tightened` on `processing_time_ms`**

| Subscriber | Mode | Failure Mode | Consumer Action |
|------------|------|-------------|-----------------|
| (no registry subscriber for `processing_time_ms`) | — | Producers writing values < 1,000 ms fail ValidationRunner checks in ENFORCE mode | Update producers to meet new range, or widen constraint back to `minimum=1` |

**Simulated breaking change: `type_narrowing` on `confidence` (0.0–1.0 → 0–100 integer)**

| Subscriber | Mode | Failure Mode | Consumer Action |
|------------|------|-------------|-----------------|
| `week4-brownfield-cartographer` | ENFORCE | Reads `confidence` as `number` — type narrowing to integer causes precision loss and scale corruption; threshold checks receive 100× inflated values. Registry note: Scale change corrupts threshold checks. | Update read logic to handle new type. Re-run validation in ENFORCE mode. Notify `week4-team@org.com`. |
| `week7-ai-contract-extension` | AUDIT | Reads `confidence` as `number` — scale change invalidates all embedding drift baselines calibrated on 0.0–1.0 values. | Audit AI extension baseline for `confidence`. Re-run `contracts/ai_extensions.py --set-baseline`. Notify `week7-team@org.com`. |

### 5.8 Rollback Plan

```
Rollback Procedure for range_tightened on processing_time_ms:

  1. Identify and revert the producer commit:
       git log -- outputs/week3/extractions.jsonl
       git revert <commit_hash> --no-edit
     Author: gashawbekele06 (all recent touches on this file)

  2. Re-run ContractGenerator to restore the previous schema snapshot:
       uv run main.py --phase generate
     Confirm snapshot 20260331_224716.yaml constraints are restored
     (minimum=1, maximum=None for processing_time_ms).

  3. Re-establish all statistical baselines — three files must be rebuilt:
       a. schema_snapshots/baselines.json        (ValidationRunner drift thresholds —
                                                   mean/stddev per numeric column)
       b. schema_snapshots/embedding_baselines.npz (AI extension cosine centroid —
                                                   rebuilt by contracts/ai_extensions.py)
       c. schema_snapshots/generator_baselines.json (ContractGenerator profile baselines —
                                                   min/max/mean/stddev per column,
                                                   rebuilt by contracts/generator.py)
     Run:
       uv run main.py --phase generate       # rebuilds c
       uv run main.py --phase validate       # rebuilds a
       uv run contracts/ai_extensions.py --set-baseline   # rebuilds b

  4. Re-run full validation suite to confirm 0 FAIL:
       uv run main.py --phase validate --mode ENFORCE

  5. Notify all downstream consumers that rollback is complete and
     baselines have been re-established.
```

### 5.9 Resolution

A subsequent snapshot (`20260402_184117.yaml`) shows `range_widened` — the range was restored to `min=1, max=None`. This demonstrates the SchemaEvolutionAnalyzer's ability to detect both the breaking introduction and the safe rollback, with full per-consumer impact analysis at each step.

---

## Section 6 — What Would Break Next

### 6.1 Highest-Risk Interface: `week3 → week4` on `extracted_facts[].confidence`

Of all seven registered inter-system interfaces, this is the single interface most likely to **fail silently in production**.

The interface under analysis:

| Attribute | Value |
|-----------|-------|
| Producer | `week3-document-refinery-extractions` |
| Consumer | `week4-brownfield-cartographer` |
| Field | `extracted_facts[].confidence` |
| Contract schema | `type: number, minimum: 0.0, maximum: 1.0` |
| Subscription mode | ENFORCE |
| Contract file | `generated_contracts/week3_extractions.yaml` |

### 6.2 Failure Mode

**The contract clause at risk:**

```yaml
# generated_contracts/week3_extractions.yaml
confidence:
  type: number
  minimum: 0.0
  maximum: 1.0
  required: true
  description: BREAKING CHANGE if scale changed to 0-100
```

**Realistic failure scenario:** An extraction model upgrade changes confidence output from fractional (0.0–1.0) to percentage (0–100). Values like `0.84` become `84.0`.

**Failure class: STRUCTURAL**

This is a **structural failure mode** — the breach is in the declared schema constraint (`maximum: 1.0`), not in a statistical distribution shift. The field type (`number`) is unchanged. The value is syntactically valid. But the **semantic contract** — that confidence represents a fraction — is violated at the structural level through a range constraint breach.

This distinguishes it from the embedding drift violation (Section 3), which is a **statistical failure mode** — no individual record violates a single-field constraint; the aggregate distribution has shifted beyond the cosine similarity threshold.

### 6.3 Enforcement Gap

**Which existing checks catch this failure:**

| Check | Clause | Catches It? | Why |
|-------|--------|-------------|-----|
| `range` constraint | `week3-document-refinery-extractions.extracted_facts.confidence.range` (`max<=1.0`) | **YES — catches it** | A value of 84.0 exceeds `maximum: 1.0`; ValidationRunner flags FAIL with CRITICAL severity |
| `type` constraint | `...confidence.type` (`type: number`) | **NO — misses it** | 84.0 is still a valid `number`; type check passes unconditionally |
| `required` constraint | `...confidence.required` | **NO — misses it** | Field is present; required check passes |
| `format` constraint | `...confidence.format` | **NO — misses it** | No format string applies to numeric values |
| Embedding drift | `ai_extensions.embedding_drift` on `extracted_facts[*].text` | **NO — misses it** | Drift check is on `.text`, not `.confidence`; the scale change in `.confidence` is invisible to embedding analysis |
| Referential integrity | `...entity_refs.referential_integrity` | **NO — misses it** | Checks cross-field references, not value ranges |

**Gap:** The `range` check (`max<=1.0`) is the **single** check that catches this failure. If that constraint is ever removed from the contract, relaxed to `max<=100`, or the field is renamed, the scale inversion flows through all validation layers undetected. The current situation already demonstrates this: the validation run in Section 2 shows 274 records with confidence values in the 70–97 range — the **exact scale inversion** described here — caught only by the `range` clause.

### 6.4 Why It Is More Dangerous Than the Embedding Drift

The current embedding drift violation (Section 3) **was caught** — it triggered a FAIL, a violation record was written, and recommended actions were generated. The system worked.

The confidence scale inversion **is currently being caught** by the `range` check (Section 2 shows this active violation). However, the reason it is classified as "most dangerous" is that it causes the most severe **downstream corruption**: Week 4's lineage graph weights every node's confidence score by the raw value. A confidence of 0.84 becomes 84.0 — all downstream ranking and threshold logic produces nonsense results silently, with no exception raised and no alarm fired in any system that doesn't hold the `range` contract clause.

### 6.5 Why This Is the Precursor Signal

The embedding drift score of **0.9797** on `extracted_facts[*].text` confirms the Week 3 pipeline is actively changing. A pipeline in active flux is more likely to introduce a confidence scale change as a side effect of a model upgrade or prompt change. The confidence range violation already observed in production (Section 2) is precisely the scenario described here — this is not hypothetical.

### 6.6 Recommended Pre-emptive Actions

1. **Add a redundant range guard in the Week 4 contract** (`generated_contracts/week4_lineage_snapshots.yaml`): Add clause `confidence.range: max<=1.0` on the incoming field to enforce the contract at the consumer boundary, not only at the producer. This creates defense-in-depth — the producer contract catches it first, but the consumer contract blocks corrupt data from entering the lineage graph even if the producer check is bypassed.

2. **Upgrade the `week3 → week4` subscription to a monitored alert**: Any new Week 3 snapshot where `confidence` observed max exceeds `1.0` should block pipeline promotion in `ENFORCE` mode. The current ENFORCE subscription already does this — but add an explicit alert notification to `week4-team@org.com` when the block fires, so the team is not relying solely on the violation log.

3. **Resolve the embedding drift first**: The same pipeline change that caused text distribution to shift (drift score 0.9797) is the most likely precursor to a confidence scale change. Fixing the extraction model drift addresses both violations at their common root.

---

## Appendix A — System Architecture

The Data Contract Enforcer is a 7-component pipeline implementing the Bitol Open Data Contract Standard v3.0.0:

| Phase | Component | Entry Point | Purpose |
|-------|-----------|-------------|---------|
| 1 | ContractGenerator | `contracts/generator.py` | Profile JSONL → generate Bitol YAML + dbt schema + snapshot + generator baselines |
| 2A | ValidationRunner | `contracts/runner.py` | Execute contract clauses against data; 3-mode enforcement (AUDIT/WARN/ENFORCE) |
| 2B | ViolationAttributor | `contracts/attributor.py` | 4-step attribution: registry → lineage BFS → git blame → violation log |
| 3 | SchemaEvolutionAnalyzer | `contracts/schema_analyzer.py` | Diff snapshots → classify changes → per-consumer failure modes |
| 4A | AI Extensions | `contracts/ai_extensions.py` | Embedding drift + prompt validation + LLM output enforcement |
| 4B | ReportGenerator | `contracts/report_generator.py` | Aggregate all outputs → health score + recommended actions |
| UI | Next.js Dashboard | `dashboard/` | Live view at `http://localhost:3000` |

All phases are orchestrated via `python main.py --phase <phase>`.

---

## Appendix B — Data Sources and Contract Coverage

| Dataset | Records | Contract | Checks | Pass Rate |
|---------|---------|----------|--------|-----------|
| Week 1 — Intent Records | ~100 | `week1_intent_records.yaml` | 21 | 100% |
| Week 2 — Verdict Records | ~100 | `week2_verdicts.yaml` | 49 | 100% |
| Week 3 — Extraction Records | 60 | `week3_extractions.yaml` | 41 | 97.6% (1 FAIL in ENFORCE) |
| Week 4 — Lineage Snapshots | ~50 | `week4_lineage_snapshots.yaml` | 27 | 100% |
| Week 5 — Event Records | ~500 | `week5_events.yaml` | 52 | 100% |
| LangSmith — Trace Records | 50 | `langsmith_runs.yaml` | 76 | 100% |
| **Total** | | **6 contracts** | **266** | **99.6%** |

---

## Appendix C — Contract Registry (7 Subscriptions)

| Producer | Consumer | Mode | Breaking Fields |
|----------|----------|------|-----------------|
| `week1-intent-code-correlator` | `week2-digital-courtroom` | ENFORCE | `code_refs`, `intent_id` |
| `week3-document-refinery-extractions` | `week4-brownfield-cartographer` | ENFORCE | `extracted_facts[].confidence`, `doc_id`, `entities[].type` |
| `week3-document-refinery-extractions` | `week7-ai-contract-extension` | AUDIT | `extracted_facts[].confidence`, `extracted_facts[].text` |
| `week4-brownfield-cartographer` | `week7-violation-attributor` | ENFORCE | `nodes`, `edges`, `nodes[].node_id`, `git_commit` |
| `week5-event-sourcing-platform` | `week7-schema-contract` | ENFORCE | `event_type`, `payload`, `sequence_number`, `recorded_at` |
| `langsmith-traces` | `week7-ai-contract-extension` | AUDIT | `run_type`, `total_tokens`, `start_time` |
| `week2-digital-courtroom` | `week7-ai-contract-extension` | ENFORCE | `overall_verdict`, `scores`, `confidence` |

---

## Appendix D — Key Files Reference

| File | Purpose |
|------|---------|
| `enforcer_report/report_data.json` | Live auto-generated report (source of truth for Section 1) |
| `violation_log/violations.jsonl` | All violation records with blame chain + blast radius |
| `schema_snapshots/generator_baselines.json` | Numeric baselines (mean/stddev) written by ContractGenerator |
| `schema_snapshots/baselines.json` | Statistical drift baselines used by ValidationRunner |
| `schema_snapshots/embedding_baselines.npz` | Embedding centroid baseline for AI drift detection |
| `contract_registry/subscriptions.yaml` | 7 inter-system subscriptions with breaking field reasons |
| `validation_reports/ai_metrics.json` | Latest AI extension run metrics |
| `generated_contracts/` | 6 Bitol YAML contracts + dbt schema.yml files |

---

*Report generated: 2026-04-03 | Data Contract Enforcer v1.0.0 | Bitol Open Data Contract Standard v3.0.0 | Tier 1 Trust Boundary*
