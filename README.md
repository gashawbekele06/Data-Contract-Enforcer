# Data Contract Enforcer
### TRP Week 7 — Schema Integrity & Lineage Attribution System

A schema governance pipeline that generates formal data contracts for all five prior-week AI system outputs, validates them on every run, traces violations to the originating commit via a contract registry + lineage graph, detects schema drift between consecutive snapshots, enforces AI-specific constraints (embedding drift, prompt input, LLM output), and produces a stakeholder health report.

**Current system state:** 1224 checks · 1224 passed · 0 failed · **Health Score 100/100**

---

## Architecture

```
outputs/week1–5 + traces/
        │
        ▼
┌─────────────────────┐       schema_snapshots/
│  ContractGenerator  │ ────► {contract_id}/{timestamp}.yaml
│  generator.py       │       generated_contracts/*.yaml
│                     │       generated_contracts/*_dbt.yml
└────────┬────────────┘
         │ Bitol YAML contracts
         ▼
┌─────────────────────┐       validation_reports/*.json
│  ValidationRunner   │ ────► baselines.json (statistical drift)
│  runner.py          │
└────────┬────────────┘
         │ FAIL results
         ▼
┌─────────────────────┐  ◄── contract_registry/subscriptions.yaml  (Step 1)
│  ViolationAttributor│  ◄── outputs/week4/lineage_snapshots.jsonl  (Step 2)
│  attributor.py      │  ◄── git log / git blame                    (Step 3)
│                     │ ────► violation_log/violations.jsonl
└─────────────────────┘
         │
         ├──────────────────────────────────────────┐
         ▼                                          ▼
┌──────────────────────┐              ┌─────────────────────────┐
│ SchemaEvolution      │              │  AI Contract Extensions │
│ Analyzer             │              │  ai_extensions.py       │
│ schema_analyzer.py   │              │  • embedding drift      │
│                      │              │  • prompt input schema  │
│ BACKWARD_INCOMPATIBLE│              │  • LLM output schema    │
│ FULL_COMPATIBLE      │              │  • trace schema         │
└──────────┬───────────┘              └────────────┬────────────┘
           │                                       │
           └───────────────┬───────────────────────┘
                           ▼
                ┌─────────────────────┐
                │  ReportGenerator    │
                │  report_generator.py│
                │                     │
                │  Score: 100/100     │
                └─────────────────────┘
```

### Trust Boundary

This system operates at **Tier 1** (single repo, single team). The `contract_registry/subscriptions.yaml` file acts as a Tier-1 registry — in a Tier-2 multi-team environment it would be replaced by a DataHub / OpenMetadata registry API call. The validation and attribution logic is identical across tiers; only the blast radius computation mechanism changes.

---

## Setup

```bash
git clone https://github.com/gashawbekele06/Data-Contract-Enforcer
cd Data-Contract-Enforcer
uv sync
```

Requires Python 3.11+. Dependencies are declared in `pyproject.toml` and managed by `uv`.

```bash
# Alternative — plain pip
pip install -r requirements.txt
```

Optional API keys (graceful degradation without them):
- `ANTHROPIC_API_KEY` — LLM column annotation in ContractGenerator (`--annotate` flag)
- `OPENAI_API_KEY` — live embedding drift detection (falls back to synthetic embeddings)

---

## Quick Start

### Run the full pipeline in one command

```bash
uv run python main.py
```

This runs all five phases in sequence: generate → validate → attribute → evolve → ai → report.

```
############################################################
  Data Contract Enforcer — 2026-04-02 18:48 UTC
  Mode: AUDIT  |  Phase: all
############################################################
  Phase 1 — ContractGenerator  ...  6 contracts generated
  Phase 2A — ValidationRunner  ...  266 checks, 0 failed
  Phase 2B — ViolationAttributor ... 0 failures to attribute
  Phase 3 — SchemaEvolutionAnalyzer ... 6 contracts diffed
  Phase 4 — AI Contract Extensions ... PASS / PASS / PASS / PASS
  Phase 5 — ReportGenerator   ... Score 100/100
```

### Demonstrate violation detection (confidence scale breaking change)

```bash
uv run python main.py --inject-violation
```

