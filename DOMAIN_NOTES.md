# DOMAIN_NOTES.md — Data Contract Enforcer
**Week 7 · TRP**

---

## Question 1 — Backward-Compatible vs Breaking Schema Changes

A **backward-compatible** change is one where existing consumers continue to work without modification. A **breaking** change forces downstream consumers to update their code before they can process the new data.

### Backward-Compatible Examples (from Weeks 1–5)

1. **Add a nullable column** — Adding `canonical_value: null` to the `entities[]` array in the Week 3 extraction record (`outputs/week3/extractions.jsonl`). Downstream consumers that don't read `canonical_value` are unaffected. The Week 4 Cartographer, which only reads `doc_id` and `extracted_facts`, continues without change.

2. **Widen an enum** — Adding `"EXTERNAL"` to the `node.type` enum in the Week 4 lineage snapshot (`outputs/week4/lineage_snapshots.jsonl`). The enum previously allowed `FILE|TABLE|SERVICE|MODEL|PIPELINE`. Adding a new valid value is additive — existing consumers that handle the known six values simply encounter an unknown enum value on unknown nodes and can ignore or log it without crashing.

3. **Widen a numeric type** — Changing `edge.confidence` in the Week 4 lineage snapshot from `float32` to `float64`. Consumers reading confidence as a float continue to work; they receive higher-precision values. The Week 7 ViolationAttributor reads confidence as a Python `float`, which is already 64-bit — no change required.

### Breaking Examples (from Weeks 1–5)

1. **Confidence scale change** — Changing `extracted_facts[*].confidence` in Week 3 from `float 0.0–1.0` to `integer 0–100`. This is the canonical example this project enforces. The Week 4 Cartographer uses confidence values to weight lineage node rankings. A value of `87` interpreted as a fraction passes a `> 0.5` threshold that `0.87` would also pass — but only by accident, and only for high values. Values like `12` (meaning 12% confidence) would fail a `> 0.5` threshold that `0.12` should correctly fail. Silent corruption.

2. **Rename a required column** — Renaming `fact_id` to `id` inside `extracted_facts[]` in the Week 3 extraction record. Any consumer that reads `extracted_facts[*].fact_id` receives `None` or a KeyError. The Week 7 ValidationRunner's `unique` check on `fact_id` immediately returns `ERROR` status (column not found) and the violation is logged. Without a contract, this surfaces as a downstream null-pointer failure hours later.

3. **Remove a required field** — Removing `sequence_number` from the Week 5 event record (`outputs/week5/events.jsonl`). The Week 7 ValidationRunner enforces that `sequence_number` is a monotonically increasing integer per `aggregate_id`. Removing it causes all ValidationRunner checks on this column to return `ERROR`. Any consumer that uses `sequence_number` to reconstruct aggregate state (replaying events in order) loses that guarantee silently.

---

## Question 2 — Confidence Scale Failure: Trace & Contract Clause

### Failure Trace

**Change:** Week 3 Document Refinery updates `extracted_facts[*].confidence` from `float 0.0–1.0` to `integer 0–100`.

**Step 1 — Week 3 output written.** `outputs/week3/extractions.jsonl` now contains records where confidence values range from 70 to 97 (representing 70%–97%). Structurally, these are still valid JSON numbers. No type error is thrown.

**Step 2 — Week 4 Cartographer reads the data.** The Cartographer loads `extracted_facts` from extraction records and uses `confidence` to weight lineage node metadata. A node with `confidence=87` is treated as having 8,700% confidence — far above the 0.0–1.0 threshold used to filter low-quality nodes.

**Step 3 — Cartographer filtering logic breaks silently.** Any threshold check of the form `if confidence > 0.5: include_in_graph()` now passes for all facts (87 > 0.5 is true, just as 0.87 > 0.5 is true). The graph appears valid. Output is produced. No exception is raised.

**Step 4 — Downstream graph quality degrades.** Low-confidence facts (e.g., `confidence=12`, meaning 12%) are included in the lineage graph because `12 > 0.5` is true. The Cartographer's graph becomes noisy — it includes speculative facts as if they were high-confidence ones.

**Step 5 — Root cause is undetectable from the graph alone.** The Week 7 ViolationAttributor, operating on the lineage graph, sees the graph structure is intact. Only the statistical distribution of confidence values betrays the change.

### Bitol Contract Clause That Catches This

```yaml
schema:
  extracted_facts:
    type: array
    items:
      confidence:
        type: number
        minimum: 0.0
        maximum: 1.0          # BREAKING CHANGE if changed to 0–100
        required: true
        description: >
          Extraction confidence as a float fraction.
          BREAKING CHANGE if scale is changed to integer 0–100.
          Any mean > 5.0 on this column indicates a scale violation.
```

