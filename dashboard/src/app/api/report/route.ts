import { NextResponse } from 'next/server'
import { getReport } from '@/lib/data'

export function GET() {
  const report = getReport()
  if (!report) return NextResponse.json({ error: 'Report not found' }, { status: 404 })
  return NextResponse.json(report)
}