Scales 274 `extracted_facts[].confidence` values from 0.0–1.0 to 0–100 in memory, triggering a CRITICAL range violation. The ViolationAttributor then:
1. Queries `contract_registry/subscriptions.yaml` for subscribers to `extracted_facts[].confidence`
2. Returns `week4-brownfield-cartographer` and `week7-ai-contract-extension` as the blast radius
3. Enriches with lineage contamination depth from the Week 4 lineage graph
4. Runs `git log` to build a ranked blame chain

```
  ✗ week3-document-refinery-extractions.extracted_facts.confidence.range
    Blast source: registry+lineage
    Subscribers : ['week4-brownfield-cartographer', 'week7-ai-contract-extension']
    Pipelines   : ['week4-lineage-generation', 'week7-ai-contract-extension']
```

### Run individual phases

```bash
uv run python main.py --phase generate    # Phase 1 only
uv run python main.py --phase validate    # Phase 2A only
uv run python main.py --phase attribute   # Phase 2B only
uv run python main.py --phase evolve      # Phase 3 only
uv run python main.py --phase ai          # Phase 4 only
uv run python main.py --phase report      # Phase 5 only
```

---

## Components

### Phase 1 — `contracts/generator.py` — ContractGenerator

Profiles a JSONL data source and emits a Bitol v3.0.0 YAML contract plus a dbt `schema.yml` counterpart. On every run a timestamped schema snapshot is saved to `schema_snapshots/` for evolution diffing.

```bash
uv run python contracts/generator.py \
  --source  outputs/week3/extractions.jsonl \
  --output  generated_contracts/ \
  --lineage outputs/week4/lineage_snapshots.jsonl \
  [--annotate]   # LLM column annotation via Claude (requires ANTHROPIC_API_KEY)
```

**What it generates per source:**
- `generated_contracts/<name>.yaml` — Bitol v3.0.0 contract (schema, quality, lineage sections)
- `generated_contracts/<name>_dbt.yml` — equivalent dbt `schema.yml` with `not_null`, `unique`, `accepted_values` tests
- `schema_snapshots/<contract_id>/<timestamp>.yaml` — snapshot for evolution analysis

**Structural profiling per column:** dtype, null_fraction, cardinality, format detection (UUID, SHA-256, ISO 8601, semver), enum detection, min/max/mean/stddev/percentiles for numeric columns, confidence-range anomaly warning.

**Lineage injection (with `--lineage`):** queries the Week 4 lineage graph to populate `lineage.downstream[]` in the contract with the consuming systems and their `breaking_if_changed` fields.

---

### Phase 1B — `contract_registry/subscriptions.yaml` — ContractRegistry

Records every inter-system data dependency. The ViolationAttributor queries this file as the authoritative subscriber list for blast radius computation — it does not derive blast radius solely from the lineage graph.

```yaml
subscriptions:
  - contract_id: week3-document-refinery-extractions
    subscriber_id: week4-brownfield-cartographer
    fields_consumed: [doc_id, extracted_facts, extraction_model]
    breaking_fields:
      - field: extracted_facts[].confidence
        reason: Used for node ranking; scale change breaks ranking logic.
    validation_mode: ENFORCE
    registered_at: '2025-01-10T09:00:00Z'
    contact: week4-team@org.com
```

**Current subscriptions (7 total):**

| Producer | Consumer | Breaking Fields |
|----------|----------|-----------------|
| week1-intent-code-correlator | week2-digital-courtroom | `code_refs`, `intent_id` |
| week3-document-refinery-extractions | week4-brownfield-cartographer | `extracted_facts[].confidence`, `doc_id` |
| week3-document-refinery-extractions | week7-ai-contract-extension | `extracted_facts[].confidence`, `extracted_facts[].text` |
| week4-brownfield-cartographer | week7-violation-attributor | `nodes`, `edges`, `nodes[].node_id`, `git_commit` |
| week5-event-sourcing-platform | week7-schema-contract | `event_type`, `payload`, `sequence_number`, `recorded_at` |
| langsmith-traces | week7-ai-contract-extension | `run_type`, `total_tokens`, `start_time` |
| week2-digital-courtroom | week7-ai-contract-extension | `overall_verdict`, `scores`, `confidence` |

In Tier-2+ production this file is replaced by a DataHub / OpenMetadata registry API.

---

### Phase 2A — `contracts/runner.py` — ValidationRunner

