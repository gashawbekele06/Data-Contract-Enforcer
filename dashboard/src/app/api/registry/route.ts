import { NextResponse } from 'next/server'
import { getSubscriptions } from '@/lib/data'

export function GET() {
  return NextResponse.json(getSubscriptions())
}
