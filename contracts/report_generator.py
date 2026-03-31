#!/usr/bin/env python3
"""
ReportGenerator — Phase 4B
============================
Auto-generates the Enforcer Report from live validation data:
  - Reads all reports from validation_reports/
  - Reads violation_log/violations.jsonl
  - Reads validation_reports/ai_metrics.json
  - Computes the Data Health Score
  - Writes enforcer_report/report_data.json
  - Writes enforcer_report/report_<date>.md (human-readable Markdown)

Usage
-----
  python contracts/report_generator.py
  python contracts/report_generator.py --output enforcer_report/report_data.json
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
VALIDATION_DIR = ROOT / "validation_reports"
VIOLATION_LOG = ROOT / "violation_log" / "violations.jsonl"
AI_METRICS = ROOT / "validation_reports" / "ai_metrics.json"
ENFORCER_DIR = ROOT / "enforcer_report"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_validation_reports() -> list[dict]:
    """Load all JSON validation reports from validation_reports/."""
    reports = []
    for p in sorted(VALIDATION_DIR.glob("*.json")):
        if p.name == "ai_metrics.json":
            continue
        try:
            with open(p, encoding="utf-8") as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return reports


def load_violations() -> list[dict]:
    """Load all violation records from violation_log/violations.jsonl."""
    if not VIOLATION_LOG.exists():
        return []
    records = []
    with open(VIOLATION_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def load_ai_metrics() -> dict:
    if AI_METRICS.exists():
        with open(AI_METRICS, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {}


# ---------------------------------------------------------------------------
# Health score computation
# ---------------------------------------------------------------------------

def compute_health_score(reports: list[dict], violations: list[dict]) -> tuple[int, str]:
    """
    Formula: (checks_passed / total_checks) × 100,
    adjusted down by 20 points per CRITICAL violation.
    Clamp to [0, 100].
    """
    if not reports:
        return 100, "No validation data available. Score assumed 100."

    total_checks = sum(r.get("total_checks", 0) for r in reports)
    total_passed = sum(r.get("passed", 0) for r in reports)

    if total_checks == 0:
        return 100, "No checks executed."

    raw = (total_passed / total_checks) * 100

    critical_violations = sum(
        1 for v in violations
        if v.get("severity") in ("CRITICAL",)
    )
    adjusted = raw - (critical_violations * 20)
    score = max(0, min(100, int(round(adjusted))))

    narrative = (
        f"{score}/100 — "
        + (
            "Healthy: all major checks passing with no critical violations."
            if score >= 90
            else (
                f"Degraded: {critical_violations} critical violation(s) detected. "
                "Immediate action required."
                if score < 60
                else "Caution: minor violations present. Review recommended."
            )
        )
    )
    return score, narrative


# ---------------------------------------------------------------------------
# Top violations summary
# ---------------------------------------------------------------------------

def top_violations(violations: list[dict], n: int = 3) -> list[dict]:
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "ERROR": 4}
    sorted_v = sorted(
        violations,
        key=lambda v: severity_order.get(v.get("severity", "LOW"), 4),
    )
    result = []
    for v in sorted_v[:n]:
        contract = v.get("contract_id", "unknown")
        col = v.get("column_name", "unknown")
        msg = v.get("message", "")
        blast = v.get("blast_radius", {})
        affected = blast.get("affected_nodes", [])
        result.append({
            "violation_id": v.get("violation_id"),
            "check_id": v.get("check_id"),
            "severity": v.get("severity"),
            "system": contract,
            "field": col,
            "message": msg,
            "downstream_impact": (
                f"Affects {len(affected)} downstream node(s): "
                f"{', '.join(affected[:3])}"
                if affected
                else "No downstream consumers identified in lineage graph."
            ),
        })
    return result


# ---------------------------------------------------------------------------
# Schema changes summary
# ---------------------------------------------------------------------------

def load_schema_evolution_reports() -> list[dict]:
    """Load schema evolution reports from validation_reports/."""
    reports = []
    for p in sorted(VALIDATION_DIR.glob("schema_evolution_*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return reports


def schema_changes_summary(evo_reports: list[dict]) -> list[dict]:
    summary = []
    for r in evo_reports:
        for c in r.get("changes", []):
            summary.append({
                "contract_id": r.get("contract_id"),
                "change_type": c.get("change_type"),
                "column": c.get("column"),
                "backward_compatible": c.get("backward_compatible"),
                "compatibility_verdict": r.get("compatibility_verdict"),
                "required_action": c.get("required_action", ""),
            })
    return summary


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------

def generate_recommended_actions(
    violations: list[dict],
    health_score: int,
    ai_metrics: dict,
) -> list[dict]:
    actions = []
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    for v in sorted(violations, key=lambda x: severity_order.get(x.get("severity", "LOW"), 4)):
        if len(actions) >= 3:
            break
        col = v.get("column_name", "unknown")
        contract = v.get("contract_id", "unknown")
        check = v.get("check_id", "")
        blast = v.get("blast_radius", {})
        pipelines = blast.get("affected_pipelines", [])
        blame = v.get("blame_chain", [{}])
        file_path = blame[0].get("file_path", "unknown") if blame else "unknown"

        actions.append({
            "priority": len(actions) + 1,
            "severity": v.get("severity"),
            "action": (
                f"Fix field '{col}' in contract '{contract}': "
                f"{v.get('message', '')[:200]}. "
                f"Locate change in {file_path} and revert or update contract clause "
                f"'{check}'."
            ),
            "affected_pipelines": pipelines,
        })

    # AI-specific actions
    ai_drift = (ai_metrics.get("embedding_drift") or {}).get("status")
    ai_llm = (ai_metrics.get("llm_output_schema") or {}).get("trend")
    if ai_drift == "FAIL" and len(actions) < 3:
        actions.append({
            "priority": len(actions) + 1,
            "severity": "HIGH",
            "action": (
                "Investigate embedding drift in extracted_facts[*].text. "
                "Re-run contracts/ai_extensions.py --set-baseline after confirming "
                "the distribution shift is intentional."
            ),
            "affected_pipelines": ["week3-document-extraction-pipeline"],
        })
    if ai_llm == "rising" and len(actions) < 3:
        actions.append({
            "priority": len(actions) + 1,
            "severity": "MEDIUM",
            "action": (
                "LLM output schema violation rate is rising. "
                "Review recent prompt changes in src/week2/courtroom.py "
                "and audit the last 50 verdict_records for schema conformance."
            ),
            "affected_pipelines": ["week2-evaluation-pipeline"],
        })

    # Default if no violations
    if not actions:
        actions.append({
            "priority": 1,
            "severity": "LOW",
            "action": (
                "System is healthy. Run contracts/generator.py on all outputs "
                "weekly to keep contracts up to date with production data."
            ),
            "affected_pipelines": [],
        })

    return actions[:3]


# ---------------------------------------------------------------------------
# AI risk assessment
# ---------------------------------------------------------------------------

def ai_risk_assessment(ai_metrics: dict) -> dict:
    drift = ai_metrics.get("embedding_drift") or {}
    prompt = ai_metrics.get("prompt_input_validation") or {}
    llm_out = ai_metrics.get("llm_output_schema") or {}
    trace = ai_metrics.get("trace_schema") or {}

    embedding_ok = drift.get("status") in ("PASS", "BASELINE_SET", None)
    prompt_ok = prompt.get("status") in ("PASS", None)
    llm_ok = llm_out.get("status") in ("PASS", None)
    trace_ok = trace.get("status") in ("PASS", None)

    overall_ok = embedding_ok and prompt_ok and llm_ok and trace_ok

    return {
        "overall_ai_status": "GREEN" if overall_ok else "AMBER",
        "embedding_drift_status": drift.get("status", "NOT_RUN"),
        "embedding_drift_score": drift.get("drift_score"),
        "embedding_threshold": drift.get("threshold", 0.15),
        "prompt_input_violation_rate": prompt.get("violation_rate"),
        "llm_output_violation_rate": llm_out.get("violation_rate"),
        "llm_output_trend": llm_out.get("trend", "stable"),
        "trace_schema_status": trace.get("status", "NOT_RUN"),
        "narrative": (
            "All AI contract checks are within acceptable bounds. "
            "The system is consuming reliable data."
            if overall_ok
            else (
                "One or more AI contract checks require attention. "
                "Review the details above and run ai_extensions.py for the latest metrics."
            )
        ),
    }


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------

def build_report() -> dict:
    reports = load_validation_reports()
    violations = load_violations()
    ai_metrics = load_ai_metrics()
    evo_reports = load_schema_evolution_reports()

    health_score, health_narrative = compute_health_score(reports, violations)
    top_viols = top_violations(violations)
    schema_changes = schema_changes_summary(evo_reports)
    actions = generate_recommended_actions(violations, health_score, ai_metrics)
    ai_risk = ai_risk_assessment(ai_metrics)

    severity_counts: Counter = Counter()
    for v in violations:
        severity_counts[v.get("severity", "UNKNOWN")] += 1

    total_checks = sum(r.get("total_checks", 0) for r in reports)
    total_passed = sum(r.get("passed", 0) for r in reports)
    total_failed = sum(r.get("failed", 0) for r in reports)
    total_warned = sum(r.get("warned", 0) for r in reports)

    return {
        "report_id": str(uuid.uuid4()),
        "generated_at": now_iso(),
        "report_date": today_str(),
        "generated_by": "ReportGenerator v1.0.0 (auto-generated from live validation data)",
        "data_health_score": health_score,
        "health_narrative": health_narrative,
        "validation_summary": {
            "total_checks": total_checks,
            "passed": total_passed,
            "failed": total_failed,
            "warned": total_warned,
            "reports_analyzed": len(reports),
        },
        "violations_this_week": {
            "total": len(violations),
            "by_severity": dict(severity_counts),
            "top_violations": top_viols,
        },
        "schema_changes_detected": schema_changes,
        "ai_risk_assessment": ai_risk,
        "recommended_actions": actions,
    }


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def write_markdown_report(report: dict, out_path: Path) -> None:
    lines = [
        f"# Data Contract Enforcer — Enforcer Report",
        f"**Generated:** {report['generated_at']}  ",
        f"**Note:** This report is auto-generated from live validation data.\n",
        "---",
        "## 1. Data Health Score",
        f"**Score: {report['data_health_score']}/100**",
        "",
        report["health_narrative"],
        "",
        "### Validation Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Checks Run | {report['validation_summary']['total_checks']} |",
        f"| Passed           | {report['validation_summary']['passed']} |",
        f"| Failed           | {report['validation_summary']['failed']} |",
        f"| Warned           | {report['validation_summary']['warned']} |",
        f"| Reports Analyzed | {report['validation_summary']['reports_analyzed']} |",
        "",
        "## 2. Violations This Week",
    ]

    sev = report["violations_this_week"]["by_severity"]
    if sev:
        lines += [
            "| Severity | Count |",
            "|----------|-------|",
        ] + [f"| {s} | {c} |" for s, c in sorted(sev.items())]
    else:
        lines.append("_No violations detected this week._")

    lines.append("")
    lines.append("### Most Significant Violations")
    for v in report["violations_this_week"]["top_violations"]:
        lines += [
            f"**[{v['severity']}] {v['system']} → `{v['field']}`**",
            f"> {v['message']}",
            f"*Downstream impact:* {v['downstream_impact']}",
            "",
        ]

    lines += [
        "## 3. Schema Changes Detected",
    ]
    changes = report["schema_changes_detected"]
    if changes:
        lines += [
            "| Contract | Column | Change Type | Compatible | Action Required |",
            "|----------|--------|-------------|------------|-----------------|",
        ] + [
            f"| {c['contract_id']} | `{c['column']}` | `{c['change_type']}` | "
            f"{'Yes' if c['backward_compatible'] else '**NO — BREAKING**'} | "
            f"{c['required_action'][:80]} |"
            for c in changes
        ]
    else:
        lines.append("_No schema changes detected in this period. Run schema_analyzer.py to check._")

    ai = report["ai_risk_assessment"]
    lines += [
        "",
        "## 4. AI System Risk Assessment",
        f"**Overall AI Status:** {ai['overall_ai_status']}",
        "",
        f"| Check | Value | Status |",
        f"|-------|-------|--------|",
        f"| Embedding Drift Score | {ai.get('embedding_drift_score', 'N/A')} "
        f"(threshold={ai['embedding_threshold']}) | {ai['embedding_drift_status']} |",
        f"| Prompt Input Violation Rate | {ai.get('prompt_input_violation_rate', 'N/A')} | — |",
        f"| LLM Output Violation Rate | {ai.get('llm_output_violation_rate', 'N/A')} | "
        f"trend={ai['llm_output_trend']} |",
        f"| Trace Schema | — | {ai['trace_schema_status']} |",
        "",
        ai["narrative"],
        "",
        "## 5. Recommended Actions",
        "",
    ]

    for action in report["recommended_actions"]:
        lines += [
            f"### Action {action['priority']} [{action['severity']}]",
            action["action"],
            "",
        ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="ReportGenerator — auto-generate the Enforcer Report from live validation data"
    )
    parser.add_argument(
        "--output",
        default=str(ENFORCER_DIR / "report_data.json"),
        help="Output path for report_data.json",
    )
    args = parser.parse_args()

    print("\n[ReportGenerator]")
    print(f"  Scanning {VALIDATION_DIR} for validation reports …")

    report = build_report()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report → {out.relative_to(ROOT)}")

    md_out = out.parent / f"report_{today_str()}.md"
    write_markdown_report(report, md_out)
    print(f"  Markdown   → {md_out.relative_to(ROOT)}")

    print(f"\n  Data Health Score : {report['data_health_score']}/100")
    print(f"  Health Narrative  : {report['health_narrative']}")
    print(f"  Total Violations  : {report['violations_this_week']['total']}")
    print(f"  AI Status         : {report['ai_risk_assessment']['overall_ai_status']}")
    print(f"  Top Action        : {report['recommended_actions'][0]['action'][:100]}…")


if __name__ == "__main__":
    main()
