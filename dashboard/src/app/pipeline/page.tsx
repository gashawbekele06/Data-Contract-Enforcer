'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Square, RotateCcw, Trash2, ChevronDown, ChevronUp, Terminal } from 'lucide-react'
import clsx from 'clsx'

// ── Step definitions ──────────────────────────────────────────────────────────

interface StepDef {
  n: number
  title: string
  subtitle: string
  defaultCmd: string
  hint?: string
}

const STEPS: StepDef[] = [
  {
    n: 1,
    title: 'Contract Generation',
    subtitle: 'Generate Bitol v3.0.0 YAML contracts for all 6 datasets',
    defaultCmd: 'uv run main.py --phase generate',
  },
  {
    n: 2,
    title: 'Violation Detection',
    subtitle: 'Validate all datasets in ENFORCE mode with injected confidence scale violation',
    defaultCmd: 'uv run main.py --phase validate --inject-violation --mode ENFORCE',
    hint: 'After running, copy the "Report :" filename for week3 from the output — you need it for Step 3.',
  },
  {
    n: 3,
    title: 'Blame Attribution',
    subtitle: 'Registry lookup → lineage BFS → git blame → violation log',
    defaultCmd:
      'uv run contracts/attributor.py --report validation_reports/week3-document-refinery-extractions_20260405_191615.json --lineage outputs/week4/lineage_snapshots.jsonl --registry contract_registry/subscriptions.yaml',
    hint: 'Replace the timestamp in the --report filename with the one from Step 2 output.',
  },
  {
    n: 4,
    title: 'Schema Evolution',
    subtitle: 'Diff two schema snapshots — classify breaking vs compatible changes',
    defaultCmd:
      'uv run contracts/schema_analyzer.py --snapshot-a schema_snapshots/week3-document-refinery-extractions/20260331_224716.yaml --snapshot-b schema_snapshots/week3-document-refinery-extractions/20260331_225113_breaking.yaml',
  },
  {
    n: 5,
    title: 'AI Extensions',
    subtitle: 'Embedding drift · prompt schema · LLM output schema · trace schema',
    defaultCmd: 'uv run contracts/ai_extensions.py',
  },
  {
    n: 6,
    title: 'Enforcer Report',
    subtitle: 'Aggregate all results into a versioned data health report',
    defaultCmd: 'uv run main.py --phase report',
  },
]

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = 'idle' | 'running' | 'success' | 'failed'

