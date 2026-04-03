import { Network, ArrowRight, ShieldAlert } from 'lucide-react'
import { getSubscriptions } from '@/lib/data'

export default async function RegistryPage() {
  const subscriptions = getSubscriptions()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Contract Registry</h1>
        <p className="text-sm text-slate-500 mt-1">
          Tier 1 · {subscriptions.length} active subscriptions · Bitol v3.0.0
        </p>
      </div>

      {/* Flow overview */}
      <div className="glass rounded-xl px-5 py-4">
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <Network className="w-3.5 h-3.5" /> Subscription Map
        </p>
        <div className="flex flex-wrap gap-2">
          {subscriptions.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 bg-slate-800/60 rounded-lg px-3 py-1.5 text-xs">
              <span className="text-indigo-300 font-mono">{s.contract_id?.replace('urn:datacontract:', '')}</span>
              <ArrowRight className="w-3 h-3 text-slate-500" />
              <span className="text-slate-300 font-mono">{s.subscriber_id?.replace('urn:datacontract:', '')}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Subscriptions table */}
      <div className="space-y-4">
        {subscriptions.map((s, i) => {
          const breakingFields = Array.isArray(s.breaking_fields)
            ? s.breaking_fields.map(f => typeof f === 'string' ? { field: f, reason: '' } : f)
            : []

          return (
            <div key={i} className="glass rounded-xl overflow-hidden">
              {/* Header */}
              <div className="px-5 py-4 border-b border-slate-800 flex items-start justify-between flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-slate-200 font-mono">
                      {s.contract_id}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-sm font-semibold text-indigo-300 font-mono">
                      {s.subscriber_id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{s.subscriber_team} · {s.contact}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] bg-slate-700/60 text-slate-400 px-2 py-0.5 rounded">
                    {s.validation_mode}
                  </span>
                  <span className="text-[11px] text-slate-600">{s.registered_at}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-slate-800">
                {/* Fields consumed */}
                <div className="px-5 py-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Fields Consumed</p>
                  <div className="flex flex-wrap gap-1.5">
                    {s.fields_consumed?.map((f, fi) => (
                      <span key={fi} className="text-[11px] font-mono bg-slate-700/50 text-slate-300 px-2 py-0.5 rounded">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Breaking fields */}
                <div className="px-5 py-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3 text-red-400" /> Breaking Fields
                  </p>
                  {breakingFields.length === 0 ? (
                    <p className="text-xs text-slate-600">None specified</p>
                  ) : (
                    <div className="space-y-1.5">
                      {breakingFields.map((bf, bfi) => (
                        <div key={bfi} className="flex items-start gap-2">
                          <span className="text-[11px] font-mono bg-red-500/10 text-red-300 px-2 py-0.5 rounded border border-red-500/20 flex-shrink-0">
                            {bf.field}
                          </span>
                          {bf.reason && (
                            <span className="text-[11px] text-slate-500 leading-tight">{bf.reason}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {subscriptions.length === 0 && (
        <div className="glass rounded-xl flex items-center justify-center h-48 text-slate-500 text-sm">
          No subscriptions found in <code className="ml-1 text-slate-400">contract_registry/subscriptions.yaml</code>
        </div>
      )}
    </div>
  )
}
