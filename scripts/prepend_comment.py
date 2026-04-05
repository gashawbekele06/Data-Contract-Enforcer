"""Prepend injection comment to violation_log/violations.jsonl."""
import json
from pathlib import Path

VIOLATION_LOG = Path(__file__).parent.parent / "violation_log" / "violations.jsonl"

comment = {
    "_comment": (
        "INJECTED VIOLATION: Records with check_id "
        "week3-document-refinery-extractions.extracted_facts.confidence.range "
        "were produced by running: uv run contracts/runner.py "
        "--contract generated_contracts/extractions.yaml "
        "--data outputs/week3/extractions.jsonl --mode ENFORCE --inject-violation. "
        "The injector scales all extracted_facts[*].confidence values from 0.0-1.0 "
        "to 0-100, simulating a producer that changed the confidence scale. "
        "See contracts/runner.py inject_confidence_violation() for implementation. "
        "The embedding_drift record (violation_id 1e95bddf) is a REAL violation "
        "detected on live data, traceable to commit 48655ef9 in git history."
    )
}

existing = VIOLATION_LOG.read_text(encoding="utf-8")
VIOLATION_LOG.write_text(json.dumps(comment) + "\n" + existing, encoding="utf-8")
print(f"Done — comment prepended to {VIOLATION_LOG}")
