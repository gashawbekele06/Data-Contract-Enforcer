# Presentation Script — Data Contract Enforcer
**TRP Week 7 · Target: ≤ 6 minutes · 6 steps in order**

---

## INTRO (≈ 20 sec)

> This is the Data Contract Enforcer — a seven-component pipeline that implements the Bitol Open Data Contract Standard v3.0.0 on six real datasets from prior TRP weeks.
> It auto-generates contracts from live data, enforces them clause-by-clause, traces violations back to specific git commits, detects schema drift, and produces a machine-generated health report.
> I'll walk through each phase live, in order.

---

## STEP 1 — Contract Generation (≈ 55 sec)

**[SCREEN: terminal, project root]**

> First — ContractGenerator. I'll run it live against the Week 3 extractions dataset.

**[TYPE:]**
```
uv run main.py --phase generate
```

> While it runs — ContractGenerator profiles `outputs/week3/extractions.jsonl`, computes column statistics, and writes a Bitol-compliant YAML contract.

**[SCREEN: open `generated_contracts/week3_extractions.yaml`, scroll to `confidence` clause]**

> Here's the generated contract. You can count over eight clauses — required, unique, type, format, pattern, enum, range, and referential integrity.
>
> The critical one is right here — `extracted_facts.confidence`, range `minimum: 0.0, maximum: 1.0`. That constraint is the contract's assertion that confidence is always a fraction, not a percentage. This clause is what makes violation detection possible in the next step.

---

## STEP 2 — Violation Detection (≈ 65 sec)

**[SCREEN: terminal]**

> Now I'll run the ValidationRunner in ENFORCE mode with an injected confidence scale violation — simulating an extraction model that returns 0–100 percentages instead of 0.0–1.0 fractions.

**[TYPE:]**
```
uv run main.py --phase validate --inject-violation --mode ENFORCE
```

> You can see the runner processing each contract clause. One check fails.

**[SCREEN: open `validation_reports/week3-document-refinery-extractions_<latest>.json`, scroll to the FAIL entry]**

> Here's the structured JSON report. Locating the failing check —
>
> `check_id: week3-document-refinery-extractions.extracted_facts.confidence.range`
> `status: FAIL`
> `severity: CRITICAL`
> `records_failing: 274`
> `actual_value: max=97.0, mean=84.3` — against an expected `max <= 1.0`
>
> Severity is CRITICAL, 274 records failing — every single confidence value in the dataset is on the wrong scale. This is exactly what the range clause was written to catch.

---

## STEP 3 — Blame Chain (≈ 65 sec)

**[SCREEN: terminal]**

> Next — ViolationAttributor. It auto-detects the latest validation report and runs a four-step attribution pipeline.

**[TYPE:]**
```
uv run contracts/attributor.py
```

> Watch the output.

**[SCREEN: attributor output — narrate as it prints]**

> Step 1 — it queries the contract registry and finds that `week3-document-refinery-extractions` has two subscribers: `week4-brownfield-cartographer` in ENFORCE mode, and `week7-ai-contract-extension` in AUDIT mode. That's the blast radius source.
>
> Step 2 — lineage BFS traversal. Starting at `week3`, it hops to Week 4's lineage pipeline and the Week 7 AI extension. Two pipelines in the contamination zone.
>
> Step 3 — git blame on `outputs/week3/extractions.jsonl`. Most recent commit touching this file: `4d2b4eb4` by `gashawbekele06` — "Complete Week 7 Data Contract Enforcer." Confidence score 0.60 — top candidate.
>
> Step 4 — violation written to `violation_log/violations.jsonl` with full blame chain and blast radius attached.

---

## STEP 4 — Schema Evolution (≈ 55 sec)

**[SCREEN: terminal]**

> Now SchemaEvolutionAnalyzer — diffing two real snapshots of the Week 3 contract.

**[TYPE:]**
```
uv run contracts/schema_analyzer.py \
  --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml \
  --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml
```

> The analyzer diffs the two YAML files and classifies every change using the Confluent schema evolution taxonomy.

**[SCREEN: analyzer output — show compatibility verdict and migration report]**

> The verdict: `BACKWARD_INCOMPATIBLE`. Change type: `range_tightened` on `processing_time_ms` — from `minimum=1, maximum=None` to `minimum=1000, maximum=60000`.
>
> The migration report lists two required actions before this change can ship: audit all producers for values below 1,000 ms, and re-establish statistical baselines in `schema_snapshots/baselines.json` after migration.
>
> The analyzer also generates the per-consumer failure mode table — showing exactly which subscribers break and what they must do.

---

## STEP 5 — AI Extensions (≈ 55 sec)

**[SCREEN: terminal]**

> Now the AI contract extensions — three checks that go beyond what a schema validator can see.

**[TYPE:]**
```
uv run contracts/ai_extensions.py
```

**[SCREEN: ai_extensions.py output]**

> Three metrics on screen.
>
> First — embedding drift. The cosine distance between the current Week 3 extraction embeddings and the stored baseline is **0.9797** against a threshold of 0.15. Status: FAIL. A score near 1.0 means the text content has moved to a completely different region of the embedding space — near-total semantic shift.
>
> Second — prompt input validation. 60 records checked, 0 quarantined. Status: PASS.
>
> Third — LLM output schema. 50 Week 2 verdict records checked, 0 violations, trend stable. Status: PASS.
>
> Overall AI status: AMBER — one check failing, two passing.

---

## STEP 6 — Enforcer Report (≈ 55 sec)

**[SCREEN: terminal]**

> Final step — the ReportGenerator. This runs end-to-end, pulling from the live violation log and all 48 validation reports.

**[TYPE:]**
```
uv run main.py --phase report
```

**[SCREEN: open `enforcer_report/report_data.json`]**

> Here's `report_data.json`. The `data_health_score` is **90 out of 100** — calculated as checks passed over total, minus five points per HIGH violation: `388/389 × 100 − (2 × 5) = 90`.
>
> The top violations are visible in plain language:
> Priority 1 — embedding drift FAIL on `extracted_facts[*].text`, score 0.9797, fix in `contracts/ai_extensions.py`.
> Priority 2 — re-run `ai_extensions.py --set-baseline` after confirming the shift is intentional.
> Priority 3 — confidence range CRITICAL on `extracted_facts[*].confidence`, propagates to `week4-brownfield-cartographer` in ENFORCE mode.
>
> Machine-generated from live data. Not hand-written.

---

## CLOSE (≈ 10 sec)

> That's all six phases — contract generation, violation detection, blame chain, schema evolution, AI extensions, and the enforcer report. Thank you.

---

## Quick Reference — Commands in Order

| Step | Command |
|------|---------|
| 1 — Generate | `uv run main.py --phase generate` |
| 2 — Validate | `uv run main.py --phase validate --inject-violation --mode ENFORCE` |
| 3 — Attribute | `uv run contracts/attributor.py` |
| 4 — Evolve | `uv run contracts/schema_analyzer.py --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml` |
| 5 — AI | `uv run contracts/ai_extensions.py` |
| 6 — Report | `uv run main.py --phase report` |

**Files to open on screen:**
- Step 1: `generated_contracts/week3_extractions.yaml` → scroll to `confidence` clause
- Step 2: `validation_reports/week3-document-refinery-extractions_<latest>.json` → scroll to FAIL entry
- Step 6: `enforcer_report/report_data.json` → show `data_health_score` and `top_violations`
