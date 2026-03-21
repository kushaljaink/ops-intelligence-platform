'use client'
import { useEffect, useState } from 'react'

type Incident = {
  id: string
  stage: string
  severity: string
  description: string
  status: string
  created_at: string
  industry: string
}

type AnalysisState = {
  loading: boolean
  result: string | null
  error: string | null
}

type WorkflowRow = {
  stage: string
  queue_size: string
  processing_time_seconds: string
  throughput: string
}

type CustomResult = {
  detected_issues: { stage: string; issues: string[] }[]
  ai_analysis: string
} | null

const BACKEND = 'https://ops-intelligence-platform.onrender.com'

const INDUSTRIES = [
  { value: 'cruise',     label: 'Cruise Terminal' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'banking',    label: 'Banking & Finance' },
  { value: 'ecommerce',  label: 'E-commerce & Logistics' },
  { value: 'airport',    label: 'Airport Operations' },
  { value: 'custom',     label: 'Custom...' },
]

const INDUSTRY_CONTEXT: Record<string, { scenario: string; what: string; example: WorkflowRow }> = {
  cruise: {
    scenario: 'A cruise terminal processing 3,000 passengers for embarkation',
    what: 'Each incident represents a boarding workflow stage where metrics have breached operational thresholds — triggering an alert.',
    example: { stage: 'baggage_drop', queue_size: '65', processing_time_seconds: '420', throughput: '6' },
  },
  healthcare: {
    scenario: 'A hospital emergency department during a high-demand shift',
    what: 'Each incident represents a patient flow stage where wait times or throughput have exceeded safe operational limits.',
    example: { stage: 'patient_triage', queue_size: '28', processing_time_seconds: '180', throughput: '8' },
  },
  banking: {
    scenario: 'A retail bank processing loan applications during peak season',
    what: 'Each incident represents a processing stage where backlog or SLA thresholds have been breached.',
    example: { stage: 'loan_verification', queue_size: '140', processing_time_seconds: '720', throughput: '3' },
  },
  ecommerce: {
    scenario: 'A fulfilment warehouse during a high-volume sales event',
    what: 'Each incident represents a fulfilment stage where pick rates, dispatch times, or queue sizes have hit critical levels.',
    example: { stage: 'warehouse_picking', queue_size: '320', processing_time_seconds: '250', throughput: '30' },
  },
  airport: {
    scenario: 'An international airport terminal during morning peak hours',
    what: 'Each incident represents a passenger processing stage where throughput or wait times have exceeded safe thresholds.',
    example: { stage: 'security_screening', queue_size: '95', processing_time_seconds: '300', throughput: '14' },
  },
  custom: {
    scenario: 'A live operational workflow with active threshold breaches',
    what: 'Each incident represents a stage in your workflow where metrics have exceeded normal operating limits.',
    example: { stage: 'your_stage', queue_size: '75', processing_time_seconds: '350', throughput: '6' },
  },
}

const CSV_TEMPLATE = `stage,queue_size,processing_time_seconds,throughput
stage_one,12,45,120
stage_two,67,380,8
stage_three,5,30,200`

