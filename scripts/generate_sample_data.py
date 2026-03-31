#!/usr/bin/env python3
"""
generate_sample_data.py — Migration & synthetic data generator for Weeks 1–5.

Produces JSONL output files conforming to the challenge schemas in outputs/:
  outputs/week1/intent_records.jsonl      (50 records)
  outputs/week2/verdicts.jsonl            (50 records)
  outputs/week3/extractions.jsonl         (50 records, adapted from real ledger)
  outputs/week4/lineage_snapshots.jsonl   (10 records, adapted from real graph)
  outputs/week5/events.jsonl              (100 records, adapted from real events)
  outputs/traces/runs.jsonl               (50 records, synthetic)

Real source paths (adapt as needed):
  WEEK3_LEDGER  = .refinery/extraction_ledger.jsonl (25 records)
  WEEK4_GRAPH   = .cartography/lineage_graph.json
  WEEK5_EVENTS  = data/events.jsonl (632 records)

Usage:
  python scripts/generate_sample_data.py
"""

import hashlib
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUTS = ROOT / "outputs"

# Paths to real prior-week data
WEEK3_LEDGER = Path(
    r"C:\Users\gasha\OneDrive\Desktop\TRP1\Week 3"
    r"\week3-document-intelligence-refinery\.refinery\extraction_ledger.jsonl"
)
WEEK4_GRAPH = Path(
    r"C:\Users\gasha\OneDrive\Desktop\TRP1\Week 4"
    r"\TRP1-Week4-Codebase-Intelligence-Systems\.cartography\lineage_graph.json"
)
WEEK5_EVENTS = Path(
    r"C:\Users\gasha\OneDrive\Desktop\TRP1\Week 5"
    r"\Agentic-Event-Store-Enterprise-Audit-Infrastructure\data\events.jsonl"
)

random.seed(42)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gen_uuid() -> str:
    return str(uuid.uuid4())


def gen_sha256(content: str = "") -> str:
    raw = content.encode() if content else uuid.uuid4().bytes
    if isinstance(raw, str):
        raw = raw.encode()
    return hashlib.sha256(raw).hexdigest()


def iso_ts(base: datetime | None = None, delta_s: int = 0) -> str:
    if base is None:
        base = datetime(2025, 1, 15, 14, 23, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


INTENTS = [
    "Extract financial facts and entities from PDF annual reports",
    "Validate extracted facts conform to confidence threshold rules",
    "Map data lineage from source documents to downstream consumers",
    "Ingest and replay audit events with causal ordering guarantees",
    "Score LLM outputs against structured evaluation rubrics",
    "Detect schema drift in inter-system data contracts",
    "Attribute data quality violations to originating code changes",
    "Generate Bitol-compatible YAML contracts from JSONL datasets",
    "Enforce confidence field range constraints across all week outputs",
    "Profile statistical distributions of numeric columns in data pipelines",
]

FILES = [
    "src/week1/correlator.py",
    "src/week2/courtroom.py",
    "src/week3/extractor.py",
    "src/week3/fact_parser.py",
    "src/week4/cartographer.py",
    "src/week4/graph_builder.py",
    "src/week5/event_store.py",
    "src/week5/aggregate.py",
    "src/week7/contracts/generator.py",
    "src/week7/contracts/runner.py",
]

GOV_TAGS = ["auth", "pii", "billing", "audit", "compliance", "lineage", "extraction"]

ENTITY_TYPES = ["PERSON", "ORG", "LOCATION", "DATE", "AMOUNT", "OTHER"]

ENTITY_POOL = [
    ("CBE", "ORG", "Commercial Bank of Ethiopia"),
    ("Ethiopian Ministry of Finance", "ORG", "Ethiopian Ministry of Finance"),
    ("NBE", "ORG", "National Bank of Ethiopia"),
    ("Addis Ababa", "LOCATION", "Addis Ababa, Ethiopia"),
    ("Q4 2023", "DATE", "2023-10-01/2023-12-31"),
    ("2.3 billion ETB", "AMOUNT", "2300000000 ETB"),
    ("14.2%", "AMOUNT", "0.142"),
    ("Abebe Girma", "PERSON", "Abebe Girma"),
    ("FY2023", "DATE", "2023-07-08/2024-07-07"),
    ("ISO 27001", "OTHER", "ISO/IEC 27001:2022"),
    ("Basel III", "OTHER", "Basel III Capital Framework"),
    ("300 million USD", "AMOUNT", "300000000 USD"),
]

FACT_TEMPLATES = [
    "The bank reported a net profit of {amount} for fiscal year {year}.",
    "Total assets increased by {pct}% compared to the previous year.",
    "Non-performing loan ratio stood at {ratio}% as of period end.",
    "Capital adequacy ratio was maintained at {cap}%, above the regulatory minimum.",
    "The institution employs approximately {n} full-time staff across all branches.",
    "Operating expenses grew by {pct}% year-over-year driven by IT investment.",
    "Loan portfolio expanded to {amount} with agricultural sector leading growth.",
    "Customer deposits reached {amount}, reflecting a {pct}% annual increase.",
    "Return on equity for the period was {pct}%, outperforming peer median.",
    "The audit committee confirmed compliance with all NBE directives.",
]

DOC_NAMES = [
    "CBE_Annual_Report_2023-24.pdf",
    "CBE_Annual_Report_2022-23.pdf",
    "CBE_Annual_Report_2021-22.pdf",
    "CBE_Annual_Report_2020-21.pdf",
    "CBE_Annual_Report_2019-20.pdf",
    "CBE_Annual_Report_2018-19.pdf",
    "CBE_Annual_Report_2017-18.pdf",
    "FTA_Performance_Survey_2022.pdf",
    "Company_Profile_2024-25.pdf",
    "NBE_Directive_SBB_71_2021.pdf",
    "Basel_III_Capital_Requirements.pdf",
    "ISO27001_Implementation_Guide.pdf",
]

EXTRACTION_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-haiku-20240307",
    "gpt-4o-2024-08-06",
]

