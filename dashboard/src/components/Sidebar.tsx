'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, ShieldCheck, AlertTriangle,
  FileText, Network, ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'

const NAV = [
  { href: '/',              label: 'Overview',    icon: LayoutDashboard },
  { href: '/validations',   label: 'Validations', icon: ShieldCheck },
  { href: '/violations',    label: 'Violations',  icon: AlertTriangle },
  { href: '/contracts',     label: 'Contracts',   icon: FileText },
  { href: '/registry',      label: 'Registry',    icon: Network },
]

export default function Sidebar() {
  const pathname = usePathname()
  return (
    <aside className="w-56 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-indigo-600 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-xs font-bold text-white leading-tight">Contract</p>
            <p className="text-xs font-bold text-indigo-400 leading-tight">Enforcer</p>
          </div>
        </div>
        <p className="text-[10px] text-slate-500 mt-1">TRP Week 7</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all',
                active
                  ? 'bg-indigo-600/20 text-indigo-300 font-medium'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
              )}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="w-4 h-4" />
                {label}
              </span>
              {active && <ChevronRight className="w-3 h-3 opacity-60" />}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-800">
        <p className="text-[10px] text-slate-600">Bitol v3.0.0 · Tier 1</p>
      </div>
    </aside>
  )
}