The `maximum: 1.0` clause is enforced by the ValidationRunner's `range` check. It compares `actual_max` against `1.0` and emits `status: FAIL, severity: CRITICAL` if the observed maximum exceeds 1.0.

---

## Question 3 — Lineage Graph → Blame Chain: Step-by-Step

When the ValidationRunner raises a `FAIL` on `extracted_facts[*].confidence.range`, the ViolationAttributor is invoked. It runs in four steps:

**Step 1 — Registry blast radius query.**
Load `contract_registry/subscriptions.yaml`. Find all subscriptions where `contract_id == "week3-document-refinery-extractions"` and `breaking_fields` contains a field that matches `confidence`. This returns the authoritative subscriber list — in this case, `week4-brownfield-cartographer` (ENFORCE mode) and `week7-ai-contract-extension` (AUDIT mode). These are the Tier 1 blast-radius nodes.

**Step 2 — Lineage graph BFS for contamination depth.**
Load the latest snapshot from `outputs/week4/lineage_snapshots.jsonl`. Build a forward-edge adjacency list from the `edges[]` array. Starting from `file::src/week3/extractor.py` (the file that produces `confidence`), run breadth-first search. For each registry subscriber, compute the shortest-path hop count from the producer node to a node matching the subscriber ID. This enriches each subscriber with a `contamination_depth` value.

**Step 3 — Git blame for cause attribution.**
For each upstream file identified in Step 2, run:
```
git log --follow --since="14 days ago" --format="%H|%an|%ae|%ai|%s" -- {file_path}
```
Rank commits by a confidence score formula: `base = 1.0 - (days_since_commit × 0.1)`, reduced by `0.2` per lineage hop. Up to 5 candidates are returned, ranked by score descending. The top candidate is the most likely cause.

**Step 4 — Violation record written.**
The full violation record — including blame chain, blast radius, registry subscribers, and contamination depths — is appended to `violation_log/violations.jsonl` in a schema designed for direct ingestion by the Week 8 Sentinel alert pipeline.

**Graph traversal specifics:** The BFS in Step 2 uses a reverse-edge adjacency list (`edge.target → edge.source`) to traverse *upstream* from the failing column's producing node. The forward-edge traversal in Step 2's contamination depth computation uses the standard direction (`edge.source → edge.target`) to find how far downstream contamination can propagate.

---

## Question 4 — LangSmith Trace Record Data Contract

```yaml
kind: DataContract
apiVersion: v3.0.0
id: langsmith-traces
info:
  title: LangSmith Trace Records — Run Schema Contract
  version: 1.0.0
  owner: week7-team
  description: >
    One record per LangSmith run. Enforces structural, statistical,
    and AI-specific constraints on LLM trace data.
servers:
  local:
    type: local
    path: outputs/traces/runs.jsonl
    format: jsonl
schema:
  # Structural clauses
  id:
    type: string
    format: uuid
    required: true
    unique: true
    description: Run UUID. Primary key.
  run_type:
    type: string
    required: true
    enum: [llm, chain, tool, retriever, embedding]
    description: >
      STRUCTURAL: Must be one of the five registered run types.
      Any other value indicates a new run type not yet registered
      in the trace schema registry.
  start_time:
    type: string
    format: iso8601
    required: true
  end_time:
    type: string
    format: iso8601
    required: true
    description: Must be >= start_time. Enforced by cross-column check.
  total_tokens:
    type: integer
    minimum: 0
    required: true
    description: >
      STRUCTURAL: Must equal prompt_tokens + completion_tokens.
      Mismatch indicates a billing or instrumentation bug.
  total_cost:
    type: number
    minimum: 0.0
    required: true

  # Statistical clause
  prompt_tokens:
    type: integer
    minimum: 0
    description: >
      STATISTICAL: Baseline mean ~4200, stddev ~800 (from first 50 runs).
      A mean shift > 3 stddev indicates prompt template change or
      context window abuse. Triggers WARN at 2 stddev, FAIL at 3 stddev.

quality:
  type: SodaChecks
  specification:
    checks for runs:
      - missing_count(id) = 0
      - duplicate_count(id) = 0
      - invalid_count(run_type) = 0  # enum check
      - min(total_cost) >= 0
      - row_count >= 1

ai_extensions:
  # AI-specific clause: embedding drift on run inputs
  embedding_drift:
    field: inputs
    threshold: 0.15
    method: cosine_distance
    baseline_path: schema_snapshots/embedding_baselines.npz
    description: >
      AI-SPECIFIC: Detects distributional shift in LLM inputs.
      A drift score > 0.15 means the prompts being sent to the model
      have changed character — different topics, formats, or lengths —
      relative to the established baseline. Triggers FAIL and writes
      to violation_log/violations.jsonl.
```