# ---------------------------------------------------------------------------
# Week 1 — intent_records
# ---------------------------------------------------------------------------

def gen_intent_records(n: int = 50) -> list[dict]:
    records = []
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        n_refs = random.randint(1, 3)
        code_refs = []
        for _ in range(n_refs):
            f = random.choice(FILES)
            ls = random.randint(1, 200)
            code_refs.append({
                "file": f,
                "line_start": ls,
                "line_end": ls + random.randint(10, 60),
                "symbol": random.choice(["extract_facts", "validate", "store_event",
                                          "build_graph", "score_rubric", "generate_contract"]),
                "confidence": round(random.uniform(0.65, 0.99), 2),
            })
        records.append({
            "intent_id": gen_uuid(),
            "description": random.choice(INTENTS),
            "code_refs": code_refs,
            "governance_tags": random.sample(GOV_TAGS, k=random.randint(1, 3)),
            "created_at": iso_ts(base, delta_s=i * 3600 + random.randint(0, 3599)),
        })
    return records


# ---------------------------------------------------------------------------
# Week 2 — verdicts
# ---------------------------------------------------------------------------

RUBRIC_IDS = [gen_sha256(f"rubric_{i}") for i in range(4)]
CRITERIA = ["completeness", "accuracy", "clarity", "compliance", "consistency"]
VERDICTS = ["PASS", "FAIL", "WARN"]


def gen_verdict_records(n: int = 50, intent_records: list | None = None) -> list[dict]:
    records = []
    base = datetime(2025, 1, 5, tzinfo=timezone.utc)
    for i in range(n):
        scores = {}
        total = 0.0
        for c in random.sample(CRITERIA, k=random.randint(2, 5)):
            s = random.randint(1, 5)
            scores[c] = {
                "score": s,
                "evidence": [f"Evidence excerpt for {c} criterion — line {random.randint(1, 200)}"],
                "notes": f"Evaluated based on rubric clause {c}.{random.randint(1, 10)}",
            }
            total += s
        mean_score = round(total / len(scores), 2)
        overall = "PASS" if mean_score >= 3.5 else ("WARN" if mean_score >= 2.5 else "FAIL")

        target = (
            random.choice(intent_records)["code_refs"][0]["file"]
            if intent_records
            else random.choice(FILES)
        )
        records.append({
            "verdict_id": gen_uuid(),
            "target_ref": target,
            "rubric_id": random.choice(RUBRIC_IDS),
            "rubric_version": f"1.{random.randint(0, 5)}.{random.randint(0, 9)}",
            "scores": scores,
            "overall_verdict": overall,
            "overall_score": mean_score,
            "confidence": round(random.uniform(0.70, 0.98), 2),
            "evaluated_at": iso_ts(base, delta_s=i * 1800 + random.randint(0, 1799)),
        })
    return records


