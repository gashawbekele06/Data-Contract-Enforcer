import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon: LucideIcon
  color?: 'indigo' | 'green' | 'red' | 'yellow' | 'slate'
}

const colors = {
  indigo: 'text-indigo-400 bg-indigo-500/10',
  green:  'text-emerald-400 bg-emerald-500/10',
  red:    'text-red-400 bg-red-500/10',
  yellow: 'text-yellow-400 bg-yellow-500/10',
  slate:  'text-slate-400 bg-slate-700/40',
}

export default function StatCard({ label, value, sub, icon: Icon, color = 'indigo' }: Props) {
  return (
    <div className="glass rounded-xl p-5 flex items-start gap-4">
      <div className={clsx('p-2.5 rounded-lg', colors[color])}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5 truncate">{sub}</p>}
      </div>
    </div>
  )
}