const emptyRow = (): WorkflowRow => ({
  stage: '',
  queue_size: '',
  processing_time_seconds: '',
  throughput: '',
})

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analyses, setAnalyses] = useState<Record<string, AnalysisState>>({})

  // Industry state
  const [selectedIndustry, setSelectedIndustry] = useState('cruise')
  const [customIndustry, setCustomIndustry] = useState('')
  const industryValue = selectedIndustry === 'custom' ? customIndustry || 'operations' : selectedIndustry
  const industryLabel = INDUSTRIES.find(i => i.value === selectedIndustry)?.label ?? customIndustry
  const context = INDUSTRY_CONTEXT[selectedIndustry] ?? INDUSTRY_CONTEXT['custom']

  // Custom analysis state
  const [inputMode, setInputMode] = useState<'form' | 'csv'>('form')
  const [formRows, setFormRows] = useState<WorkflowRow[]>([emptyRow()])
  const [csvText, setCsvText] = useState('')
  const [customLoading, setCustomLoading] = useState(false)
  const [customResult, setCustomResult] = useState<CustomResult>(null)
  const [customError, setCustomError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setIncidents([])
    setAnalyses({})
    fetch(`${BACKEND}/incidents?industry=${industryValue}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => {
        setIncidents(d.incidents ?? [])
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [industryValue])

  const analyzeIncident = async (id: string) => {
    setAnalyses(prev => ({ ...prev, [id]: { loading: true, result: null, error: null } }))
    try {
      const r = await fetch(`${BACKEND}/analyze-incident/${id}`, { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const d = await r.json()
      setAnalyses(prev => ({ ...prev, [id]: { loading: false, result: d.ai_analysis, error: null } }))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setAnalyses(prev => ({ ...prev, [id]: { loading: false, result: null, error: message } }))
    }
  }

  const updateRow = (index: number, field: keyof WorkflowRow, value: string) => {
    setFormRows(prev => prev.map((r, i) => i === index ? { ...r, [field]: value } : r))
  }

  const addRow = () => setFormRows(prev => [...prev, emptyRow()])
  const removeRow = (index: number) => setFormRows(prev => prev.filter((_, i) => i !== index))

  const parseRows = (): WorkflowRow[] | null => {
    if (inputMode === 'form') return formRows
    const lines = csvText.trim().split('\n').filter(Boolean)
    if (lines.length < 2) return null
    return lines.slice(1).map(line => {
      const [stage, queue_size, processing_time_seconds, throughput] = line.split(',')
      return {
        stage: stage?.trim() ?? '',
        queue_size: queue_size?.trim() ?? '',
        processing_time_seconds: processing_time_seconds?.trim() ?? '',
        throughput: throughput?.trim() ?? '',
      }
    })
  }

  const analyzeCustom = async () => {
    const rows = parseRows()
    if (!rows || rows.length === 0) { setCustomError('No data to analyze.'); return }
    setCustomLoading(true)
    setCustomResult(null)
    setCustomError(null)
    try {
      const payload = {
        industry: industryValue,
        rows: rows.map(r => ({
          stage: r.stage,
          queue_size: parseFloat(r.queue_size) || 0,
          processing_time_seconds: parseFloat(r.processing_time_seconds) || 0,
          throughput: parseFloat(r.throughput) || 0,
        })),
      }
      const r = await fetch(`${BACKEND}/analyze-custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setCustomResult(await r.json())
    } catch (err: unknown) {
      setCustomError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setCustomLoading(false)
    }
  }

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'workflow_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const severityColor = (severity: string) => {
    if (severity === 'high') return 'bg-red-500/20 text-red-400 border border-red-500/30'
    if (severity === 'medium') return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
    return 'bg-green-500/20 text-green-400 border border-green-500/30'
  }

  const stageLabel = (stage: string) =>
    stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

  const ex = context.example

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-1">Ops Intelligence Platform</h1>
            <p className="text-gray-400">
              {selectedIndustry === 'custom' && customIndustry
                ? `${customIndustry.charAt(0).toUpperCase() + customIndustry.slice(1)} Operations`
                : industryLabel
              } — Live incident monitoring
            </p>
          </div>

          {/* Industry selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-400 whitespace-nowrap">Industry:</label>
            <select
              value={selectedIndustry}
              onChange={e => {
                setSelectedIndustry(e.target.value)
                setCustomResult(null)
                setCustomError(null)
                setFormRows([emptyRow()])
              }}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {INDUSTRIES.map(i => (
                <option key={i.value} value={i.value}>{i.label}</option>
              ))}
            </select>
            {selectedIndustry === 'custom' && (
              <input
                value={customIndustry}
                onChange={e => setCustomIndustry(e.target.value)}
                placeholder="e.g. retail, manufacturing..."
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 w-48"
              />
            )}
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">Total incidents</p>
            <p className="text-2xl font-bold">{incidents.length}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">High severity</p>
            <p className="text-2xl font-bold text-red-400">
              {incidents.filter(i => i.severity === 'high').length}
            </p>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">Open</p>
            <p className="text-2xl font-bold text-yellow-400">
              {incidents.filter(i => i.status === 'open').length}
            </p>
          </div>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

          {/* LEFT — Demo Incidents */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Live Demo — Active Incidents</h2>

            {/* Context banner */}
            <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-4">
              <p className="text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-1">Demo Scenario</p>
              <p className="text-sm text-gray-300 mb-1">{context.scenario}</p>
              <p className="text-xs text-gray-500">{context.what}</p>
            </div>

            {loading ? (
              <p className="text-gray-400">Loading incidents...</p>
            ) : error ? (
              <p className="text-red-400">Failed to load incidents: {error}</p>
            ) : incidents.length === 0 ? (
              <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-gray-500 text-sm">
                No incidents found for this industry.
              </div>
            ) : (
              <div className="space-y-4">
                {incidents.map(incident => {
                  const analysis = analyses[incident.id]
                  return (
                    <div key={incident.id} className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-semibold text-lg">{stageLabel(incident.stage)}</h3>
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${severityColor(incident.severity)}`}>
                          {incident.severity.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-gray-400 text-sm mb-3">{incident.description}</p>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span>Status: <span className="text-yellow-400">{incident.status}</span></span>
                          <span>Detected: {new Date(incident.created_at).toLocaleString()}</span>
                        </div>
                        <button
                          onClick={() => analyzeIncident(incident.id)}
                          disabled={analysis?.loading}
                          className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {analysis?.loading ? (
                            <>
                              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                              </svg>
                              Analyzing…
                            </>
                          ) : 'Analyze with AI'}
                        </button>
                      </div>
                      {analysis?.error && (
                        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                          Error: {analysis.error}
                        </div>
                      )}
                      {analysis?.result && (
                        <div className="mt-4 p-4 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">AI Analysis</p>
                          <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{analysis.result}</p>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* RIGHT — Try With Your Data */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Try With Your Data</h2>

            {/* How it works banner */}
            <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-4">
              <p className="text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-1">How it works</p>
              <p className="text-sm text-gray-300">Enter your own workflow stages and metrics. The AI will detect bottlenecks and give you specific recommendations — tailored to the selected industry.</p>
            </div>

            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">

              {/* Mode toggle */}
              <div className="flex rounded-lg bg-gray-800 p-1 mb-6 w-fit">
                {(['form', 'csv'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => { setInputMode(mode); setCustomResult(null); setCustomError(null) }}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      inputMode === mode ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {mode === 'form' ? 'Simple Form' : 'Paste CSV'}
                  </button>
                ))}
              </div>

              {/* Simple Form */}
              {inputMode === 'form' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-xs text-gray-500 px-1">
                    <span>Stage</span>
                    <span>Queue size</span>
                    <span>Proc. time (s)</span>
                    <span>Throughput/hr</span>
                  </div>
                  {formRows.map((row, i) => (
                    <div key={i} className="grid grid-cols-4 gap-2 items-center">
                      <input
                        value={row.stage}
                        onChange={e => updateRow(i, 'stage', e.target.value)}
                        placeholder={ex.stage}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                      <input
                        type="number"
                        value={row.queue_size}
                        onChange={e => updateRow(i, 'queue_size', e.target.value)}
                        placeholder={ex.queue_size}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                      <input
                        type="number"
                        value={row.processing_time_seconds}
                        onChange={e => updateRow(i, 'processing_time_seconds', e.target.value)}
                        placeholder={ex.processing_time_seconds}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                      <div className="flex gap-2">
                        <input
                          type="number"
                          value={row.throughput}
                          onChange={e => updateRow(i, 'throughput', e.target.value)}
                          placeholder={ex.throughput}
                          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-full"
                        />
                        {formRows.length > 1 && (
                          <button
                            onClick={() => removeRow(i)}
                            className="text-gray-600 hover:text-red-400 transition-colors text-lg leading-none"
                          >×</button>
                        )}
                      </div>
                    </div>
                  ))}
                  <p className="text-xs text-gray-600 px-1 mt-1">
                    e.g. stage: <span className="text-gray-500">{ex.stage}</span> · queue: <span className="text-gray-500">{ex.queue_size}</span> · proc. time: <span className="text-gray-500">{ex.processing_time_seconds}s</span> · throughput: <span className="text-gray-500">{ex.throughput}/hr</span>
                  </p>
                  <button
                    onClick={addRow}
                    className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors mt-1"
                  >
                    + Add stage
                  </button>
                </div>
              )}

              {/* CSV mode */}
              {inputMode === 'csv' && (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">
                    Format: <code className="text-gray-400">stage, queue_size, processing_time_seconds, throughput</code>
                  </p>
                  <textarea
                    value={csvText}
                    onChange={e => setCsvText(e.target.value)}
                    placeholder={`stage,queue_size,processing_time_seconds,throughput\n${ex.stage},${ex.queue_size},${ex.processing_time_seconds},${ex.throughput}`}
                    rows={7}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-indigo-500 resize-none"
                  />
                  <button
                    onClick={downloadTemplate}
                    className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Download template CSV
                  </button>
                </div>
              )}

              {/* Analyze button */}
              <button
                onClick={analyzeCustom}
                disabled={customLoading}
                className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {customLoading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Analyzing…
                  </>
                ) : 'Analyze My Data'}
              </button>

              {/* Custom result */}
              {customError && (
                <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  Error: {customError}
                </div>
              )}
              {customResult && (
                <div className="mt-4 space-y-4">
                  {customResult.detected_issues.length > 0 ? (
                    <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Detected Issues</p>
                      <ul className="space-y-1">
                        {customResult.detected_issues.map((item, i) => (
                          <li key={i} className="text-sm text-yellow-300">
                            <span className="font-medium">{stageLabel(item.stage)}:</span>{' '}
                            <span className="text-yellow-400/80">{item.issues.join(', ')}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
                      No threshold violations detected across all stages.
                    </div>
                  )}
                  <div className="p-4 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                    <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">AI Recommendations</p>
                    <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{customResult.ai_analysis}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </main>
  )
}
