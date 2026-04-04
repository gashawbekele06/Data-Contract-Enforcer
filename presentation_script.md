# Presentation Demo Script — Data Contract Enforcer
**TRP Week 7 · 6 minutes · Dashboard-first presentation**

> **Setup before recording:**
> - Dashboard running at `http://localhost:3000` (run `cd dashboard && npm run dev`)
> - Terminal open and ready at project root
> - Browser on dashboard Overview page
> - Font size bumped for readability

---

## INTRO — 20 seconds · [SCREEN: Dashboard Overview page]

> "This is the Data Contract Enforcer — a seven-component pipeline built on the Bitol Open Data Contract Standard v3.0.0, enforcing data quality across six real datasets from prior TRP weeks.
> It auto-generates contracts, enforces them clause-by-clause, traces violations to git commits, detects schema drift, and publishes everything to this live dashboard.
> I'll walk through all six phases live, in order."

---

## STEP 1 — Contract Generation · 55 seconds

### [SCREEN: Dashboard → Contracts page (`/contracts`)]

> "First, I'll navigate to the Contracts page. You can see six auto-generated Bitol v3.0.0 contracts — one per dataset. Each shows its clause count and downstream subscriber count."

> "Now let me run ContractGenerator live."

### [SWITCH TO: Terminal]

**[TYPE:]**
```
uv run main.py --phase generate
```

> "While it runs — it profiles `outputs/week3/extractions.jsonl`, computes per-column statistics, and writes a Bitol YAML contract."

### [SWITCH TO: Dashboard → Contracts page, click `week3_extractions.yaml` to expand]

> "Here's the generated contract. Click to expand — you can see over eight clauses: required, unique, format, pattern, enum, range, type, and referential integrity."

> "The critical clause is right here — `extracted_facts.confidence` — `minimum: 0.0, maximum: 1.0`. This is the contract's assertion that confidence is always a fraction, not a percentage. This single clause is what makes violation detection possible in the next step."

---

## STEP 2 — Violation Detection · 60 seconds

### [SCREEN: Terminal]

> "Now I'll run the ValidationRunner in ENFORCE mode with an injected confidence scale violation — simulating an extraction model that returns 0–100 percentages instead of 0.0–1.0 fractions."

**[TYPE:]**
```
uv run main.py --phase validate --inject-violation --mode ENFORCE
```

> "Forty checks pass. One fails."

### [SWITCH TO: Dashboard → Validations page (`/validations`)]

> "Back on the dashboard — Validations page. Here's the structured report for `week3-document-refinery-extractions`. You can see: 40 passed, 1 failed."

> "Expanding the report — scroll to the FAIL entry:"

> "`check_id: week3-document-refinery-extractions.extracted_facts.confidence.range`"
> "`status: FAIL`"
> "`severity: CRITICAL`"
> "`records_failing: 274`"
> "`actual_value: max=97.0, mean=84.3` — against expected `max <= 1.0`."

> "Severity is CRITICAL. All 274 confidence values are on the wrong scale — caught by that range clause we just generated."

---

## STEP 3 — Blame Chain · 60 seconds

### [SCREEN: Terminal]

> "Now ViolationAttributor — a four-step attribution pipeline."

**[TYPE:]**
```
uv run contracts/attributor.py
```

> "It auto-detects the latest validation report. Watch the four steps."

### [NARRATE AS OUTPUT PRINTS:]

> "Step 1 — registry lookup. Contract `week3-document-refinery-extractions` has two direct subscribers in `subscriptions.yaml`: `week4-brownfield-cartographer` in ENFORCE mode, and `week7-ai-contract-extension` in AUDIT mode. These are the Tier 1, registry-confirmed blast radius nodes."

> "Step 2 — lineage BFS. Traversing from Week 3 outward — two pipelines confirmed contaminated."

> "Step 3 — git blame on the data file. Top candidate: commit `4d2b4eb4` by `gashawbekele06`, confidence score 0.60. That score is calculated as 50% recency weight, 30% file relevance, 20% line frequency. Attribution is speculative at 0.60 — the violation is a systematic scale shift across all 274 records, not a single inserted bad value."

> "Step 4 — violation written to `violation_log/violations.jsonl` with full blame chain and blast radius."

### [SWITCH TO: Dashboard → Violations page (`/violations`)]

> "On the dashboard Violations page — you can see the violation card: severity HIGH, check ID, commit candidate, and both direct downstream nodes."

---

## STEP 4 — Schema Evolution · 55 seconds

### [SCREEN: Terminal]

> "SchemaEvolutionAnalyzer — diffing two real snapshots of the Week 3 contract."

**[TYPE:]**
```
uv run contracts/schema_analyzer.py \
  --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml \
  --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml
```

