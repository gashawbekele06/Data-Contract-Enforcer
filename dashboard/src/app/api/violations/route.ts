import { NextResponse } from 'next/server'
import { getViolations } from '@/lib/data'

export function GET() {
  return NextResponse.json(getViolations())
}
