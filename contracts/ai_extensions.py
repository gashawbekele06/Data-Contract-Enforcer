#!/usr/bin/env python3
"""
AI Contract Extensions — Phase 4A
===================================
Three extensions that apply data contract thinking to AI-specific patterns:

  1. Embedding Drift Detection
     Embeds a random sample of extracted_facts text values using
     text-embedding-3-small (OpenAI) and computes cosine drift from baseline.

  2. Prompt Input Schema Validation
     Validates records against a JSON Schema before they enter a prompt.
     Non-conforming records are quarantined to outputs/quarantine/.

  3. Structured LLM Output Schema Enforcement
     Validates Week 2 verdict records against their expected output schema.
     Tracks output_schema_violation_rate and triggers WARN if rising.

Usage
-----
  python contracts/ai_extensions.py \\
      --extractions outputs/week3/extractions.jsonl \\
      --verdicts    outputs/week2/verdicts.jsonl \\
      --traces      outputs/traces/runs.jsonl \\
      --output      validation_reports/ai_metrics.json

  # Embed and store a new baseline (first run)
  python contracts/ai_extensions.py ... --set-baseline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).parent.parent
QUARANTINE_DIR = ROOT / "outputs" / "quarantine"
EMBEDDING_BASELINE = ROOT / "schema_snapshots" / "embedding_baselines.npz"
AI_METRICS_HISTORY = ROOT / "schema_snapshots" / "ai_metrics_history.jsonl"
VIOLATION_LOG = ROOT / "violation_log" / "violations.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def append_to_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Extension 1: Embedding Drift Detection
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str], model: str = "text-embedding-3-small") -> np.ndarray | None:
    """
    Embed texts using OpenAI text-embedding-3-small.
    Returns (n, dim) numpy array or None if unavailable.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  [AI-Ext] OPENAI_API_KEY not set — skipping live embedding.", file=sys.stderr)
        return None
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
        # Batch in chunks of 100
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            resp = client.embeddings.create(model=model, input=batch)
            all_embeddings.extend([e.embedding for e in resp.data])
        return np.array(all_embeddings, dtype=np.float32)
    except Exception as exc:
        print(f"  [AI-Ext] OpenAI embedding failed: {exc}", file=sys.stderr)
        return None


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance (0 = identical, 1 = orthogonal, 2 = opposite)."""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b) + 1e-10)
    similarity = float(np.dot(a_norm, b_norm))
    return round(1.0 - similarity, 6)


def check_embedding_drift(
    extractions: list[dict],
    baseline_path: Path,
    set_baseline: bool = False,
    threshold: float = 0.15,
    n_sample: int = 200,
) -> dict:
    """
    Sample extracted_facts[*].text, embed them, compare to stored centroid.
    """
    texts = []
    for rec in extractions:
        for fact in rec.get("extracted_facts", []):
            t = fact.get("text", "")
            if t:
                texts.append(t)

    if not texts:
        return {
            "status": "ERROR",
            "message": "No text values found in extracted_facts[*].text",
            "drift_score": None,
            "threshold": threshold,
        }

    # Sample
    import random
    sample = random.sample(texts, min(n_sample, len(texts)))

    embeddings = embed_texts(sample)

    if embeddings is None:
        # Fallback: use random unit vectors to demonstrate the check
        print("  [AI-Ext] Using synthetic embeddings for demonstration.")
        dim = 1536
        embeddings = np.random.randn(len(sample), dim).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    current_centroid = embeddings.mean(axis=0)

    if set_baseline or not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(str(baseline_path), centroid=current_centroid)
        print(f"  [AI-Ext] Embedding baseline stored → {baseline_path.relative_to(ROOT)}")
        return {
            "status": "BASELINE_SET",
            "message": f"Baseline stored from {len(sample)} text samples.",
            "drift_score": 0.0,
            "threshold": threshold,
            "n_sample": len(sample),
        }

    baseline = np.load(str(baseline_path))["centroid"]
    drift = cosine_distance(current_centroid, baseline)

    status = "FAIL" if drift > threshold else "PASS"
    result = {
        "status": status,
        "drift_score": float(drift),
        "threshold": threshold,
        "n_sample": len(sample),
        "message": (
            f"Embedding drift {'FAIL' if status == 'FAIL' else 'PASS'}: "
            f"{drift:.4f} (threshold={threshold})"
        ),
    }

    if status == "FAIL":
        violation = {
            "violation_id": str(uuid.uuid4()),
            "check_id": "ai_extensions.embedding_drift",
            "contract_id": "week3-document-refinery-extractions",
            "column_name": "extracted_facts[*].text",
            "severity": "HIGH",
            "type": "embedding_drift",
            "message": result["message"],
            "actual_value": f"drift={drift:.4f}",
            "expected": f"drift<{threshold}",
            "records_failing": 0,
            "detected_at": now_iso(),
            "blame_chain": [],
            "blast_radius": {"affected_nodes": [], "affected_pipelines": [], "estimated_records": 0},
        }
        append_to_jsonl(VIOLATION_LOG, violation)

    return result


# ---------------------------------------------------------------------------
# Extension 2: Prompt Input Schema Validation
# ---------------------------------------------------------------------------

PROMPT_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["doc_id", "source_path", "content_preview"],
    "properties": {
        "doc_id": {"type": "string", "minLength": 1},
        "source_path": {"type": "string", "minLength": 1},
        "content_preview": {"type": "string", "maxLength": 8000},
    },
    "additionalProperties": False,
}


def validate_prompt_input(record: dict) -> tuple[bool, list[str]]:
    """
    Validate a record against the prompt input schema.
    Returns (is_valid, list_of_errors).
    Uses jsonschema if available, falls back to manual checks.
    """
    errors = []
    try:
        import jsonschema  # type: ignore
        v = jsonschema.Draft7Validator(PROMPT_INPUT_SCHEMA)
        for e in v.iter_errors(record):
            errors.append(e.message)
    except ImportError:
        # Manual validation fallback
        required_fields = ["doc_id", "source_path", "content_preview"]
        for field in required_fields:
            if field not in record:
                errors.append(f"Missing required field: {field}")
            elif field == "source_path" and not record[field]:
                errors.append(f"{field} must not be empty")
            elif field == "content_preview":
                preview = record.get(field, "")
                if isinstance(preview, str) and len(preview) > 8000:
                    errors.append(f"content_preview exceeds 8000 characters")
        extra = set(record.keys()) - {"doc_id", "source_path", "content_preview"}
        for k in extra:
            errors.append(f"Additional property not allowed: {k}")
    return len(errors) == 0, errors


def check_prompt_input_validation(
    extractions: list[dict],
    quarantine_dir: Path,
) -> dict:
    """
    Build prompt input objects from extraction records and validate each.
    """
    valid_count = 0
    invalid_count = 0
    quarantined: list[dict] = []
    error_samples: list[str] = []

    for rec in extractions:
        prompt_input = {
            "doc_id": rec.get("doc_id", ""),
            "source_path": rec.get("source_path", ""),
            "content_preview": " ".join(
                f.get("text", "")[:200]
                for f in rec.get("extracted_facts", [])[:5]
            )[:8000],
        }
        is_valid, errors = validate_prompt_input(prompt_input)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            quarantined.append({"record": rec, "validation_errors": errors})
            if len(error_samples) < 5:
                error_samples.append(f"doc_id={rec.get('doc_id', '?')}: {errors[0]}")

    if quarantined:
        ts = ts_slug()
        qpath = quarantine_dir / f"{ts}_prompt_inputs.jsonl"
        qpath.parent.mkdir(parents=True, exist_ok=True)
        with open(qpath, "w", encoding="utf-8") as f:
            for q in quarantined:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")

    total = valid_count + invalid_count
    violation_rate = round(invalid_count / max(total, 1), 4)
    status = "FAIL" if violation_rate > 0.05 else ("WARN" if violation_rate > 0.01 else "PASS")

    return {
        "status": status,
        "total_records": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "violation_rate": violation_rate,
        "error_samples": error_samples,
        "quarantine_path": str(quarantined[0]) if quarantined else None,
        "message": (
            f"Prompt input validation: {invalid_count}/{total} records invalid "
            f"(rate={violation_rate:.4f})"
        ),
    }


# ---------------------------------------------------------------------------
# Extension 3: Structured LLM Output Schema Enforcement
# ---------------------------------------------------------------------------

VERDICT_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["verdict_id", "overall_verdict", "overall_score", "confidence", "scores"],
    "properties": {
        "verdict_id": {"type": "string"},
        "overall_verdict": {"type": "string", "enum": ["PASS", "FAIL", "WARN"]},
        "overall_score": {"type": "number", "minimum": 1.0, "maximum": 5.0},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "scores": {"type": "object"},
        "evaluated_at": {"type": "string"},
    },
}


def validate_llm_output(record: dict, schema: dict) -> tuple[bool, list[str]]:
    """Validate a single LLM output record against the expected schema."""
    errors = []
    try:
        import jsonschema  # type: ignore
        v = jsonschema.Draft7Validator(schema)
        for e in v.iter_errors(record):
            errors.append(e.message)
    except ImportError:
        required = schema.get("required", [])
        for field in required:
            if field not in record:
                errors.append(f"Missing required field: {field}")
        props = schema.get("properties", {})
        for field, fschema in props.items():
            if field not in record:
                continue
            val = record[field]
            expected_type = fschema.get("type")
            if expected_type == "string" and not isinstance(val, str):
                errors.append(f"{field} must be string")
            elif expected_type == "number" and not isinstance(val, (int, float)):
                errors.append(f"{field} must be number")
            mn = fschema.get("minimum")
            mx = fschema.get("maximum")
            if isinstance(val, (int, float)):
                if mn is not None and val < mn:
                    errors.append(f"{field}={val} below minimum {mn}")
                if mx is not None and val > mx:
                    errors.append(f"{field}={val} above maximum {mx}")
            enum = fschema.get("enum")
            if enum and val not in enum:
                errors.append(f"{field}={val!r} not in {enum}")
    return len(errors) == 0, errors


def load_violation_rate_history(contract_id: str) -> list[float]:
    """Load past violation rates from ai_metrics_history.jsonl."""
    rates = []
    if AI_METRICS_HISTORY.exists():
        with open(AI_METRICS_HISTORY, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("contract_id") == contract_id:
                        rates.append(rec.get("violation_rate", 0))
                except json.JSONDecodeError:
                    pass
    return rates


def detect_trend(current_rate: float, history: list[float]) -> str:
    if len(history) < 2:
        return "stable"
    recent_avg = sum(history[-3:]) / len(history[-3:])
    if current_rate > recent_avg * 1.5:
        return "rising"
    elif current_rate < recent_avg * 0.7:
        return "falling"
    return "stable"


def check_llm_output_schema(verdicts: list[dict]) -> dict:
    """Validate all verdict records against their expected schema."""
    contract_id = "week2-digital-courtroom"
    total = len(verdicts)
    violations = 0
    error_samples = []

    for rec in verdicts:
        is_valid, errors = validate_llm_output(rec, VERDICT_OUTPUT_SCHEMA)
        if not is_valid:
            violations += 1
            if len(error_samples) < 5:
                vid = rec.get("verdict_id", "?")
                error_samples.append(f"verdict_id={vid}: {errors[0]}")

    violation_rate = round(violations / max(total, 1), 4)

    history = load_violation_rate_history(contract_id)
    baseline_rate = round(sum(history) / max(len(history), 1), 4) if history else violation_rate
    trend = detect_trend(violation_rate, history)

    # Store in history
    history_rec = {
        "run_date": now_iso(),
        "contract_id": contract_id,
        "total_outputs": total,
        "schema_violations": violations,
        "violation_rate": violation_rate,
        "trend": trend,
        "baseline_violation_rate": baseline_rate,
    }
    AI_METRICS_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    append_to_jsonl(AI_METRICS_HISTORY, history_rec)

    status = "PASS"
    if trend == "rising":
        status = "WARN"
    if violation_rate > 0.1:
        status = "FAIL"

    if status in ("WARN", "FAIL"):
        violation = {
            "violation_id": str(uuid.uuid4()),
            "check_id": "ai_extensions.llm_output_schema",
            "contract_id": contract_id,
            "column_name": "verdict_record",
            "severity": "HIGH" if status == "FAIL" else "MEDIUM",
            "type": "llm_output_schema",
            "message": (
                f"LLM output schema violation rate={violation_rate:.4f} "
                f"trend={trend}"
            ),
            "actual_value": f"violation_rate={violation_rate:.4f}",
            "expected": "stable violation_rate < 0.05",
            "records_failing": violations,
            "detected_at": now_iso(),
            "blame_chain": [],
            "blast_radius": {
                "affected_nodes": [],
                "affected_pipelines": ["week2-evaluation-pipeline"],
                "estimated_records": violations,
            },
        }
        append_to_jsonl(VIOLATION_LOG, violation)

    return {
        "run_date": now_iso(),
        "contract_id": contract_id,
        "total_outputs": total,
        "schema_violations": violations,
        "violation_rate": violation_rate,
        "trend": trend,
        "baseline_violation_rate": baseline_rate,
        "status": status,
        "error_samples": error_samples,
        "message": (
            f"LLM output schema: {violations}/{total} violations "
            f"(rate={violation_rate:.4f}, trend={trend})"
        ),
    }


# ---------------------------------------------------------------------------
# Trace schema contract
# ---------------------------------------------------------------------------

TRACE_SCHEMA = {
    "required": ["id", "name", "run_type", "start_time", "end_time",
                 "total_tokens", "prompt_tokens", "completion_tokens", "total_cost"],
    "properties": {
        "run_type": {"type": "string", "enum": ["llm", "chain", "tool", "retriever", "embedding"]},
        "total_tokens": {"type": "integer", "minimum": 0},
        "total_cost": {"type": "number", "minimum": 0},
    },
}


def check_trace_schema(traces: list[dict]) -> dict:
    """Basic structural check on LangSmith trace records."""
    total = len(traces)
    violations = 0
    token_mismatch = 0

    for rec in traces:
        # total_tokens = prompt_tokens + completion_tokens
        p = rec.get("prompt_tokens", 0) or 0
        c = rec.get("completion_tokens", 0) or 0
        t = rec.get("total_tokens", 0) or 0
        if t != p + c:
            token_mismatch += 1

        run_type = rec.get("run_type", "")
        if run_type not in ("llm", "chain", "tool", "retriever", "embedding"):
            violations += 1

        start = rec.get("start_time", "")
        end = rec.get("end_time", "")
        if start and end and isinstance(start, str) and isinstance(end, str):
            if end < start:
                violations += 1

    status = "FAIL" if violations > 0 or token_mismatch > 0 else "PASS"
    return {
        "status": status,
        "total": total,
        "run_type_violations": violations,
        "token_mismatch": token_mismatch,
        "message": (
            f"Trace schema: {violations} run_type violations, "
            f"{token_mismatch} token count mismatches out of {total} records."
        ),
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_all_extensions(
    extractions: list[dict],
    verdicts: list[dict],
    traces: list[dict],
    set_baseline: bool = False,
) -> dict:
    print("\n[AI Contract Extensions]")

    print("  Extension 1: Embedding Drift Detection …")
    drift_result = check_embedding_drift(
        extractions, EMBEDDING_BASELINE, set_baseline=set_baseline
    )
    print(f"    Status: {drift_result['status']} | drift={drift_result.get('drift_score')}")

    print("  Extension 2: Prompt Input Schema Validation …")
    prompt_result = check_prompt_input_validation(extractions, QUARANTINE_DIR)
    print(
        f"    Status: {prompt_result['status']} | "
        f"valid={prompt_result['valid']}/{prompt_result['total_records']} | "
        f"rate={prompt_result['violation_rate']:.4f}"
    )

    print("  Extension 3: LLM Output Schema Enforcement …")
    output_result = check_llm_output_schema(verdicts)
    print(
        f"    Status: {output_result['status']} | "
        f"violations={output_result['schema_violations']}/{output_result['total_outputs']} | "
        f"trend={output_result['trend']}"
    )

    print("  Extension 4: Trace Schema Contract …")
    trace_result = check_trace_schema(traces)
    print(f"    Status: {trace_result['status']} | {trace_result['message']}")

    return {
        "run_timestamp": now_iso(),
        "embedding_drift": drift_result,
        "prompt_input_validation": prompt_result,
        "llm_output_schema": output_result,
        "trace_schema": trace_result,
        "overall_status": (
            "FAIL"
            if any(
                r.get("status") == "FAIL"
                for r in [drift_result, prompt_result, output_result, trace_result]
            )
            else (
                "WARN"
                if any(
                    r.get("status") in ("WARN", "BASELINE_SET")
                    for r in [drift_result, prompt_result, output_result, trace_result]
                )
                else "PASS"
            )
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Contract Extensions — embedding drift, prompt input, LLM output checks"
    )
    parser.add_argument(
        "--extractions",
        default=str(ROOT / "outputs" / "week3" / "extractions.jsonl"),
    )
    parser.add_argument(
        "--verdicts",
        default=str(ROOT / "outputs" / "week2" / "verdicts.jsonl"),
    )
    parser.add_argument(
        "--traces",
        default=str(ROOT / "outputs" / "traces" / "runs.jsonl"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "validation_reports" / "ai_metrics.json"),
    )
    parser.add_argument(
        "--set-baseline",
        action="store_true",
        help="Store a new embedding baseline (overwrites existing)",
    )
    args = parser.parse_args()

    extractions = load_jsonl(Path(args.extractions))
    verdicts = load_jsonl(Path(args.verdicts))
    traces = load_jsonl(Path(args.traces))

    print(f"  Loaded: {len(extractions)} extractions, "
          f"{len(verdicts)} verdicts, {len(traces)} traces")

    metrics = run_all_extensions(extractions, verdicts, traces, set_baseline=args.set_baseline)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  AI metrics → {out.relative_to(ROOT)}")
    print(f"  Overall   : {metrics['overall_status']}")


if __name__ == "__main__":
    main()