> "The analyzer diffs the two YAML files and classifies every change using the Confluent schema evolution taxonomy."

### [NARRATE OUTPUT:]

> "Compatibility verdict: `BACKWARD_INCOMPATIBLE`."
> "Change type: `range_tightened` on `processing_time_ms` — from minimum 1, unbounded, to minimum 1,000 maximum 60,000."
> "Any extraction completing under one second now fails validation."

> "The migration impact report lists four concrete steps before this ships — including re-establishing all three statistical baseline files. The per-consumer failure mode table shows exactly which subscribers break and how."

### [SWITCH TO: Dashboard → Registry page (`/registry`)]

> "On the Registry page — you can see the full subscription map. This is the data contract registry — seven active subscriptions showing producer-to-consumer relationships and breaking fields."

---

## STEP 5 — AI Extensions · 50 seconds

### [SCREEN: Terminal]

> "Now the AI contract extensions — three checks beyond what a schema validator can see."

**[TYPE:]**
```
uv run contracts/ai_extensions.py
```

### [NARRATE AS OUTPUT PRINTS:]

> "Three metrics."

> "First — embedding drift. Cosine distance between the current Week 3 extraction embeddings — real text from `outputs/week3/extractions.jsonl` — and the stored centroid. Score: **0.9797**, threshold: 0.15. Status: FAIL. A score near 1.0 means the text has moved to a completely different region of the embedding space — near-total semantic shift."

> "Second — prompt input validation against real Week 3 records. 60 checked, 0 quarantined. PASS."

> "Third — LLM output schema against real Week 2 verdict records from `outputs/week2/`. 50 checked, 0 violations, trend stable. PASS."

> "All three metrics on screen. Overall AI status: AMBER."

---

## STEP 6 — Enforcer Report · 50 seconds

### [SCREEN: Terminal]

> "Final step — ReportGenerator, end-to-end."

**[TYPE:]**
```
uv run main.py --phase report
```

> "It aggregates all 48 validation reports and the violation log."

### [SWITCH TO: Dashboard → Overview page (`/`)]

> "Back to the dashboard Overview page — the live enforcer report."

> "Health score: **90 out of 100**. Calculated as checks passed over total, minus five points per HIGH violation: `388/389 × 100 − (2 × 5) = 90`."

> "Top violations in plain language:"
> "Priority 1 — embedding drift FAIL on `extracted_facts[*].text`, score 0.9797, fix in `contracts/ai_extensions.py`."
> "Priority 2 — re-run `ai_extensions.py --set-baseline` after confirming the shift is intentional."
> "Priority 3 — confidence range CRITICAL on `extracted_facts[*].confidence`, 274 records, propagates to `week4-brownfield-cartographer` in ENFORCE mode."

> "Machine-generated from live data. Not hand-written."

---

## CLOSE — 10 seconds

> "That's all six phases — contract generation, violation detection, blame chain, schema evolution, AI extensions, and the enforcer report — all running live from the dashboard. Thank you."

---

## Timing Guide

| Step | Target | Key rubric check |
|------|--------|-----------------|
| Intro | 0:00–0:20 | — |
| 1 — Contract Generation | 0:20–1:15 | Show ≥8 clauses + `confidence` range clause explicitly |
| 2 — Violation Detection | 1:15–2:15 | Show JSON report with FAIL, CRITICAL severity, records_failing=274 |
| 3 — Blame Chain | 2:15–3:15 | Narrate: failing check → lineage hop → commit hash + confidence score |
| 4 — Schema Evolution | 3:15–4:10 | Show BACKWARD_INCOMPATIBLE verdict + migration impact report |
| 5 — AI Extensions | 4:10–5:00 | All 3 metrics visible: drift=0.9797, 0/60 quarantined, 0/50 violations |
| 6 — Enforcer Report | 5:00–5:50 | Show health score + 3 violations in plain language |
| Close | 5:50–6:00 | — |

## Commands in Order

```bash
uv run main.py --phase generate
uv run main.py --phase validate --inject-violation --mode ENFORCE
uv run contracts/attributor.py
uv run contracts/schema_analyzer.py \
  --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml \
  --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml
uv run contracts/ai_extensions.py
uv run main.py --phase report
```

## Dashboard Pages to Visit

| Step | URL | What to show |
|------|-----|-------------|
| 1 | `localhost:3000/contracts` | Expand `week3_extractions.yaml` → point to `confidence` range clause |
| 2 | `localhost:3000/validations` | FAIL row — `confidence.range`, CRITICAL, 274 records |
| 3 | `localhost:3000/violations` | Violation card with blame chain and subscribers |
| 4 | `localhost:3000/registry` | Subscription map + breaking fields |
| 6 | `localhost:3000` (Overview) | Health gauge 90/100 + top 3 violations |
