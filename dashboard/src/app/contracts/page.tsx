'use client'

import { useState, useEffect } from 'react'
import { FileText, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'

interface ContractFile {
  name: string
  contract_id: string
  title: string
  version: string
  owner: string
  clause_count: number
  downstream_count: number
}

export default function ContractsPage() {
  const [contracts, setContracts] = useState<ContractFile[] | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [yamlCache, setYamlCache] = useState<Record<string, string>>({})
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/contracts')
      .then(r => r.json())
      .then(setContracts)
      .catch(() => setContracts([]))
  }, [])

  const toggle = async (name: string) => {
    if (expanded === name) { setExpanded(null); return }
    setExpanded(name)
    if (!yamlCache[name]) {
      const res = await fetch(`/api/contracts?name=${encodeURIComponent(name)}`)
      const data = await res.json()
      setYamlCache(c => ({ ...c, [name]: data.yaml ?? '' }))
    }
  }

  const copy = (name: string) => {
    navigator.clipboard.writeText(yamlCache[name] ?? '')
    setCopied(name)
    setTimeout(() => setCopied(null), 1500)
  }

  if (!contracts) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
        Loading contracts…
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Contracts</h1>
        <p className="text-sm text-slate-500 mt-1">
          {contracts.length} generated Bitol v3.0.0 contracts
        </p>
      </div>

      <div className="space-y-2">
        {contracts.map(c => (
          <div key={c.name} className="glass rounded-xl overflow-hidden">
            <button
              onClick={() => toggle(c.name)}
              className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                <div className="text-left min-w-0">
                  <p className="text-sm font-semibold text-slate-200 truncate">{c.title}</p>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{c.contract_id}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                <div className="hidden sm:flex gap-4 text-xs text-slate-500">
                  <span>v{c.version}</span>
                  <span>{c.owner}</span>
                  <span>{c.downstream_count} downstream</span>
                </div>
                {expanded === c.name
                  ? <ChevronDown className="w-4 h-4 text-slate-400" />
                  : <ChevronRight className="w-4 h-4 text-slate-400" />}
              </div>
            </button>

            {expanded === c.name && (
              <div className="border-t border-slate-800">
                <div className="flex items-center justify-between px-5 py-2 border-b border-slate-800/60">
                  <span className="text-xs text-slate-500 font-mono">{c.name}</span>
                  <button
                    onClick={() => copy(c.name)}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    {copied === c.name
                      ? <><Check className="w-3.5 h-3.5 text-emerald-400" /> Copied</>
                      : <><Copy className="w-3.5 h-3.5" /> Copy YAML</>}
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <pre className="px-5 py-4 text-xs text-slate-300 leading-relaxed font-mono whitespace-pre max-h-[500px] overflow-y-auto">
                    {yamlCache[c.name] ?? 'Loading…'}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {contracts.length === 0 && (
        <div className="glass rounded-xl flex items-center justify-center h-48 text-slate-500 text-sm">
          No contracts found — run <code className="ml-1 text-slate-400">python main.py --phase generate</code>
        </div>
      )}
    </div>
  )
}
