import { spawn } from 'child_process'
import path from 'path'

const PROJECT_ROOT = path.resolve(process.cwd(), '..')

const ALLOWED_PREFIXES = ['uv run', 'python ', 'python3 ', 'uv ']

export async function POST(req: Request) {
  const body = await req.json() as { command?: string }
  const command = (body.command ?? '').trim()

  if (!command) {
    return new Response('Missing command', { status: 400 })
  }

  const allowed = ALLOWED_PREFIXES.some(p => command.startsWith(p))
  if (!allowed) {
    return new Response(
      `Command not allowed. Must start with: ${ALLOWED_PREFIXES.join(' | ')}`,
      { status: 400 }
    )
  }

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    start(controller) {
      const child = spawn(command, {
        cwd: PROJECT_ROOT,
        shell: true,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
      })

      const send = (text: string) => {
        try { controller.enqueue(encoder.encode(text)) } catch { /* closed */ }
      }

      child.stdout.on('data', (chunk: Buffer) => send(chunk.toString('utf-8')))
      child.stderr.on('data', (chunk: Buffer) => send(chunk.toString('utf-8')))

      child.on('error', (err: Error) => {
        send(`\n[ERROR] ${err.message}\n`)
        try { controller.close() } catch { /* already closed */ }
      })

      child.on('close', (code: number | null) => {
        send(`\n[EXIT ${code ?? 1}]\n`)
        try { controller.close() } catch { /* already closed */ }
      })
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-cache, no-store',
      'X-Accel-Buffering': 'no',
    },
  })
}
