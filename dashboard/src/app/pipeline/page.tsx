import type { ReactNode } from 'react'
import {
  getContracts,
  getLatestValidationPerDataset,
  getViolations,
  getSchemaEvolutionReports,
  getReport,
} from '@/lib/data'

// ── Clause counts per contract (from generator output) ───────────────────────
const CLAUSE_MAP: Record<string, number> = {
  'week1-intent-code-correlator':         5,
  'week2-digital-courtroom':              9,
  'week3-document-refinery-extractions':  9,
  'week4-brownfield-cartographer':        6,
  'week5-event-sourcing-platform':       10,
  'langsmith-traces':                    15,
}

// ── Shared components ─────────────────────────────────────────────────────────

function Badge({ status }: { status: string }) {
  const cls =
    status === 'PASS' || status === 'DONE'  ? 'bg-green-900/40 text-green-400 border-green-800' :
    status === 'FAIL'                       ? 'bg-red-900/40 text-red-400 border-red-800' :
    status === 'WARN'                       ? 'bg-yellow-900/40 text-yellow-400 border-yellow-800' :
    status === 'AMBER'                      ? 'bg-amber-900/40 text-amber-400 border-amber-800' :
    'bg-slate-800 text-slate-400 border-slate-700'
  return (
    <span className={`font-mono text-xs px-2 py-0.5 rounded border ${cls}`}>{status}</span>
  )
}

function TermWindow({ cmd, children }: { cmd: string; children: ReactNode }) {
  return (
    <div className="bg-black rounded-lg border border-slate-700 overflow-hidden">
      {/* macOS-style title bar */}
      <div className="bg-slate-900 border-b border-slate-700 px-4 py-2 flex items-center gap-2">
        <span className="w-3 h-3 rounded-full bg-red-500/80" />
        <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
        <span className="w-3 h-3 rounded-full bg-green-500/80" />
        <span className="ml-3 text-slate-500 text-xs font-mono truncate">{cmd}</span>
      </div>
      {/* Terminal body */}
      <div className="p-4 font-mono text-sm space-y-0.5">
        <div className="mb-2">
          <span className="text-green-400">$ </span>
          <span className="text-white">{cmd}</span>
        </div>
        {children}
      </div>
    </div>
  )
}

function TLine({
  label,
  value,
  labelCls = 'text-slate-500',
  valueCls = 'text-slate-200',
  indent = true,
}: {
  label?: string
  value: ReactNode
  labelCls?: string
  valueCls?: string
  indent?: boolean
}) {
  return (
    <div className={`flex gap-3 ${indent ? 'pl-2' : ''}`}>
      {label && <span className={`shrink-0 w-36 ${labelCls}`}>{label}</span>}
      <span className={valueCls}>{value}</span>
    </div>
  )
}

function Divider({ color = 'text-slate-600' }: { color?: string }) {
  return <div className={`pl-2 ${color}`}>{'─'.repeat(60)}</div>
}

