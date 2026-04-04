# Presentation Demo Script — Data Contract Enforcer
**TRP Week 7 · 6 minutes · Live terminal demo**

> **Setup before presenting:**
> - Terminal open and ready at project root
> - Dashboard running at `http://localhost:3000` (run `cd dashboard && npm run dev`)
> - Browser on dashboard Overview page
> - Font size bumped for readability

---

## INTRO — 35 seconds · [SCREEN: Dashboard Overview page]

### What is this project?

> "The **Data Contract Enforcer** is a seven-component pipeline that automatically generates, enforces, and monitors data quality contracts across six real datasets — all built on the **Bitol Open Data Contract Standard v3.0.0**."

### What problem does it solve?

> "In production data pipelines, schema breaks and silent data corruption are discovered late — after downstream consumers are already affected. This project solves that by treating data quality as a **contract**: a machine-readable, version-controlled agreement between producers and consumers."

### What is the goal?

> "The goal is a fully automated enforcement loop: generate contracts from real data, validate every record clause-by-clause, trace violations to the git commit that introduced them, detect breaking schema evolution, extend enforcement to AI-specific signals like embedding drift — and surface everything in a live dashboard. I'll walk through all six phases right now."

---

## STEP 1 — Contract Generation · 50 seconds
**[0:35 – 1:25]**

### [SCREEN: Terminal]

> "Phase 1 — ContractGenerator. I'm running it now against all six datasets."

**[TYPE:]**
```
uv run main.py --phase generate
```

> "As it runs — it reads each `.jsonl` file, profiles every column, computes statistics, and writes a Bitol v3.0.0 YAML contract. Watch the clause counts."

### [NARRATE AS OUTPUT PRINTS:]

> "Week 1 — intent records — 5 schema clauses. Week 2 — verdicts — 9 clauses. Week 3 — extractions — 9 clauses. Week 4 — lineage snapshots — 6 clauses. Week 5 — events — 10 clauses. LangSmith traces — 15 clauses."

> "Each contract also gets a versioned snapshot written to `schema_snapshots/` — that's what powers schema evolution detection in Step 4."

### [SWITCH TO: Dashboard → Contracts page (`/contracts`), expand `week3_extractions.yaml`]

> "Here's the Week 3 contract. The critical clause is `extracted_facts.confidence` — minimum 0.0, maximum 1.0. This is the contract's assertion that confidence is always a fraction. That single clause is what triggers the violation in the next step."

---

## STEP 2 — Violation Detection · 55 seconds
**[1:25 – 2:20]**

### [SCREEN: Terminal]

> "Phase 2 — ValidationRunner in ENFORCE mode with an injected violation. I'm simulating an extraction model that returns confidence as a 0–100 percentage instead of a 0.0–1.0 fraction."

**[TYPE:]**
```
uv run main.py --phase validate --inject-violation --mode ENFORCE
```

### [NARRATE AS OUTPUT PRINTS:]

> "Week 1 — 21 checks, all pass. Week 2 — 49 checks, all pass."

> "Week 3 — watch this. The injector scaled 274 confidence values to the 0–100 range. Result: 40 pass, **1 fail**."

> "The failure message: `CRITICAL` — `extracted_facts[*].confidence range violation`. Actual range: 70 to 97. Expected: 0.0 to 1.0. The contract caught it immediately."

> "Week 4, 5, and LangSmith traces — all clear. This is ENFORCE mode — in production, this failure would block the pipeline."

### [SWITCH TO: Dashboard → Validations page (`/validations`)]

> "On the dashboard Validations page — the FAIL row is visible. Severity CRITICAL. 274 records affected."

---

## STEP 3 — Violation Attribution · 50 seconds
**[2:20 – 3:10]**

### [SCREEN: Terminal]

> "Phase 3 — ViolationAttributor. This does four things: registry lookup, lineage traversal, git blame, and violation logging."

**[TYPE:]**
```
uv run contracts/attributor.py --report validation_reports/week3-document-refinery-extractions_20260404_172448.json
```

> "Step 1 — registry lookup. Contract `week3-document-refinery-extractions` has two downstream subscribers: `week4-brownfield-cartographer` in ENFORCE mode, and `week7-ai-contract-extension` in AUDIT mode. These are the confirmed blast-radius nodes."

> "Step 2 — lineage BFS. Traversing outward from Week 3 — two pipelines confirmed contaminated."

> "Step 3 — git blame on the data file. Top candidate: commit `4d2b4eb4` by `gashawbekele06`, attribution confidence 0.60. That score is 50% recency, 30% file relevance, 20% line frequency."

> "Step 4 — violation written to `violation_log/violations.jsonl` with the full blame chain and blast radius attached."

### [SWITCH TO: Dashboard → Violations page (`/violations`)]

> "Here's the violation card — severity HIGH, the check ID, the commit candidate, and both downstream nodes."

---

## STEP 4 — Schema Evolution · 50 seconds
**[3:10 – 4:00]**

### [SCREEN: Terminal]

> "Phase 4 — SchemaEvolutionAnalyzer. I'm diffing two real snapshots of the Week 3 contract — a baseline and a breaking change I committed earlier."

**[TYPE:]**
```
uv run contracts/schema_analyzer.py \
  --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml \
  --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml
```

