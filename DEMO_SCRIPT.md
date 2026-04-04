# Data Contract Enforcer — Live Demo Script
## 6-Step Presentation | Target: Under 6 Minutes

> **HOW TO USE THIS SCRIPT**
> - Text in **[ACTION: ...]** = what to do on screen (don't read aloud)
> - All other text = read aloud exactly as written
> - Practice until each step feels natural — do not rush commands

---

## BEFORE YOU START

**Terminal:** Open in project root: `c:\Users\gasha\OneDrive\Desktop\TRP1\Week 7\Data-Contract-Enforcer`
**Dashboard:** Start Next.js dev server (`cd dashboard && npm run dev`) — open `localhost:3000` in browser
**Files pre-opened in editor (tabs ready):**
- `generated_contracts/week3_extractions.yaml`
- `enforcer_report/report_data.json`

---

## OPENING (0:00 — 0:10)

"Today I'm demoing the Data Contract Enforcer — a six-step governance pipeline that generates contracts, detects violations, traces blame, detects schema drift, enforces AI-specific constraints, and produces a full health report. Let's run it live."

---

## STEP 1 — CONTRACT GENERATION (0:10 — 1:00)

**[ACTION: Focus terminal. Clear it. Type and run:]**
```
python contracts/generator.py outputs/week3/extractions.jsonl
```

"Step one: contract generation. I'm running the ContractGenerator live against our Week 3 extractions dataset — eight hundred records produced by the Document Refinery pipeline."

**[ACTION: While the command runs, narrate:]**

"The generator profiles every field — types, patterns, cardinality, value ranges — and emits a Bitol v3.0.0 YAML contract."

**[ACTION: Once output finishes, open `generated_contracts/week3_extractions.yaml` in editor. Scroll slowly through the schema section.]**

"Here's the generated contract. Let me count the clauses: `doc_id` with UUID format validation — that's one. `source_path`, `source_hash` with SHA-256 pattern — two, three. `extracted_facts` as a required array — four. Inside it: `fact_id`, `text`, `page_ref` — five, six, seven. And here —"

**[ACTION: Scroll to the `confidence` clause and highlight it or zoom in:]**

"— clause eight: `extracted_facts[*].confidence`, typed as a float with `minimum: 0.0` and `maximum: 1.0`. This is the confidence range clause — it enforces that every confidence score stays between zero and one. This single clause is what our violation in the next step will break."

---

## STEP 2 — VIOLATION DETECTION (1:00 — 2:00)

**[ACTION: Switch back to terminal. Run:]**
```
python contracts/runner.py --inject-violation
```

"Step two: violation detection. I'm running the ValidationRunner against the violated dataset — this simulates a producer that changed the confidence scale from zero-to-one to zero-to-one-hundred, a breaking change."

**[ACTION: While running, narrate:]**

"The runner checks every clause in the contract against every record in the dataset."

**[ACTION: When output completes, scroll the JSON report visible in terminal or open the latest file in `validation_reports/`. Point to the FAIL block:]**

"Here's the structured JSON report. Look at the status: `FAIL`. The failing check is `extracted_facts[*].confidence.range` — exactly the clause we just generated."

**[ACTION: Point to severity field:]**

"Severity: `CRITICAL`. And here —"

**[ACTION: Point to records_failing:]**

"— `records_failing: 274`. Two hundred and seventy-four records have confidence values in the range seventy to ninety-seven — which violates the zero-to-one contract. That's the violation we'll now trace."

---

## STEP 3 — BLAME CHAIN (2:00 — 3:00)

**[ACTION: Terminal. Run:]**
```
python contracts/attributor.py
```

"Step three: blame chain. The ViolationAttributor takes that FAIL result and traverses the lineage graph to find who introduced the breaking change and what downstream systems are now contaminated."

**[ACTION: As output scrolls, narrate the traversal:]**

"Watch the traversal. First it loads the contract registry — our Tier-1 subscriptions file — and identifies which downstream systems consume `extracted_facts[*].confidence`."

**[ACTION: Point to the registry subscriber section in output:]**

"It finds two subscribers: `week4-brownfield-cartographer` and `week7-ai-contract-extension`. Both registered `confidence` as a breaking field — because the Cartographer uses it for lineage node weighting."

**[ACTION: Point to the commit / blame section:]**

"Now the git blame: the attributor traces to commit hash starting with `aaaaaaa`, authored by `unknown@platform.dev`, message: `feat: modify extracted_facts output format`. That is the originating commit."

**[ACTION: Point to blast_radius in output or violations.jsonl:]**

"And the blast radius: two affected downstream pipelines, `week4-lineage-generation` and `week7-ai-contract-extension`, with an estimated two hundred seventy-four contaminated records. The lineage hop to the Cartographer is depth zero — direct dependency. Week 7 is depth one."

---

## STEP 4 — SCHEMA EVOLUTION (3:00 — 4:00)

**[ACTION: Terminal. Run:]**
```
python contracts/schema_analyzer.py
```

"Step four: schema evolution. The SchemaEvolutionAnalyzer diffs two consecutive contract snapshots for the Week 3 dataset to detect structural changes."

**[ACTION: When output appears, point to the change classification:]**

"The analyzer compares the earlier snapshot to the current one and classifies every detected change using a compatibility taxonomy."

**[ACTION: Point to the BACKWARD_INCOMPATIBLE / CRITICAL entry:]**

"Here: change type `range_tightened` on field `processing_time_ms` — classified as `BACKWARD_INCOMPATIBLE`, risk level `CRITICAL`. Tightening a range is a breaking change because existing producers that emit values in the old wider range will immediately fail validation."

**[ACTION: Point to the migration impact report section:]**

"Below that is the generated migration impact report: required action — producers must audit their `processing_time_ms` outputs and align to the new bounds before the contract is enforced in production. This is the automated impact report the team gets with every schema change."

---

## STEP 5 — AI EXTENSIONS (4:00 — 5:00)

**[ACTION: Terminal. Run:]**
```
python contracts/ai_extensions.py
```

"Step five: AI-specific contract extensions. These go beyond traditional schema checks to govern the statistical and semantic properties of AI outputs. We're running on real Week 3 extraction text and real Week 2 verdict records."

**[ACTION: While running, narrate:]**

"The extension embeds a two-hundred-record sample of `extracted_facts[*].text` using OpenAI's text-embedding-3-small model and computes cosine distance from the stored baseline."

**[ACTION: When output appears, point to embedding drift score:]**

"Embedding drift score: `0.95`. The threshold is `0.15`. Status: `FAIL`. This tells us the semantic content of our extractions has drifted significantly from the baseline — the AI is extracting structurally different facts than it was before."

**[ACTION: Point to prompt input validation result:]**

"Prompt input validation: `violation_rate: 0.0` — every pre-prompt record conforms to the input schema. No quarantine events."

**[ACTION: Point to LLM output violation rate:]**

"LLM output schema violation rate: `0.0`, trend: `stable`. Our Week 2 courtroom verdict records are still conforming to the expected structured output schema. Three metrics — all visible, all meaningful."

---

## STEP 6 — ENFORCER REPORT (5:00 — 5:50)

**[ACTION: Terminal. Run:]**
```
python contracts/report_generator.py
```

"Step six: the full enforcer report. The ReportGenerator aggregates all forty-eight validation reports, the violation log, and the AI metrics into a single end-to-end health assessment."

**[ACTION: When it finishes, open `enforcer_report/report_data.json` in editor:]**

"Here's `report_data.json`. At the top —"

**[ACTION: Point to data_health_score:]**

"— `data_health_score: 90`. Ninety out of one hundred. The system is healthy overall, but two high-severity violations require attention — those are our embedding drift FAILs."

**[ACTION: Scroll to top_violations array:]**

"The top three violations in plain language: violation one — `extracted_facts[*].confidence` range breach, CRITICAL severity, two hundred seventy-four failing records, introduced by a scale change from zero-one to zero-one-hundred. Violation two — embedding drift score of 0.95 on Week 3 extraction text, exceeding the 0.15 threshold. Violation three — schema range tightening on `processing_time_ms`, classified as a breaking change."

**[ACTION: Switch to dashboard in browser, show the overview page briefly:]**

"And the dashboard at localhost:3000 surfaces all of this — health score, violation details, blame chains, and the full contract registry — in one place."

---

## CLOSING (5:50 — 6:00)

"Six steps, end-to-end: contract generation, violation detection, blame attribution, schema evolution, AI extensions, and the enforcer report. Thank you."

---

## COMMAND CHEAT SHEET

| Step | Command |
|------|---------|
| 1. Contract Generation | `python contracts/generator.py outputs/week3/extractions.jsonl` |
| 2. Violation Detection | `python contracts/runner.py --inject-violation` |
| 3. Blame Chain | `python contracts/attributor.py` |
| 4. Schema Evolution | `python contracts/schema_analyzer.py` |
| 5. AI Extensions | `python contracts/ai_extensions.py` |
| 6. Enforcer Report | `python contracts/report_generator.py` |

## RUBRIC CHECKLIST

- [x] **Contract Gen:** Run live, show YAML, count 8+ clauses, explicitly point out `extracted_facts[*].confidence` range clause
- [x] **Violation Detection:** Run live, show structured JSON report, say "FAIL", point to severity "CRITICAL", point to `records_failing: 274`
- [x] **Blame Chain:** Run live, narrate traversal (registry → lineage → git blame), name the commit hash, author, and two downstream affected nodes
- [x] **Schema Evolution:** Run live, say "BACKWARD_INCOMPATIBLE", show the generated migration impact report
- [x] **AI Extensions:** Run live on real Week 3 + Week 2 data, show all three: embedding drift score (0.95), prompt input rate (0.0), LLM output rate (0.0)
- [x] **Enforcer Report:** Run live end-to-end, show `data_health_score: 90`, name top three violations in plain language
- [x] **Professional Delivery:** Sequence is 1→2→3→4→5→6, no dead time, each step transitions directly into the next