interface StepState {
  cmd: string
  status: Status
  output: string
  open: boolean
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function colorClass(line: string): string {
  if (/\[EXIT 0\]/.test(line))               return 'text-green-500'
  if (/\[EXIT/.test(line))                   return 'text-red-500'
  if (/\[ERROR\]/.test(line))                return 'text-red-400'
  if (/\bCRITICAL\b/.test(line))             return 'text-red-400'
  if (/\bFAIL\b/.test(line))                 return 'text-red-400'
  if (/✗|✘/.test(line))                      return 'text-red-400'
  if (/\bPASS\b/.test(line))                 return 'text-green-400'
  if (/✓|✔/.test(line))                      return 'text-green-400'
  if (/\bWARN\b|\bAMBER\b/.test(line))       return 'text-yellow-400'
  if (/⚠|WARNING/.test(line))               return 'text-yellow-400'
  if (/\bHIGH\b/.test(line))                 return 'text-orange-400'
  if (/^(─{3,}|#{1,3} )/.test(line.trim())) return 'text-slate-500'
  if (/Traceback|Error:|Exception:/.test(line)) return 'text-red-400'
  return 'text-slate-300'
}

function StatusBadge({ status }: { status: Status }) {
  const cfg: Record<Status, { label: string; cls: string }> = {
    idle:    { label: 'IDLE',    cls: 'bg-slate-800 text-slate-400 border-slate-700' },
    running: { label: 'RUNNING', cls: 'bg-blue-900/50 text-blue-300 border-blue-700 animate-pulse' },
    success: { label: 'PASS',    cls: 'bg-green-900/50 text-green-400 border-green-700' },
    failed:  { label: 'FAIL',    cls: 'bg-red-900/50 text-red-400 border-red-700' },
  }
  const { label, cls } = cfg[status]
  return (
    <span className={`font-mono text-xs px-2 py-0.5 rounded border ${cls}`}>{label}</span>
  )
}

function DotIndicator({ status, n }: { status: Status; n: number }) {
  const cls =
    status === 'success' ? 'bg-green-500 border-green-600 text-black' :
    status === 'failed'  ? 'bg-red-500 border-red-600 text-black' :
    status === 'running' ? 'bg-blue-500 border-blue-600 text-black animate-pulse' :
    'bg-slate-700 border-slate-600 text-slate-300'
  return (
    <div className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm font-bold font-mono shrink-0 ${cls}`}>
      {n}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const [steps, setSteps] = useState<Record<number, StepState>>(
    Object.fromEntries(
      STEPS.map(s => [s.n, { cmd: s.defaultCmd, status: 'idle', output: '', open: false }])
    )
  )
  const abortRefs = useRef<Record<number, AbortController>>({})
  const outputRefs = useRef<Record<number, HTMLDivElement | null>>({})
  // Ref so runStep/runAll never read stale cmd state
  const cmdsRef = useRef<Record<number, string>>(
    Object.fromEntries(STEPS.map(s => [s.n, s.defaultCmd]))
  )

  // Auto-scroll each output div when it changes
  useEffect(() => {
    STEPS.forEach(s => {
      const el = outputRefs.current[s.n]
      if (el) el.scrollTop = el.scrollHeight
    })
  }, [steps])

  const updateStep = useCallback((n: number, patch: Partial<StepState>) => {
    setSteps(prev => ({ ...prev, [n]: { ...prev[n], ...patch } }))
  }, [])

  const appendOutput = useCallback((n: number, text: string) => {
    setSteps(prev => ({ ...prev, [n]: { ...prev[n], output: prev[n].output + text } }))
  }, [])

  const runStep = useCallback(async (n: number): Promise<boolean> => {
    const cmd = cmdsRef.current[n].trim()
    if (!cmd) return false

    // Abort any previous run for this step
    abortRefs.current[n]?.abort()
    const abort = new AbortController()
    abortRefs.current[n] = abort

    updateStep(n, { status: 'running', output: '', open: true })

    try {
      const res = await fetch('/api/run-step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
        signal: abort.signal,
      })

      if (!res.ok) {
        const msg = await res.text()
        updateStep(n, { status: 'failed', output: `[ERROR] ${msg}` })
        return false
      }

      const reader = res.body?.getReader()
      if (!reader) { updateStep(n, { status: 'failed' }); return false }

      const decoder = new TextDecoder()
      let exitCode = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        const m = text.match(/\[EXIT (\d+)\]/)
        if (m) exitCode = parseInt(m[1])
        appendOutput(n, text)
      }

      const success = exitCode === 0
      updateStep(n, { status: success ? 'success' : 'failed' })
      return success
    } catch (err) {
      if ((err as Error).name === 'AbortError') return false
      appendOutput(n, `\n[ERROR] ${(err as Error).message}`)
      updateStep(n, { status: 'failed' })
      return false
    }
  }, [updateStep, appendOutput])

  const stopStep = useCallback((n: number) => {
    abortRefs.current[n]?.abort()
    setSteps(prev => ({
      ...prev,
      [n]: { ...prev[n], status: 'failed', output: prev[n].output + '\n[STOPPED by user]\n' },
    }))
  }, [])

  const resetStep = useCallback((n: number) => {
    abortRefs.current[n]?.abort()
    cmdsRef.current[n] = STEPS[n - 1].defaultCmd
    updateStep(n, { cmd: STEPS[n - 1].defaultCmd, status: 'idle', output: '' })
  }, [updateStep])

  // Run all steps sequentially — stops on first failure
  const runAll = useCallback(async () => {
    for (const step of STEPS) {
      const success = await runStep(step.n)
      if (!success) break
    }
  }, [runStep])

  const allDone = STEPS.every(s => steps[s.n]?.status === 'success')

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top bar */}
      <div className="border-b border-slate-800 px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Terminal className="w-5 h-5 text-indigo-400" />
            Pipeline Runner
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            Run each phase in order · edit any command before executing
          </p>
        </div>
        <div className="flex items-center gap-3">
          {allDone && (
            <span className="text-green-400 text-sm font-mono">✓ All phases complete</span>
          )}
          <button
            onClick={runAll}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg font-medium transition-colors"
          >
            <Play className="w-4 h-4" />
            Run All (1→6)
          </button>
        </div>
      </div>

      {/* Steps */}
      <div className="px-8 py-6 max-w-5xl mx-auto space-y-0">
        {STEPS.map((def, idx) => {
          const state = steps[def.n]
          const isLast = idx === STEPS.length - 1
          return (
            <div key={def.n} className="flex gap-5">
              {/* Left: step indicator + connector */}
              <div className="flex flex-col items-center">
                <DotIndicator status={state.status} n={def.n} />
                {!isLast && (
                  <div className={clsx(
                    'w-0.5 flex-1 min-h-[1.5rem] mt-1',
                    state.status === 'success' ? 'bg-green-800' : 'bg-slate-800'
                  )} />
                )}
              </div>

              {/* Right: card */}
              <div className={clsx(
                'flex-1 rounded-xl border transition-colors',
                !isLast ? 'mb-3' : '',
                state.status === 'running' ? 'border-blue-700 bg-slate-900' :
                state.status === 'success' ? 'border-green-800 bg-slate-900' :
                state.status === 'failed'  ? 'border-red-800 bg-slate-900' :
                'border-slate-800 bg-slate-900'
              )}>

                {/* Card header */}
                <div className="px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white text-sm">{def.title}</span>
                      <StatusBadge status={state.status} />
                    </div>
                    <p className="text-slate-500 text-xs mt-0.5">{def.subtitle}</p>
                  </div>
                  <button
                    onClick={() => updateStep(def.n, { open: !state.open })}
                    className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                    title={state.open ? 'Collapse' : 'Expand'}
                  >
                    {state.open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>

                {/* Expandable body */}
                {state.open && (
                  <div className="border-t border-slate-800 px-4 py-3 space-y-3">

                    {/* Hint */}
                    {def.hint && (
                      <p className="text-amber-400 text-xs bg-amber-900/20 border border-amber-800/50 rounded px-3 py-2">
                        ⚠ {def.hint}
                      </p>
                    )}

                    {/* Command input */}
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500 font-mono">command</label>
                      <textarea
                        className="w-full bg-black text-green-400 font-mono text-xs rounded-lg border border-slate-700 focus:border-indigo-500 focus:outline-none px-3 py-2 resize-none leading-relaxed"
                        rows={def.defaultCmd.length > 80 ? 3 : 1}
                        value={state.cmd}
                        onChange={e => {
                          cmdsRef.current[def.n] = e.target.value
                          updateStep(def.n, { cmd: e.target.value })
                        }}
                        spellCheck={false}
                        disabled={state.status === 'running'}
                      />
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2">
                      {state.status === 'running' ? (
                        <button
                          onClick={() => stopStep(def.n)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs rounded-lg font-medium transition-colors"
                        >
                          <Square className="w-3 h-3" />
                          Stop
                        </button>
                      ) : (
                        <button
                          onClick={() => runStep(def.n)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-xs rounded-lg font-medium transition-colors"
                        >
                          <Play className="w-3 h-3" />
                          Run Step {def.n}
                        </button>
                      )}
                      <button
                        onClick={() => resetStep(def.n)}
                        disabled={state.status === 'running'}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-white text-xs rounded-lg font-medium transition-colors"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Reset
                      </button>
                      {state.output && (
                        <button
                          onClick={() => updateStep(def.n, { output: '' })}
                          disabled={state.status === 'running'}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-white text-xs rounded-lg font-medium transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                          Clear
                        </button>
                      )}
                    </div>

                    {/* Terminal output */}
                    {(state.output || state.status === 'running') && (
                      <div
                        ref={el => { outputRefs.current[def.n] = el }}
                        className="bg-black rounded-lg border border-slate-800 p-3 h-72 overflow-y-auto font-mono text-xs leading-5"
                      >
                        {state.status === 'running' && !state.output && (
                          <span className="text-slate-500 animate-pulse">Running…</span>
                        )}
                        {state.output.split('\n').map((line, i) => (
                          <div key={i} className={colorClass(line)}>
                            {line || '\u00A0'}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Collapsed summary when done */}
                {!state.open && (state.status === 'success' || state.status === 'failed') && (
                  <div className="border-t border-slate-800 px-4 py-2">
                    <p className={clsx(
                      'text-xs font-mono truncate',
                      state.status === 'success' ? 'text-green-600' : 'text-red-600'
                    )}>
                      {state.output.split('\n').filter(Boolean).slice(-2).join(' · ')}
                    </p>
                  </div>
                )}

              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
