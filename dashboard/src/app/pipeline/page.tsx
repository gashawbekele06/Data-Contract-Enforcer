'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Square, RotateCcw, Trash2, ChevronDown, ChevronUp, Terminal, Zap } from 'lucide-react'
import clsx from 'clsx'

// ── Week data ─────────────────────────────────────────────────────────────────

interface WeekData {
  n: number
  label: string
  source: string
  contractFile: string
  contractId: string
  injectViolation: boolean
}

const WEEK_DATA: Record<number, WeekData> = {
  1: {
    n: 1,
    label: 'Intent Code Correlator',
    source: 'outputs/week1/intent_records.jsonl',
    contractFile: 'generated_contracts/intent_records.yaml',
    contractId: 'week1-intent-code-correlator',
    injectViolation: false,
  },
  2: {
    n: 2,
    label: 'Digital Courtroom',
    source: 'outputs/week2/verdicts.jsonl',
    contractFile: 'generated_contracts/verdicts.yaml',
    contractId: 'week2-digital-courtroom',
    injectViolation: false,
  },
  3: {
    n: 3,
    label: 'Document Refinery',
    source: 'outputs/week3/extractions.jsonl',
    contractFile: 'generated_contracts/extractions.yaml',
    contractId: 'week3-document-refinery-extractions',
    injectViolation: true,
  },
  4: {
    n: 4,
    label: 'Brownfield Cartographer',
    source: 'outputs/week4/lineage_snapshots.jsonl',
    contractFile: 'generated_contracts/lineage_snapshots.yaml',
    contractId: 'week4-brownfield-cartographer',
    injectViolation: false,
  },
  5: {
    n: 5,
    label: 'Event Sourcing Platform',
    source: 'outputs/week5/events.jsonl',
    contractFile: 'generated_contracts/events.yaml',
    contractId: 'week5-event-sourcing-platform',
    injectViolation: false,
  },
}

// ── Command builders ──────────────────────────────────────────────────────────

function buildCmds(
  week: WeekData,
  snapshots: string[],
  reportFile?: string,
): Record<number, string> {
  const inject = week.injectViolation ? ' --inject-violation' : ''
  const snapshotDir = `schema_snapshots/${week.contractId}`

  // Step 4: pick best two snapshots
  let step4 = `uv run contracts/schema_analyzer.py` +
    ` --snapshot-a ${snapshotDir}/<SNAPSHOT_A>.yaml` +
    ` --snapshot-b ${snapshotDir}/<SNAPSHOT_B>.yaml`

  if (snapshots.length >= 2) {
    // For week3, prefer the known breaking snapshot pair for a clear demo
    if (
      week.contractId === 'week3-document-refinery-extractions' &&
      snapshots.includes('20260331_224716.yaml') &&
      snapshots.includes('20260331_225113_breaking.yaml')
    ) {
      step4 =
        `uv run contracts/schema_analyzer.py` +
        ` --snapshot-a ${snapshotDir}/20260331_224716.yaml` +
        ` --snapshot-b ${snapshotDir}/20260331_225113_breaking.yaml`
    } else {
      const a = snapshots[snapshots.length - 2]
      const b = snapshots[snapshots.length - 1]
      step4 = `uv run contracts/schema_analyzer.py --snapshot-a ${snapshotDir}/${a} --snapshot-b ${snapshotDir}/${b}`
    }
  }

  const reportArg = reportFile ?? `validation_reports/${week.contractId}_<TIMESTAMP>.json`

  return {
    1: `uv run contracts/generator.py --source ${week.source} --output generated_contracts`,
    2: `uv run contracts/runner.py --contract ${week.contractFile} --data ${week.source} --mode ENFORCE${inject}`,
    3: `uv run contracts/attributor.py --report ${reportArg} --lineage outputs/week4/lineage_snapshots.jsonl --registry contract_registry/subscriptions.yaml`,
    4: step4,
    5: 'uv run contracts/ai_extensions.py',
    6: 'uv run main.py --phase report',
  }
}

// ── Step definitions ──────────────────────────────────────────────────────────

