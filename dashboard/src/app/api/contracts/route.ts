import { NextResponse } from 'next/server'
import { getContracts, getContractYaml } from '@/lib/data'

export function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const name = searchParams.get('name')
  if (name) {
    const yaml = getContractYaml(name)
    return NextResponse.json({ yaml })
  }
  return NextResponse.json(getContracts())
}