# ---------------------------------------------------------------------------
# Week 3 — extractions (adapted from real extraction_ledger.jsonl)
# ---------------------------------------------------------------------------

def _make_entities(n: int = 3) -> list[dict]:
    pool = random.sample(ENTITY_POOL, k=min(n, len(ENTITY_POOL)))
    return [
        {
            "entity_id": gen_uuid(),
            "name": e[0],
            "type": e[1],
            "canonical_value": e[2],
        }
        for e in pool
    ]


def _make_facts(entities: list[dict], n: int = 4) -> list[dict]:
    facts = []
    for _ in range(n):
        template = random.choice(FACT_TEMPLATES)
        text = template.format(
            amount=f"{random.randint(1, 500)} million ETB",
            year=random.randint(2018, 2024),
            pct=round(random.uniform(1.0, 30.0), 1),
            ratio=round(random.uniform(0.5, 8.0), 2),
            cap=round(random.uniform(10.0, 18.0), 1),
            n=random.randint(5000, 30000),
        )
        refs = random.sample([e["entity_id"] for e in entities],
                             k=min(2, len(entities)))
        facts.append({
            "fact_id": gen_uuid(),
            "text": text,
            "entity_refs": refs,
            "confidence": round(random.uniform(0.70, 0.97), 2),  # MUST be 0.0–1.0
            "page_ref": random.randint(1, 160) if random.random() > 0.1 else None,
            "source_excerpt": f"...{text[:80]}...",
        })
    return facts


