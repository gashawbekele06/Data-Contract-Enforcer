# Data Contract Enforcer
### TRP Week 7 — Schema Integrity & Lineage Attribution System

A schema governance pipeline that generates data contracts for multi-week AI system outputs, validates them, attributes violations to their source commits, detects schema drift, enforces AI-specific constraints, and produces a health report.

---

## Setup

```bash
# Clone and install
git clone https://github.com/gashawbekele06/Data-Contract-Enforcer
cd Data-Contract-Enforcer
uv sync
```

Requires Python 3.11+. All dependencies are declared in `pyproject.toml` and managed by `uv`.

**Alternative (plain pip — no uv required):**
```bash
pip install -r requirements.txt
```

Optional (AI annotation and embedding drift): set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` in environment. All scripts degrade gracefully without API keys.

---

## Quick Start — Full Pipeline

Run each step in sequence on a fresh clone:

```bash
# 1. Generate synthetic + adapted JSONL outputs from prior week data
uv run python scripts/generate_sample_data.py

# 2. Generate contracts for all data sources
uv run python contracts/generator.py --source outputs/week3/extractions.jsonl --output generated_contracts/ --lineage outputs/week4/lineage_snapshots.jsonl
uv run python contracts/generator.py --source outputs/week5/events.jsonl       --output generated_contracts/

# 3. Validate data against contract
uv run python contracts/runner.py --contract generated_contracts/week3_extractions.yaml --data outputs/week3/extractions.jsonl --output validation_reports/

# 4. Attribute violations to source commits
uv run python contracts/attributor.py --report validation_reports/<report>.json --lineage outputs/week4/lineage_snapshots.jsonl

# 5. Detect schema evolution (run after any schema change)
uv run python contracts/schema_analyzer.py --contract-id week3-document-refinery-extractions --since "7 days ago" --output validation_reports/

# 6. Run AI contract extensions
uv run python contracts/ai_extensions.py --extractions outputs/week3/extractions.jsonl --verdicts outputs/week2/verdicts.jsonl --traces outputs/traces/runs.jsonl --set-baseline

# 7. Generate enforcer report
uv run python contracts/report_generator.py --output enforcer_report/
```

---

## Entry Points

### `scripts/generate_sample_data.py`
Bootstraps all output data files under `outputs/`. Adapts real Week 3 extraction ledger and Week 5 event records to the challenge schema, adding synthetic records to reach target counts.

```
outputs/
  week1/intent_records.jsonl     (50 records)
  week2/verdicts.jsonl           (50 records)
  week3/extractions.jsonl        (50 records — adapted from real Week 3 data)
  week4/lineage_snapshots.jsonl  (10 records)
  week5/events.jsonl             (100 records — adapted from real Week 5 data)
  traces/runs.jsonl              (50 records)
  quarantine/                    (prompt validation failures go here)
```

Run this once on a fresh clone. Subsequent runs are idempotent.

---

### `contracts/generator.py` — Contract Generation
Profiles a JSONL data source and emits a Bitol v3.0.0 YAML contract plus a dbt `schema.yml` counterpart.

```bash
uv run python contracts/generator.py \
  --source outputs/week3/extractions.jsonl \
  --output generated_contracts/ \
  [--lineage outputs/week4/lineage_snapshots.jsonl] \
  [--annotate]   # calls Claude to enhance clause descriptions
```

**Expected output:**
```
[ContractGenerator] Profiling 50 records from outputs/week3/extractions.jsonl
[ContractGenerator] Generated contract: generated_contracts/week3_extractions.yaml (9 clauses)
[ContractGenerator] Generated dbt schema: generated_contracts/week3_extractions_dbt.yml
[ContractGenerator] Schema snapshot saved → schema_snapshots/week3-document-refinery-extractions/20260401_120000.yaml
```

Each re-run adds a new timestamped snapshot in `schema_snapshots/`. The diff between consecutive snapshots is detected by `schema_analyzer.py`.

---

### `contracts/runner.py` — Contract Validation
Runs a set of quality checks from a Bitol contract against a JSONL data file and produces a structured JSON report.

```bash
uv run python contracts/runner.py \
  --contract generated_contracts/week3_extractions.yaml \
  --data outputs/week3/extractions.jsonl \
  --output validation_reports/ \
  [--inject-violation]   # modifies data in memory to demo violation detection