Executes every clause in a Bitol contract against a JSONL snapshot and produces a structured JSON report. Never crashes — missing columns return `ERROR` status and execution continues.

```bash
uv run python contracts/runner.py \
  --contract generated_contracts/week3_extractions.yaml \
  --data     outputs/week3/extractions.jsonl \
  [--output  validation_reports/week3_$(date +%Y%m%d_%H%M).json] \
  [--inject-violation]   # in-memory confidence 0→100 scale breach for demo
```

**Check types implemented:**

| Check | Severity | Description |
|-------|----------|-------------|
| `required` | CRITICAL | null count = 0 for required fields |
| `unique` | CRITICAL | duplicate count = 0 for primary keys |
| `format` | HIGH | UUID / SHA-256 / ISO 8601 / semver pattern match |
| `pattern` | HIGH | arbitrary regex (e.g. `^(claude\|gpt)-`) |
| `enum` | CRITICAL | value ∈ declared allowed set |
| `range` | CRITICAL/HIGH | numeric min/max bounds |
| `statistical_drift` | HIGH/MEDIUM | mean deviation > 2σ / 3σ from baseline |
| `nested_confidence` | CRITICAL | `extracted_facts[*].confidence` 0.0–1.0 |
| `referential_integrity` | HIGH | `entity_refs[]` → `entities[].entity_id` |
| `monotonic_sequence` | CRITICAL | `sequence_number` monotonic per `aggregate_id` |
| `temporal_order` | HIGH | `recorded_at ≥ occurred_at`, `end_time > start_time` |

**Report schema:**
```json
{
  "report_id": "uuid-v4",
  "contract_id": "week3-document-refinery-extractions",
  "snapshot_id": "sha256-of-input-jsonl",
  "run_timestamp": "ISO 8601",
  "total_checks": 41, "passed": 41, "failed": 0,
  "results": [{"check_id": "...", "status": "PASS", "severity": "LOW", ...}]
}
```

---

### Phase 2B — `contracts/attributor.py` — ViolationAttributor

Four-step attribution pipeline (as specified in Phase 2B):

**Step 1 — Registry blast radius query**
Loads `contract_registry/subscriptions.yaml`. Finds subscribers whose `breaking_fields` match the failing field. This is the authoritative subscriber list — not derived from the lineage graph.

**Step 2 — Lineage graph enrichment**
BFS on the Week 4 lineage graph from the producer node to each registry subscriber. Computes `contamination_depth` (hop count) for each subscriber.

**Step 3 — Git blame for cause attribution**
Runs `git log --follow --since="14 days ago"` on each upstream file. Ranks candidates by temporal proximity. Confidence formula: `base = 1.0 − (days_since × 0.1) − (hops × 0.2)`, clamped to [0.05, 1.0].

**Step 4 — Write violation log**
Appends to `violation_log/violations.jsonl` with registry-sourced blast radius, lineage contamination depth, and ranked blame chain (≤5 candidates).

```bash
uv run python contracts/attributor.py \
  --report   validation_reports/week3-document-refinery-extractions_<ts>.json \
  --lineage  outputs/week4/lineage_snapshots.jsonl \
  --registry contract_registry/subscriptions.yaml \
  [--check-id week3-document-refinery-extractions.extracted_facts.confidence.range]
```

**Violation log record schema:**
```json
{
  "violation_id": "uuid-v4",
  "check_id": "week3-document-refinery-extractions.extracted_facts.confidence.range",
  "severity": "CRITICAL",
  "blame_chain": [{"rank": 1, "file_path": "src/week3/extractor.py", "confidence_score": 0.94}],
  "blast_radius": {
    "registry_subscribers": [{"subscriber_id": "week4-brownfield-cartographer", "contamination_depth": 1}],
    "affected_nodes": [...],
    "affected_pipelines": ["week4-lineage-generation"],
    "blast_radius_source": "registry+lineage"
  }
}
```

---

### Phase 3 — `contracts/schema_analyzer.py` — SchemaEvolutionAnalyzer

Diffs consecutive schema snapshots and classifies every detected change using the Confluent Schema Registry compatibility taxonomy.

```bash
uv run python contracts/schema_analyzer.py \
  --contract-id week3-document-refinery-extractions \
  --since "7 days ago"
```

**Change taxonomy:**

