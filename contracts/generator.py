#!/usr/bin/env python3
"""
ContractGenerator — Phase 1
============================
Reads a JSONL dataset and generates:
  1. A Bitol-compatible YAML data contract  (generated_contracts/<name>.yaml)
  2. A dbt schema.yml counterpart           (generated_contracts/<name>_dbt.yml)
  3. A schema snapshot                      (schema_snapshots/<contract_id>/<ts>.yaml)

Optionally injects lineage context from the Week 4 snapshot and annotates
ambiguous columns with Claude via the Anthropic SDK.

Usage
-----
  python contracts/generator.py \\
      --source  outputs/week3/extractions.jsonl \\
      --output  generated_contracts/

  # with lineage context
  python contracts/generator.py \\
      --source   outputs/week3/extractions.jsonl \\
      --output   generated_contracts/ \\
      --lineage  outputs/week4/lineage_snapshots.jsonl

  # with LLM annotation (requires ANTHROPIC_API_KEY)
  python contracts/generator.py \\
      --source  outputs/week3/extractions.jsonl \\
      --output  generated_contracts/ \\
      --annotate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Constants & lookup tables
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent

# Map stem → canonical contract id
CONTRACT_ID_MAP = {
    "intent_records": "week1-intent-code-correlator",
    "verdicts": "week2-digital-courtroom",
    "extractions": "week3-document-refinery-extractions",
    "lineage_snapshots": "week4-brownfield-cartographer",
    "events": "week5-event-sourcing-platform",
    "runs": "langsmith-traces",
}

# Map stem → output file base name (without extension)
# Ensures generated files use the week-prefixed name expected by runner.py
OUTPUT_STEM_MAP = {
    "intent_records": "week1_intent_records",
    "verdicts": "week2_verdicts",
    "extractions": "week3_extractions",
    "lineage_snapshots": "week4_lineage_snapshots",
    "events": "week5_events",
    "runs": "runs",
}

CONTRACT_TITLE_MAP = {
    "intent_records": "Week 1 Intent-Code Correlator — Intent Records",
    "verdicts": "Week 2 Digital Courtroom — Verdict Records",
    "extractions": "Week 3 Document Refinery — Extraction Records",
    "lineage_snapshots": "Week 4 Brownfield Cartographer — Lineage Snapshots",
    "events": "Week 5 Event Sourcing Platform — Event Records",
    "runs": "LangSmith Trace Exports",
}

CONTRACT_OWNER_MAP = {
    "intent_records": "week1-team",
    "verdicts": "week2-team",
    "extractions": "week3-team",
    "lineage_snapshots": "week4-team",
    "events": "week5-team",
    "runs": "platform-observability-team",
}

# Downstream consumer lineage registry
DOWNSTREAM_MAP = {
    "extractions": [
        {
            "id": "week4-cartographer",
            "description": "Cartographer ingests doc_id and extracted_facts as node metadata",
            "fields_consumed": ["doc_id", "extracted_facts", "extraction_model"],
            "breaking_if_changed": ["extracted_facts.confidence", "doc_id"],
        }
    ],
    "lineage_snapshots": [
        {
            "id": "week7-violation-attributor",
            "description": "ViolationAttributor uses lineage graph for blast-radius computation",
            "fields_consumed": ["nodes", "edges", "git_commit"],
            "breaking_if_changed": ["nodes", "edges"],
        }
    ],
    "events": [
        {
            "id": "week7-schema-contract",
            "description": "Payload validated against event type's JSON Schema",
            "fields_consumed": ["event_type", "payload", "schema_version"],
            "breaking_if_changed": ["event_type", "payload"],
        }
    ],
    "verdicts": [
        {
            "id": "week7-ai-contract-extension",
            "description": "LLM output schema validation tracks verdict structure",
            "fields_consumed": ["overall_verdict", "scores", "confidence"],
            "breaking_if_changed": ["overall_verdict", "scores"],
        }
    ],
    "runs": [
        {
            "id": "week7-ai-contract-extension",
            "description": "AI Contract Extension enforces trace schema",
            "fields_consumed": ["run_type", "total_tokens", "total_cost"],
            "breaking_if_changed": ["run_type", "total_tokens"],
        }
    ],
}

# Known enum field values
ENUM_FIELDS: dict[str, list[str]] = {
    "overall_verdict": ["PASS", "FAIL", "WARN"],
    "run_type": ["llm", "chain", "tool", "retriever", "embedding"],
    "relationship": ["IMPORTS", "CALLS", "READS", "WRITES", "PRODUCES", "CONSUMES"],
    "type": ["FILE", "TABLE", "SERVICE", "MODEL", "PIPELINE", "EXTERNAL"],
    "entity_type": ["PERSON", "ORG", "LOCATION", "DATE", "AMOUNT", "OTHER"],
    "aggregate_type": ["Document", "Loan", "Application", "User"],
}

# Patterns for format detection
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.I)
SHA40_RE = re.compile(r"^[a-f0-9]{40}$", re.I)
ISO_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_string_format(values: list[str]) -> str | None:
    """Return the dominant format tag for a list of string samples."""
    if not values:
        return None
    sample = [v for v in values if isinstance(v, str)][:50]
    if not sample:
        return None
    uuid_matches = sum(1 for v in sample if UUID_RE.match(v))
    sha256_matches = sum(1 for v in sample if SHA256_RE.match(v))
    sha40_matches = sum(1 for v in sample if SHA40_RE.match(v))
    iso_matches = sum(1 for v in sample if ISO_TS_RE.match(v))
    semver_matches = sum(1 for v in sample if SEMVER_RE.match(v))
    total = len(sample)
    threshold = 0.8 * total
    if uuid_matches >= threshold:
        return "uuid"
    if sha256_matches >= threshold:
        return "sha256"
    if sha40_matches >= threshold:
        return "sha256-40"
    if iso_matches >= threshold:
        return "date-time"
    if semver_matches >= threshold:
        return "semver"
    return None


def flatten_nested_col(series: pd.Series) -> tuple[str, dict]:
    """
    Detect if a column holds dicts or lists and return a summary
    for the contract generator.
    """
    non_null = series.dropna()
    if non_null.empty:
        return "null", {}
    first = non_null.iloc[0]
    if isinstance(first, list):
        # Inspect list elements
        all_items = [item for row in non_null if isinstance(row, list) for item in row]
        if all_items and isinstance(all_items[0], dict):
            inner_keys = list(all_items[0].keys())
            return "array_of_objects", {"sample_keys": inner_keys[:10]}
        return "array", {}
    if isinstance(first, dict):
        return "object", {"sample_keys": list(first.keys())[:10]}
    return "unknown", {}


# ---------------------------------------------------------------------------
# Structural & statistical profiling
# ---------------------------------------------------------------------------

def profile_column(col_name: str, series: pd.Series) -> dict:
    """Return a rich profile dict for a single column."""
    profile: dict[str, Any] = {
        "column": col_name,
        "null_fraction": float(series.isna().mean()),
        "total": int(len(series)),
        "non_null": int(series.notna().sum()),
    }

    non_null = series.dropna()

    # Detect nested structures
    if non_null.apply(lambda v: isinstance(v, (list, dict))).any():
        kind, meta = flatten_nested_col(non_null)
        profile["dtype"] = kind
        profile.update(meta)
        return profile

    # Numeric columns
    if pd.api.types.is_float_dtype(series) or pd.api.types.is_integer_dtype(series):
        numeric = pd.to_numeric(non_null, errors="coerce").dropna()
        profile["dtype"] = "float" if pd.api.types.is_float_dtype(series) else "integer"
        if len(numeric):
            profile["min"] = float(numeric.min())
            profile["max"] = float(numeric.max())
            profile["mean"] = float(numeric.mean())
            profile["stddev"] = float(numeric.std())
            profile["p25"] = float(numeric.quantile(0.25))
            profile["p50"] = float(numeric.quantile(0.50))
            profile["p75"] = float(numeric.quantile(0.75))
            profile["p95"] = float(numeric.quantile(0.95))
            profile["p99"] = float(numeric.quantile(0.99))
            # Detect likely-confidence columns
            if "confidence" in col_name.lower():
                if numeric.max() > 1.0:
                    profile["WARNING"] = (
                        f"max={numeric.max():.2f} — possible 0-100 scale; "
                        "contract expects 0.0–1.0"
                    )
                elif numeric.mean() > 0.99:
                    profile["WARNING"] = "mean > 0.99 — values may be clamped"
                elif numeric.mean() < 0.01:
                    profile["WARNING"] = "mean < 0.01 — values may be broken"
        return profile

    # Boolean
    if pd.api.types.is_bool_dtype(series):
        profile["dtype"] = "boolean"
        return profile

    # String
    str_vals = non_null.astype(str)
    profile["dtype"] = "string"
    profile["cardinality"] = int(str_vals.nunique())
    profile["sample_values"] = str_vals.value_counts().head(5).index.tolist()

    fmt = detect_string_format(str_vals.tolist())
    if fmt:
        profile["format"] = fmt

    # Enum detection
    for field, values in ENUM_FIELDS.items():
        if field in col_name.lower() or col_name.lower() in field:
            observed = set(str_vals.unique())
            if observed.issubset(set(values)):
                profile["enum"] = values
                break
    else:
        if profile["cardinality"] <= 10:
            profile["enum"] = str_vals.value_counts().index.tolist()

    return profile


def profile_dataframe(df: pd.DataFrame) -> dict[str, dict]:
    """Profile every column in the DataFrame."""
    return {col: profile_column(col, df[col]) for col in df.columns}


# ---------------------------------------------------------------------------
# Bitol YAML contract builder
# ---------------------------------------------------------------------------

def _schema_clause(col_name: str, p: dict) -> dict:
    """Translate a column profile into a Bitol schema clause."""
    clause: dict[str, Any] = {}
    dtype = p.get("dtype", "string")

    if dtype in ("array_of_objects", "array"):
        clause["type"] = "array"
        if dtype == "array_of_objects":
            clause["items"] = {k: {"type": "string"} for k in p.get("sample_keys", [])}
            # Special handling for known sub-schemas
            if col_name == "extracted_facts":
                clause["items"] = {
                    "fact_id": {"type": "string", "format": "uuid", "unique": True},
                    "text": {"type": "string", "minLength": 1},
                    "entity_refs": {"type": "array", "items": {"type": "string", "format": "uuid"}},
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "required": True,
                        "description": "BREAKING CHANGE if scale changed to 0-100",
                    },
                    "page_ref": {"type": "integer", "nullable": True},
                    "source_excerpt": {"type": "string"},
                }
            elif col_name == "entities":
                clause["items"] = {
                    "entity_id": {"type": "string", "format": "uuid", "unique": True},
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["PERSON", "ORG", "LOCATION", "DATE", "AMOUNT", "OTHER"],
                    },
                    "canonical_value": {"type": "string"},
                }
            elif col_name == "code_refs":
                clause["items"] = {
                    "file": {"type": "string"},
                    "line_start": {"type": "integer", "minimum": 1},
                    "line_end": {"type": "integer", "minimum": 1},
                    "symbol": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                }
            elif col_name == "nodes":
                clause["items"] = {
                    "node_id": {"type": "string", "pattern": "^[a-z]+::.+"},
                    "type": {
                        "type": "string",
                        "enum": ["FILE", "TABLE", "SERVICE", "MODEL", "PIPELINE", "EXTERNAL"],
                    },
                    "label": {"type": "string"},
                    "metadata": {"type": "object"},
                }
            elif col_name == "edges":
                clause["items"] = {
                    "source": {"type": "string",
                               "description": "Must reference a node_id in nodes[]"},
                    "target": {"type": "string",
                               "description": "Must reference a node_id in nodes[]"},
                    "relationship": {
                        "type": "string",
                        "enum": ["IMPORTS", "CALLS", "READS", "WRITES", "PRODUCES", "CONSUMES"],
                    },
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                }
        clause["required"] = p["null_fraction"] < 0.01
        return clause

    if dtype == "object":
        clause["type"] = "object"
        clause["required"] = p["null_fraction"] < 0.01
        if col_name == "token_count":
            clause["properties"] = {
                "input": {"type": "integer", "minimum": 0},
                "output": {"type": "integer", "minimum": 0},
            }
        elif col_name == "metadata":
            clause["properties"] = {
                "causation_id": {"type": "string", "nullable": True},
                "correlation_id": {"type": "string", "format": "uuid"},
                "user_id": {"type": "string"},
                "source_service": {"type": "string"},
            }
        elif col_name == "scores":
            clause["description"] = (
                "Map of criterion_name → {score: int 1–5, evidence: list[str], notes: str}"
            )
            clause["additionalProperties"] = {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
            }
        return clause

    if dtype == "float":
        clause["type"] = "number"
        clause["required"] = p["null_fraction"] < 0.01
        mn = p.get("min")
        mx = p.get("max")
        if mn is not None:
            clause["minimum"] = mn
        if mx is not None:
            clause["maximum"] = mx
        if "confidence" in col_name.lower():
            clause["minimum"] = 0.0
            clause["maximum"] = 1.0
            clause["description"] = (
                "Confidence score — MUST remain in 0.0–1.0 float range. "
                "Changing scale to 0–100 is a BREAKING CHANGE."
            )
        return clause

    if dtype == "integer":
        clause["type"] = "integer"
        clause["required"] = p["null_fraction"] < 0.01
        mn = p.get("min")
        mx = p.get("max")
        if mn is not None:
            clause["minimum"] = int(mn)
        if mx is not None and mx <= 1_000_000:
            clause["maximum"] = int(mx)
        if col_name == "processing_time_ms":
            clause["minimum"] = 1
            clause["description"] = "Must be a positive integer (milliseconds)."
        if col_name in ("score",):
            clause["minimum"] = 1
            clause["maximum"] = 5
        return clause

    if dtype == "boolean":
        clause["type"] = "boolean"
        return clause

    # String
    clause["type"] = "string"
    clause["required"] = p["null_fraction"] < 0.01
    fmt = p.get("format")
    if fmt:
        clause["format"] = fmt
        if fmt == "uuid":
            clause["pattern"] = (
                "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
        elif fmt == "sha256":
            clause["pattern"] = "^[a-f0-9]{64}$"
        elif fmt == "sha256-40":
            clause["pattern"] = "^[a-f0-9]{40}$"
        elif fmt == "date-time":
            clause["description"] = "ISO 8601 timestamp"
    enums = p.get("enum")
    if enums and len(enums) <= 10:
        clause["enum"] = enums
    card = p.get("cardinality", 999)
    if card == 1:
        clause["unique"] = False
    # Derived descriptions
    if col_name in ("extraction_model",):
        clause["pattern"] = "^(claude|gpt)-"
        clause["description"] = "Model identifier. Must match pattern claude-* or gpt-*."
    if col_name in ("overall_verdict",):
        clause["enum"] = ["PASS", "FAIL", "WARN"]
        clause["description"] = "One of exactly PASS | FAIL | WARN."
    if col_name in ("run_type",):
        clause["enum"] = ["llm", "chain", "tool", "retriever", "embedding"]
    if p.get("null_fraction", 0) > 0:
        clause["nullable"] = True
    return clause


def build_quality_checks(stem: str, profiles: dict[str, dict]) -> dict:
    """Build Soda-style quality checks for the contract."""
    table = stem  # use stem as table name in Soda
    checks = []

    for col, p in profiles.items():
        dtype = p.get("dtype", "")
        nf = p.get("null_fraction", 0)
        if nf == 0 and dtype not in ("array_of_objects", "array", "object"):
            checks.append(f"missing_count({col}) = 0")

        if p.get("format") == "uuid":
            checks.append(f"duplicate_count({col}) = 0")

        if "confidence" in col.lower() and dtype == "float":
            checks.append(f"min({col}) >= 0.0")
            checks.append(f"max({col}) <= 1.0")

        if col == "overall_score" and dtype == "float":
            checks.append(f"min({col}) >= 1.0")
            checks.append(f"max({col}) <= 5.0")

        if col == "processing_time_ms" and dtype == "integer":
            checks.append(f"min({col}) >= 1")

        if col == "total_tokens" and dtype == "integer":
            checks.append(f"min({col}) >= 0")

    checks.append("row_count >= 1")

    return {
        "type": "SodaChecks",
        "specification": {f"checks for {table}": checks},
    }


def load_lineage_snapshot(lineage_path: str | None) -> dict:
    """Load the most recent lineage snapshot and return it."""
    if not lineage_path:
        return {}
    p = Path(lineage_path)
    if not p.exists():
        return {}
    records = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not records:
        return {}
    # Return latest by captured_at
    records.sort(key=lambda r: r.get("captured_at", ""), reverse=True)
    return records[0]


def find_downstream_from_lineage(lineage: dict, dataset_name: str) -> list[dict]:
    """
    Query the lineage graph for downstream consumers of the given dataset.
    Returns list of node dicts that consume this dataset.
    """
    if not lineage:
        return []
    nodes = {n["node_id"]: n for n in lineage.get("nodes", [])}
    edges = lineage.get("edges", [])
    # Find edges where source matches any node containing dataset_name
    consumers = []
    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if dataset_name.replace("_", "") in src.replace("_", "").lower():
            tgt_node = nodes.get(tgt)
            if tgt_node:
                consumers.append({
                    "id": tgt,
                    "label": tgt_node.get("label", tgt),
                    "relationship": edge.get("relationship"),
                })
    return consumers


def llm_annotate_column(
    col_name: str,
    table_name: str,
    dtype: str,
    sample_values: list,
    adjacent_cols: list[str],
) -> dict | None:
    """
    Call Claude to annotate an ambiguous column.
    Returns None if ANTHROPIC_API_KEY is not set or call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"You are a data contract expert. Given this column:\n"
            f"  Table: {table_name}\n"
            f"  Column: {col_name}\n"
            f"  Data type: {dtype}\n"
            f"  Sample values: {sample_values[:5]}\n"
            f"  Adjacent columns: {adjacent_cols[:5]}\n\n"
            "Provide a short JSON response with exactly these keys:\n"
            '  "description": plain-English business description (1 sentence)\n'
            '  "business_rule": validation expression (1 line)\n'
            '  "cross_column_relationship": any cross-column constraint or null\n'
            "Only output valid JSON, no markdown."
        )
        msg = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        return json.loads(text)
    except Exception as exc:
        print(f"  [LLM annotation skipped for {col_name}]: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class ContractGenerator:
    def __init__(
        self,
        source_path: str,
        output_dir: str,
        lineage_path: str | None = None,
        annotate: bool = False,
    ):
        self.source = Path(source_path)
        self.output_dir = Path(output_dir)
        self.lineage_path = lineage_path
        self.annotate = annotate
        self.stem = self.source.stem  # e.g. "extractions"
        self.contract_id = CONTRACT_ID_MAP.get(self.stem, self.stem.replace("_", "-"))
        # Output file base name: e.g. "week3_extractions" so runner.py finds the right file
        self.out_stem = OUTPUT_STEM_MAP.get(self.stem, self.stem)
        self.now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def load_data(self) -> pd.DataFrame:
        records = []
        with open(self.source, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  [WARN] Skipping malformed line: {e}", file=sys.stderr)
        if not records:
            raise ValueError(f"No records found in {self.source}")
        print(f"  Loaded {len(records)} records from {self.source.name}")
        return pd.DataFrame(records)

    def build_contract(
        self,
        df: pd.DataFrame,
        profiles: dict[str, dict],
        lineage: dict,
        annotations: dict[str, dict],
    ) -> dict:
        schema: dict[str, Any] = {}
        for col, p in profiles.items():
            clause = _schema_clause(col, p)
            if col in annotations:
                clause["llm_annotations"] = annotations[col]
            # Only mark primary key fields as unique (not foreign keys like parent_run_id,
            # causation_id, correlation_id, aggregate_id — these can repeat across records)
            _FK_SUFFIXES = ("parent_run_id", "causation_id", "correlation_id",
                            "aggregate_id", "rubric_id", "target_ref")
            if p.get("format") == "uuid" and col.endswith("_id") and col not in _FK_SUFFIXES:
                clause["unique"] = True
            schema[col] = clause

        quality = build_quality_checks(self.stem, profiles)

        # Lineage: lookup static downstream map first, then supplement from lineage graph
        static_downstream = DOWNSTREAM_MAP.get(self.stem, [])
        graph_downstream = find_downstream_from_lineage(lineage, self.stem)
        # Merge (deduplicate by id)
        downstream_ids = {d["id"] for d in static_downstream}
        for gd in graph_downstream:
            if gd["id"] not in downstream_ids:
                static_downstream.append(gd)

        contract = {
            "kind": "DataContract",
            "apiVersion": "v3.0.0",
            "id": self.contract_id,
            "info": {
                "title": CONTRACT_TITLE_MAP.get(self.stem, self.stem),
                "version": "1.0.0",
                "owner": CONTRACT_OWNER_MAP.get(self.stem, "platform-team"),
                "description": (
                    f"Auto-generated contract for {self.stem.replace('_', ' ')}. "
                    f"One record per unit of output. Generated {self.now}."
                ),
                "generated_by": "ContractGenerator v1.0.0",
                "generated_at": self.now,
            },
            "servers": {
                "local": {
                    "type": "local",
                    "path": str(self.source.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
                    if self.source.resolve().is_relative_to(ROOT.resolve())
                    else str(self.source).replace("\\", "/"),
                    "format": "jsonl",
                }
            },
            "terms": {
                "usage": "Internal inter-system data contract. Do not publish externally.",
                "limitations": (
                    "All confidence fields must remain in 0.0–1.0 float range. "
                    "Do not change to percentage scale without a formal migration plan."
                ),
            },
            "schema": schema,
            "quality": quality,
            "lineage": {
                "upstream": [],
                "downstream": static_downstream,
            },
        }
        return contract

    def build_dbt_schema(self, contract: dict) -> dict:
        """Generate dbt schema.yml from the Bitol contract."""
        columns = []
        tests_model = []

        schema = contract.get("schema", {})
        for col_name, clause in schema.items():
            dbt_col: dict[str, Any] = {"name": col_name}
            col_tests = []

            # not_null
            if clause.get("required") and not clause.get("nullable"):
                col_tests.append("not_null")

            # unique
            if clause.get("unique"):
                col_tests.append("unique")

            # accepted_values
            enums = clause.get("enum")
            if enums:
                col_tests.append({"accepted_values": {"values": enums}})

            if col_tests:
                dbt_col["tests"] = col_tests
            if clause.get("description"):
                dbt_col["description"] = clause["description"]
            columns.append(dbt_col)

        return {
            "version": 2,
            "models": [
                {
                    "name": self.stem,
                    "description": contract["info"]["description"],
                    "columns": columns,
                }
            ],
        }

    def save_snapshot(self, contract: dict) -> None:
        snap_dir = ROOT / "schema_snapshots" / self.contract_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{self.ts_slug}.yaml"
        with open(snap_path, "w", encoding="utf-8") as f:
            yaml.dump(contract, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        try:
            print(f"  Snapshot saved → {snap_path.relative_to(ROOT.resolve())}")
        except ValueError:
            print(f"  Snapshot saved → {snap_path}")

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[ContractGenerator] contract_id={self.contract_id}")
        print(f"  Source : {self.source}")
        print(f"  Output : {self.output_dir}")

        df = self.load_data()
        print("  Profiling columns …")
        profiles = profile_dataframe(df)

        lineage = load_lineage_snapshot(self.lineage_path)
        if lineage:
            print(f"  Lineage snapshot loaded: {len(lineage.get('nodes', []))} nodes, "
                  f"{len(lineage.get('edges', []))} edges")

        annotations: dict[str, dict] = {}
        if self.annotate:
            all_cols = list(profiles.keys())
            for col, p in profiles.items():
                dtype = p.get("dtype", "string")
                sample = p.get("sample_values", [])
                if not sample and p.get("min") is not None:
                    sample = [p.get("min"), p.get("max")]
                if dtype in ("string",) and not p.get("format") and not p.get("enum"):
                    ann = llm_annotate_column(col, self.stem, dtype, sample, all_cols)
                    if ann:
                        annotations[col] = ann

        contract = self.build_contract(df, profiles, lineage, annotations)

        # Save Bitol YAML
        out_yaml = self.output_dir / f"{self.out_stem}.yaml"
        with open(out_yaml, "w", encoding="utf-8") as f:
            yaml.dump(contract, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        try:
            print(f"  Contract YAML → {out_yaml.resolve().relative_to(ROOT.resolve())}")
        except ValueError:
            print(f"  Contract YAML → {out_yaml}")

        # Save dbt schema.yml
        dbt = self.build_dbt_schema(contract)
        out_dbt = self.output_dir / f"{self.out_stem}_dbt.yml"
        with open(out_dbt, "w", encoding="utf-8") as f:
            yaml.dump(dbt, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        try:
            print(f"  dbt schema.yml → {out_dbt.resolve().relative_to(ROOT.resolve())}")
        except ValueError:
            print(f"  dbt schema.yml → {out_dbt}")

        # Save schema snapshot
        self.save_snapshot(contract)

        clause_count = len(contract.get("schema", {}))
        print(f"  Generated {clause_count} schema clauses.")
        print("  Done.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ContractGenerator — generate Bitol YAML contracts from JSONL files"
    )
    parser.add_argument(
        "--source", required=True, help="Path to the JSONL input file"
    )
    parser.add_argument(
        "--output", required=True, help="Directory to write generated contract YAML files"
    )
    parser.add_argument(
        "--lineage",
        default=None,
        help="Path to outputs/week4/lineage_snapshots.jsonl for lineage context injection",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Enable LLM column annotation via Claude (requires ANTHROPIC_API_KEY)",
    )
    args = parser.parse_args()

    gen = ContractGenerator(
        source_path=args.source,
        output_dir=args.output,
        lineage_path=args.lineage,
        annotate=args.annotate,
    )
    gen.run()


if __name__ == "__main__":
    main()
