import fs from 'fs'
import path from 'path'

const PROJECT_ROOT = path.resolve(process.cwd(), '..')

const ALLOWED = new Set([
  'week1-intent-code-correlator',
  'week2-digital-courtroom',
  'week3-document-refinery-extractions',
  'week4-brownfield-cartographer',
  'week5-event-sourcing-platform',
])

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const contract = searchParams.get('contract') ?? ''

  if (!ALLOWED.has(contract)) {
    return Response.json({ snapshots: [] })
  }

  const dir = path.join(PROJECT_ROOT, 'schema_snapshots', contract)
  try {
    const files = fs.readdirSync(dir)
      .filter((f: string) => f.endsWith('.yaml'))
      .sort()
    return Response.json({ snapshots: files })
  } catch {
    return Response.json({ snapshots: [] })
  }
}
