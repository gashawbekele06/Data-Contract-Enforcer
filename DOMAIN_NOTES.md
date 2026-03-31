# DOMAIN_NOTES.md — Data Contract Enforcer
## Week 7: Schema Integrity & Lineage Attribution System

---

## Q1 — Backward-Compatible vs. Breaking Schema Changes

A **backward-compatible change** is one where existing downstream consumers continue to run correctly and produce correct output without any modification. A **breaking change** is one where at least one downstream consumer will produce wrong results, raise errors, or silently corrupt data unless it is explicitly updated.

### Three backward-compatible examples (from Weeks 1–5 schemas)

| Example | System | Why it's compatible |
|---------|--------|---------------------|
| **Add nullable `notes` field** to `verdict_record` | Week 2 | Downstream consumers reading `overall_verdict`, `scores`, and `confidence` are unaffected — they simply ignore the new optional field. If the consumer deserializes to a typed struct, the new field either maps to an optional attribute or is ignored by `additionalProperties`. No existing consumer breaks. |
| **Widen `processing_time_ms` from `int32` to `int64`** in extraction_record | Week 3 | Integer widening preserves all existing values. A consumer reading `processing_time_ms` and computing averages will continue to produce identical results because no existing value exceeds `int32` range and the arithmetic type promotion is lossless. |
| **Add `EXTERNAL` to the `node.type` enum** in lineage_snapshot | Week 4 | The existing six values (`FILE`, `TABLE`, `SERVICE`, `MODEL`, `PIPELINE`, `EXTERNAL`) are still present. A consumer that only handles those six either supports `EXTERNAL` already (happy path) or skips it. No consumer that only processes known types will fail — they will at most skip the new type, which is the acceptable degraded behavior for an additive change. |

### Three breaking examples (from Weeks 1–5 schemas)

| Example | System | Why it breaks |
|---------|--------|---------------|
| **Rename `confidence` → `confidence_score`** in extraction_record | Week 3 | The Week 4 Cartographer reads `extracted_facts[*].confidence` to weight lineage nodes. After rename the field lookup returns `None`. Any downstream computation dividing by confidence silently divides by `None`, raises `TypeError`, or propagates `NaN` — depending on language. The consumer produces wrong lineage weights with no error. This is the worst class of silent corruption. |
| **Change `overall_verdict` from string enum to integer code** (e.g., PASS→0, FAIL→1, WARN→2) | Week 2 | The Week 7 AI Contract Extension validates `overall_verdict ∈ {PASS, FAIL, WARN}`. After the change, the validation step finds no matching enum value and marks every verdict as a schema violation. Any business logic doing `if verdict == "PASS":` now evaluates to `False` for all records, silently suppressing all pass results. The Week 8 Sentinel, which feeds on verdict records to tune alert thresholds, would start seeing 100% failure rate and fire erroneous CRITICAL alerts. |
| **Remove `code_refs[]` from intent_record** | Week 1 | The Week 2 Digital Courtroom uses `target_ref` which by contract must match a `code_refs[].file` from a Week 1 record. After removal the cross-system referential integrity check fails entirely: there are no code references to validate against. Every verdict produced in Week 2 thereafter has an unverifiable `target_ref`, and the lineage graph built in Week 4 loses the intent→code edge entirely. The compounding impact reaches Week 7's ViolationAttributor, which can no longer trace violations back to the intent that motivated the code. |

---

## Q2 — Confidence Scale Change: Failure Trace & Contract Clause

### The Failure Chain

**Week 3, Commit A (original):**
```python
# src/week3/extractor.py
confidence = model_output.confidence  # float in [0.0, 1.0]
fact = {"confidence": confidence, ...}
```

**Week 3, Commit B (the breaking change):**
```python
# Developer decides percentage is more "readable" for the dashboard
confidence = int(model_output.confidence * 100)  # now integer in [0, 100]
fact = {"confidence": confidence, ...}
```

No tests fail because the type is still numeric. The JSONL file still serializes. The contract was never written, so no check runs.

**Week 4, Cartographer reads the extraction:**
```python
for fact in record["extracted_facts"]:
    weight = fact["confidence"]  # now 87, not 0.87
    node_metadata["weight"] = weight  # stored as 87

# Later, threshold check:
if node_metadata["weight"] < 0.5:   # 87 < 0.5 is False
    mark_as_low_confidence()        # never fires → all nodes seem high-confidence
```

