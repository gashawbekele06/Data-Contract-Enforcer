import { NextResponse } from 'next/server'
import { getLatestValidationPerDataset, getAllValidationReports } from '@/lib/data'

export function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const mode = searchParams.get('mode') ?? 'summary'
  if (mode === 'all') {
    return NextResponse.json(getAllValidationReports())
  }
  return NextResponse.json(getLatestValidationPerDataset())
}
