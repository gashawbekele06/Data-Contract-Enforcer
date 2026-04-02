# Data Contract Enforcer — 6-Minute Video Demo Script
## TRP Week 7 · Bitol v3.0.0 · Health Score 100/100

---

## SETUP BEFORE RECORDING

Open two windows side-by-side:
- **Left:** Terminal (Git Bash) in `Data-Contract-Enforcer/`
- **Right:** Browser at `http://localhost:3000` (run `cd dashboard && npm run dev`)

Start recording at the Overview dashboard page.

---

## ── MINUTES 1–3 ────────────────────────────────────────────────────────────

---

### STEP 1 — Contract Generation (≈ 55 sec)

**[Show dashboard — Overview page]**

> "This is the Data Contract Enforcer dashboard — a Next.js app reading live data
> from the pipeline. 1,224 checks, all passing, health score 100 out of 100.
> Let me show you how each piece is built — starting with contract generation."

**[Switch to terminal. Run:]**
```bash
PYTHONIOENCODING=utf-8 py -3 contracts/generator.py outputs/week3/extractions.jsonl
```

**[While it runs — narrate:]**
> "ContractGenerator v1.0.0 scans the raw JSONL, infers types, detects
> patterns like UUIDs and date-times, computes range statistics, and emits
> a Bitol v3.0.0 YAML contract."

**[After it finishes — open the file:]**
```bash
cat generated_contracts/week3_extractions.yaml
```

**[Scroll slowly and point out — narrate each:]**
> - Line 3: `id: week3-document-refinery-extractions` — the contract's stable identifier
> - Line 26: `pattern: ^[0-9a-f]{8}-…` — UUID format enforcement on `doc_id`, marked `unique: true`
> - Lines 51–56: **`extracted_facts[].confidence: minimum: 0.0 / maximum: 1.0`**
>   → *"This is Clause 1 of our core invariant — confidence is a float 0–1,
>   not a 0–100 percentage. The description says BREAKING CHANGE if scale changes."*
> - Line 94: `processing_time_ms: minimum: 1` — must be positive
> - Lines 87–91: `extraction_model: enum:` — model allowlist enforced
> - Lines 113–126: `quality: SodaChecks` — 9 statistical checks (null counts, dup counts, row count)

**Clause count to mention: 9 schema columns + 9 quality checks = 18 total clauses in this contract**

**[Switch to browser → Contracts page]**
> "The dashboard's Contracts page exposes the same YAML — click any contract
> to expand the viewer. You can copy it to clipboard or hand it to any consumer team."

---

### STEP 2 — Violation Detection (≈ 55 sec)

**[Switch to terminal. Run (inject the confidence scale breach):]**
```bash
PYTHONIOENCODING=utf-8 py -3 main.py --phase validate --inject-violation
```

**[Narrate while running:]**
> "We inject a known violation — 5 records where confidence is reported as
> values in the range 15–87 instead of 0.0–1.0 — a classic 0-to-100 scale
> confusion bug. The runner evaluates every clause in the contract."

**[Point at terminal output — highlight:]**
```
check_id : week3-document-refinery-extractions.extracted_facts.confidence.range
status   : FAIL
severity : CRITICAL
records  : 5 of 200 failing
```

> "The FAIL is CRITICAL severity because this field is in the registry's
> breaking_fields list — any scale change silently corrupts all downstream
> confidence thresholds."

**[Switch to browser → Validations page]**
> "In the Validations page, every check result is listed. Green check marks
> for all 40 passing clauses, a red X on `extracted_facts.confidence.range`.
> The JSON report is written to `validation_reports/` with the exact failing
> record count."

---

### STEP 3 — Blame Chain & Blast Radius (≈ 55 sec)

**[Switch to terminal. Run:]**
```bash
PYTHONIOENCODING=utf-8 py -3 contracts/attributor.py \
  --check-id "week3-document-refinery-extractions.extracted_facts.confidence.range" \
  --contract-id "week3-document-refinery-extractions" \
  --registry contract_registry/subscriptions.yaml
```