| Change Type | Compatible | Risk |
|-------------|------------|------|
| `add_nullable_column` | Yes | LOW |
| `add_required_column` | No | CRITICAL |
| `rename_column` | No | CRITICAL |
| `type_widening` | Yes | MEDIUM |
| `type_narrowing` | No | CRITICAL |
| `remove_column` | No | CRITICAL |
| `add_enum_value` | Yes | LOW |
| `remove_enum_value` | No | HIGH |
| `range_tightened` | No | HIGH |
| `range_widened` | Yes | LOW |
| `pattern_changed` | No | HIGH |

Automatically injects a synthetic breaking snapshot (confidence 0→100, `processing_time_ms` minimum raised from 1→1000) when only one snapshot exists — allowing demonstration of `BACKWARD_INCOMPATIBLE` detection without modifying source data.

---

### Phase 4 — `contracts/ai_extensions.py` — AI Contract Extensions

```bash
uv run python contracts/ai_extensions.py \
  --extractions outputs/week3/extractions.jsonl \
  --verdicts    outputs/week2/verdicts.jsonl \
  --traces      outputs/traces/runs.jsonl \
  [--set-baseline]   # store embedding centroid as baseline (first run)
```

**Extension 1 — Embedding Drift Detection**
Samples `extracted_facts[*].text`, computes embeddings (OpenAI `text-embedding-3-small` or synthetic fallback), measures cosine distance from the baseline centroid. FAIL if drift > 0.15. Baseline stored in `schema_snapshots/embedding_baselines.npz`.

**Extension 2 — Prompt Input Schema Validation**
Validates each extraction record against a JSON Schema (requires `doc_id`, `source_path`, `content_preview`). Non-conforming records quarantined to `outputs/quarantine/`. FAIL if violation rate > 5%, WARN if > 1%.

**Extension 3 — LLM Output Schema Enforcement**
Validates Week 2 verdict records: `overall_verdict ∈ {PASS,FAIL,WARN}`, `scores[].score ∈ [1,5]`, `confidence ∈ [0.0,1.0]`. Tracks `violation_rate` history in `schema_snapshots/ai_metrics_history.jsonl`. WARN if trend is rising, FAIL if rate > 10%.

**Extension 4 — Trace Schema Contract**
Validates LangSmith trace records: `run_type` enum, `total_tokens = prompt_tokens + completion_tokens`, `end_time > start_time`, `total_cost ≥ 0`.

---

### Phase 5 — `contracts/report_generator.py` — ReportGenerator

```bash
uv run python contracts/report_generator.py
```

Aggregates all validation reports, violation log, schema evolution reports, and AI metrics into `enforcer_report/report_data.json` and `enforcer_report/report_{date}.md`.

**Health score formula:**
```
score = (total_passed / total_checks) × 100  −  (critical_violations × 20)
```

| Score | Narrative |
|-------|-----------|
| ≥ 90 | Healthy: all major checks passing with no critical violations. |
| 60–89 | Caution: minor violations present. Review recommended. |
| < 60 | Degraded: N critical violation(s) detected. Immediate action required. |

---

## Data Sources

| Week | File | Records | Schema Status |
|------|------|---------|---------------|
| Week 1 | `outputs/week1/intent_records.jsonl` | 50 | ✓ All checks pass (21 checks) |
| Week 2 | `outputs/week2/verdicts.jsonl` | 50 | ✓ All checks pass (49 checks) |
| Week 3 | `outputs/week3/extractions.jsonl` | 60 | ✓ All checks pass (41 checks) |
| Week 4 | `outputs/week4/lineage_snapshots.jsonl` | 10 | ✓ All checks pass (27 checks) |
| Week 5 | `outputs/week5/events.jsonl` | 100 | ✓ All checks pass (52 checks) |
| LangSmith | `outputs/traces/runs.jsonl` | 50 | ✓ All checks pass (76 checks) |

---

## Generated Contracts

| Contract File | Contract ID | Clauses | dbt File |
|---------------|-------------|---------|----------|
| `week1_intent_records.yaml` | week1-intent-code-correlator | 5 | `week1_intent_records_dbt.yml` |
| `week2_verdicts.yaml` | week2-digital-courtroom | 9 | `week2_verdicts_dbt.yml` |
| `week3_extractions.yaml` | week3-document-refinery-extractions | 9 | `week3_extractions_dbt.yml` |
| `week4_lineage_snapshots.yaml` | week4-brownfield-cartographer | 6 | `week4_lineage_snapshots_dbt.yml` |
| `week5_events.yaml` | week5-event-sourcing-platform | 10 | `week5_events_dbt.yml` |
| `runs.yaml` | langsmith-traces | 15 | `runs_dbt.yml` |

