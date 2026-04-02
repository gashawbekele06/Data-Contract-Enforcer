import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'Data Contract Enforcer',
  description: 'Schema Integrity & Lineage Attribution Dashboard — TRP Week 7',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-slate-950">
          <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
        </main>
      </body>
    </html>
  )
}