**[Narrate while running:]**
> "The attributor runs a 4-step pipeline:
> Step 1 — Registry query: which subscriptions have confidence in breaking_fields?
> Step 2 — Lineage BFS: how many hops downstream does contamination travel?
> Step 3 — Git blame: which commit introduced the data that broke the clause?
> Step 4 — Write to violation log."

**[Point at terminal output — highlight:]**
```
blast_radius_source : registry+lineage
registry_subscribers: week4-brownfield-cartographer (depth=1)
                      week7-ai-contract-extension   (depth=2)
blame_chain rank 1  : author=<author>, commit=<hash>
```

> "The registry tells us week4 is one hop downstream and week7-ai is two hops.
> That's the authoritative blast radius — not a guess from hardcoded maps."

**[Switch to browser → Violations page]**
> "The Violations page renders the full violation card — actual vs expected,
> ranked blame chain with commit hash and author, and the registry subscribers
> table showing contamination depth. Every field is populated from the live
> violation log."

---

## ── MINUTES 4–6 ────────────────────────────────────────────────────────────

---

### STEP 4 — Schema Evolution (≈ 55 sec)

**[Switch to terminal. Run:]**
```bash
PYTHONIOENCODING=utf-8 py -3 main.py --phase evolve
```

**[Narrate while running:]**
> "The SchemaEvolutionAnalyzer diffs two consecutive schema snapshots.
> We have a baseline snapshot and an injected breaking snapshot where
> `processing_time_ms` minimum was tightened from 1 to 1000."

**[Point at terminal output — highlight:]**
```
Snapshot A : 20260402_183608.yaml   (baseline)
Snapshot B : 20260402_183936_breaking.yaml
change_type: range_tightened
column     : processing_time_ms
old_value  : min=1, max=None
new_value  : min=1000, max=60000
verdict    : BACKWARD_INCOMPATIBLE  ← 1 breaking change
```

> "BACKWARD_INCOMPATIBLE means existing producers writing values between
> 1 and 999 milliseconds will now fail validation. The analyzer also generates
> a migration checklist and rollback plan."

**[Show migration checklist in terminal:]**
```
[ ] range_tightened on 'processing_time_ms': Migration plan required.
[ ] Run full validation on all downstream consumers
[ ] Update blast radius report and notify affected teams
[ ] Tag release with BREAKING_CHANGE label
```

**[Switch to browser → Overview page → Schema Changes section]**
> "The dashboard's Schema Changes panel shows the same result — red 'Breaking'
> badge on range_tightened, green 'Compatible' badge for the subsequent
> range_widened recovery. Auditors can see breaking changes at a glance."

---

### STEP 5 — AI Extensions (≈ 55 sec)

**[Switch to terminal. Run:]**
```bash
PYTHONIOENCODING=utf-8 py -3 contracts/ai_extensions.py \
  --data outputs/week3/extractions.jsonl \
  --llm-output outputs/week2/verdicts.jsonl \
  --traces outputs/langsmith/traces.jsonl
```

**[Narrate while running:]**
> "ai_extensions.py runs four AI-specific contract checks — things that
> regular schema validators cannot catch."

**[Point at terminal output — highlight each:]**
```
[1] Embedding Drift:
    drift_score = 0.9534   threshold = 0.15   status = FAIL
    → Text distribution has shifted significantly since baseline.

[2] Prompt Input Validation:
    60 records checked / 0 invalid   violation_rate = 0.0%  status = PASS

[3] LLM Output Schema:
    50 outputs / 0 violations   rate = 0.0%   trend = stable  status = PASS

[4] Trace Schema:
    50 traces / 0 run_type violations / 0 token mismatches  status = PASS
```

> "The embedding drift score of 0.95 against a threshold of 0.15 — that is
> the only amber signal. The extracted_facts text distribution has drifted
> far from the baseline stored in schema_snapshots/baselines.json.
> Prompt inputs, LLM outputs, and LangSmith traces are all clean."

**[Switch to browser → Overview page → AI Quality section]**
> "The dashboard shows AMBER status with the exact drift score 0.9534 / 0.15,
> and the recommended action: re-run ai_extensions.py with --set-baseline
> after confirming the shift is intentional."

---

### STEP 6 — Enforcer Report (≈ 55 sec)

