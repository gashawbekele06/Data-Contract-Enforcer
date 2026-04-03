#!/usr/bin/env python3
"""
Data Contract Enforcer — Full Orchestration Pipeline
=====================================================
Runs all phases of the Week 7 Data Contract Enforcer in sequence:

  Phase 1  — ContractGenerator: generate Bitol YAML + dbt schema.yml for all weeks
  Phase 2A — ValidationRunner:  validate each week's JSONL against its contract
  Phase 2B — ViolationAttributor: trace FAILs to originating commits via registry + lineage
  Phase 3  — SchemaEvolutionAnalyzer: diff schema snapshots, classify changes
  Phase 4  — AI Contract Extensions: embedding drift, prompt validation, LLM output
  Phase 5  — ReportGenerator: produce enforcer_report/report_data.json + report.md

Usage
-----
  python main.py                          # run full pipeline
  python main.py --phase generate         # Phase 1 only
  python main.py --phase validate         # Phase 2A only
  python main.py --phase attribute        # Phase 2B only
  python main.py --phase evolve           # Phase 3 only
  python main.py --phase ai              # Phase 4 only
  python main.py --phase report          # Phase 5 only
  python main.py --inject-violation      # inject confidence scale violation for demo
  python main.py --mode AUDIT            # validation mode (AUDIT|WARN|ENFORCE)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent

# Dataset definitions: (stem, source_path, contract_id, output_stem)
DATASETS = [
    {
        "stem": "intent_records",
        "source": ROOT / "outputs" / "week1" / "intent_records.jsonl",
        "contract_id": "week1-intent-code-correlator",
        "contract_file": "week1_intent_records.yaml",
        "label": "Week 1 — Intent Records",
    },
    {
        "stem": "verdicts",
        "source": ROOT / "outputs" / "week2" / "verdicts.jsonl",
        "contract_id": "week2-digital-courtroom",
        "contract_file": "week2_verdicts.yaml",
        "label": "Week 2 — Verdict Records",
    },
    {
        "stem": "extractions",
        "source": ROOT / "outputs" / "week3" / "extractions.jsonl",
        "contract_id": "week3-document-refinery-extractions",
        "contract_file": "week3_extractions.yaml",
        "label": "Week 3 — Extraction Records",
    },
    {
        "stem": "lineage_snapshots",
        "source": ROOT / "outputs" / "week4" / "lineage_snapshots.jsonl",
        "contract_id": "week4-brownfield-cartographer",
        "contract_file": "week4_lineage_snapshots.yaml",
        "label": "Week 4 — Lineage Snapshots",
    },
    {
        "stem": "events",
        "source": ROOT / "outputs" / "week5" / "events.jsonl",
        "contract_id": "week5-event-sourcing-platform",
        "contract_file": "week5_events.yaml",
        "label": "Week 5 — Event Records",
    },
    {
        "stem": "runs",
        "source": ROOT / "outputs" / "traces" / "runs.jsonl",
        "contract_id": "langsmith-traces",
        "contract_file": "runs.yaml",
        "label": "LangSmith — Trace Records",
    },
]

LINEAGE_PATH = ROOT / "outputs" / "week4" / "lineage_snapshots.jsonl"
REGISTRY_PATH = ROOT / "contract_registry" / "subscriptions.yaml"
GENERATED_CONTRACTS_DIR = ROOT / "generated_contracts"
VALIDATION_REPORTS_DIR = ROOT / "validation_reports"
VIOLATION_LOG = ROOT / "violation_log" / "violations.jsonl"


def header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Phase 1 — ContractGenerator
# ---------------------------------------------------------------------------

def phase_generate(annotate: bool = False) -> None:
    header("Phase 1 — ContractGenerator")
    from contracts.generator import ContractGenerator

    for ds in DATASETS:
        source = ds["source"]
        if not source.exists():
            print(f"  [SKIP] {ds['label']}: source not found at {source}")
            continue
        gen = ContractGenerator(
            source_path=str(source),
            output_dir=str(GENERATED_CONTRACTS_DIR),
            lineage_path=str(LINEAGE_PATH) if LINEAGE_PATH.exists() else None,
            annotate=annotate,
        )
        gen.run()


# ---------------------------------------------------------------------------
# Phase 2A — ValidationRunner
# ---------------------------------------------------------------------------

def phase_validate(inject_violation: bool = False, mode: str = "ENFORCE") -> list[str]:
    """Returns list of validation report paths that contain FAILs."""
    header("Phase 2A — ValidationRunner")
    from contracts.runner import ValidationRunner

    report_paths_with_failures = []

    for ds in DATASETS:
        source = ds["source"]
        contract_file = GENERATED_CONTRACTS_DIR / ds["contract_file"]

        if not source.exists():
            print(f"  [SKIP] {ds['label']}: source not found")
            continue
        if not contract_file.exists():
            print(f"  [SKIP] {ds['label']}: contract not found at {contract_file}")
            continue

        out_path = VALIDATION_REPORTS_DIR / f"{ds['contract_id']}_{ts()}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Only inject violation on the week3 dataset if requested
        inject = inject_violation and ds["stem"] == "extractions"

        runner = ValidationRunner(
            contract_path=str(contract_file),
            data_path=str(source),
            inject_violation=inject,
            mode=mode,
        )
        report = runner.run(output_path=str(out_path))

        if report.get("failed", 0) > 0:
            report_paths_with_failures.append(str(out_path))

    return report_paths_with_failures


# ---------------------------------------------------------------------------
# Phase 2B — ViolationAttributor
# ---------------------------------------------------------------------------

def phase_attribute(report_paths: list[str]) -> None:
    header("Phase 2B — ViolationAttributor")
    from contracts.attributor import (
        attribute_violation,
        append_violation,
        load_latest_lineage,
        load_registry,
    )

    if not report_paths:
        print("  No validation failures to attribute.")
        return

    lineage = load_latest_lineage(str(LINEAGE_PATH))
    registry = load_registry(REGISTRY_PATH)

    subs = registry.get("subscriptions", []) if registry else []
    print(f"  Registry loaded: {len(subs)} subscriptions")

    for report_path in report_paths:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        contract_id = report.get("contract_id", "unknown")
        failures = [r for r in report.get("results", []) if r["status"] == "FAIL"]
        if not failures:
            continue

        print(f"\n  Attributing {len(failures)} failure(s) in {contract_id}")
        for check_result in failures:
            violation = attribute_violation(check_result, contract_id, lineage, registry)
            append_violation(violation)
            br = violation.get("blast_radius", {})
            reg_subs = br.get("registry_subscribers", [])
            print(f"    ✗ {check_result['check_id'][:80]}")
            print(f"      Blast source: {br.get('blast_radius_source')}")
            print(f"      Subscribers : {[s['subscriber_id'] for s in reg_subs]}")


# ---------------------------------------------------------------------------
# Phase 3 — SchemaEvolutionAnalyzer
# ---------------------------------------------------------------------------

def phase_evolve() -> None:
    header("Phase 3 — SchemaEvolutionAnalyzer")
    import sys
    from contracts.schema_analyzer import (
        list_snapshots, load_snapshot_schema, diff_schemas,
        build_migration_report, _inject_breaking_snapshot,
    )

    contract_ids = [
        "week3-document-refinery-extractions",
        "week5-event-sourcing-platform",
        "week1-intent-code-correlator",
        "week2-digital-courtroom",
        "week4-brownfield-cartographer",
        "langsmith-traces",
    ]

    for contract_id in contract_ids:
        snap_dir = ROOT / "schema_snapshots" / contract_id
        if not snap_dir.exists():
            print(f"  [SKIP] No snapshots for {contract_id}")
            continue

        snaps = list_snapshots(contract_id, since_days=30)
        if len(snaps) < 2:
            if len(snaps) == 1:
                print(f"  [INFO] {contract_id}: 1 snapshot — injecting synthetic breaking change for demo")
                _inject_breaking_snapshot(contract_id, snaps[0])
                snaps = list_snapshots(contract_id, since_days=30)
            if len(snaps) < 2:
                print(f"  [SKIP] {contract_id}: still only {len(snaps)} snapshot(s) after injection")
                continue

        snap_a, snap_b = snaps[-2], snaps[-1]
        schema_a = load_snapshot_schema(snap_a)
        schema_b = load_snapshot_schema(snap_b)
        changes = diff_schemas(schema_a, schema_b)
        report = build_migration_report(contract_id, str(snap_a), str(snap_b),
                                        changes, schema_a, schema_b)

        out_path = VALIDATION_REPORTS_DIR / f"schema_evolution_{contract_id}_{ts()}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(report, f, indent=2)

        print(f"  {contract_id}: {report['compatibility_verdict']} | "
              f"{report['total_changes']} changes, {report['breaking_changes']} breaking → "
              f"{out_path.name}")


# ---------------------------------------------------------------------------
# Phase 4 — AI Contract Extensions
# ---------------------------------------------------------------------------

def phase_ai() -> None:
    header("Phase 4 — AI Contract Extensions")
    from contracts.ai_extensions import run_all_extensions, load_jsonl

    extractions = load_jsonl(ROOT / "outputs" / "week3" / "extractions.jsonl")
    verdicts = load_jsonl(ROOT / "outputs" / "week2" / "verdicts.jsonl")
    traces = load_jsonl(ROOT / "outputs" / "traces" / "runs.jsonl")

    metrics = run_all_extensions(extractions, verdicts, traces)

    ai_metrics_path = VALIDATION_REPORTS_DIR / "ai_metrics.json"
    ai_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ai_metrics_path, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(metrics, f, indent=2)
    print(f"  AI metrics → {ai_metrics_path.name}")
    print(f"  Overall AI status: {metrics['overall_status']}")


# ---------------------------------------------------------------------------
# Phase 5 — ReportGenerator
# ---------------------------------------------------------------------------

def phase_report() -> None:
    header("Phase 5 — ReportGenerator")
    from contracts.report_generator import build_report, write_markdown_report, today_str
    from pathlib import Path as _Path
    import json as _json

    report = build_report()

    enforcer_dir = ROOT / "enforcer_report"
    enforcer_dir.mkdir(parents=True, exist_ok=True)

    out_json = enforcer_dir / "report_data.json"
    with open(out_json, "w", encoding="utf-8") as f:
        _json.dump(report, f, indent=2)
    print(f"  JSON report   → {out_json.relative_to(ROOT)}")

    out_md = enforcer_dir / f"report_{today_str()}.md"
    write_markdown_report(report, out_md)
    print(f"  Markdown      → {out_md.relative_to(ROOT)}")

    print(f"\n  Data Health Score : {report['data_health_score']}/100")
    print(f"  Health Narrative  : {report['health_narrative']}")
    print(f"  Total Violations  : {report['violations_this_week']['total']}")
    print(f"  AI Status         : {report['ai_risk_assessment']['overall_ai_status']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Data Contract Enforcer — full orchestration pipeline"
    )
    parser.add_argument(
        "--phase",
        choices=["generate", "validate", "attribute", "evolve", "ai", "report", "all"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Enable LLM column annotation in ContractGenerator (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--inject-violation",
        action="store_true",
        help="Inject a confidence scale violation (0–100) into week3 data for demonstration",
    )
    parser.add_argument(
        "--mode",
        choices=["AUDIT", "WARN", "ENFORCE"],
        default="AUDIT",
        help="Validation enforcement mode (default: AUDIT)",
    )
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"  Data Contract Enforcer — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {args.mode}  |  Phase: {args.phase}")
    print(f"{'#'*60}")

    phase = args.phase

    if phase in ("generate", "all"):
        phase_generate(annotate=args.annotate)

    if phase in ("validate", "all"):
        failed_reports = phase_validate(inject_violation=args.inject_violation, mode=args.mode)
    else:
        # Collect existing reports with failures for attribution
        failed_reports = []
        for p in sorted(VALIDATION_REPORTS_DIR.glob("*.json")):
            if "schema_evolution" in p.name or "ai_metrics" in p.name:
                continue
            try:
                with open(p) as f:
                    r = json.load(f)
                if r.get("failed", 0) > 0:
                    failed_reports.append(str(p))
            except Exception:
                pass

    if phase in ("attribute", "all"):
        phase_attribute(failed_reports)

    if phase in ("evolve", "all"):
        phase_evolve()

    if phase in ("ai", "all"):
        phase_ai()

    if phase in ("report", "all"):
        phase_report()

    print(f"\n{'#'*60}")
    print("  Pipeline complete.")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
