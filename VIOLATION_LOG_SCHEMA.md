# Violation Log Schema Analysis & Week 8 Sentinel Integration

## Current State

The `violation_log/violations.jsonl` currently contains 3 violations with rich metadata:

| Violation | Type | Severity | Records | Status |
|-----------|------|----------|---------|--------|
| `ai_extensions.embedding_drift` | Embedding Drift | HIGH | 0 | No blame chain |
| `ai_extensions.embedding_drift` | Embedding Drift | HIGH | 0 | No blame chain |
| `week3-document-refinery-extractions.extracted_facts.confidence.range` | Schema Range | CRITICAL | 274 | Full blame chain + blast radius |

---

## Week 8 Integration Requirements

**Context:** "Every violation record written this week must be ingestible by Week 8's alert pipeline without modification."

This means the schema must support:
1. ✅ **Unique identification** — `violation_id`, `check_id`
2. ✅ **Temporal tracking** — `detected_at` (ISO8601)
3. ✅ **Severity classification** — `severity` (HIGH, CRITICAL)
4. ✅ **Root cause attribution** — `blame_chain` with commit hash + author
5. ✅ **Impact quantification** — `blast_radius`, `records_failing`
6. ✅ **Subscription awareness** — `registry_subscribers` with contact info & breaking fields
7. ✅ **Contract lineage** — `lineage_hops` in blame chain

---

## Issues for Week 8 Consumption

### ❌ Issue 1: Incomplete Blame Chain for AI Violations
**Lines 1–2:** Both embedding drift violations have `"blame_chain": []` — empty.

**Problem:** Week 8 Sentinel cannot attribute drift to a commit if no blame chain exists. AI violations need to trace back to when the model outputs changed.

**Required:** When `ai_extensions.py` detects embedding drift, it should:
- Scan recent commits to `ai/baselines.json` or model config files
- Populate `blame_chain` with the most recent model/training change commits
- Assign `confidence_score` based on file recency + semantic relevance (e.g., 0.7 for baseline change)

**Example fix:**
```json
"blame_chain": [
  {
    "rank": 1,
    "file_path": "contracts/ai_extensions.py",
    "commit_hash": "abc123...",
    "author": "data-team@org.com",
    "commit_timestamp": "2026-04-03 17:45:00 +0000",
    "commit_message": "fix: update embedding baseline for week3 extractions",
    "confidence_score": 0.65,
    "lineage_hops": 0
  }
]
```

---

### ❌ Issue 2: Missing Schema Version
**All violations:** No `schema_version` field.

**Problem:** Week 8 is a different project. If the violation schema changes in Week 8.1, it needs to know which version it's consuming.

**Required:** Add `"schema_version": "1.0.0"` to every violation record.

**Example fix:**
```json
{
  "schema_version": "week7-data-contract-enforcer/violation-log/1.0.0",
  "violation_id": "...",
  ...
}
```

---

### ❌ Issue 3: No Mitigation Guidance
**All violations:** Missing `mitigation_steps` and `escalation_contact`.

**Problem:** Week 8 Sentinel is an alert system. It receives the violation, but operators don't know what to do or who to call.

**Required:** Add fields for Week 8 to surface in alerts:
- `required_action`: string (e.g., "Audit all producers, re-baseline, or tighten acceptance criteria")
- `mitigation_steps`: array of strings (e.g., ["Run ai_extensions.py --set-baseline", "Confirm distribution shift is intentional"])
- `escalation_contact`: string (team email or Slack channel)

**Example fix:**
```json
{
  ...,
  "required_action": "Re-establish embedding baseline if extraction model output changed intentionally",
  "mitigation_steps": [
    "Run: uv run contracts/ai_extensions.py --set-baseline",
    "If drift is unintended, revert extraction model to prior commit",
    "Re-run validation to confirm resolution"
  ],
  "escalation_contact": "week7-data-quality@org.com",
  ...
}
```

---

### ⚠️ Issue 4: Incomplete Blast Radius for AI Violations
**Lines 1–2:** Both embedding drift violations have empty `"blast_radius"`:
```json
"blast_radius": {
  "affected_nodes": [],
  "affected_pipelines": [],
  "estimated_records": 0
}
```

**Problem:** The embedding drift DOES impact downstream pipelines, but no subscribers are listed. Week 8 Sentinel won't know which teams to notify.

**Required:** When embedding drift is detected, `ai_extensions.py` must:
- Query the contract registry for subscribers to `week3-document-refinery-extractions`
- Assess whether they use `extracted_facts[*].text` for embedding-based checks
- Populate `registry_subscribers` just like the confidence range violation does