**[Switch to terminal. Run:]**
```bash
PYTHONIOENCODING=utf-8 py -3 contracts/report_generator.py
```

**[Narrate while running:]**
> "report_generator.py aggregates all validation reports, the violation log,
> schema evolution diffs, and AI metrics into a single structured report."

**[Point at terminal output — highlight:]**
```
Reports analyzed : 48
Total checks     : 1,224
Passed           : 1,224   Failed : 0
Health Score     : 100 / 100
```

**[Open the report file:]**
```bash
cat enforcer_report/report_data.json
```

**[Point at key fields:]**
```json
"data_health_score": 100,
"health_narrative": "100/100 — Healthy: all major checks passing with no critical violations.",

"violations_this_week": {
  "total": 1,
  "by_severity": { "HIGH": 1 },
  "top_violations": [{
    "check_id": "ai_extensions.embedding_drift",
    "severity": "HIGH",
    "message": "Embedding drift FAIL: 0.9534 (threshold=0.15)"
  }]
},

"recommended_actions": [
  { "priority": 1, "severity": "HIGH",
    "action": "Fix field extracted_facts[*].text … revert or update clause ai_extensions.embedding_drift." },
  { "priority": 2, "severity": "HIGH",
    "action": "Investigate embedding drift … Re-run ai_extensions.py --set-baseline …" }
]
```

> "1,224 checks, 1,224 passing, health score 100. The one open item is the
> embedding drift violation — clearly identified with the remediation action
> and the affected pipeline."

**[Switch to browser → Overview page — full view]**

> "The dashboard reflects this live. Health gauge shows 100 in green.
> Every dataset at 100% pass rate. Schema changes visible. AI quality AMBER
> with the drift score. Two prioritized recommended actions.
> This is the complete Data Contract Enforcer pipeline — from raw JSONL
> to structured governance in six automated steps."

**[End on full Overview page]**

---

## QUICK REFERENCE — Commands

| Step | Command |
|------|---------|
| 1. Generate | `PYTHONIOENCODING=utf-8 py -3 contracts/generator.py outputs/week3/extractions.jsonl` |
| 2. Validate  | `PYTHONIOENCODING=utf-8 py -3 main.py --phase validate --inject-violation` |
| 3. Attribute | `PYTHONIOENCODING=utf-8 py -3 contracts/attributor.py --contract-id week3-document-refinery-extractions --registry contract_registry/subscriptions.yaml` |
| 4. Evolve    | `PYTHONIOENCODING=utf-8 py -3 main.py --phase evolve` |
| 5. AI        | `PYTHONIOENCODING=utf-8 py -3 contracts/ai_extensions.py --data outputs/week3/extractions.jsonl --llm-output outputs/week2/verdicts.jsonl --traces outputs/langsmith/traces.jsonl` |
| 6. Report    | `PYTHONIOENCODING=utf-8 py -3 contracts/report_generator.py` |

## QUICK REFERENCE — Dashboard Pages to Show

| Step | Dashboard Page | Key Elements to Point At |
|------|---------------|--------------------------|
| 1 | Contracts → week3_extractions.yaml | confidence range clause (lines 51–56), quality SodaChecks |
| 2 | Validations → week3 | Red ✗ on confidence.range, CRITICAL badge, 5 records failing |
| 3 | Violations | Blame chain card, blast radius with registry subscribers |
| 4 | Overview → Schema Changes | Breaking badge on range_tightened, Compatible badge on range_widened |
| 5 | Overview → AI Quality | AMBER, drift 0.9534/0.15, PASS on prompts/outputs/traces |
| 6 | Overview (full page) | 100 gauge, 1224/1224 bar, recommended actions list |

## KEY NUMBERS TO MENTION

- **1,224** total contract checks across 6 datasets
- **100/100** data health score (formula: passed/total × 100 − critical_violations × 20)
- **18** clauses in the week3 contract (9 schema + 9 quality)
- **7** subscriptions in the contract registry (Tier 1)
- **4-step** attribution pipeline (registry → lineage BFS → git blame → violation log)
- **11** schema change types from Confluent compatibility model
- **0.9534** embedding drift score vs **0.15** threshold
- **2** contamination hops: week3 → week4 (depth=1) → week7-ai (depth=2)