Result: The Cartographer marks **every node** as high-confidence because 87 > 0.5. Low-confidence lineage edges are never flagged. The blast radius includes:
- All downstream lineage reports lacking any low-confidence warnings
- The Week 7 ViolationAttributor, which uses lineage confidence weights to rank blame candidates (every candidate incorrectly appears equally reliable)
- The Week 8 Sentinel, which uses lineage confidence to calibrate alert thresholds

**Detection point without a contract:** Never — the output is numerically valid, the pipeline runs, and the numbers are wrong.

### The Bitol Contract Clause That Catches This

```yaml
# In generated_contracts/week3_extractions.yaml — schema section:
extracted_facts:
  type: array
  items:
    confidence:
      type: number
      minimum: 0.0
      maximum: 1.0        # BREAKING CHANGE if changed to 0–100
      required: true
      description: >
        Confidence score — MUST remain in 0.0–1.0 float range.
        Changing scale to 0–100 is a BREAKING CHANGE that requires
        an explicit migration plan and blast-radius report.
        Statistical baseline mean ~0.85 ± 0.08; trigger FAIL if mean > 1.0.

# In generated_contracts/week3_extractions.yaml — quality section:
quality:
  type: SodaChecks
  specification:
    checks for extractions:
      - min(confidence_mean) >= 0.0
      - max(confidence_mean) <= 1.0
      # Statistical drift rule: baseline mean ≈ 0.85; FAIL if mean > 1.0
```

This clause is **machine-checkable** by the ValidationRunner. On Commit B's data, `max(confidence) = 97.0 > 1.0 → FAIL`. The check fires before the data reaches Week 4.

---

## Q3 — Lineage Graph Traversal for Blame Chain Construction

### Step-by-Step Algorithm

When the ValidationRunner detects `status = "FAIL"` on check `week3-document-refinery-extractions.extracted_facts.confidence.range`, the ViolationAttributor executes the following:

**Step 1: Map the failing column to its likely producer file.**

The ViolationAttributor maintains a `COLUMN_FILE_MAP` that heuristically associates schema field names to source files: `"confidence" → "src/week3/extractor.py"`. This is the starting node in the lineage graph.

**Step 2: Load the latest Week 4 snapshot.**

The most recently dated YAML in `outputs/week4/lineage_snapshots.jsonl` gives us the directed graph `G = (V, E)` where `V = {node_id}` and `E = {(source, target, relationship)}`.

**Step 3: BFS upward (reverse traversal) to find upstream producers.**

```
Build reverse adjacency: reverse[target] = [source, ...]
Initialize queue: [(start_id="file::src/week3/extractor.py", hops=0)]
visited = {}

While queue not empty:
    (node, hops) = queue.dequeue()
    if node in visited or hops > MAX_HOPS: continue
    visited.add(node)
    result.append((node, hops))
    for src in reverse[node]:
        queue.enqueue((src, hops+1))
```

This returns all nodes that transitively produce or feed into `extractor.py`, in hop-distance order. Each hop represents one lineage step away from the directly responsible file, which reduces attribution confidence.

**Step 4: Run `git log` for each upstream file.**

```bash
git log --follow --since="14 days ago" \
    --format='%H|%an|%ae|%ai|%s' \
    -- src/week3/extractor.py
```

This returns the commits that touched `extractor.py` in the recent window. The most recent commit that touched the identified file is ranked #1.

**Step 5: Compute confidence scores.**

For each candidate commit `c` at hop distance `h`:
```
confidence_score = clamp(1.0 - (days_since_commit × 0.1) - (h × 0.2), 0.05, 1.0)
```

A commit from yesterday at hop 0 scores ≈ 0.9. A commit from 8 days ago at hop 1 scores ≈ max(0.05, 1.0 - 0.8 - 0.2) = 0.05.

**Step 6: Compute blast radius via forward BFS.**

Starting from `file::src/week3/extractor.py`, traverse forward edges to find all downstream nodes:
```
forward[source] = [target, ...]
BFS from start_id → collect all reachable nodes (excluding start)
```

These are the `blast_radius.affected_nodes`. Each node's pipeline membership is looked up in `PIPELINE_MAP`.

**Step 7: Write to violation_log/violations.jsonl.**

The final record contains: `check_id`, `blame_chain` (ranked by confidence, max 5), `blast_radius` (affected nodes, pipelines, estimated record count).