```

**Expected output (clean data):**
```
[ValidationRunner] Loaded contract: week3-document-refinery-extractions (9 clauses)
[ValidationRunner] Loaded 50 records from outputs/week3/extractions.jsonl
[ValidationRunner] Validation complete — PASS=40 FAIL=1 WARN=0
Report: validation_reports/week3_extractions_20260401_120000.json
```

The JSON report schema: `{report_id, contract_id, total_checks, passed, failed, warned, results[{check_id, column_name, check_type, status, actual_value, expected, severity, records_failing, sample_failing, message}]}`.

---

### `contracts/attributor.py` — Violation Attribution
Takes a validation report and a lineage snapshot, traverses the lineage graph via BFS, runs `git log` on upstream files, and produces a blame chain ranked by confidence score.

```bash
uv run python contracts/attributor.py \
  --report validation_reports/week3_extractions_20260401_120000.json \
  --lineage outputs/week4/lineage_snapshots.jsonl \
  [--check-id week3-document-refinery-extractions.processing_time_ms.range]
```

**Expected output:**
```
[ViolationAttributor] Loaded report: 2 FAIL checks
[ViolationAttributor] Loaded lineage graph: 10 nodes, 9 edges

check: week3-document-refinery-extractions.processing_time_ms.range
  severity  : HIGH
  blame chain (3):
    1. abc1234 "Fix extractor timing units" — Jane Smith — hop 0 — confidence 0.90
    2. def5678 "Merge extractor refactor"    — Core Team  — hop 1 — confidence 0.60
    3. (no git history for upstream nodes)
  blast radius: 3 downstream nodes, pipelines: [week4-cartographer], ~150 records affected

Violations appended → violation_log/violations.jsonl
```

---

### `contracts/schema_analyzer.py` — Schema Evolution Detection
Diffs consecutive schema snapshots for a contract ID and classifies changes using the Confluent compatibility taxonomy.

```bash
uv run python contracts/schema_analyzer.py \
  --contract-id week3-document-refinery-extractions \
  --since "7 days ago" \
  [--output validation_reports/]
```

**Expected output (after a breaking change injection):**
```
[SchemaEvolutionAnalyzer] Contract: week3-document-refinery-extractions
  Snapshot A: schema_snapshots/.../20260331_224716.yaml
  Snapshot B: schema_snapshots/.../20260331_224912_breaking.yaml
  Compatibility: BACKWARD_INCOMPATIBLE
  Changes: 1 total, 1 breaking
    BREAKING  processing_time_ms.range_tightened (minimum: 1 → 1000)
              action: Coordinate migration. Existing records fail new range check.
              risk: HIGH
Migration report → validation_reports/schema_evolution_week3_....json
```

Change taxonomy used: `field_added`, `field_removed`, `type_widened`, `type_narrowed`, `range_expanded`, `range_tightened`, `enum_value_added`, `enum_value_removed`.

---

### `contracts/ai_extensions.py` — AI-Specific Contract Enforcement
Three AI-specific checks: embedding drift, prompt input schema validation, and LLM output schema enforcement. Degrades gracefully without API keys.

```bash
uv run python contracts/ai_extensions.py \
  --extractions outputs/week3/extractions.jsonl \
  --verdicts outputs/week2/verdicts.jsonl \
  --traces outputs/traces/runs.jsonl \
  [--set-baseline]   # first run: establishes embedding centroid baseline