---

## Question 5 — Contract Staleness: Root Cause & Prevention

### Most Common Failure Mode

The most common production failure mode is **contract drift**: the contract is written once, passes its first validation run, and is never updated again. Meanwhile, the data producer evolves — new fields are added, types are widened, enums gain values, statistical distributions shift — and the contract silently becomes descriptive rather than prescriptive. By the time a downstream consumer fails, the contract has been wrong for weeks.

### Why Contracts Get Stale

1. **Contracts are written by the producer team, validated by no one else.** The team that writes the contract is the same team that changes the schema. There is no external enforcer to flag when a change violates the contract.
2. **Schema changes are not surfaced as contract events.** A developer renames a column in a migration script. This is a git commit. No alerting system connects that commit to the contracts that cover that column.
3. **No feedback loop between contract failures and contract updates.** When a contract clause begins failing, the instinct is to fix the data, not review whether the contract itself needs versioning. Contracts accumulate technical debt.
4. **Contracts cover structure but not statistics.** A type-only contract misses the confidence `0.0–1.0` → `0–100` change entirely — the type is still `number`, the contract still passes, and the corruption is invisible.

### How This Architecture Prevents It

1. **ContractGenerator re-runs on every pipeline execution.** Every time the pipeline runs, it regenerates contracts from live data and writes a timestamped snapshot to `schema_snapshots/`. The SchemaEvolutionAnalyzer diffs consecutive snapshots automatically — schema changes surface as events, not surprises.
2. **Statistical baselines are stored and compared.** `schema_snapshots/baselines.json` stores the mean and stddev of every numeric column from the first validation run. Subsequent runs compare current statistics against stored baselines and emit WARNING at 2σ and FAIL at 3σ. The confidence scale change produces a mean shift from ~0.87 to ~84.3 — over 80 standard deviations. This is impossible to miss.
3. **The violation log feeds the Week 8 Sentinel.** Every violation record contains `signal_type`, `alert_priority`, `routing`, and `snapshot_ref` fields designed for direct ingestion by an alert pipeline. Violations are not silent — they are routed to the owning team within 30 minutes for CRITICAL/HIGH severity.
4. **Git blame connects schema changes to people.** When a contract violation is detected, the ViolationAttributor traces it to the specific commit. The feedback loop is: violation detected → commit identified → author notified. This makes contract breakage costly to ignore.

---

## Known Limitations & Reflection

### Limitation 1 — Mock Embedder Produces Orthogonal Vectors (drift = 1.0000)

The embedding drift check in `contracts/ai_extensions.py` uses synthetic random unit vectors when `OPENAI_API_KEY` is not set. Because the random vectors are generated fresh on each run with no fixed seed, the current-run centroid and the stored baseline centroid are uncorrelated pseudo-random vectors. Their cosine similarity approaches zero (vectors are nearly orthogonal in high-dimensional space), producing a drift score near 1.0 — the maximum after clamping.

**Consequence:** The embedding drift violation is real (the detection mechanism fires correctly, the violation is logged correctly, the blast radius is accurate) but the drift *score* is an artefact of the mock embedder rather than a genuine semantic shift in the extraction text. With a live `OPENAI_API_KEY`, real embeddings would produce a much more meaningful score.

**Fix for production:** Set `OPENAI_API_KEY` and run `uv run contracts/ai_extensions.py --set-baseline` once to store a real centroid baseline. Subsequent runs will compute real cosine drift.

### Limitation 2 — V2 Blame Points to Data File, Not Source Code Producer

The `violation_log/violations.jsonl` record for the embedding drift violation (`violation_id: 1e95bddf`) attributes the blame to `outputs/week3/extractions.jsonl` with commit `4d2b4eb4`. This is the data output file, not the source code that generated it (`src/week3/extractor.py`).

**Root cause:** The `COLUMN_FILE_MAP` in `contracts/attributor.py` maps `confidence` → `src/week3/extractor.py`, but `extracted_facts[*].text` is not in the map. The attributor's git blame fallback runs against `outputs/week3/extractions.jsonl` directly, finding the commit that last touched the output file rather than the producer. The lineage graph traversal (Step 2) would walk from `file::src/week3/extractor.py` to the output, but `_git_blame_chain` in `ai_extensions.py` skips the lineage traversal entirely and goes straight to git log.

**Fix for production:** Add `"text": "src/week3/extractor.py"` to `COLUMN_FILE_MAP` in `attributor.py`, and update `_git_blame_chain` in `ai_extensions.py` to consult the lineage graph before running git log, so it starts from the producing source file rather than the output file.