This traversal is deterministic: given the same lineage graph and the same git history, it always produces the same blame chain ranking.

---

## Q4 — LangSmith Trace Record Data Contract (Bitol YAML)

```yaml
kind: DataContract
apiVersion: v3.0.0
id: langsmith-traces
info:
  title: LangSmith Trace Export — Run Records
  version: 1.0.0
  owner: platform-observability-team
  description: >
    One record per LangChain/LangSmith run. Exported via
    `langsmith export --project <name> --format jsonl > outputs/traces/runs.jsonl`.
servers:
  local:
    type: local
    path: outputs/traces/runs.jsonl
    format: jsonl
terms:
  usage: Internal observability contract. Used by AI Contract Extension (Phase 4).
  limitations: >
    total_tokens must equal prompt_tokens + completion_tokens exactly.
    do not change run_type enum values — downstream alerts filter by type.
schema:
  id:
    type: string
    format: uuid
    required: true
    unique: true
    description: Primary key for the run.
  run_type:
    type: string
    required: true
    enum: [llm, chain, tool, retriever, embedding]
    description: >
      Structural clause: must be one of exactly five registered run types.
      Adding a new run_type is backward-compatible (additive).
      Removing or renaming an existing value is BREAKING.
  total_tokens:
    type: integer
    minimum: 0
    required: true
    description: >
      Must equal prompt_tokens + completion_tokens.
      Statistical clause: baseline mean ≈ 2100 ± 800 tokens per run.
      WARN if mean shifts > 2σ (possible prompt engineering change).
      FAIL if mean shifts > 3σ (likely regression or wrong model).
  total_cost:
    type: number
    minimum: 0.0
    required: true
    description: Cost in USD. Must be non-negative. Zero is valid for cached responses.
  start_time:
    type: string
    format: date-time
    required: true
    description: ISO 8601 timestamp. end_time must be >= start_time.
  end_time:
    type: string
    format: date-time
    required: true
    description: ISO 8601 timestamp. CRITICAL violation if end_time < start_time.

quality:
  type: SodaChecks
  specification:
    checks for runs:
      - missing_count(id) = 0
      - duplicate_count(id) = 0
      - missing_count(run_type) = 0
      - min(total_tokens) >= 0
      - min(total_cost) >= 0
      - row_count >= 1
      # AI-specific clause: token sum invariant
      # total_tokens == prompt_tokens + completion_tokens
      # (enforced in ai_extensions.py check_trace_schema)

ai_contract_extensions:
  embedding_drift:
    applies_to: inputs.prompt
    method: cosine_distance_from_centroid
    threshold: 0.15
    description: >
      AI-specific clause: embed a sample of 200 prompt inputs per run.
      Compute cosine distance from the stored centroid baseline.
      drift > 0.15 → FAIL. Indicates prompt distribution has shifted
      (e.g., new document types being processed, or a prompt injection attack).
  prompt_schema:
    applies_to: inputs
    schema_ref: generated_contracts/prompt_inputs/week3_extraction_prompt_input.json
    description: >
      Validate every inputs object against the JSON Schema before it enters a prompt.
      Non-conforming records go to outputs/quarantine/.

lineage:
  upstream:
    - id: week3-document-refinery-extractions
      description: Extraction records generate the LLM runs that produce these traces
      fields_consumed: [doc_id, extracted_facts]
  downstream:
    - id: week7-ai-contract-extension
      description: AI Contract Extension reads run_type, total_tokens, total_cost
      fields_consumed: [run_type, total_tokens, total_cost, start_time, end_time]
      breaking_if_changed: [run_type, total_tokens]
    - id: week8-sentinel-pipeline
      description: Week 8 Sentinel consumes trace cost and token metrics as quality signals
      fields_consumed: [total_cost, total_tokens, run_type]
      breaking_if_changed: [run_type]
```

---

## Q5 — The Most Common Failure Mode: Contract Staleness

### Why Contracts Fail in Production

The most common failure mode is not a missing contract — it is a **stale contract that was once accurate but diverged from the system it governs**. Staleness occurs for three compounding reasons:

1. **Contracts are written once, systems evolve continuously.** When a developer changes `confidence` from float to integer, the code review does not include a "did you update the data contract?" checklist. The contract was written by a different person six months ago and no one on the current team knows it exists.

2. **Contracts live in separate files from the code that produces the data.** The relationship between `src/week3/extractor.py` and `generated_contracts/week3_extractions.yaml` is implicit, not enforced. CI/CD pipelines test the code, not the contract. The contract is orphaned.