const STEP_DEFS = [
  { n: 1, title: 'Contract Generation',  subtitle: 'Generates Bitol v3.0.0 YAML contract for the selected week\'s data' },
  { n: 2, title: 'Violation Detection',  subtitle: 'Validates data in ENFORCE mode — report filename auto-feeds Step 3' },
  { n: 3, title: 'Blame Attribution',    subtitle: 'Registry lookup → lineage BFS → git blame → violation log' },
  { n: 4, title: 'Schema Evolution',     subtitle: 'Diffs two schema snapshots and classifies breaking vs compatible changes' },
  { n: 5, title: 'AI Extensions',        subtitle: 'Embedding drift · prompt schema · LLM output schema · trace schema' },
  { n: 6, title: 'Enforcer Report',      subtitle: 'Aggregates all results into a versioned data health report' },
]

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = 'idle' | 'running' | 'success' | 'failed'

interface StepState {
  cmd: string
  status: Status
  output: string
  open: boolean
  autoDetected: boolean  // Step 3: timestamp was auto-filled from Step 2 output
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function colorClass(line: string): string {
  if (/\[EXIT 0\]/.test(line))                return 'text-green-500'
  if (/\[EXIT/.test(line))                    return 'text-red-500'
  if (/\[ERROR\]|\[STOPPED/.test(line))       return 'text-yellow-400'
  if (/\bCRITICAL\b|\bFAIL\b|✗|✘/.test(line)) return 'text-red-400'
  if (/\bPASS\b|✓|✔/.test(line))             return 'text-green-400'
  if (/\bWARN\b|\bAMBER\b|⚠|WARNING/.test(line)) return 'text-yellow-400'
  if (/\bHIGH\b/.test(line))                 return 'text-orange-400'
  if (/^(─{3,}|#{1,3} )/.test(line.trim()))  return 'text-slate-500'
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
  return <span className={`font-mono text-xs px-2 py-0.5 rounded border ${cls}`}>{label}</span>
}

function Dot({ status, n }: { status: Status; n: number }) {
  const cls =
    status === 'success' ? 'bg-green-500 border-green-400 text-black' :
    status === 'failed'  ? 'bg-red-500 border-red-400 text-black' :
    status === 'running' ? 'bg-blue-500 border-blue-400 text-black animate-pulse' :
    'bg-slate-700 border-slate-600 text-slate-300'
  return (
    <div className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm font-bold font-mono shrink-0 ${cls}`}>
      {n}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

const defaultCmds = buildCmds(WEEK_DATA[3], [])

export default function PipelinePage() {
  const [selectedWeek, setSelectedWeek] = useState(3)
  const [steps, setSteps] = useState<Record<number, StepState>>(
    Object.fromEntries(
      STEP_DEFS.map(s => [s.n, {
        cmd: defaultCmds[s.n],
        status: 'idle' as Status,
        output: '',
        open: false,
        autoDetected: false,
      }])
    )
  )

  const weekRef      = useRef(3)
  const snapshotsRef = useRef<string[]>([])
  const cmdsRef      = useRef<Record<number, string>>({ ...defaultCmds })
  const abortRefs  = useRef<Record<number, AbortController>>({})
  const outputRefs = useRef<Record<number, HTMLDivElement | null>>({})

  // ── When week changes: fetch snapshots → rebuild all commands ───────────────
  useEffect(() => {
    weekRef.current = selectedWeek
    const weekData = WEEK_DATA[selectedWeek]

    fetch(`/api/snapshots?contract=${weekData.contractId}`)
      .then(r => r.json())
      .then(({ snapshots }: { snapshots: string[] }) => {
        applyWeek(weekData, snapshots)
      })
      .catch(() => applyWeek(weekData, []))

    function applyWeek(w: WeekData, snapshots: string[]) {
      snapshotsRef.current = snapshots
      const cmds = buildCmds(w, snapshots)
      cmdsRef.current = { ...cmds }
      setSteps(prev =>
        Object.fromEntries(
          STEP_DEFS.map(s => [s.n, {
            ...prev[s.n],
            cmd: cmds[s.n],
            // Only reset if the step isn't currently running
            ...(prev[s.n].status !== 'running'
              ? { status: 'idle', output: '', autoDetected: false }
              : {}),
          }])
        )
      )
    }
  }, [selectedWeek])

  // ── Auto-scroll output divs ─────────────────────────────────────────────────
  useEffect(() => {
    STEP_DEFS.forEach(s => {
      const el = outputRefs.current[s.n]
      if (el) el.scrollTop = el.scrollHeight
    })
  }, [steps])

  // ── Helpers ─────────────────────────────────────────────────────────────────
  const updateStep = useCallback((n: number, patch: Partial<StepState>) => {
    setSteps(prev => ({ ...prev, [n]: { ...prev[n], ...patch } }))
  }, [])

  const appendOutput = useCallback((n: number, text: string) => {
    setSteps(prev => ({ ...prev, [n]: { ...prev[n], output: prev[n].output + text } }))
  }, [])

  // ── Run a single step ───────────────────────────────────────────────────────
  const runStep = useCallback(async (n: number): Promise<boolean> => {
    const cmd = cmdsRef.current[n]?.trim()
    if (!cmd) return false

    abortRefs.current[n]?.abort()
    const abort = new AbortController()
    abortRefs.current[n] = abort

    updateStep(n, { status: 'running', output: '', open: true, autoDetected: false })

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
      let localOutput = ''
      let exitCode = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        const m = text.match(/\[EXIT (\d+)\]/)
        if (m) exitCode = parseInt(m[1])
        localOutput += text
        appendOutput(n, text)
      }

      // ── Cascade: Step 2 → Step 3 auto-timestamp ──────────────────────────
      if (n === 2) {
        const match = localOutput.match(/validation_reports\/([\w-]+_\d{8}_\d{6}\.json)/)
        if (match) {
          const reportFile = `validation_reports/${match[1]}`
          const weekData = WEEK_DATA[weekRef.current]
          // Fetch current snapshots to rebuild step 4 correctly too
          const snaps = await fetch(`/api/snapshots?contract=${weekData.contractId}`)
            .then(r => r.json())
            .then((d: { snapshots: string[] }) => d.snapshots)
            .catch(() => [] as string[])
          const newCmd = buildCmds(weekData, snaps, reportFile)[3]
          cmdsRef.current[3] = newCmd
          setSteps(prev => ({
            ...prev,
            3: { ...prev[3], cmd: newCmd, autoDetected: true },
          }))
        }
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
    const weekData = WEEK_DATA[weekRef.current]
    const defaultCmd = buildCmds(weekData, snapshotsRef.current)[n]
    cmdsRef.current[n] = defaultCmd
    updateStep(n, { cmd: defaultCmd, status: 'idle', output: '', autoDetected: false })
  }, [updateStep])

  const runAll = useCallback(async () => {
    for (const s of STEP_DEFS) {
      const ok = await runStep(s.n)
      if (!ok) break
    }
  }, [runStep])

  const allDone = STEP_DEFS.every(s => steps[s.n]?.status === 'success')
  const anyRunning = STEP_DEFS.some(s => steps[s.n]?.status === 'running')

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* ── Top bar ── */}
      <div className="border-b border-slate-800 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Terminal className="w-5 h-5 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold leading-tight">Pipeline Runner</h1>
            <p className="text-slate-400 text-xs">
              Data Contract Enforcer · Bitol v3.0.0 · 6-phase enforcement
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {allDone && <span className="text-green-400 text-sm font-mono">✓ All phases complete</span>}
          <button
            onClick={runAll}
            disabled={anyRunning}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors"
          >
            <Zap className="w-4 h-4" />
            Run All (1 → 6)
          </button>
        </div>
      </div>

      {/* ── Week selector ── */}
      <div className="border-b border-slate-800 px-8 py-3 flex items-center gap-4">
        <span className="text-slate-400 text-xs font-medium uppercase tracking-wide shrink-0">Dataset</span>
        <div className="flex gap-2 flex-wrap">
          {Object.values(WEEK_DATA).map(w => (
            <button
              key={w.n}
              onClick={() => !anyRunning && setSelectedWeek(w.n)}
              disabled={anyRunning}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
                selectedWeek === w.n
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-indigo-600 hover:text-white',
                anyRunning && 'opacity-40 cursor-not-allowed'
              )}
            >
              <span className="font-mono text-slate-400 mr-1.5">W{w.n}</span>
              {w.label}
            </button>
          ))}
        </div>
        <div className="ml-auto text-xs text-slate-500 font-mono">
          {WEEK_DATA[selectedWeek].source}
        </div>
      </div>

      {/* ── Steps ── */}
      <div className="px-8 py-6 max-w-5xl mx-auto">
        {STEP_DEFS.map((def, idx) => {
          const state = steps[def.n]
          const isLast = idx === STEP_DEFS.length - 1
          const hasTimestampPlaceholder = state.cmd.includes('<TIMESTAMP>')

          return (
            <div key={def.n} className="flex gap-5">
              {/* Dot + connector */}
              <div className="flex flex-col items-center">
                <Dot status={state.status} n={def.n} />
                {!isLast && (
                  <div className={clsx(
                    'w-0.5 flex-1 min-h-6 mt-1',
                    state.status === 'success' ? 'bg-green-800' : 'bg-slate-800'
                  )} />
                )}
              </div>

              {/* Card */}
              <div className={clsx(
                'flex-1 rounded-xl border transition-colors',
                !isLast && 'mb-3',
                state.status === 'running' ? 'border-blue-700' :
                state.status === 'success' ? 'border-green-800' :
                state.status === 'failed'  ? 'border-red-800'   :
                'border-slate-800',
                'bg-slate-900'
              )}>
                {/* Card header */}
                <div className="px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-white text-sm">
                        Step {def.n} — {def.title}
                      </span>
                      <StatusBadge status={state.status} />
                      {def.n === 3 && state.autoDetected && (
                        <span className="text-green-400 text-xs font-mono bg-green-900/30 border border-green-800 px-1.5 py-0.5 rounded">
                          ✓ timestamp auto-detected from Step 2
                        </span>
                      )}
                      {def.n === 3 && !state.autoDetected && hasTimestampPlaceholder && state.status === 'idle' && (
                        <span className="text-amber-400 text-xs font-mono bg-amber-900/20 border border-amber-800/50 px-1.5 py-0.5 rounded">
                          ⚠ run Step 2 first to auto-fill timestamp
                        </span>
                      )}
                    </div>
                    <p className="text-slate-500 text-xs mt-0.5">{def.subtitle}</p>
                  </div>
                  <button
                    onClick={() => updateStep(def.n, { open: !state.open })}
                    className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                  >
                    {state.open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>

                {/* Expandable body */}
                {state.open && (
                  <div className="border-t border-slate-800 px-4 py-3 space-y-3">
                    {/* Command textarea */}
                    <div className="space-y-1">
                      <label className="text-xs text-slate-500 font-mono">command</label>
                      <textarea
                        className={clsx(
                          'w-full bg-black font-mono text-xs rounded-lg border focus:outline-none px-3 py-2 resize-none leading-relaxed',
                          hasTimestampPlaceholder
                            ? 'text-amber-400 border-amber-800 focus:border-amber-600'
                            : 'text-green-400 border-slate-700 focus:border-indigo-500'
                        )}
                        rows={state.cmd.length > 90 ? 3 : 2}
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
                          <Square className="w-3 h-3" /> Stop
                        </button>
                      ) : (
                        <button
                          onClick={() => runStep(def.n)}
                          disabled={hasTimestampPlaceholder}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs rounded-lg font-medium transition-colors"
                          title={hasTimestampPlaceholder ? 'Replace <TIMESTAMP> before running' : undefined}
                        >
                          <Play className="w-3 h-3" /> Run Step {def.n}
                        </button>
                      )}
                      <button
                        onClick={() => resetStep(def.n)}
                        disabled={state.status === 'running'}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-white text-xs rounded-lg font-medium transition-colors"
                      >
                        <RotateCcw className="w-3 h-3" /> Reset
                      </button>
                      {state.output && state.status !== 'running' && (
                        <button
                          onClick={() => updateStep(def.n, { output: '' })}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg font-medium transition-colors"
                        >
                          <Trash2 className="w-3 h-3" /> Clear
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
                          <div key={i} className={colorClass(line)}>{line || '\u00A0'}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Collapsed summary after run */}
                {!state.open && (state.status === 'success' || state.status === 'failed') && (
                  <div className="border-t border-slate-800 px-4 py-2">
                    <p className={clsx(
                      'text-xs font-mono truncate',
                      state.status === 'success' ? 'text-green-700' : 'text-red-700'
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