def load_real_week3() -> list[dict]:
    if not WEEK3_LEDGER.exists():
        return []
    records = []
    with open(WEEK3_LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def gen_extraction_records(n: int = 50) -> list[dict]:
    real = load_real_week3()  # up to 25 real records

    records = []
    base = datetime(2025, 1, 10, tzinfo=timezone.utc)

    # Convert real data first
    for i, r in enumerate(real[:n]):
        doc_id = gen_uuid()
        source = r.get("filename", f"document_{i}.pdf")
        entities = _make_entities(random.randint(2, 5))
        facts = _make_facts(entities, random.randint(3, 7))
        proc_ms = int(r.get("processing_time_sec", random.uniform(5, 500)) * 1000)
        page_count = r.get("page_count", 100)
        records.append({
            "doc_id": doc_id,
            "source_path": f"docs/{source}",
            "source_hash": gen_sha256(r.get("doc_id", doc_id)),
            "extracted_facts": facts,
            "entities": entities,
            "extraction_model": random.choice(EXTRACTION_MODELS),
            "processing_time_ms": proc_ms,
            "token_count": {
                "input": page_count * random.randint(25, 35),
                "output": len(facts) * random.randint(80, 150),
            },
            "extracted_at": r.get("timestamp",
                                   iso_ts(base, delta_s=i * 7200 + random.randint(0, 3600))),
        })

    # Fill synthetic records to reach n
    for i in range(len(real), n):
        doc_name = random.choice(DOC_NAMES)
        doc_id = gen_uuid()
        entities = _make_entities(random.randint(2, 6))
        facts = _make_facts(entities, random.randint(3, 8))
        records.append({
            "doc_id": doc_id,
            "source_path": f"docs/{doc_name}",
            "source_hash": gen_sha256(doc_id),
            "extracted_facts": facts,
            "entities": entities,
            "extraction_model": random.choice(EXTRACTION_MODELS),
            "processing_time_ms": random.randint(800, 120000),
            "token_count": {
                "input": random.randint(3000, 8000),
                "output": random.randint(400, 1500),
            },
            "extracted_at": iso_ts(base,
                                    delta_s=(len(real) + i) * 7200 + random.randint(0, 3600)),
        })
    return records


# ---------------------------------------------------------------------------
# Week 4 — lineage_snapshots
# ---------------------------------------------------------------------------

NODE_FILES = [
    "src/week1/correlator.py",
    "src/week2/courtroom.py",
    "src/week2/scorer.py",
    "src/week3/extractor.py",
    "src/week3/fact_parser.py",
    "src/week3/entity_linker.py",
    "src/week4/cartographer.py",
    "src/week4/graph_builder.py",
    "src/week5/event_store.py",
    "src/week5/aggregate.py",
    "src/week7/contracts/generator.py",
    "src/week7/contracts/runner.py",
    "src/week7/contracts/attributor.py",
]

NODE_TYPES = ["FILE", "TABLE", "SERVICE", "MODEL", "PIPELINE", "EXTERNAL"]

EDGE_RELATIONSHIPS = ["IMPORTS", "CALLS", "READS", "WRITES", "PRODUCES", "CONSUMES"]

FAKE_COMMITS = [gen_sha256(f"commit_{i}")[:40] for i in range(20)]


def gen_lineage_snapshots(n: int = 10) -> list[dict]:
    records = []
    base = datetime(2025, 1, 10, tzinfo=timezone.utc)
    for i in range(n):
        nodes = []
        used_ids = set()
        for f in random.sample(NODE_FILES, k=random.randint(6, len(NODE_FILES))):
            node_id = f"file::{f}"
            if node_id in used_ids:
                continue
            used_ids.add(node_id)
            nodes.append({
                "node_id": node_id,
                "type": "FILE",
                "label": Path(f).name,
                "metadata": {
                    "path": f,
                    "language": "python",
                    "purpose": f"Implements {Path(f).stem.replace('_', ' ')} logic",
                    "last_modified": iso_ts(base, delta_s=i * 86400 - random.randint(0, 86400)),
                },
            })

        node_ids = [n["node_id"] for n in nodes]
        edges = []
        for _ in range(random.randint(len(nodes), len(nodes) * 2)):
            src, tgt = random.sample(node_ids, 2)
            edges.append({
                "source": src,
                "target": tgt,
                "relationship": random.choice(EDGE_RELATIONSHIPS),
                "confidence": round(random.uniform(0.7, 1.0), 2),
            })

        records.append({
            "snapshot_id": gen_uuid(),
            "codebase_root": "/workspace/data-contract-enforcer",
            "git_commit": random.choice(FAKE_COMMITS),
            "nodes": nodes,
            "edges": edges,
            "captured_at": iso_ts(base, delta_s=i * 86400 + random.randint(0, 3600)),
        })
    return records


# ---------------------------------------------------------------------------
# Week 5 — events (adapted from real events.jsonl)
# ---------------------------------------------------------------------------

def load_real_week5() -> list[dict]:
    if not WEEK5_EVENTS.exists():
        return []
    records = []
    with open(WEEK5_EVENTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def adapt_week5_event(r: dict, seq_counter: dict) -> dict:
    """Map real event fields to challenge schema."""
    stream_id = r.get("stream_id", gen_uuid())
    # extract aggregate_id from stream_id: 'loan-<uuid>' -> last part
    parts = stream_id.split("-", 1)
    agg_type = parts[0].capitalize() if len(parts) > 1 else "Aggregate"
    agg_id = parts[1] if len(parts) > 1 else stream_id

    agg_key = agg_id
    if agg_key not in seq_counter:
        seq_counter[agg_key] = 0
    seq_counter[agg_key] += 1

    recorded = r.get("recorded_at", iso_ts())
    # occurred_at = recorded_at (events recorded near occurrence)
    occurred = recorded

    meta = r.get("metadata", {}) or {}
    return {
        "event_id": r.get("event_id", gen_uuid()),
        "event_type": r.get("event_type", "UnknownEvent"),
        "aggregate_id": agg_id,
        "aggregate_type": agg_type,
        "sequence_number": seq_counter[agg_key],
        "payload": r.get("payload", {}),
        "metadata": {
            "causation_id": meta.get("causation_id", None),
            "correlation_id": meta.get("correlation_id", gen_uuid()),
            "user_id": meta.get("user_id", "system"),
            "source_service": meta.get("source_service", f"week5-{agg_type.lower()}-service"),
        },
        "schema_version": str(r.get("event_version", "1.0")),
        "occurred_at": occurred,
        "recorded_at": recorded,
    }


def gen_event_records(n: int = 100) -> list[dict]:
    real = load_real_week5()
    seq_counter: dict = {}
    records = []
    for r in real[:n]:
        records.append(adapt_week5_event(r, seq_counter))

    # Pad with synthetic if needed
    synthetic_types = [
        "DocumentProcessed", "ContractViolationDetected", "SchemaSnapshotCreated",
        "ValidationRunCompleted", "BlameChainComputed",
    ]
    base = datetime(2025, 2, 1, tzinfo=timezone.utc)
    for i in range(len(records), n):
        agg_id = gen_uuid()
        agg_key = agg_id
        seq_counter[agg_key] = i + 1
        occurred = iso_ts(base, delta_s=i * 600)
        records.append({
            "event_id": gen_uuid(),
            "event_type": random.choice(synthetic_types),
            "aggregate_id": agg_id,
            "aggregate_type": "Document",
            "sequence_number": 1,
            "payload": {"doc_id": gen_uuid(), "status": "processed"},
            "metadata": {
                "causation_id": None,
                "correlation_id": gen_uuid(),
                "user_id": "system",
                "source_service": "week5-document-service",
            },
            "schema_version": "1.0",
            "occurred_at": occurred,
            "recorded_at": occurred,
        })
    return records


# ---------------------------------------------------------------------------
# LangSmith traces
# ---------------------------------------------------------------------------

RUN_TYPES = ["llm", "chain", "tool", "retriever", "embedding"]
CHAIN_NAMES = [
    "DocumentExtractionChain", "FactParserLLM", "EntityLinkerTool",
    "EmbeddingRetriever", "ContractValidatorChain", "ScoringRubricLLM",
]


def gen_trace_records(n: int = 50, extraction_records: list | None = None) -> list[dict]:
    records = []
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    root_runs: list[str] = []
    for i in range(n):
        run_type = random.choice(RUN_TYPES)
        prompt_t = random.randint(1000, 6000)
        compl_t = random.randint(200, 1500)
        start = base + timedelta(seconds=i * 120 + random.randint(0, 119))
        end = start + timedelta(seconds=random.randint(1, 10))
        parent = random.choice(root_runs) if root_runs and random.random() > 0.4 else None
        run_id = gen_uuid()
        if parent is None:
            root_runs.append(run_id)
        if len(root_runs) > 20:
            root_runs = root_runs[-20:]

        records.append({
            "id": run_id,
            "name": random.choice(CHAIN_NAMES),
            "run_type": run_type,
            "inputs": {"prompt": f"Analyze document chunk {i}"},
            "outputs": {"result": f"Extracted {random.randint(1, 8)} facts"},
            "error": None,
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_tokens": prompt_t + compl_t,
            "prompt_tokens": prompt_t,
            "completion_tokens": compl_t,
            "total_cost": round((prompt_t * 0.000003 + compl_t * 0.000015), 6),
            "tags": random.sample(["week3", "week5", "extraction", "validation", "contract"], k=2),
            "parent_run_id": parent,
            "session_id": gen_uuid(),
        })
    return records


# ---------------------------------------------------------------------------
# Write helper
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records):>4} records → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating sample output data …")

    intent = gen_intent_records(50)
    write_jsonl(OUTPUTS / "week1" / "intent_records.jsonl", intent)

    verdicts = gen_verdict_records(50, intent_records=intent)
    write_jsonl(OUTPUTS / "week2" / "verdicts.jsonl", verdicts)

    extractions = gen_extraction_records(50)
    write_jsonl(OUTPUTS / "week3" / "extractions.jsonl", extractions)

    lineage = gen_lineage_snapshots(10)
    write_jsonl(OUTPUTS / "week4" / "lineage_snapshots.jsonl", lineage)

    events = gen_event_records(100)
    write_jsonl(OUTPUTS / "week5" / "events.jsonl", events)

    traces = gen_trace_records(50, extraction_records=extractions)
    write_jsonl(OUTPUTS / "traces" / "runs.jsonl", traces)

    print("\nDone. All output files generated.")


if __name__ == "__main__":
    main()