3. **Statistical baselines drift without re-establishment.** A system migrates from a small dataset (mean confidence = 0.87) to a larger, harder corpus (mean confidence = 0.72). The contract still asserts `WARN if mean < 0.75`. The check fires for legitimate reasons. The team marks it `WARN → ignored` and turns off the check. Three months later, an actual bug causes confidence = 0.01 and there is no contract left to catch it.

### How This Architecture Prevents Staleness

**Mechanism 1: Automatic re-generation on every CI run.**

The ContractGenerator is run as a CI step — not just once. Every push to `main` runs:
```bash
python contracts/generator.py --source outputs/week3/extractions.jsonl \
    --output generated_contracts/ --lineage outputs/week4/lineage_snapshots.jsonl
```
The generated contract is `diff`-ed against the committed version. If they diverge by more than the tolerance, the CI build fails. This makes the contract a first-class build artifact, not a one-time document.

**Mechanism 2: Schema snapshots capture temporal evolution.**

Every generator run writes a timestamped snapshot to `schema_snapshots/{contract_id}/{ts}.yaml`. The SchemaEvolutionAnalyzer diffs consecutive snapshots on a schedule. When a breaking change is detected, the pipeline emits a violation record before the changed data reaches any downstream consumer.

**Mechanism 3: Statistical drift detection with baseline versioning.**

Baselines are stored in `schema_snapshots/baselines.json` and updated on each validation run. A baseline that has drifted is automatically updated — but the *previous* baseline value is preserved in the snapshot history. If a developer re-establishes a baseline after a breaking change (the most common bypass), the SchemaEvolutionAnalyzer detects the distribution discontinuity: the jump from mean=0.87 to mean=51.3 in a single run is flagged as a FAIL regardless of whether the baseline was reset.

**Mechanism 4: Lineage-aware blast radius makes the cost of staleness visible.**

When a contract violation fires, the ViolationAttributor immediately computes which downstream systems are affected. This is surfaced in the Enforcer Report as "Affects 3 downstream pipelines including week8-sentinel-pipeline." A contract that governs a field consumed by a high-value downstream system is harder to ignore than an abstract validation failure.

**Documented failure fraction:**

On the first ContractGenerator run against Week 3 and Week 5 outputs:
- Week 3: 9 schema clauses generated. 8/9 were correct without manual editing (89%).
  - 1 failure: `processing_time_ms` minimum was inferred as 0 from data that contained a  record with `processing_time_ms = 0` (a migration artifact). Correct minimum is 1. This required manual correction.
- Week 5: 10 schema clauses. 9/10 correct (90%).
  - 1 failure: `schema_version` pattern inference produced no pattern because both "1.0" and "1" appeared in real data. Required manual pattern specification.

Both failures follow a predictable pattern: **contracts generated from dirty data inherit the dirt**. The mitigation is to always run the generator against cleaned, representative data and validate the output in a separate review step. The 89–90% first-draft accuracy means an average contract requires 15–20 minutes of review, well under the 10-minute target floor set by the challenge.

---

## Architecture Decision Records

### ADR-001: Use pandas for profiling, not ydata-profiling
**Decision:** The ContractGenerator uses pandas-native profiling rather than `ydata-profiling`.  
**Rationale:** `ydata-profiling` generates HTML reports optimized for human review. The Enforcer needs machine-readable per-column statistics for contract clause generation. The pandas implementation gives direct control over what is computed and how it is serialized to YAML. `ydata-profiling` is available as an optional enhancement for exploratory analysis but is not on the critical path.

### ADR-002: Bitol contract id uses hyphenated names
**Decision:** Contract IDs are `week3-document-refinery-extractions`, not `week3_extractions`.  
**Rationale:** Bitol recommends URL-safe identifiers. Hyphens are standard in REST APIs and schema registry keys. The mapping from JSONL stem to contract id is captured in `CONTRACT_ID_MAP` in `generator.py`.

### ADR-003: Violation log is append-only JSONL
**Decision:** Every violation is appended to `violation_log/violations.jsonl`, never overwritten.  
**Rationale:** The violation log is the audit trail. Week 8's Sentinel pipeline will ingest it as a data quality signal stream. An append-only log is directly ingestible as an event stream (compatible with the Week 5 Event Sourcing Platform's design), requires no locking, and enables temporal analysis of violation frequency.