```

**Expected output:**
```
[EmbeddingDriftDetector] BASELINE_SET — baseline stored to schema_snapshots/embedding_baselines.npz
[PromptInputValidator]   PASS — 50/50 prompts conform to schema
[LLMOutputEnforcer]      PASS — 0/50 violations (trend: stable)
[TraceSchemaContract]    PASS
AI metrics → validation_reports/ai_metrics.json
```

On second run (without `--set-baseline`): checks drift against the stored centroid. Quarantined records written to `outputs/quarantine/quarantine_{ts}.jsonl`.

---

### `contracts/report_generator.py` — Enforcer Report
Aggregates all validation reports, schema evolution reports, and AI metrics into a single health score and Markdown report.

```bash
uv run python contracts/report_generator.py \
  [--output enforcer_report/]
```

**Expected output:**
```
[ReportGenerator] Scanned 5 validation reports, 1 schema evolution reports
Data Health Score: 78 / 100
  Narrative: Caution: minor violations present. Review recommended.
  Total violations: 2 (0 CRITICAL, 1 HIGH)
  Schema changes: 1 (1 breaking)
  AI status: GREEN
Report data → enforcer_report/report_data.json
Markdown report → enforcer_report/report_2026-04-01.md
```

Health score formula: `(passed / total) × 100 − 20 × critical_violations`.

---

## Directory Structure

```
Data-Contract-Enforcer/
├── contracts/
│   ├── generator.py        # ContractGenerator — Bitol YAML + dbt schema.yml
│   ├── runner.py           # ValidationRunner — all check types
│   ├── attributor.py       # ViolationAttributor — BFS + git blame
│   ├── schema_analyzer.py  # SchemaEvolutionAnalyzer — snapshot diffing
│   ├── ai_extensions.py    # AI Contract Extensions — embedding drift, prompt validation
│   └── report_generator.py # ReportGenerator — health score + Markdown
├── scripts/
│   └── generate_sample_data.py
├── generated_contracts/    # Bitol YAML + dbt YML (one per data source)
├── schema_snapshots/       # Timestamped schema snapshots per contract_id
├── validation_reports/     # JSON reports (validation, schema_evolution, ai_metrics)
├── violation_log/
│   └── violations.jsonl    # Append-only violation log
├── enforcer_report/        # report_data.json + report_{date}.md
├── outputs/                # JSONL data files (week1–5, traces, quarantine)
├── DOMAIN_NOTES.md         # Phase 0 domain reconnaissance
├── main.py                 # Pipeline orchestrator
├── pyproject.toml
└── README.md
```

---

## Generated Contracts

| Contract File | Contract ID | Clauses | Source |
|---------------|-------------|---------|--------|
| `week3_extractions.yaml` | week3-document-refinery-extractions | 9 | Real Week 3 data |
| `week5_events.yaml` | week5-event-sourcing-platform | 10 | Real Week 5 data |
| `week1_intent_records.yaml` | week1-intent-code-correlator | 5 | Synthetic |
| `week2_verdicts.yaml` | week2-digital-courtroom | 9 | Synthetic |
| `week4_lineage.yaml` | week4-brownfield-cartographer | 6 | Synthetic |
| `langsmith_traces.yaml` | langsmith-traces | 15 | Synthetic |

All contracts follow the [Bitol Open Data Contract Standard v3.0.0](https://bitol.io).

---

## Design Decisions

- **Bitol v3.0.0** for all contracts — `kind: DataContract`, `apiVersion: v3.0.0`, machine-readable schema + quality + lineage sections.
- **Append-only violation log** — compatible with the Week 5 Event Sourcing Platform; interpretable as an event stream by Week 8's Sentinel.
- **Automatic re-generation on CI** — contracts are build artifacts, not documentation. Stale contracts are caught by diffing generated vs. committed YAML.
- **Graceful API key degradation** — all AI features fall back to synthetic/rule-based equivalents so the pipeline runs end-to-end in any environment.