### [NARRATE OUTPUT:]

> "Compatibility verdict: **BACKWARD_INCOMPATIBLE**."

> "One breaking change — `range_tightened` on `processing_time_ms`. The range was tightened to a 1,000–60,000 ms window. Any extraction that completes under one second now fails validation."

> "The analyzer classifies changes using the Confluent schema evolution taxonomy and generates a migration impact report — including which subscribers break and what steps are required before this ships."

### [SWITCH TO: Dashboard → Registry page (`/registry`)]

> "On the Registry page — the full subscription map. Seven active subscriptions, producer-to-consumer relationships, and the flagged breaking field."

---

## STEP 5 — AI Extensions · 50 seconds
**[4:00 – 4:50]**

### [SCREEN: Terminal]

> "Phase 5 — AI contract extensions. Four checks beyond what a schema validator can see."

**[TYPE:]**
```
uv run contracts/ai_extensions.py
```

### [NARRATE AS OUTPUT PRINTS:]

> "Extension 1 — **Embedding Drift Detection**. Cosine distance between current Week 3 extraction embeddings and the stored centroid: **1.039**. Threshold is 0.15. Status: **FAIL**. A score over 1.0 signals near-total semantic shift — the text topics have moved to a completely different region of embedding space."

> "Extension 2 — **Prompt Input Schema Validation**. 60 real Week 3 records checked against the input schema. 60 valid, 0 quarantined. **PASS**."

> "Extension 3 — **LLM Output Schema Enforcement**. 50 Week 2 verdict records checked for output schema violations. 0 violations, trend stable. **PASS**."

> "Extension 4 — **Trace Schema Contract**. 50 LangSmith run records checked. 0 run_type violations, 0 token count mismatches. **PASS**."

> "Overall AI status: **AMBER** — three extensions pass, but embedding drift is flagging a real distributional shift that schema checks alone would never catch."

---

## STEP 6 — Enforcer Report · 50 seconds
**[4:50 – 5:45]**

### [SCREEN: Terminal]

> "Final phase — ReportGenerator. It aggregates every validation report and violation log into a single summary."

**[TYPE:]**
```
uv run main.py --phase report
```

### [SWITCH TO: Dashboard → Overview page (`/`)]

> "Back to the dashboard Overview page — the live enforcer report."

> "**Data Health Score: 65 out of 100.** The score drops when CRITICAL violations are present — and right now there are 4 total violations across the pipeline, including the CRITICAL confidence range failure and the AI embedding drift."

> "Health narrative — quote: 'Caution: violations present. Review recommended.' Machine-generated. Not hand-written."

> "AI status: **AMBER**. Three of four AI extensions pass — only the embedding drift fails, signaling that the document extraction model's output distribution has shifted since the baseline was set."

> "This report is the deliverable — a single, versioned, machine-generated audit trail of every contract clause checked, every violation found, and every downstream system at risk."

---

## CLOSE — 15 seconds
**[5:45 – 6:00]**

> "Six phases: contract generation, violation detection, blame attribution, schema evolution, AI extensions, and the enforcer report — all running live, all enforced automatically."

> "The core idea: **data quality as a contract** — not a one-time check, but a versioned, enforceable agreement that catches breaks before they propagate. Thank you."

---

## Timing Guide

| Step | Time | Duration | Key thing to say |
|------|------|----------|-----------------|
| Intro | 0:00–0:35 | 35s | Project definition → problem → goal |
| 1 — Generate | 0:35–1:25 | 50s | Clause counts + `confidence` range clause |
| 2 — Validate | 1:25–2:20 | 55s | CRITICAL FAIL, 274 records, wrong scale |
| 3 — Attribution | 2:20–3:10 | 50s | Blast radius → commit hash → violation log |
| 4 — Schema Evolution | 3:10–4:00 | 50s | BACKWARD_INCOMPATIBLE + range_tightened |
| 5 — AI Extensions | 4:00–4:50 | 50s | drift=1.039 FAIL, 3 extensions PASS, AMBER |
| 6 — Report | 4:50–5:45 | 55s | Health 65/100, 4 violations, AMBER |
| Close | 5:45–6:00 | 15s | Data quality as a contract |

---

## Commands in Order

```bash
uv run main.py --phase generate
uv run main.py --phase validate --inject-violation --mode ENFORCE
uv run contracts/attributor.py --report validation_reports/week3-document-refinery-extractions_20260404_172448.json
uv run contracts/schema_analyzer.py \
  --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml \
  --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml
uv run contracts/ai_extensions.py
uv run main.py --phase report
```

> **Note on Step 3:** Pass `--report` explicitly pointing to the week3 validation report. Without it, the attributor defaults to the latest report (LangSmith traces), which has no failures.

## Dashboard Pages to Visit

| Step | URL | What to show |
|------|-----|-------------|
| 1 | `localhost:3000/contracts` | Expand `week3_extractions.yaml` → point to `confidence` range clause |
| 2 | `localhost:3000/validations` | FAIL row — `confidence.range`, CRITICAL, 274 records |
| 3 | `localhost:3000/violations` | Violation card with blame chain and subscribers |
| 4 | `localhost:3000/registry` | Subscription map + breaking fields |
| 6 | `localhost:3000` (Overview) | Health gauge 65/100 + AMBER AI status |
