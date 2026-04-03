import clsx from 'clsx'

const styles: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-300 border border-red-500/30',
  HIGH:     'bg-orange-500/20 text-orange-300 border border-orange-500/30',
  MEDIUM:   'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  LOW:      'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  INFO:     'bg-slate-600/40 text-slate-400 border border-slate-600/50',
  PASS:     'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
  FAIL:     'bg-red-500/20 text-red-300 border border-red-500/30',
  WARN:     'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
  ERROR:    'bg-orange-500/20 text-orange-300 border border-orange-500/30',
}

export default function SeverityBadge({ value }: { value: string }) {
  const upper = value?.toUpperCase() ?? 'INFO'
  return (
    <span className={clsx('inline-block text-[11px] font-semibold px-2 py-0.5 rounded-md', styles[upper] ?? styles.INFO)}>
      {upper}
    </span>
  )
}
