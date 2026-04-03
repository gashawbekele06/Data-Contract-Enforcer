import { CheckCircle2, XCircle, AlertTriangle, Clock } from 'lucide-react'
import SeverityBadge from '@/components/SeverityBadge'
import { getAllValidationReports } from '@/lib/data'

function StatusIcon({ status }: { status: string }) {
  if (status === 'PASS') return <CheckCircle2 className="w-4 h-4 text-emerald-400" />
  if (status === 'FAIL') return <XCircle className="w-4 h-4 text-red-400" />
  if (status === 'WARN') return <AlertTriangle className="w-4 h-4 text-yellow-400" />
  return <AlertTriangle className="w-4 h-4 text-orange-400" />
}

export default async function ValidationsPage() {
  const reports = getAllValidationReports()

  const grouped: Record<string, typeof reports> = {}
  for (const r of reports) {
    if (!grouped[r.contract_id]) grouped[r.contract_id] = []
    grouped[r.contract_id].push(r)
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Validation Reports</h1>
        <p className="text-sm text-slate-500 mt-1">
          {reports.length} reports across {Object.keys(grouped).length} datasets
        </p>
      </div>

      {Object.entries(grouped).map(([contractId, reps]) => {
        const latest = reps[0]
        return (
          <section key={contractId}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-slate-200 font-mono">{contractId}</h2>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span className="text-emerald-400">{latest.passed} passed</span>
                {latest.failed > 0 && <span className="text-red-400">{latest.failed} failed</span>}
                {latest.warned > 0 && <span className="text-yellow-400">{latest.warned} warned</span>}
              </div>
            </div>

            {/* Latest report check results */}
            <div className="glass rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-2 text-xs text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                Latest run: {latest.run_timestamp}
                {latest.injected_violation && (
                  <span className="ml-2 bg-yellow-500/20 text-yellow-300 px-2 py-0.5 rounded text-[11px]">
                    injected violation
                  </span>
                )}
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800/60 text-xs text-slate-500 uppercase tracking-wide">
                    <th className="text-left px-5 py-2.5 w-8"></th>
                    <th className="text-left px-3 py-2.5">Check ID</th>
                    <th className="text-left px-3 py-2.5">Column</th>
                    <th className="text-left px-3 py-2.5">Type</th>
                    <th className="text-left px-3 py-2.5">Severity</th>
                    <th className="text-right px-4 py-2.5">Records Failing</th>
                    <th className="text-left px-4 py-2.5">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {latest.results?.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-800/20 transition-colors">
                      <td className="px-5 py-2.5">
                        <StatusIcon status={r.status} />
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs text-indigo-300">{r.check_id}</td>
                      <td className="px-3 py-2.5 font-mono text-xs text-slate-400">{r.column_name || '—'}</td>
                      <td className="px-3 py-2.5 text-xs text-slate-400">{r.check_type}</td>
                      <td className="px-3 py-2.5"><SeverityBadge value={r.severity} /></td>
                      <td className="px-4 py-2.5 text-right text-xs text-slate-400">
                        {r.records_failing > 0 ? (
                          <span className="text-red-400 font-semibold">{r.records_failing}</span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-400 max-w-xs truncate">{r.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* History (other runs) */}
            {reps.length > 1 && (
              <div className="mt-2 flex gap-2 flex-wrap">
                {reps.slice(1).map((r, i) => (
                  <div key={i} className="text-[11px] text-slate-500 bg-slate-800/60 rounded px-2 py-1">
                    {r.run_timestamp.slice(0, 16)} — {r.passed}/{r.total_checks} passed
                  </div>
                ))}
              </div>
            )}
          </section>
        )
      })}

      {reports.length === 0 && (
        <div className="flex items-center justify-center h-64 text-slate-500">
          No validation reports found — run{' '}
          <code className="ml-1 text-slate-400">python main.py --phase validate</code>
        </div>
      )}
    </div>
  )
}
