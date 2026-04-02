import {
  ShieldCheck, CheckCircle2, XCircle, AlertTriangle,
  TrendingUp, Database, Layers, GitBranch,
} from 'lucide-react'
import StatCard from '@/components/StatCard'
import SeverityBadge from '@/components/SeverityBadge'
import { getReport, getLatestValidationPerDataset } from '@/lib/data'

function HealthGauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score))
  const color =
    pct >= 90 ? '#34d399'
    : pct >= 70 ? '#fbbf24'
    : '#f87171'
  return (
    <div className="flex flex-col items-center justify-center py-6">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r="50" fill="none" stroke="#1e293b" strokeWidth="14" />
          <circle
            cx="60" cy="60" r="50" fill="none"
            stroke={color} strokeWidth="14" strokeLinecap="round"
            strokeDasharray={`${2 * Math.PI * 50}`}
            strokeDashoffset={`${2 * Math.PI * 50 * (1 - pct / 100)}`}
            style={{ transition: 'stroke-dashoffset 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{pct}</span>
          <span className="text-xs text-slate-400">/ 100</span>
        </div>
      </div>
      <p className="mt-3 text-sm font-semibold" style={{ color }}>
        {pct >= 90 ? 'Healthy' : pct >= 70 ? 'Degraded' : 'Critical'}
      </p>
    </div>
  )
}

function PassBar({ passed, total }: { passed: number; total: number }) {
  const pct = total > 0 ? (passed / total) * 100 : 100
  return (
    <div className="w-full bg-slate-800 rounded-full h-1.5">
      <div
        className="h-1.5 rounded-full bg-emerald-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export default async function OverviewPage() {
  const report = getReport()
  const datasets = getLatestValidationPerDataset()

  if (!report) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        No report data found — run <code className="ml-1 text-slate-400">python main.py --phase report</code>
      </div>
    )
  }

  const { validation_summary: vs, violations_this_week: vw, schema_changes_detected, ai_risk_assessment: ai } = report

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Overview</h1>
        <p className="text-sm text-slate-500 mt-1">
          Data Contract Enforcer · Bitol v3.0.0 · Report {report.report_date}
        </p>
      </div>

      {/* Top row: gauge + stat cards */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Gauge */}
        <div className="glass rounded-xl lg:col-span-1 flex flex-col items-center justify-center">
          <p className="text-xs text-slate-500 uppercase tracking-wide pt-5">Health Score</p>
          <HealthGauge score={report.data_health_score} />
        </div>

        {/* Stats */}
        <div className="lg:col-span-4 grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Checks" value={vs.total_checks.toLocaleString()} icon={Database} color="indigo" />
          <StatCard label="Passed" value={vs.passed.toLocaleString()} icon={CheckCircle2} color="green" />
          <StatCard label="Failed" value={vs.failed} icon={XCircle} color={vs.failed > 0 ? 'red' : 'green'} />
          <StatCard label="Violations" value={vw.total} icon={AlertTriangle} color={vw.total > 0 ? 'yellow' : 'green'} />
        </div>
      </div>

      {/* Health narrative */}
      <div className="glass rounded-xl px-5 py-4 text-sm text-slate-400 leading-relaxed">
        {report.health_narrative}
      </div>

      {/* Per-dataset validation table */}
      <section>
        <h2 className="text-base font-semibold text-slate-200 mb-3">Validation by Dataset</h2>
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wide">
                <th className="text-left px-5 py-3">Dataset</th>
                <th className="text-right px-4 py-3">Checks</th>
                <th className="text-right px-4 py-3">Passed</th>
                <th className="text-right px-4 py-3">Failed</th>
                <th className="px-4 py-3 w-40">Pass Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {datasets.map(d => (
                <tr key={d.contract_id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-5 py-3 text-slate-200 font-medium">{d.label}</td>
                  <td className="px-4 py-3 text-right text-slate-400">{d.latest_total}</td>
                  <td className="px-4 py-3 text-right text-emerald-400">{d.latest_passed}</td>
                  <td className="px-4 py-3 text-right text-red-400">{d.latest_failed || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <PassBar passed={d.latest_passed} total={d.latest_total} />
                      <span className="text-xs text-slate-400 w-10 text-right">{d.pass_rate}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bottom row: top violations + schema changes + AI */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top violations */}
        <section className="lg:col-span-1">
          <h2 className="text-base font-semibold text-slate-200 mb-3">Top Violations</h2>
          <div className="glass rounded-xl divide-y divide-slate-800/60">
            {vw.top_violations.length === 0 ? (
              <p className="px-5 py-8 text-sm text-slate-500 text-center">No violations</p>
            ) : (
              vw.top_violations.map((v, i) => (
                <div key={i} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-500 font-mono">{v.check_id}</span>
                    <SeverityBadge value={v.severity} />
                  </div>
                  <p className="text-sm text-slate-300 truncate">{v.message}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{v.system} · {v.field}</p>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Schema changes */}
        <section className="lg:col-span-1">
          <h2 className="text-base font-semibold text-slate-200 mb-3">Schema Changes</h2>
          <div className="glass rounded-xl divide-y divide-slate-800/60">
            {schema_changes_detected.length === 0 ? (
              <p className="px-5 py-8 text-sm text-slate-500 text-center">No changes detected</p>
            ) : (
              schema_changes_detected.map((c, i) => (
                <div key={i} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-indigo-400">{c.change_type}</span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-md font-medium ${c.backward_compatible ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                      {c.backward_compatible ? 'Compatible' : 'Breaking'}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300 font-mono">{c.column}</p>
                  <p className="text-xs text-slate-500 mt-0.5 truncate">{c.required_action}</p>
                </div>
              ))
            )}
          </div>
        </section>

        {/* AI metrics */}
        <section className="lg:col-span-1">
          <h2 className="text-base font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-indigo-400" /> AI Quality
          </h2>
          <div className="glass rounded-xl p-5 space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">Overall AI Status</span>
              <SeverityBadge value={ai.overall_ai_status} />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">Embedding Drift</span>
              <span className="text-sm text-slate-300">
                {ai.embedding_drift_score !== null
                  ? ai.embedding_drift_score.toFixed(4)
                  : '—'}{' '}
                <span className="text-xs text-slate-500">/ {ai.embedding_threshold}</span>
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">Prompt Violations</span>
              <span className="text-sm text-slate-300">
                {ai.prompt_input_violation_rate !== null
                  ? `${(ai.prompt_input_violation_rate * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">LLM Output Violations</span>
              <span className="text-sm text-slate-300">
                {ai.llm_output_violation_rate !== null
                  ? `${(ai.llm_output_violation_rate * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">Output Trend</span>
              <span className="text-sm text-slate-300">{ai.llm_output_trend}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-500">Trace Schema</span>
              <span className="text-sm text-slate-300">{ai.trace_schema_status}</span>
            </div>
            <p className="text-xs text-slate-500 pt-2 border-t border-slate-800 leading-relaxed">
              {ai.narrative}
            </p>
          </div>
        </section>
      </div>

      {/* Recommended actions */}
      {report.recommended_actions.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-indigo-400" /> Recommended Actions
          </h2>
          <div className="glass rounded-xl divide-y divide-slate-800/60">
            {report.recommended_actions.map((a, i) => (
              <div key={i} className="px-5 py-3 flex items-start gap-4">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-600/20 flex items-center justify-center text-xs font-bold text-indigo-400">
                  {a.priority}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <SeverityBadge value={a.severity} />
                    <span className="text-sm text-slate-300">{a.action}</span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Affects: {a.affected_pipelines.join(', ')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
