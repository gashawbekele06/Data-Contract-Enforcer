import fs from 'fs'
import path from 'path'
import type {
  ReportData, ValidationReport, Violation, Subscription, ContractFile, DatasetSummary,
} from './types'

// Data root is one level up from the Next.js project (dashboard/)
const DATA_ROOT = path.join(process.cwd(), '..')

function readJson<T>(filePath: string): T | null {
  try {
    const raw = fs.readFileSync(filePath, 'utf-8')
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function readJsonl<T>(filePath: string): T[] {
  try {
    const raw = fs.readFileSync(filePath, 'utf-8')
    return raw
      .split('\n')
      .filter(l => l.trim())
      .map(l => JSON.parse(l) as T)
  } catch {
    return []
  }
}

// ── Report ──────────────────────────────────────────────────────────────────

export function getReport(): ReportData | null {
  return readJson<ReportData>(path.join(DATA_ROOT, 'enforcer_report', 'report_data.json'))
}

// ── Validation reports ───────────────────────────────────────────────────────

const DATASET_LABELS: Record<string, string> = {
  'week1-intent-code-correlator':         'Week 1 — Intent Records',
  'week2-digital-courtroom':              'Week 2 — Verdict Records',
  'week3-document-refinery-extractions':  'Week 3 — Extraction Records',
  'week4-brownfield-cartographer':        'Week 4 — Lineage Snapshots',
  'week5-event-sourcing-platform':        'Week 5 — Event Records',
  'langsmith-traces':                     'LangSmith — Trace Records',
}

export function getAllValidationReports(): ValidationReport[] {
  const dir = path.join(DATA_ROOT, 'validation_reports')
  try {
    return fs
      .readdirSync(dir)
      .filter(f => f.endsWith('.json') && !f.startsWith('schema_evolution') && f !== 'ai_metrics.json')
      .sort()
      .reverse()
      .map(f => readJson<ValidationReport>(path.join(dir, f)))
      .filter((r): r is ValidationReport => r !== null)
  } catch {
    return []
  }
}

export function getLatestValidationPerDataset(): DatasetSummary[] {
  const all = getAllValidationReports()
  const latest: Record<string, ValidationReport> = {}
  for (const r of all) {
    if (!latest[r.contract_id] || r.run_timestamp > latest[r.contract_id].run_timestamp) {
      latest[r.contract_id] = r
    }
  }
  return Object.values(latest).map(r => ({
    contract_id: r.contract_id,
    label: DATASET_LABELS[r.contract_id] ?? r.contract_id,
    latest_passed: r.passed,
    latest_failed: r.failed,
    latest_total: r.total_checks,
    latest_timestamp: r.run_timestamp,
    pass_rate: r.total_checks > 0 ? Math.round((r.passed / r.total_checks) * 100) : 100,
  }))
}

export function getValidationReportsByDataset(contractId: string): ValidationReport[] {
  return getAllValidationReports().filter(r => r.contract_id === contractId)
}

// ── Violations ───────────────────────────────────────────────────────────────

export function getViolations(): Violation[] {
  return readJsonl<Violation>(path.join(DATA_ROOT, 'violation_log', 'violations.jsonl'))
}

// ── AI metrics ───────────────────────────────────────────────────────────────

export function getAiMetrics(): Record<string, unknown> | null {
  return readJson(path.join(DATA_ROOT, 'validation_reports', 'ai_metrics.json'))
}

// ── Contract registry ────────────────────────────────────────────────────────

export function getSubscriptions(): Subscription[] {
  try {
    // Read YAML without importing js-yaml at module level (dynamic import for server)
    const raw = fs.readFileSync(
      path.join(DATA_ROOT, 'contract_registry', 'subscriptions.yaml'),
      'utf-8'
    )
    // Simple YAML parser for this specific structure — avoids js-yaml build issues
    return parseSubscriptionsYaml(raw)
  } catch {
    return []
  }
}

function parseSubscriptionsYaml(raw: string): Subscription[] {
  // Use js-yaml dynamically
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const yaml = require('js-yaml')
    const doc = yaml.load(raw) as { subscriptions: Subscription[] }
    return doc?.subscriptions ?? []
  } catch {
    return []
  }
}

// ── Generated contracts ──────────────────────────────────────────────────────

export function getContracts(): ContractFile[] {
  const dir = path.join(DATA_ROOT, 'generated_contracts')
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const yaml = require('js-yaml')
    return fs
      .readdirSync(dir)
      .filter(f => f.endsWith('.yaml') && !f.endsWith('_dbt.yml'))
      .sort()
      .map(f => {
        const filePath = path.join(dir, f)
        try {
          const doc = yaml.load(fs.readFileSync(filePath, 'utf-8')) as Record<string, unknown>
          const info = (doc?.info as Record<string, unknown>) ?? {}
          const schema = (doc?.schema as Record<string, unknown>) ?? {}
          const lineage = (doc?.lineage as Record<string, unknown>) ?? {}
          const downstream = (lineage?.downstream as unknown[]) ?? []
          return {
            name: f,
            contract_id: (doc?.id as string) ?? f.replace('.yaml', ''),
            title: (info?.title as string) ?? f,
            version: (info?.version as string) ?? '1.0.0',
            owner: (info?.owner as string) ?? 'unknown',
            clause_count: Object.keys(schema).length,
            downstream_count: downstream.length,
            path: filePath,
          } satisfies ContractFile
        } catch {
          return null
        }
      })
      .filter((c): c is ContractFile => c !== null)
  } catch {
    return []
  }
}

export function getContractYaml(name: string): string {
  try {
    const dir = path.join(DATA_ROOT, 'generated_contracts')
    // Sanitize: only allow yaml files, no path traversal
    const safe = path.basename(name)
    if (!safe.endsWith('.yaml') || safe.includes('..')) return ''
    return fs.readFileSync(path.join(dir, safe), 'utf-8')
  } catch {
    return ''
  }
}

// ── Schema evolution ─────────────────────────────────────────────────────────

export function getSchemaEvolutionReports(): ValidationReport[] {
  const dir = path.join(DATA_ROOT, 'validation_reports')
  try {
    return fs
      .readdirSync(dir)
      .filter(f => f.startsWith('schema_evolution') && f.endsWith('.json'))
      .sort()
      .reverse()
      .map(f => readJson<ValidationReport>(path.join(dir, f)))
      .filter((r): r is ValidationReport => r !== null)
  } catch {
    return []
  }
}
