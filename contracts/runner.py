#!/usr/bin/env python3
"""
ValidationRunner — Phase 2A
============================
Executes every contract clause in a Bitol YAML file against a JSONL data snapshot
and produces a structured JSON validation report.

Usage
-----
  python contracts/runner.py \\
      --contract generated_contracts/extractions.yaml \\
      --data     outputs/week3/extractions.jsonl \\
      --output   validation_reports/week3_$(date +%Y%m%d_%H%M).json

  # inject a violation to demonstrate drift detection
  python contracts/runner.py \\
      --contract generated_contracts/extractions.yaml \\
      --data     outputs/week3/extractions.jsonl \\
      --inject-violation
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
BASELINES_PATH = ROOT / "schema_snapshots" / "baselines.json"

# Regex patterns
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.I)
SHA40_RE = re.compile(r"^[a-f0-9]{40}$", re.I)
ISO_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

PATTERN_MAP = {
    "uuid": UUID_RE,
    "sha256": SHA256_RE,
    "sha256-40": SHA40_RE,
    "date-time": ISO_TS_RE,
    "semver": SEMVER_RE,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Check result builder
# ---------------------------------------------------------------------------

def result(
    check_id: str,
    column_name: str,
    check_type: str,
    status: str,
    actual_value: Any,
    expected: Any,
    severity: str,
    records_failing: int = 0,
    sample_failing: list | None = None,
    message: str = "",
) -> dict:
    return {
        "check_id": check_id,
        "column_name": column_name,
        "check_type": check_type,
        "status": status,
        "actual_value": str(actual_value),
        "expected": str(expected),
        "severity": severity,
        "records_failing": records_failing,
        "sample_failing": sample_failing or [],
        "message": message,
    }


def error_result(check_id: str, column_name: str, check_type: str, message: str) -> dict:
    return result(
        check_id, column_name, check_type,
        status="ERROR",
        actual_value="N/A",
        expected="N/A",
        severity="ERROR",
        message=message,
    )


# ---------------------------------------------------------------------------
# Individual check runners
# ---------------------------------------------------------------------------

def check_required(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.required"
    if clause.get("required") and not clause.get("nullable"):
        null_count = int(series.isna().sum())
        if null_count > 0:
            return result(
                check_id, col, "required", "FAIL",
                f"null_count={null_count}", "null_count=0",
                "CRITICAL", null_count,
                message=f"{col} has {null_count} null values but is required.",
            )
    return result(check_id, col, "required", "PASS", "null_count=0", "null_count=0", "LOW")


def check_unique(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.unique"
    if not clause.get("unique"):
        return result(check_id, col, "unique", "PASS", "N/A", "N/A", "LOW",
                      message="Uniqueness not required.")
    non_null = series.dropna()
    dup_count = int(len(non_null) - non_null.nunique())
    if dup_count > 0:
        dupes = non_null[non_null.duplicated()].head(5).astype(str).tolist()
        return result(
            check_id, col, "unique", "FAIL",
            f"duplicates={dup_count}", "duplicates=0",
            "CRITICAL", dup_count, dupes,
            message=f"{col} has {dup_count} duplicate values.",
        )
    return result(check_id, col, "unique", "PASS", "duplicates=0", "duplicates=0", "LOW")


def check_format(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.format"
    fmt = clause.get("format")
    if not fmt or fmt not in PATTERN_MAP:
        return result(check_id, col, "format", "PASS", "N/A", "N/A", "LOW",
                      message="No format check required.")
    pattern = PATTERN_MAP[fmt]
    non_null = series.dropna().astype(str)
    fail_mask = ~non_null.map(lambda v: bool(pattern.match(v)))
    fail_count = int(fail_mask.sum())
    if fail_count > 0:
        sample = non_null[fail_mask].head(3).tolist()
        return result(
            check_id, col, "format", "FAIL",
            f"invalid_format={fail_count}", f"format={fmt}",
            "HIGH", fail_count, sample,
            message=f"{col}: {fail_count} values don't match format '{fmt}'.",
        )
    return result(check_id, col, "format", "PASS",
                  f"all match format={fmt}", f"format={fmt}", "LOW")


def check_pattern(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.pattern"
    pattern_str = clause.get("pattern")
    if not pattern_str:
        return result(check_id, col, "pattern", "PASS", "N/A", "N/A", "LOW",
                      message="No pattern check required.")
    try:
        pat = re.compile(pattern_str)
    except re.error as e:
        return error_result(check_id, col, "pattern", f"Invalid pattern regex: {e}")
    non_null = series.dropna().astype(str)
    fail_mask = ~non_null.map(lambda v: bool(pat.search(v)))
    fail_count = int(fail_mask.sum())
    if fail_count > 0:
        sample = non_null[fail_mask].head(3).tolist()
        return result(
            check_id, col, "pattern", "FAIL",
            f"pattern_fails={fail_count}", f"pattern={pattern_str}",
            "HIGH", fail_count, sample,
            message=f"{col}: {fail_count} values don't match pattern '{pattern_str}'.",
        )
    return result(check_id, col, "pattern", "PASS",
                  f"all match pattern={pattern_str}", f"pattern={pattern_str}", "LOW")


def check_enum(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.enum"
    enums = clause.get("enum")
    if not enums:
        return result(check_id, col, "enum", "PASS", "N/A", "N/A", "LOW",
                      message="No enum check required.")
    allowed = set(str(e) for e in enums)
    non_null = series.dropna().astype(str)
    bad_mask = ~non_null.isin(allowed)
    bad_count = int(bad_mask.sum())
    if bad_count > 0:
        sample = non_null[bad_mask].head(3).tolist()
        return result(
            check_id, col, "enum", "FAIL",
            f"invalid_values={bad_count}", f"allowed={enums}",
            "CRITICAL", bad_count, sample,
            message=f"{col}: {bad_count} values not in allowed set {enums}.",
        )
    return result(check_id, col, "enum", "PASS",
                  f"all in allowed set", f"allowed={enums}", "LOW")


def check_range(contract_id: str, col: str, clause: dict, series: pd.Series) -> dict:
    check_id = f"{contract_id}.{col}.range"
    mn = clause.get("minimum")
    mx = clause.get("maximum")
    if mn is None and mx is None:
        return result(check_id, col, "range", "PASS", "N/A", "N/A", "LOW",
                      message="No range check required.")
    numeric = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    if numeric.empty:
        return error_result(check_id, col, "range", f"No numeric values in {col}")

    fails = []
    if mn is not None:
        below = numeric[numeric < mn]
        fails.extend(below.index.tolist())
    if mx is not None:
        above = numeric[numeric > mx]
        fails.extend(above.index.tolist())

    fail_count = len(set(fails))
    actual_min = float(numeric.min())
    actual_max = float(numeric.max())
    actual_mean = float(numeric.mean())

    if fail_count > 0:
        sample_ids = list(set(fails))[:3]
        sev = "CRITICAL" if "confidence" in col.lower() else "HIGH"
        return result(
            check_id, col, "range", "FAIL",
            f"min={actual_min:.4f}, max={actual_max:.4f}, mean={actual_mean:.4f}",
            f"min>={mn}, max<={mx}",
            sev, fail_count, [str(s) for s in sample_ids],
            message=(
                f"{col} range violation: actual [{actual_min:.4f}, {actual_max:.4f}] "
                f"vs expected [{mn}, {mx}]. "
                + (
                    "confidence is in 0–100 range, not 0.0–1.0. Breaking change detected."
                    if "confidence" in col.lower() and actual_max > 1.0
                    else ""
                )
            ),
        )
    return result(
        check_id, col, "range", "PASS",
        f"min={actual_min:.4f}, max={actual_max:.4f}",
        f"min>={mn}, max<={mx}", "LOW",
    )


def check_nested_confidence(
    contract_id: str,
    col: str,
    records: list[dict],
) -> list[dict]:
    """
    For array-of-objects columns like extracted_facts, check nested confidence fields.
    Returns list of check result dicts.
    """
    results = []
    check_id = f"{contract_id}.{col}.confidence.range"

    confidences = []
    fact_ids_failing = []
    for i, rec in enumerate(records):
        items = rec.get(col)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            conf = item.get("confidence")
            if conf is None:
                continue
            try:
                c = float(conf)
                confidences.append(c)
                if c > 1.0 or c < 0.0:
                    fid = item.get("fact_id", item.get("node_id", str(i)))
                    fact_ids_failing.append(str(fid))
            except (TypeError, ValueError):
                pass

    if not confidences:
        return []

    actual_min = min(confidences)
    actual_max = max(confidences)
    actual_mean = sum(confidences) / len(confidences)
    fail_count = len(fact_ids_failing)

    if fail_count > 0:
        results.append(result(
            check_id, f"{col}[*].confidence", "range", "FAIL",
            f"max={actual_max:.4f}, mean={actual_mean:.4f}",
            "max<=1.0, min>=0.0",
            "CRITICAL", fail_count, fact_ids_failing[:5],
            message=(
                f"{col}[*].confidence range violation: "
                f"actual [{actual_min:.4f}, {actual_max:.4f}]. "
                + (
                    "confidence is in 0–100 range, not 0.0–1.0. Breaking change detected."
                    if actual_max > 1.0
                    else "confidence has negative values."
                )
            ),
        ))
    else:
        results.append(result(
            check_id, f"{col}[*].confidence", "range", "PASS",
            f"min={actual_min:.4f}, max={actual_max:.4f}",
            "max<=1.0, min>=0.0", "LOW",
        ))
    return results


def check_statistical_drift(
    contract_id: str,
    col: str,
    series: pd.Series,
    baselines: dict,
) -> list[dict]:
    """
    Compare current distribution to baseline. Emit WARN (>2σ) or FAIL (>3σ).
    Also updates baselines if this is the first run for this column.
    """
    results = []
    key = f"{contract_id}.{col}"
    numeric = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    if len(numeric) < 5:
        return []

    current_mean = float(numeric.mean())
    current_std = float(numeric.std())

    if key not in baselines:
        baselines[key] = {"mean": current_mean, "stddev": current_std, "n": int(len(numeric))}
        return []

    baseline = baselines[key]
    base_mean = baseline["mean"]
    base_std = baseline.get("stddev", 0)
    if base_std == 0:
        return []

    deviation = abs(current_mean - base_mean) / base_std
    check_id = f"{key}.drift"
    if deviation > 3:
        results.append(result(
            check_id, col, "statistical_drift", "FAIL",
            f"mean={current_mean:.4f} (baseline={base_mean:.4f}, σ={base_std:.4f})",
            f"deviation < 3σ (current={deviation:.2f}σ)",
            "HIGH", 0, [],
            message=(
                f"Statistical drift FAIL: {col} mean shifted {deviation:.1f}σ from baseline "
                f"({base_mean:.4f} → {current_mean:.4f}). "
                + (
                    "Possible scale change from 0.0–1.0 to 0–100."
                    if "confidence" in col.lower() and current_mean > 1.0
                    else ""
                )
            ),
        ))
    elif deviation > 2:
        results.append(result(
            check_id, col, "statistical_drift", "WARN",
            f"mean={current_mean:.4f} (baseline={base_mean:.4f}, σ={base_std:.4f})",
            f"deviation < 2σ (current={deviation:.2f}σ)",
            "MEDIUM", 0, [],
            message=f"Statistical drift WARNING: {col} mean shifted {deviation:.1f}σ from baseline.",
        ))

    # Update baseline incrementally
    baselines[key] = {"mean": current_mean, "stddev": current_std, "n": int(len(numeric))}
    return results


def check_referential_integrity(
    contract_id: str,
    records: list[dict],
) -> list[dict]:
    """
    For extraction records: verify entity_refs in extracted_facts point to
    entity_ids that exist in the same record's entities[].
    """
    results = []
    check_id = f"{contract_id}.extracted_facts.entity_refs.referential_integrity"
    if contract_id != "week3-document-refinery-extractions":
        return []

    bad_refs = 0
    sample_bad: list[str] = []
    for rec in records:
        entity_ids = {e["entity_id"] for e in rec.get("entities", [])
                      if isinstance(e, dict) and "entity_id" in e}
        for fact in rec.get("extracted_facts", []):
            if not isinstance(fact, dict):
                continue
            for ref in fact.get("entity_refs", []):
                if ref not in entity_ids:
                    bad_refs += 1
                    if len(sample_bad) < 5:
                        sample_bad.append(f"fact={fact.get('fact_id', '?')} ref={ref}")

    if bad_refs > 0:
        results.append(result(
            check_id,
            "extracted_facts[*].entity_refs",
            "referential_integrity", "FAIL",
            f"dangling_refs={bad_refs}",
            "all entity_refs in entities[]",
            "HIGH", bad_refs, sample_bad,
            message=f"{bad_refs} entity_refs in extracted_facts point to non-existent entity_ids.",
        ))
    else:
        results.append(result(
            check_id,
            "extracted_facts[*].entity_refs",
            "referential_integrity", "PASS",
            "all refs valid", "all entity_refs in entities[]", "LOW",
        ))
    return results


def check_event_monotonic_sequence(
    contract_id: str,
    records: list[dict],
) -> list[dict]:
    """Verify sequence_number is monotonically increasing per aggregate_id."""
    if contract_id != "week5-event-sourcing-platform":
        return []

    check_id = f"{contract_id}.sequence_number.monotonic"
    agg_seqs: dict[str, list[int]] = defaultdict(list)
    for r in records:
        agg_id = r.get("aggregate_id", "")
        seq = r.get("sequence_number")
        if seq is not None:
            try:
                agg_seqs[agg_id].append(int(seq))
            except (TypeError, ValueError):
                pass

    bad_aggs = []
    for agg_id, seqs in agg_seqs.items():
        for i in range(1, len(seqs)):
            if seqs[i] <= seqs[i - 1]:
                bad_aggs.append(agg_id)
                break

    if bad_aggs:
        return [result(
            check_id, "sequence_number", "monotonic_sequence", "FAIL",
            f"non_monotonic_aggregates={len(bad_aggs)}",
            "monotonically increasing per aggregate_id",
            "CRITICAL", len(bad_aggs), bad_aggs[:5],
            message=f"sequence_number is not monotonically increasing for {len(bad_aggs)} aggregates.",
        )]
    return [result(
        check_id, "sequence_number", "monotonic_sequence", "PASS",
        "all sequences monotonic", "monotonically increasing per aggregate_id", "LOW",
    )]


def check_temporal_order(
    contract_id: str,
    col_before: str,
    col_after: str,
    records: list[dict],
) -> list[dict]:
    """Verify col_after >= col_before for every record."""
    check_id = f"{contract_id}.{col_after}.temporal_order"
    bad = 0
    for rec in records:
        t1 = rec.get(col_before)
        t2 = rec.get(col_after)
        if t1 and t2 and isinstance(t1, str) and isinstance(t2, str):
            if t2 < t1:
                bad += 1

    if bad > 0:
        return [result(
            check_id, col_after, "temporal_order", "FAIL",
            f"violations={bad}",
            f"{col_after} >= {col_before}",
            "HIGH", bad, [],
            message=f"{bad} records where {col_after} < {col_before}.",
        )]
    return [result(
        check_id, col_after, "temporal_order", "PASS",
        f"all {col_after} >= {col_before}",
        f"{col_after} >= {col_before}", "LOW",
    )]


# ---------------------------------------------------------------------------
# Inject violation helper (for demonstration)
# ---------------------------------------------------------------------------

def inject_confidence_violation(records: list[dict]) -> list[dict]:
    """
    Simulate the breaking change: confidence changed from 0.0–1.0 to 0–100.
    Applied to 30% of records for demonstration.
    """
    import copy
    records_copy = copy.deepcopy(records)
    modified = 0
    for rec in records_copy:
        for fact in rec.get("extracted_facts", []):
            if isinstance(fact, dict) and "confidence" in fact:
                if fact["confidence"] <= 1.0:
                    fact["confidence"] = round(fact["confidence"] * 100, 1)
                    modified += 1
    print(f"  [inject] Scaled {modified} confidence values to 0–100 range")
    return records_copy


# ---------------------------------------------------------------------------
# Main ValidationRunner
# ---------------------------------------------------------------------------

class ValidationRunner:
    def __init__(
        self,
        contract_path: str,
        data_path: str,
        inject_violation: bool = False,
    ):
        self.contract_path = Path(contract_path)
        self.data_path = Path(data_path)
        self.inject_violation = inject_violation

    def load_contract(self) -> dict:
        with open(self.contract_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_data(self) -> tuple[list[dict], pd.DataFrame]:
        records = []
        with open(self.data_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  [WARN] Skipping malformed line: {e}", file=sys.stderr)
        if self.inject_violation:
            records = inject_confidence_violation(records)
        df = pd.DataFrame(records)
        return records, df

    def load_baselines(self) -> dict:
        if BASELINES_PATH.exists():
            with open(BASELINES_PATH, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_baselines(self, baselines: dict) -> None:
        BASELINES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BASELINES_PATH, "w", encoding="utf-8") as f:
            json.dump(baselines, f, indent=2)

    def run(self, output_path: str | None = None) -> dict:
        print(f"\n[ValidationRunner]")
        print(f"  Contract : {self.contract_path}")
        print(f"  Data     : {self.data_path}")
        if self.inject_violation:
            print("  Mode     : INJECTED VIOLATION (confidence scale 0-100)")

        contract = self.load_contract()
        records, df = self.load_data()

        contract_id = contract.get("id", "unknown")
        snapshot_id = sha256_file(self.data_path)
        run_ts = now_iso()
        ts = ts_slug()

        schema = contract.get("schema", {})
        all_results: list[dict] = []
        baselines = self.load_baselines()

        # ---- per-column checks ----
        for col, clause in schema.items():
            if col not in df.columns:
                all_results.append(error_result(
                    f"{contract_id}.{col}",
                    col, "missing_column",
                    f"Column '{col}' not found in data. Expected by contract.",
                ))
                continue

            series = df[col]
            dtype = clause.get("type", "string")

            if dtype in ("array", "object"):
                # Delegate to nested checks
                if col in ("extracted_facts", "entities", "nodes", "edges", "code_refs"):
                    nested = check_nested_confidence(contract_id, col, records)
                    all_results.extend(nested)
                required_check = check_required(contract_id, col, clause, series)
                all_results.append(required_check)
                continue

            all_results.append(check_required(contract_id, col, clause, series))
            all_results.append(check_unique(contract_id, col, clause, series))
            all_results.append(check_format(contract_id, col, clause, series))
            all_results.append(check_pattern(contract_id, col, clause, series))
            all_results.append(check_enum(contract_id, col, clause, series))
            all_results.append(check_range(contract_id, col, clause, series))

            # Statistical drift for numeric columns
            if dtype in ("number", "integer"):
                drift = check_statistical_drift(contract_id, col, series, baselines)
                all_results.extend(drift)

        # ---- cross-record checks ----
        if contract_id == "week3-document-refinery-extractions":
            all_results.extend(check_referential_integrity(contract_id, records))

        if contract_id == "week5-event-sourcing-platform":
            all_results.extend(check_event_monotonic_sequence(contract_id, records))
            all_results.extend(
                check_temporal_order(contract_id, "occurred_at", "recorded_at", records)
            )

        if contract_id == "langsmith-traces":
            all_results.extend(
                check_temporal_order(contract_id, "start_time", "end_time", records)
            )

        # ---- update baselines ----
        self.save_baselines(baselines)

        # ---- aggregate ----
        passed = sum(1 for r in all_results if r["status"] == "PASS")
        failed = sum(1 for r in all_results if r["status"] == "FAIL")
        warned = sum(1 for r in all_results if r["status"] == "WARN")
        errored = sum(1 for r in all_results if r["status"] == "ERROR")

        report = {
            "report_id": str(uuid.uuid4()),
            "contract_id": contract_id,
            "snapshot_id": snapshot_id,
            "run_timestamp": run_ts,
            "injected_violation": self.inject_violation,
            "total_checks": len(all_results),
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "errored": errored,
            "results": all_results,
        }

        if output_path:
            out = Path(output_path)
        else:
            out = ROOT / "validation_reports" / f"{contract_id}_{ts}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"  Report   : {out.relative_to(ROOT)}")
        print(f"  Results  : PASS={passed} FAIL={failed} WARN={warned} ERROR={errored}")
        if failed:
            print("  !! VIOLATIONS DETECTED !!")
            for r in all_results:
                if r["status"] == "FAIL":
                    print(f"     [{r['severity']}] {r['check_id']}: {r['message'][:120]}")
        return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ValidationRunner — execute contract checks against a JSONL dataset"
    )
    parser.add_argument("--contract", required=True, help="Path to Bitol YAML contract file")
    parser.add_argument("--data", required=True, help="Path to JSONL data file")
    parser.add_argument(
        "--output", default=None,
        help="Path for the output validation report JSON (default: auto-named in validation_reports/)"
    )
    parser.add_argument(
        "--inject-violation",
        action="store_true",
        help="Inject a confidence scale violation (0-100) to demonstrate drift detection",
    )
    args = parser.parse_args()

    runner = ValidationRunner(
        contract_path=args.contract,
        data_path=args.data,
        inject_violation=args.inject_violation,
    )
    runner.run(output_path=args.output)


if __name__ == "__main__":
    main()