All contracts follow the [Bitol Open Data Contract Standard v3.0.0](https://bitol.io).

---

## Directory Structure

```
Data-Contract-Enforcer/
├── contracts/
│   ├── __init__.py
│   ├── generator.py        # Phase 1  — ContractGenerator
│   ├── runner.py           # Phase 2A — ValidationRunner
│   ├── attributor.py       # Phase 2B — ViolationAttributor (registry + lineage)
│   ├── schema_analyzer.py  # Phase 3  — SchemaEvolutionAnalyzer
│   ├── ai_extensions.py    # Phase 4  — AI Contract Extensions
│   └── report_generator.py # Phase 5  — ReportGenerator
├── contract_registry/
│   └── subscriptions.yaml  # Tier-1 registry: 7 inter-system subscriptions
├── generated_contracts/    # Bitol YAML + dbt YML (one per data source)
├── schema_snapshots/       # Timestamped snapshots per contract_id + baselines
│   ├── week1-intent-code-correlator/
│   ├── week2-digital-courtroom/
│   ├── week3-document-refinery-extractions/
│   ├── week4-brownfield-cartographer/
│   ├── week5-event-sourcing-platform/
│   ├── langsmith-traces/
│   ├── baselines.json          # Statistical drift baselines
│   ├── embedding_baselines.npz # Embedding centroid baseline
│   └── ai_metrics_history.jsonl
├── validation_reports/     # JSON reports: validation, schema_evolution, ai_metrics
├── violation_log/
│   └── violations.jsonl    # Append-only violation log (Week-8-Sentinel compatible)
├── enforcer_report/
│   ├── report_data.json    # Machine-readable health report
│   └── report_2026-04-02.md # Human-readable Markdown report
├── outputs/
│   ├── week1/intent_records.jsonl
│   ├── week2/verdicts.jsonl
│   ├── week3/extractions.jsonl
│   ├── week4/lineage_snapshots.jsonl
│   ├── week5/events.jsonl
│   ├── traces/runs.jsonl
│   └── quarantine/         # Prompt validation failures
├── scripts/
│   └── generate_sample_data.py
├── DOMAIN_NOTES.md         # Phase 0 domain reconnaissance (5 questions answered)
├── main.py                 # Full pipeline orchestrator
├── pyproject.toml
└── README.md
```

---

## Design Decisions

**Enforcement at the consumer boundary.** The ValidationRunner runs at the consumer's ingestion boundary — not at the producer side. This mirrors how production API clients validate responses: Stripe publishes a schema, you check it before you process it. The SchemaEvolutionAnalyzer is the pre-emptive (producer-side) layer; the ValidationRunner is the reactive layer.

**Registry over lineage-only blast radius.** The ViolationAttributor queries `contract_registry/subscriptions.yaml` as the authoritative subscriber list (Step 1), then uses the lineage graph only for contamination-depth enrichment (Step 2). This is architecturally correct for Tier-1 and degrades cleanly to Tier-2 by replacing the YAML load with a registry API call — the remaining three steps are identical.

**Bitol v3.0.0 + dbt dual output.** Every generated contract is immediately usable in two ecosystems: as a Bitol YAML for this pipeline and as a dbt `schema.yml` for any team already running dbt. No additional translation required.

**Append-only violation log.** `violation_log/violations.jsonl` is structured to be directly ingestible by the Week-8 Sentinel as a data-quality event stream. Every violation record is immutable and contains the full blame chain and blast radius at the time of detection.

**Statistical drift baseline.** The first ValidationRunner run on a new contract establishes baselines in `schema_snapshots/baselines.json`. Subsequent runs detect silent corruption (e.g. confidence scale 0.0–1.0 → 0–100) via mean deviation > 2σ/3σ, even when the type check passes.

**Graceful API key degradation.** All AI features (`--annotate`, embedding drift) fall back to rule-based equivalents. The pipeline runs fully end-to-end in any environment with zero API keys — including CI.