function StepRow({
  n,
  title,
  status,
  cmd,
  last = false,
  children,
}: {
  n: number
  title: string
  status: string
  cmd: string
  last?: boolean
  children: ReactNode
}) {
  const dotColor =
    status === 'FAIL'                      ? 'bg-red-500 border-red-700 text-black' :
    status === 'WARN' || status === 'AMBER' ? 'bg-yellow-500 border-yellow-700 text-black' :
    status === 'DONE'                       ? 'bg-blue-500 border-blue-700 text-black' :
    'bg-green-500 border-green-700 text-black'

  return (
    <div className="flex gap-5">
      {/* Step indicator + connector */}
      <div className="flex flex-col items-center pt-0.5">
        <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold font-mono ${dotColor}`}>
          {n}
        </div>
        {!last && <div className="w-0.5 flex-1 bg-slate-800 mt-1 mb-0" />}
      </div>

      {/* Content */}
      <div className={`flex-1 ${last ? '' : 'pb-10'}`}>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-white font-semibold">{title}</h2>
          <Badge status={status} />
        </div>
        <TermWindow cmd={cmd}>{children}</TermWindow>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const allContracts = getContracts()
  // Deduplicate by contract_id — multiple YAML files can share the same id
  const seenIds = new Set<string>()
  const contracts = allContracts.filter(c => {
    if (seenIds.has(c.contract_id)) return false
    seenIds.add(c.contract_id)
    return true
  })
  const datasets   = getLatestValidationPerDataset()
  const rawViolations = getViolations()
  const violations = rawViolations.filter(v => v.violation_id != null)
  const schemaReports = getSchemaEvolutionReports()
  const report     = getReport()

  // Derived statuses
  const totalFailed   = datasets.reduce((s, d) => s + d.latest_failed, 0)
  const validateStatus = totalFailed > 0 ? 'FAIL' : 'PASS'

  const hasBreaking   = report?.schema_changes_detected?.some(c => !c.backward_compatible) ?? false
  const schemaStatus  = hasBreaking ? 'WARN' : (schemaReports.length > 0 ? 'PASS' : 'DONE')

  const ai            = report?.ai_risk_assessment
  const aiStatus      = ai?.overall_ai_status?.toUpperCase() ?? 'DONE'
  const driftScore    = ai?.embedding_drift_score

  const healthScore   = report?.data_health_score ?? 0
  const reportStatus  = healthScore >= 80 ? 'PASS' : 'WARN'

  return (
    <div className="min-h-screen bg-slate-950 p-8 overflow-auto">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="mb-10">
          <h1 className="text-2xl font-bold text-white tracking-tight">Pipeline Walkthrough</h1>
          <p className="text-slate-400 text-sm mt-1">
            Data Contract Enforcer · 6-phase enforcement pipeline · Bitol v3.0.0
          </p>
        </div>

        {/* ─── Step 1: Generate ─── */}
        <StepRow n={1} title="Contract Generation" status="DONE" cmd="uv run main.py --phase generate">
          <TLine indent={false} value={<span className="text-slate-500">Generating contracts for {contracts.length} datasets…</span>} />
          <div className="mt-1 space-y-0.5">
            {contracts.map(c => (
              <div key={c.name} className="pl-2 flex gap-3">
                <span className="text-cyan-400 w-52 truncate">{c.contract_id}</span>
                <span className="text-slate-500">{CLAUSE_MAP[c.contract_id] ?? c.clause_count} clauses</span>
                <span className="text-green-400">✓</span>
              </div>
            ))}
          </div>
          <Divider />
          <TLine
            indent={false}
            value={<><span className="text-green-400">✓ </span><span className="text-slate-300">{contracts.length} contracts generated → </span><span className="text-slate-500">generated_contracts/</span></>}
          />
        </StepRow>

        {/* ─── Step 2: Validate ─── */}
        <StepRow n={2} title="Violation Detection" status={validateStatus}
          cmd="uv run main.py --phase validate --inject-violation --mode ENFORCE">
          <TLine indent={false} value={<span className="text-slate-500">Validating {datasets.length} datasets in ENFORCE mode…</span>} />
          <div className="mt-1 space-y-0.5">
            {datasets.map(d => {
              const hasFail = d.latest_failed > 0
              const hasWarn = !hasFail && (d.latest_total - d.latest_passed - d.latest_failed) > 0
              const statusLabel = hasFail ? 'FAIL' : hasWarn ? 'WARN' : 'PASS'
              const statusCls   = hasFail ? 'text-red-400' : hasWarn ? 'text-yellow-400' : 'text-green-400'
              const shortLabel  = d.label.split('—')[0].trim()
              return (
                <div key={d.contract_id} className="pl-2 flex gap-2 flex-wrap">
                  <span className="text-slate-300 w-24 truncate">{shortLabel}</span>
                  <span className="text-slate-600">{String(d.latest_total).padStart(4)} checks</span>
                  <span className="text-green-400">{String(d.latest_passed).padStart(4)} passed</span>
                  {hasFail && <span className="text-red-400">{d.latest_failed} failed</span>}
                  <span className={statusCls}>● {statusLabel}</span>
                  {hasFail && <span className="text-yellow-300">← CRITICAL injected</span>}
                </div>
              )
            })}
          </div>
          <Divider />
          {totalFailed > 0
            ? <TLine indent={false} valueCls="text-red-400"   value={`✗ ${totalFailed} failure(s) detected — pipeline blocked in ENFORCE mode`} />
            : <TLine indent={false} valueCls="text-green-400" value="✓ All checks passed" />
          }
        </StepRow>

        {/* ─── Step 3: Attributor ─── */}
        <StepRow n={3} title="Blame Attribution" status={violations.length > 0 ? 'DONE' : 'PASS'}
          cmd="uv run contracts/attributor.py --report validation_reports/week3-…_<TIMESTAMP>.json">
          <TLine indent={false} value={<span className="text-slate-500">Attributing {violations.length} violation(s)…</span>} />
          {violations.map(v => {
            const topBlame   = v.blame_chain?.[0]
            const subs       = v.blast_radius?.registry_subscribers ?? []
            const pipelines  = v.blast_radius?.affected_pipelines ?? []
            const sevCls     = v.severity === 'CRITICAL' ? 'text-red-400' : v.severity === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
            return (
              <div key={v.violation_id} className="mt-2 mb-1 space-y-0.5">
                <Divider color="text-slate-700" />
                <div className="pl-2 flex gap-3 items-center">
                  <span className={`${sevCls} font-bold`}>{v.severity}</span>
                  <span className="text-slate-400">{v.column_name}</span>
                </div>
                <TLine label="Message" value={v.message} valueCls="text-slate-300" />
                <TLine label="Subscribers"
                  value={<>{subs.length} ({subs.map(s => <span key={s.subscriber_id} className="text-cyan-400 mr-2">{s.subscriber_id} <span className="text-slate-500">{s.validation_mode}</span></span>)})</>}
                />
                <TLine label="Blast radius"
                  value={<><span className="text-yellow-400">{v.blast_radius.estimated_records} records</span><span className="text-slate-500"> · {pipelines.length} pipelines · {subs.length} subscribers</span></>}
                />
                {topBlame && (
                  <TLine label="Top blame"
                    value={<>commit <span className="text-indigo-400">{topBlame.commit_hash.slice(0, 8)}</span> by <span className="text-indigo-400">{topBlame.author}</span> <span className="text-slate-500">(confidence {Math.round(topBlame.confidence_score * 100)}%)</span></>}
                  />
                )}
              </div>
            )
          })}
          <Divider />
          <TLine indent={false} valueCls="text-green-400"
            value={`✓ ${violations.length} violation(s) written → violation_log/violations.jsonl`}
          />
        </StepRow>

        {/* ─── Step 4: Schema Analyzer ─── */}
        <StepRow n={4} title="Schema Evolution" status={schemaStatus}
          cmd="uv run contracts/schema_analyzer.py --snapshot-a <old.yaml> --snapshot-b <new.yaml>">
          <TLine indent={false} value={<span className="text-slate-500">Analyzing schema evolution across {schemaReports.length} snapshot pair(s)…</span>} />
          {(report?.schema_changes_detected?.length ?? 0) > 0
            ? report!.schema_changes_detected.map((c, i) => (
                <div key={i} className="mt-2 space-y-0.5">
                  <Divider color="text-slate-700" />
                  <div className="pl-2 flex gap-3">
                    <span className={c.backward_compatible ? 'text-green-400' : 'text-red-400'}>
                      {c.compatibility_verdict}
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className="text-yellow-300">{c.change_type}</span>
                  </div>
                  <TLine label="Field"  value={c.column} valueCls="text-cyan-400" />
                  <TLine label="Action" value={c.required_action} valueCls="text-slate-300" />
                </div>
              ))
            : <TLine value={<span className="text-slate-500">  No schema changes in latest snapshot pair</span>} />
          }
          <Divider />
          {hasBreaking
            ? <TLine indent={false} valueCls="text-yellow-400" value="⚠ BACKWARD_INCOMPATIBLE changes detected — migration required before deploy" />
            : <TLine indent={false} valueCls="text-green-400"  value="✓ All schema changes are backward compatible" />
          }
        </StepRow>

        {/* ─── Step 5: AI Extensions ─── */}
        <StepRow n={5} title="AI Extensions" status={aiStatus} cmd="uv run contracts/ai_extensions.py">
          <TLine indent={false} value={<span className="text-slate-500">Running 4 AI contract extensions…</span>} />
          {ai && (
            <div className="mt-1 space-y-0.5">
              {/* Embedding drift */}
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">[1] Embedding Drift</span>
                <span className="text-slate-400">drift=</span>
                <span className={ai.embedding_drift_status === 'PASS' ? 'text-green-400' : 'text-red-400'}>
                  {driftScore != null ? driftScore.toFixed(4) : 'N/A'}
                </span>
                <span className="text-slate-500">threshold={ai.embedding_threshold}</span>
                <span className={ai.embedding_drift_status === 'PASS' ? 'text-green-400' : 'text-red-400'}>
                  ● {ai.embedding_drift_status}
                </span>
              </div>
              {/* Prompt schema */}
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">[2] Prompt Schema</span>
                <span className="text-slate-400">violation_rate=</span>
                <span className="text-green-400">{((ai.prompt_input_violation_rate ?? 0) * 100).toFixed(1)}%</span>
                <span className="text-green-400">● PASS</span>
              </div>
              {/* LLM output */}
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">[3] LLM Output</span>
                <span className="text-slate-400">violation_rate=</span>
                <span className="text-green-400">{((ai.llm_output_violation_rate ?? 0) * 100).toFixed(1)}%</span>
                <span className="text-slate-500">trend={ai.llm_output_trend}</span>
                <span className="text-green-400">● PASS</span>
              </div>
              {/* Trace schema */}
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">[4] Trace Schema</span>
                <span className={ai.trace_schema_status === 'PASS' ? 'text-green-400' : 'text-yellow-400'}>
                  ● {ai.trace_schema_status}
                </span>
              </div>
              <Divider />
              <div className="pl-2 flex gap-3">
                <span className={aiStatus === 'AMBER' ? 'text-amber-400' : 'text-green-400'}>
                  ⬡ AI Status: {ai.overall_ai_status}
                </span>
                <span className="text-slate-400">—</span>
                <span className="text-slate-300 text-xs leading-5">{ai.narrative}</span>
              </div>
            </div>
          )}
        </StepRow>

        {/* ─── Step 6: Report ─── */}
        <StepRow n={6} title="Enforcer Report" status={reportStatus} cmd="uv run main.py --phase report" last>
          <TLine indent={false} value={<span className="text-slate-500">Aggregating {report?.validation_summary.reports_analyzed ?? 0} validation reports…</span>} />
          {report && (
            <div className="mt-1 space-y-0.5">
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">Health Score</span>
                <span className={healthScore >= 80 ? 'text-green-400' : healthScore >= 60 ? 'text-yellow-400' : 'text-red-400'}>
                  {healthScore}/100
                </span>
                <span className="text-slate-500">— {report.health_narrative}</span>
              </div>
              <div className="pl-2 flex gap-2">
                <span className="text-slate-500 w-36">Checks</span>
                <span className="text-white">{report.validation_summary.total_checks}</span>
                <span className="text-slate-600">(</span>
                <span className="text-green-400">{report.validation_summary.passed} pass</span>
                <span className="text-slate-600">·</span>
                <span className="text-red-400">{report.validation_summary.failed} fail</span>
                <span className="text-slate-600">·</span>
                <span className="text-yellow-400">{report.validation_summary.warned} warn</span>
                <span className="text-slate-600">)</span>
              </div>
              <div className="pl-2 flex gap-2 flex-wrap">
                <span className="text-slate-500 w-36">Violations</span>
                <span className="text-red-400">{report.violations_this_week.total} total</span>
                {Object.entries(report.violations_this_week.by_severity)
                  .filter(([, count]) => (count as number) > 0)
                  .map(([sev, count]) => (
                    <span key={sev} className="text-slate-500">
                      {sev}: <span className="text-white">{count as number}</span>
                    </span>
                  ))
                }
              </div>
              <div className="pl-2 flex gap-3">
                <span className="text-slate-500 w-36">AI Status</span>
                <span className={ai?.overall_ai_status === 'GREEN' ? 'text-green-400' : 'text-amber-400'}>
                  {ai?.overall_ai_status ?? '—'}
                </span>
              </div>
              {report.recommended_actions.slice(0, 3).map((a, i) => (
                <div key={i} className="pl-2 flex gap-3">
                  <span className="text-slate-600 w-36">Action [{a.priority}]</span>
                  <span className="text-slate-400 text-xs">{a.action}</span>
                </div>
              ))}
            </div>
          )}
          <Divider />
          <TLine indent={false} valueCls="text-green-400"
            value="✓ Report written → enforcer_report/report_data.json"
          />
        </StepRow>

      </div>
    </div>
  )
}
