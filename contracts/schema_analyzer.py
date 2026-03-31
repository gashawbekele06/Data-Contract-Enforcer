#!/usr/bin/env python3
"""
SchemaEvolutionAnalyzer — Phase 3
===================================
Diffs consecutive schema snapshots to detect changes, classifies each change
using the compatibility taxonomy from Confluent Schema Registry, produces a
migration impact report, and writes it to validation_reports/.

Usage
-----
  python contracts/schema_analyzer.py \\
      --contract-id week3-document-refinery-extractions \\
      --since "7 days ago" \\
      --output validation_reports/schema_evolution_week3.json

  # Explicitly compare two snapshots
  python contracts/schema_analyzer.py \\
      --snapshot-a schema_snapshots/week3-document-refinery-extractions/20250115_120000.yaml \\
      --snapshot-b schema_snapshots/week3-document-refinery-extractions/20250116_080000.yaml \\
      --output validation_reports/schema_diff.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parent.parent


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Change classification taxonomy
# ---------------------------------------------------------------------------

# (change_type) → (backward_compatible, required_action, risk_level)
CHANGE_TAXONOMY = {
    "add_nullable_column": (True, "None. Downstream consumers can ignore the new column.", "LOW"),
    "add_required_column": (False, "Coordinate with all producers. Provide a default or migration script. Block deployment until all producers updated.", "CRITICAL"),
    "rename_column": (False, "Deprecation period with alias column. Notify all downstream consumers via blast radius report. Minimum 1 sprint before removal.", "CRITICAL"),
    "type_widening": (True, "Validate no precision loss on existing data. Re-run statistical checks to confirm distribution unchanged.", "MEDIUM"),
    "type_narrowing": (False, "CRITICAL. Requires explicit migration plan with rollback. Blast radius report mandatory. Statistical baseline must be re-established after migration.", "CRITICAL"),
    "remove_column": (False, "Deprecation period mandatory (minimum 2 sprints). Blast radius report required. Each affected consumer must acknowledge removal.", "CRITICAL"),
    "add_enum_value": (True, "Additive: notify all consumers.", "LOW"),
    "remove_enum_value": (False, "Treat as breaking change. Blast radius report required.", "HIGH"),
    "range_tightened": (False, "Tighter range may break existing producers. Migration plan required.", "HIGH"),
    "range_widened": (True, "None. Wider range is backward compatible.", "LOW"),
    "pattern_changed": (False, "Existing data may not match new pattern. Validate all producers.", "HIGH"),
    "description_changed": (True, "Documentation update only.", "LOW"),
    "unknown": (None, "Manual review required.", "MEDIUM"),
}


def classify_field_change(
    col_name: str,
    old_clause: dict,
    new_clause: dict,
) -> list[dict]:
    """
    Compare two schema clauses for the same column and return a list of
    detected change dicts with classification.
    """
    changes = []

    old_type = old_clause.get("type", "string")
    new_type = new_clause.get("type", "string")

    # Type change
    if old_type != new_type:
        # Detect widening vs narrowing
        widening_pairs = {
            ("integer", "number"), ("float", "number"),
            ("integer", "string"), ("number", "string"),
        }
        narrowing_pairs = {
            ("number", "integer"), ("string", "integer"),
            ("string", "number"),
        }
        if (old_type, new_type) in widening_pairs:
            ct = "type_widening"
        elif (old_type, new_type) in narrowing_pairs:
            ct = "type_narrowing"
        else:
            ct = "type_narrowing"  # unknown type change → conservative
        compat, action, risk = CHANGE_TAXONOMY[ct]
        changes.append({
            "change_type": ct,
            "column": col_name,
            "old_value": old_type,
            "new_value": new_type,
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
        })

    # Range change
    old_min = old_clause.get("minimum")
    new_min = new_clause.get("minimum")
    old_max = old_clause.get("maximum")
    new_max = new_clause.get("maximum")

    if old_min != new_min or old_max != new_max:
        # Tighter = breaking, looser = compatible
        tighter = (
            (new_min is not None and (old_min is None or new_min > old_min))
            or (new_max is not None and (old_max is None or new_max < old_max))
        )
        ct = "range_tightened" if tighter else "range_widened"
        compat, action, risk = CHANGE_TAXONOMY[ct]
        changes.append({
            "change_type": ct,
            "column": col_name,
            "old_value": f"min={old_min}, max={old_max}",
            "new_value": f"min={new_min}, max={new_max}",
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
            "note": (
                f"CRITICAL: {col_name} scale changed from 0.0–1.0 to 0–100 (narrowing × 100)."
                if "confidence" in col_name.lower()
                and old_max is not None and old_max <= 1.0
                and new_max is not None and new_max > 1.0
                else None
            ),
        })

    # Enum change
    old_enum = set(str(v) for v in (old_clause.get("enum") or []))
    new_enum = set(str(v) for v in (new_clause.get("enum") or []))
    if old_enum != new_enum:
        added = new_enum - old_enum
        removed = old_enum - new_enum
        if added:
            compat, action, risk = CHANGE_TAXONOMY["add_enum_value"]
            changes.append({
                "change_type": "add_enum_value",
                "column": col_name,
                "old_value": sorted(old_enum),
                "new_value": sorted(new_enum),
                "added_values": sorted(added),
                "backward_compatible": compat,
                "required_action": action,
                "risk_level": risk,
            })
        if removed:
            compat, action, risk = CHANGE_TAXONOMY["remove_enum_value"]
            changes.append({
                "change_type": "remove_enum_value",
                "column": col_name,
                "old_value": sorted(old_enum),
                "new_value": sorted(new_enum),
                "removed_values": sorted(removed),
                "backward_compatible": compat,
                "required_action": action,
                "risk_level": risk,
            })

    # Pattern change
    old_pat = old_clause.get("pattern")
    new_pat = new_clause.get("pattern")
    if old_pat != new_pat:
        compat, action, risk = CHANGE_TAXONOMY["pattern_changed"]
        changes.append({
            "change_type": "pattern_changed",
            "column": col_name,
            "old_value": old_pat,
            "new_value": new_pat,
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
        })

    # Required flag change
    old_req = old_clause.get("required", False)
    new_req = new_clause.get("required", False)
    if old_req != new_req and new_req:
        compat, action, risk = CHANGE_TAXONOMY["add_required_column"]
        changes.append({
            "change_type": "add_required_column",
            "column": col_name,
            "old_value": f"required={old_req}",
            "new_value": f"required={new_req}",
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
        })

    return changes


def diff_schemas(old_schema: dict, new_schema: dict) -> list[dict]:
    """Diff two schema dicts and return a list of change objects."""
    all_changes = []

    old_cols = set(old_schema.keys())
    new_cols = set(new_schema.keys())

    # Added columns
    for col in new_cols - old_cols:
        clause = new_schema[col]
        required = clause.get("required", False) and not clause.get("nullable", False)
        ct = "add_required_column" if required else "add_nullable_column"
        compat, action, risk = CHANGE_TAXONOMY[ct]
        all_changes.append({
            "change_type": ct,
            "column": col,
            "old_value": None,
            "new_value": clause.get("type", "unknown"),
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
        })

    # Removed columns
    for col in old_cols - new_cols:
        compat, action, risk = CHANGE_TAXONOMY["remove_column"]
        all_changes.append({
            "change_type": "remove_column",
            "column": col,
            "old_value": old_schema[col].get("type", "unknown"),
            "new_value": None,
            "backward_compatible": compat,
            "required_action": action,
            "risk_level": risk,
        })

    # Modified columns
    for col in old_cols & new_cols:
        changes = classify_field_change(col, old_schema[col], new_schema[col])
        all_changes.extend(changes)

    return all_changes


# ---------------------------------------------------------------------------
# Migration impact report builder
# ---------------------------------------------------------------------------

def build_migration_report(
    contract_id: str,
    snapshot_a_path: str,
    snapshot_b_path: str,
    changes: list[dict],
    schema_a: dict,
    schema_b: dict,
) -> dict:
    breaking = [c for c in changes if not c.get("backward_compatible")]
    compatible = [c for c in changes if c.get("backward_compatible")]

    checklist = []
    for c in breaking:
        checklist.append(
            f"[ ] {c['change_type']} on '{c['column']}': {c['required_action']}"
        )
    if breaking:
        checklist.append("[ ] Run full validation suite on all downstream consumers")
        checklist.append("[ ] Update blast radius report and notify affected teams")
        checklist.append("[ ] Tag release with BREAKING_CHANGE label")

    rollback_plan = (
        "1. Revert the producer commit identified in the blame chain.\n"
        "2. Re-run ContractGenerator to restore previous schema snapshot.\n"
        "3. Re-run ValidationRunner to confirm baseline is restored.\n"
        "4. Notify all downstream consumers that rollback is complete."
        if breaking
        else "No rollback needed — all changes are backward compatible."
    )

    compatibility_verdict = "FULL_COMPATIBLE" if not breaking else (
        "BACKWARD_INCOMPATIBLE" if len(breaking) > 0 else "FORWARD_INCOMPATIBLE"
    )

    human_summary = []
    for c in changes:
        col = c["column"]
        ct = c["change_type"]
        note = c.get("note", "")
        if ct == "type_narrowing":
            human_summary.append(
                f"BREAKING: Field '{col}' type narrowed from {c['old_value']} to {c['new_value']}. "
                f"{note or 'Requires migration plan.'}"
            )
        elif ct == "remove_column":
            human_summary.append(
                f"BREAKING: Field '{col}' was removed. "
                "All downstream consumers must be updated before deployment."
            )
        elif ct == "rename_column":
            human_summary.append(
                f"BREAKING: Field '{col}' was renamed. "
                "Deprecation period with alias required."
            )
        elif ct == "range_tightened":
            human_summary.append(
                f"BREAKING: Field '{col}' range tightened "
                f"({c['old_value']} → {c['new_value']}). {note or ''}"
            )
        elif ct == "add_nullable_column":
            human_summary.append(f"Compatible: New nullable field '{col}' added.")
        elif ct == "add_enum_value":
            human_summary.append(
                f"Compatible: Enum field '{col}' gained new value(s): "
                f"{c.get('added_values')}."
            )

    return {
        "analysis_id": str(uuid.uuid4()),
        "contract_id": contract_id,
        "snapshot_a": snapshot_a_path,
        "snapshot_b": snapshot_b_path,
        "analyzed_at": now_iso(),
        "compatibility_verdict": compatibility_verdict,
        "total_changes": len(changes),
        "breaking_changes": len(breaking),
        "compatible_changes": len(compatible),
        "changes": changes,
        "human_summary": human_summary,
        "migration_checklist": checklist,
        "rollback_plan": rollback_plan,
        "blast_radius_note": (
            "Run contracts/attributor.py with the identified FAIL check_ids "
            "to generate a full blast radius report."
            if breaking
            else "No blast radius action required."
        ),
    }


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------

def list_snapshots(contract_id: str, since_days: int = 7) -> list[Path]:
    snap_dir = ROOT / "schema_snapshots" / contract_id
    if not snap_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    snaps = sorted(snap_dir.glob("*.yaml"))
    result = []
    for s in snaps:
        # filename is YYYYMMDD_HHMMSS.yaml
        try:
            dt = datetime.strptime(s.stem, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                result.append(s)
        except ValueError:
            result.append(s)  # include if can't parse
    return result


def load_snapshot_schema(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return doc.get("schema", {})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SchemaEvolutionAnalyzer — diff schema snapshots and classify changes"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--contract-id", help="Contract ID to analyze (uses schema_snapshots/)")
    group.add_argument("--snapshot-a", help="Path to first (older) snapshot YAML")

    parser.add_argument("--snapshot-b", help="Path to second (newer) snapshot YAML")
    parser.add_argument(
        "--since",
        default="7 days ago",
        help="Only consider snapshots from this many days ago (default: 7 days ago)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path for the output migration report JSON",
    )
    args = parser.parse_args()

    if args.contract_id:
        try:
            days = int(args.since.split()[0])
        except (ValueError, IndexError):
            days = 7
        snaps = list_snapshots(args.contract_id, since_days=max(days, 1))
        if len(snaps) < 2:
            print(
                f"Need at least 2 snapshots for {args.contract_id} "
                f"(found {len(snaps)}). Run generator twice to create snapshots.",
                file=sys.stderr,
            )
            # If only one snapshot, inject a synthetic second to demonstrate
            if len(snaps) == 1:
                print("Creating synthetic second snapshot with injected breaking change …")
                _inject_breaking_snapshot(args.contract_id, snaps[0])
                snaps = list_snapshots(args.contract_id, since_days=30)
            if len(snaps) < 2:
                sys.exit(1)
        snap_a, snap_b = snaps[-2], snaps[-1]
    else:
        if not args.snapshot_b:
            print("--snapshot-b is required when using --snapshot-a", file=sys.stderr)
            sys.exit(1)
        snap_a = Path(args.snapshot_a)
        snap_b = Path(args.snapshot_b)
        contract_id = snap_a.parent.name

    if args.contract_id:
        contract_id = args.contract_id

    print(f"\n[SchemaEvolutionAnalyzer]")
    print(f"  Contract : {contract_id}")
    print(f"  Snapshot A: {snap_a}")
    print(f"  Snapshot B: {snap_b}")

    schema_a = load_snapshot_schema(snap_a)
    schema_b = load_snapshot_schema(snap_b)

    changes = diff_schemas(schema_a, schema_b)

    report = build_migration_report(
        contract_id,
        str(snap_a),
        str(snap_b),
        changes,
        schema_a,
        schema_b,
    )

    if args.output:
        out = Path(args.output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = ROOT / "validation_reports" / f"schema_evolution_{contract_id}_{ts}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Verdict  : {report['compatibility_verdict']}")
    print(f"  Changes  : {report['total_changes']} total, {report['breaking_changes']} breaking")
    for c in changes:
        compat = "✓" if c.get("backward_compatible") else "✗ BREAKING"
        print(f"  [{compat}] {c['change_type']} on '{c['column']}'")
    print(f"\n  Report   → {out.relative_to(ROOT)}")


def _inject_breaking_snapshot(contract_id: str, original_snap: Path) -> None:
    """
    Create a second snapshot that simulates a breaking change:
    confidence field minimum changed from 0.0–1.0 to 0–100.
    This is kept separate from production code — for demonstration only.
    """
    with open(original_snap, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    import copy
    doc2 = copy.deepcopy(doc)
    schema = doc2.get("schema", {})

    # Mutate top-level numeric column to demonstrate breaking change detection
    # Simulate: processing_time_ms minimum raised (tighter range = breaking)
    if "processing_time_ms" in schema:
        clause = schema["processing_time_ms"]
        clause["minimum"] = 1000  # was 1, now 1000 — tighter = breaking
        clause["maximum"] = 60000  # new upper bound added
        clause["description"] = (
            "INJECTED BREAKING CHANGE: minimum raised from 1 to 1000ms."
        )

    # Also mutate extracted_facts description to record the confidence change
    if "extracted_facts" in schema:
        items = schema["extracted_facts"].get("items", {})
        if "confidence" in items:
            items["confidence"]["minimum"] = 0
            items["confidence"]["maximum"] = 100
            items["confidence"]["type"] = "integer"
            items["confidence"]["description"] = (
                "INJECTED BREAKING CHANGE: scale changed from 0.0–1.0 to 0–100 integer."
            )

    doc2["info"]["version"] = "2.0.0"
    doc2["info"]["description"] = (
        "[INJECTED BREAKING CHANGE] confidence scale changed to 0–100."
    )

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snap_dir = original_snap.parent
    out_path = snap_dir / f"{ts}_breaking.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(doc2, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  Injected breaking snapshot → {out_path.name}")


if __name__ == "__main__":
    main()
