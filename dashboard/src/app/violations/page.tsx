import { AlertTriangle, GitCommit, Radio, Users } from 'lucide-react'
import SeverityBadge from '@/components/SeverityBadge'
import { getViolations } from '@/lib/data'

export default async function ViolationsPage() {
  const violations = getViolations()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Violations</h1>
        <p className="text-sm text-slate-500 mt-1">
          {violations.length} violation{violations.length !== 1 ? 's' : ''} recorded · 4-step attribution pipeline
        </p>
      </div>

      {violations.length === 0 && (
        <div className="glass rounded-xl flex items-center justify-center h-48 text-slate-500">
          <AlertTriangle className="w-5 h-5 mr-2" /> No violations in log
        </div>
      )}

      {violations.map((v, idx) => (
        <div key={idx} className="glass rounded-xl overflow-hidden">
          {/* Violation header */}
          <div className="px-5 py-4 border-b border-slate-800 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <SeverityBadge value={v.severity} />
                <span className="text-sm font-semibold text-white">{v.message}</span>
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500 flex-wrap">
                <span className="font-mono text-indigo-300">{v.check_id}</span>
                <span>·</span>
                <span className="font-mono">{v.contract_id}</span>
                <span>·</span>
                <span className="font-mono">{v.column_name}</span>
                {v.detected_at && (
                  <>
                    <span>·</span>
                    <span>{v.detected_at.slice(0, 16)}</span>
                  </>
                )}
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-slate-500">Records Failing</p>
              <p className="text-xl font-bold text-red-400">{v.records_failing}</p>
            </div>
          </div>

          {/* Actual vs Expected */}
          <div className="px-5 py-3 border-b border-slate-800 flex gap-8 text-sm">
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Actual</p>
              <p className="text-red-300 font-mono">{v.actual_value}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Expected</p>
              <p className="text-emerald-300 font-mono">{v.expected}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-slate-800">
            {/* Blame chain */}
            <div className="px-5 py-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-1.5 mb-3">
                <GitCommit className="w-3.5 h-3.5" /> Blame Chain
              </h3>
              {v.blame_chain?.length > 0 ? (
                <div className="space-y-2">
                  {v.blame_chain.map((b, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-slate-700 flex items-center justify-center text-[11px] text-slate-400 font-bold">
                        {b.rank}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs text-slate-300 font-semibold">{b.author}</p>
                        <p className="text-xs text-slate-500 font-mono truncate">{b.commit_hash?.slice(0, 8)} — {b.commit_message?.slice(0, 60)}</p>
                        <div className="flex gap-3 mt-0.5 text-[11px] text-slate-600">
                          <span>{b.commit_timestamp?.slice(0, 10)}</span>
                          <span>confidence: {(b.confidence_score * 100).toFixed(0)}%</span>
                          {b.lineage_hops != null && <span>hops: {b.lineage_hops}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-600">No blame data</p>
              )}
            </div>

            {/* Blast radius */}
            <div className="px-5 py-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-1.5 mb-3">
                <Radio className="w-3.5 h-3.5" /> Blast Radius
                {v.blast_radius?.blast_radius_source && (
                  <span className="ml-1 text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded">
                    {v.blast_radius.blast_radius_source}
                  </span>
                )}
              </h3>
              {v.blast_radius ? (
                <div className="space-y-2">
                  <div className="flex gap-6 text-sm">
                    <div>
                      <p className="text-xs text-slate-500">Est. Records</p>
                      <p className="text-white font-semibold">{v.blast_radius.estimated_records?.toLocaleString() ?? '—'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Affected Nodes</p>
                      <p className="text-white font-semibold">{v.blast_radius.affected_nodes?.length ?? 0}</p>
                    </div>
                  </div>

                  {v.blast_radius.affected_nodes?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {v.blast_radius.affected_nodes.map((n, i) => (
                        <span key={i} className="text-[11px] bg-slate-700/60 text-slate-400 px-2 py-0.5 rounded font-mono">
                          {n}
                        </span>
                      ))}
                    </div>
                  )}

                  {(v.blast_radius.registry_subscribers?.length ?? 0) > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-slate-500 flex items-center gap-1 mb-2">
                        <Users className="w-3 h-3" /> Registry Subscribers
                      </p>
                      <div className="space-y-1.5">
                        {(v.blast_radius.registry_subscribers ?? []).map((s, i) => (
                          <div key={i} className="flex items-center justify-between bg-slate-800/60 rounded px-3 py-1.5">
                            <div>
                              <p className="text-xs text-slate-300 font-semibold">{s.subscriber_id}</p>
                              <p className="text-[11px] text-slate-500">{s.subscriber_team} · {s.contact}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-[11px] text-slate-500">depth</p>
                              <p className="text-xs text-indigo-300 font-semibold">{s.contamination_depth ?? '—'}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-slate-600">No blast radius data</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