**Example fix (combining Issues 2 & 4):**
```json
{
  "violation_id": "0720e5f7-e2e9-457c-bb85-2034af8cbbc0",
  "check_id": "ai_extensions.embedding_drift",
  "contract_id": "week3-document-refinery-extractions",
  "column_name": "extracted_facts[*].text",
  "severity": "HIGH",
  "type": "embedding_drift",
  "message": "Embedding drift FAIL: 0.9797 (threshold=0.15)",
  "actual_value": "drift=0.9797",
  "expected": "drift<0.15",
  "records_failing": 60,  // Update: should be record count checked, not 0
  "schema_version": "week7-data-contract-enforcer/violation-log/1.0.0",
  "detected_at": "2026-04-03T13:44:00Z",
  "blame_chain": [
    {
      "rank": 1,
      "file_path": "contracts/ai_extensions.py",
      "commit_hash": "a1b2c3d4...",
      "author": "extraction-team@org.com",
      "commit_timestamp": "2026-04-03 12:00:00 +0000",
      "commit_message": "feat: update embedding baseline",
      "confidence_score": 0.70,
      "lineage_hops": 0
    }
  ],
  "blast_radius": {
    "registry_subscribers": [
      {
        "subscriber_id": "week7-ai-contract-extension",
        "subscriber_team": "week7",
        "validation_mode": "AUDIT",
        "contact": "week7-team@org.com",
        "fields_consumed": ["extracted_facts[].text"],
        "breaking_field": "extracted_facts[].text",
        "breaking_reason": "Embedding drift invalidates text-based quality signals.",
        "contamination_depth": 0
      }
    ],
    "affected_nodes": [],
    "affected_pipelines": ["week7-ai-contract-extension"],
    "estimated_records": 60,
    "blast_radius_source": "registry"
  },
  "required_action": "Re-establish embedding drift baseline if distribution shift is intentional",
  "mitigation_steps": [
    "Review extraction model changes in past 48 hours",
    "If intentional: uv run contracts/ai_extensions.py --set-baseline",
    "If unintended: revert extraction model to prior version",
    "Re-run ai_extensions.py to validate resolution"
  ],
  "escalation_contact": "week7-team@org.com"
}
```

---

### ⚠️ Issue 5: `records_failing` Inconsistency for AI Violations
**Lines 1–2:** `"records_failing": 0` for embedding drift.

**Problem:** Embedding drift was detected by analyzing 60 real extraction records. Week 8 Sentinel may use `records_failing` to prioritize alerts. A count of 0 looks like a non-issue.

**Required:** Set `records_failing` to the number of records analyzed (e.g., 60 extractions checked against baseline).

---

## Recommended Changelist for `attributor.py` and `ai_extensions.py`

### In `attributor.py`:
1. After writing violation to `violations.jsonl`, ensure all violations have (`schema_version`)
2. Populate `required_action`, `mitigation_steps`, `escalation_contact` based on violation type

### In `ai_extensions.py`:
1. **Blame chain:** When embedding drift is detected, run git blame on `contracts/ai_extensions.py` baseline commits
2. **Blast radius:** Query contract registry for subscribers to the affected contract
3. **Records failing:** Set to count of records analyzed, not 0
4. **Escalation:** Determine appropriate contact from registry

---

## Schema Diff for Week 8 Readiness

**Current JSON schema:** 12 top-level fields + nested `blame_chain` and `blast_radius`

**Missing top-level fields needed for Week 8 Sentinel:**
```diff
{
  + "schema_version": "week7-data-contract-enforcer/violation-log/1.0.0",
  ...existing fields...
  + "required_action": "string",
  + "mitigation_steps": ["string"],
  + "escalation_contact": "string"
}
```

**Total additions:** 3 fields (always populated), ~2-4 lines per violation JSON.

---

## Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `contracts/attributor.py` | Add schema_version, required_action, mitigation_steps, escalation_contact | HIGH |
| `contracts/ai_extensions.py` | Populate blame_chain, blast_radius for embedding drift violations; fix records_failing | HIGH |
| `contract_registry/subscriptions.yaml` | Ensure Week 7 AI extension is listed as subscriber to week3 | HIGH |
| `violation_log/violations.jsonl` | Regenerate all 3 violations with complete schema | HIGH |

---

## Validation Checklist for Week 8 Readiness

- [ ] All violations have `schema_version` = `"week7-data-contract-enforcer/violation-log/1.0.0"`
- [ ] All violations with impact have non-empty `blame_chain` (rank, commit_hash, author, confidence_score)
- [ ] All violations have `required_action` (string, actionable for operators)
- [ ] All violations have `mitigation_steps` (array, executable)
- [ ] All violations have `escalation_contact` (email or Slack channel)
- [ ] All violations have accurate `records_failing` (≥1 if records were actually checked)
- [ ] All violations have populated `blast_radius` with registry lookup results
- [ ] Every `registry_subscribers` entry includes `contact`, `breaking_field`, `breaking_reason`

---

## Quick Test for Week 8 Readiness

Run this after regenerating violations:
```bash
# Count violations
wc -l violation_log/violations.jsonl

# Check for missing schema_version
grep -v "schema_version" violation_log/violations.jsonl

# Check for empty blame chains (should only be okay if type is not 'confidence_range')
jq '.[] | select(.blame_chain | length == 0)' violation_log/violations.jsonl

# Check for missing escalation_contact
jq '.[] | select(.escalation_contact == null)' violation_log/violations.jsonl
```

If all three grep/jq commands return no output, the log is ready for Week 8.
