'use client'
import { useEffect, useState } from 'react'

type Incident = {
  id: string; stage: string; severity: string; description: string
  status: string; created_at: string; resolved_at?: string; industry: string
}
type AnalysisState = {
  loading: boolean; result: string | null; error: string | null
  rateLimit: boolean; confidence?: number; confidenceReason?: string
}
type WorkflowRow = { stage: string; queue_size: string; processing_time_seconds: string; throughput: string }
type CustomResult = { detected_issues: { stage: string; issues: string[] }[]; ai_analysis: string } | null
type Stats = { total: number; high_severity: number; open: number; trend: number }
type AnalysisLog = { id: string; ai_analysis: string; triggered_by: string; created_at: string; confidence_score?: number; confidence_reason?: string }
type HealthScore = { stage: string; health_score: number; avg_24h: number; trend: string; status: string }
type RecurringPattern = { stage: string; breach_count: number; peak_hour_label: string; peak_dow_label: string; peak_hour_pct: number; peak_dow_pct: number; insight: string; severity: string }
type CascadePrediction = { source_stage: string; target_stage: string; confidence: number; lag_hours: number; insight: string; alert: boolean }
type AnomalyScore = { stage: string; current_health: number; baseline_health: number; deviation: number; anomaly_score: number; flag: boolean; insight: string }
type ETAPrediction = { stage: string; current_health: number; eta_hours: number | null; status: string; urgency: string; factors: string[]; insight: string }
type ForecastSlot = { stage: string; dow_label: string; hour_label: string; breach_rate: number; avg_health: number; risk: string; date: string; days_away: number; forecast: string }
type WhatIfResult = { stage: string; change_description: string; current: { queue: number; processing_time: number; throughput: number; health: number }; projected: { queue: number; processing_time: number; throughput: number; health: number }; health_improvement: number; would_resolve_breach: boolean; ai_assessment: string } | null
type ResolutionEffectiveness = { stage: string; total_incidents: number; resolved: number; open: number; high_severity: number; resolution_rate: number; avg_resolution_minutes: number | null; avg_gap_hours: number | null; is_recurring: boolean; effectiveness: string; most_common_action: string | null; insight: string }
type Playbook = { stage: string; playbook: string; data_summary: { total_incidents: number; resolution_rate: number; actions_recorded: number; best_actions: string[]; generated_at: string } } | null
type OutcomeResult = { success: boolean; action_category: string; health_before: number | null; health_after: number | null; improvement: number | null } | null

const BACKEND = 'https://ops-intelligence-platform.onrender.com'

const INDUSTRIES = [
  { value: 'cruise', label: 'Cruise Terminal' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'banking', label: 'Banking & Finance' },
  { value: 'ecommerce', label: 'E-commerce & Logistics' },
  { value: 'airport', label: 'Airport Operations' },
  { value: 'custom', label: 'Custom...' },
]

const INDUSTRY_CONTEXT: Record<string, { scenario: string; what: string; example: WorkflowRow }> = {
  cruise: { scenario: 'A cruise terminal processing 3,000 passengers for embarkation', what: 'Each incident represents a boarding workflow stage where metrics have breached operational thresholds.', example: { stage: 'baggage_drop', queue_size: '65', processing_time_seconds: '420', throughput: '6' } },
  healthcare: { scenario: 'A hospital emergency department during a high-demand shift', what: 'Each incident represents a patient flow stage where wait times or throughput have exceeded safe limits.', example: { stage: 'patient_triage', queue_size: '28', processing_time_seconds: '180', throughput: '8' } },
  banking: { scenario: 'A retail bank processing loan applications during peak season', what: 'Each incident represents a processing stage where backlog or SLA thresholds have been breached.', example: { stage: 'loan_verification', queue_size: '140', processing_time_seconds: '720', throughput: '3' } },
  ecommerce: { scenario: 'A fulfilment warehouse during a high-volume sales event', what: 'Each incident represents a fulfilment stage where pick rates or queue sizes have hit critical levels.', example: { stage: 'warehouse_picking', queue_size: '320', processing_time_seconds: '250', throughput: '30' } },
  airport: { scenario: 'An international airport terminal during morning peak hours', what: 'Each incident represents a passenger processing stage where throughput or wait times have exceeded safe thresholds.', example: { stage: 'security_screening', queue_size: '95', processing_time_seconds: '300', throughput: '14' } },
  custom: { scenario: 'A live operational workflow with active threshold breaches', what: 'Each incident represents a stage where metrics have exceeded normal operating limits.', example: { stage: 'your_stage', queue_size: '75', processing_time_seconds: '350', throughput: '6' } },
}

const WHATIF_CHANGES = [
  { value: 'add_staff', label: 'Add Staff' },
  { value: 'reduce_queue', label: 'Reduce Queue' },
  { value: 'upgrade_equipment', label: 'Upgrade Equipment' },
  { value: 'extend_hours', label: 'Extend Hours' },
]

const CSV_TEMPLATE = `stage,queue_size,processing_time_seconds,throughput\nstage_one,12,45,120\nstage_two,67,380,8`
const emptyRow = (): WorkflowRow => ({ stage: '', queue_size: '', processing_time_seconds: '', throughput: '' })

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analyses, setAnalyses] = useState<Record<string, AnalysisState>>({})
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [historyMap, setHistoryMap] = useState<Record<string, AnalysisLog[]>>({})
  const [showHistoryId, setShowHistoryId] = useState<string | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)

  // Outcome tracking
  const [showOutcomeId, setShowOutcomeId] = useState<string | null>(null)
  const [outcomeText, setOutcomeText] = useState('')
  const [outcomeMinutes, setOutcomeMinutes] = useState('')
  const [outcomeSubmitting, setOutcomeSubmitting] = useState(false)
  const [outcomeResults, setOutcomeResults] = useState<Record<string, OutcomeResult>>({})

  // Intelligence state
  const [healthScores, setHealthScores] = useState<HealthScore[]>([])
  const [patterns, setPatterns] = useState<RecurringPattern[]>([])
  const [cascades, setCascades] = useState<CascadePrediction[]>([])
  const [anomalies, setAnomalies] = useState<AnomalyScore[]>([])
  const [etaPredictions, setEtaPredictions] = useState<ETAPrediction[]>([])
  const [forecast, setForecast] = useState<ForecastSlot[]>([])
  const [effectiveness, setEffectiveness] = useState<ResolutionEffectiveness[]>([])
  const [intelLoading, setIntelLoading] = useState(false)
  const [activeIntelTab, setActiveIntelTab] = useState<'health' | 'patterns' | 'cascade' | 'anomaly' | 'eta' | 'forecast' | 'whatif' | 'effectiveness' | 'playbook'>('health')

  // What-if
  const [whatIfStage, setWhatIfStage] = useState('')
  const [whatIfChange, setWhatIfChange] = useState('add_staff')
  const [whatIfMagnitude, setWhatIfMagnitude] = useState(2)
  const [whatIfLoading, setWhatIfLoading] = useState(false)
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult>(null)
  const [whatIfRateLimit, setWhatIfRateLimit] = useState(false)

  // Playbook
  const [playbookStage, setPlaybookStage] = useState('')
  const [playbookLoading, setPlaybookLoading] = useState(false)
  const [playbook, setPlaybook] = useState<Playbook>(null)
  const [playbookRateLimit, setPlaybookRateLimit] = useState(false)

  // Industry
  const [selectedIndustry, setSelectedIndustry] = useState('cruise')
  const [customIndustry, setCustomIndustry] = useState('')
  const industryValue = selectedIndustry === 'custom' ? customIndustry || 'operations' : selectedIndustry
  const industryLabel = INDUSTRIES.find(i => i.value === selectedIndustry)?.label ?? customIndustry
  const context = INDUSTRY_CONTEXT[selectedIndustry] ?? INDUSTRY_CONTEXT['custom']

  // Custom analysis
  const [inputMode, setInputMode] = useState<'form' | 'csv'>('form')
  const [formRows, setFormRows] = useState<WorkflowRow[]>([emptyRow()])
  const [csvText, setCsvText] = useState('')
  const [customLoading, setCustomLoading] = useState(false)
  const [customResult, setCustomResult] = useState<CustomResult>(null)
  const [customError, setCustomError] = useState<string | null>(null)
  const [customRateLimit, setCustomRateLimit] = useState(false)

  const fetchIntelligence = async (industry: string) => {
    setIntelLoading(true)
    try {
      const [h, p, c, a, eta, fc, eff] = await Promise.all([
        fetch(`${BACKEND}/intelligence/health-scores?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/recurring-patterns?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/cascade-predictions?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/anomaly-scores?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/eta-to-breach?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/capacity-forecast?industry=${industry}`).then(r => r.json()),
        fetch(`${BACKEND}/intelligence/resolution-effectiveness?industry=${industry}`).then(r => r.json()),
      ])
      setHealthScores(h.health_scores ?? [])
      setPatterns(p.patterns ?? [])
      setCascades(c.predictions ?? [])
      setAnomalies(a.anomaly_scores ?? [])
      setEtaPredictions(eta.predictions ?? [])
      setForecast(fc.forecast ?? [])
      setEffectiveness(eff.effectiveness ?? [])
    } catch (e) { console.error('Intel fetch failed', e) }
    finally { setIntelLoading(false) }
  }

  const fetchData = (industry: string) => {
    setLoading(true); setError(null); setIncidents([]); setAnalyses({}); setStats(null)
    Promise.all([
      fetch(`${BACKEND}/incidents?industry=${industry}`).then(r => r.json()),
      fetch(`${BACKEND}/incidents/stats?industry=${industry}`).then(r => r.json()),
    ])
      .then(([incData, statsData]) => { setIncidents(incData.incidents ?? []); setStats(statsData); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }

  useEffect(() => {
    fetchData(industryValue)
    fetchIntelligence(industryValue)
    setWhatIfStage(''); setWhatIfResult(null); setPlaybook(null); setPlaybookStage('')
  }, [industryValue])

  const analyzeIncident = async (id: string) => {
    setAnalyses(prev => ({ ...prev, [id]: { loading: true, result: null, error: null, rateLimit: false } }))
    try {
      const r = await fetch(`${BACKEND}/analyze-incident/${id}`, { method: 'POST' })
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setAnalyses(prev => ({ ...prev, [id]: { loading: false, result: null, error: null, rateLimit: true } })); return }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setAnalyses(prev => ({ ...prev, [id]: { loading: false, result: d.ai_analysis, error: null, rateLimit: false, confidence: d.confidence_score, confidenceReason: d.confidence_reason } }))
    } catch (err: unknown) {
      setAnalyses(prev => ({ ...prev, [id]: { loading: false, result: null, error: err instanceof Error ? err.message : 'Unknown error', rateLimit: false } }))
    }
  }

  const resolveIncident = async (id: string) => {
    setResolvingId(id)
    try {
      const r = await fetch(`${BACKEND}/incidents/${id}/resolve`, { method: 'PATCH' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setIncidents(prev => prev.map(i => i.id === id ? { ...i, status: 'resolved' } : i))
      setStats(prev => prev ? { ...prev, open: Math.max(0, prev.open - 1) } : prev)
      setShowOutcomeId(id)
    } catch (err) { console.error(err) }
    finally { setResolvingId(null) }
  }

  const submitOutcome = async (incidentId: string) => {
    if (!outcomeText.trim()) return
    setOutcomeSubmitting(true)
    try {
      const r = await fetch(`${BACKEND}/incidents/${incidentId}/outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_taken: outcomeText, resolved_in_minutes: outcomeMinutes ? parseInt(outcomeMinutes) : null }),
      })
      const d = await r.json()
      setOutcomeResults(prev => ({ ...prev, [incidentId]: d }))
      setShowOutcomeId(null)
      setOutcomeText('')
      setOutcomeMinutes('')
    } catch (e) { console.error(e) }
    finally { setOutcomeSubmitting(false) }
  }

  const fetchHistory = async (id: string) => {
    if (showHistoryId === id) { setShowHistoryId(null); return }
    try {
      const r = await fetch(`${BACKEND}/incidents/${id}/analysis-history`)
      const d = await r.json()
      setHistoryMap(prev => ({ ...prev, [id]: d.history ?? [] }))
    } catch { /* ignore */ }
    setShowHistoryId(id)
  }

  const runWhatIf = async () => {
    if (!whatIfStage) return
    setWhatIfLoading(true); setWhatIfResult(null); setWhatIfRateLimit(false)
    try {
      const r = await fetch(`${BACKEND}/intelligence/whatif-simulation?industry=${industryValue}&stage=${whatIfStage}&change=${whatIfChange}&magnitude=${whatIfMagnitude}`)
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setWhatIfRateLimit(true); return }
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      setWhatIfResult(d)
    } catch (e) { console.error(e) }
    finally { setWhatIfLoading(false) }
  }

  const generatePlaybook = async () => {
    if (!playbookStage) return
    setPlaybookLoading(true); setPlaybook(null); setPlaybookRateLimit(false)
    try {
      const r = await fetch(`${BACKEND}/intelligence/playbook/${playbookStage}?industry=${industryValue}`)
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setPlaybookRateLimit(true); return }
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      setPlaybook(d)
    } catch (e) { console.error(e) }
    finally { setPlaybookLoading(false) }
  }

  const updateRow = (index: number, field: keyof WorkflowRow, value: string) =>
    setFormRows(prev => prev.map((r, i) => i === index ? { ...r, [field]: value } : r))
  const addRow = () => setFormRows(prev => [...prev, emptyRow()])
  const removeRow = (index: number) => setFormRows(prev => prev.filter((_, i) => i !== index))

  const parseRows = (): WorkflowRow[] | null => {
    if (inputMode === 'form') return formRows
    const lines = csvText.trim().split('\n').filter(Boolean)
    if (lines.length < 2) return null
    return lines.slice(1).map(line => {
      const [stage, queue_size, processing_time_seconds, throughput] = line.split(',')
      return { stage: stage?.trim() ?? '', queue_size: queue_size?.trim() ?? '', processing_time_seconds: processing_time_seconds?.trim() ?? '', throughput: throughput?.trim() ?? '' }
    })
  }

  const analyzeCustom = async () => {
    const rows = parseRows()
    if (!rows || rows.length === 0) { setCustomError('No data to analyze.'); return }
    setCustomLoading(true); setCustomResult(null); setCustomError(null); setCustomRateLimit(false)
    try {
      const r = await fetch(`${BACKEND}/analyze-custom`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry: industryValue, rows: rows.map(r => ({ stage: r.stage, queue_size: parseFloat(r.queue_size) || 0, processing_time_seconds: parseFloat(r.processing_time_seconds) || 0, throughput: parseFloat(r.throughput) || 0 })) }),
      })
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setCustomRateLimit(true); return }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setCustomResult(d)
    } catch (err: unknown) { setCustomError(err instanceof Error ? err.message : 'Unknown error') }
    finally { setCustomLoading(false) }
  }

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'workflow_template.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const severityColor = (s: string) => s === 'high' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : s === 'medium' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' : 'bg-green-500/20 text-green-400 border border-green-500/30'
  const stageLabel = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  const healthColor = (status: string) => ({ healthy: 'text-green-400', warning: 'text-yellow-400', critical: 'text-orange-400', severe: 'text-red-400' }[status] ?? 'text-gray-400')
  const healthBarColor = (status: string) => ({ healthy: 'bg-green-500', warning: 'bg-yellow-500', critical: 'bg-orange-500', severe: 'bg-red-500' }[status] ?? 'bg-gray-500')
  const trendIcon = (t: string) => t === 'degrading' ? '↓' : t === 'improving' ? '↑' : '→'
  const trendColor = (t: string) => t === 'degrading' ? 'text-red-400' : t === 'improving' ? 'text-green-400' : 'text-gray-500'
  const urgencyColor = (u: string) => ({ critical: 'bg-red-500/10 border-red-500/30', warning: 'bg-orange-500/10 border-orange-500/30', monitor: 'bg-yellow-500/10 border-yellow-500/30' }[u] ?? 'bg-gray-800 border-gray-700')
  const trendLabel = (trend: number) => trend > 0 ? <span className="text-xs text-red-400 ml-2">↑ {trend} from yesterday</span> : trend < 0 ? <span className="text-xs text-green-400 ml-2">↓ {Math.abs(trend)} from yesterday</span> : <span className="text-xs text-gray-500 ml-2">same as yesterday</span>

  const confidenceColor = (score: number) => score >= 80 ? 'bg-green-500' : score >= 65 ? 'bg-yellow-500' : 'bg-orange-500'
  const confidenceLabel = (score: number) => score >= 80 ? 'High confidence' : score >= 65 ? 'Moderate confidence' : 'Low confidence'
  const effectivenessColor = (e: string) => e === 'good' ? 'text-green-400 bg-green-500/10 border-green-500/20' : e === 'moderate' ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20'

  const activeAlerts = cascades.filter(c => c.alert)
  const criticalETA = etaPredictions.filter(e => e.urgency === 'critical' || e.urgency === 'warning')
  const ex = context.example

  const intelTabs = [
    { key: 'health', label: 'Stage Health' },
    { key: 'patterns', label: 'Recurring Patterns' },
    { key: 'cascade', label: 'Cascade Predictions', badge: activeAlerts.length, badgeColor: 'bg-orange-500' },
    { key: 'anomaly', label: 'Anomaly Scores' },
    { key: 'eta', label: 'ETA to Breach', badge: criticalETA.length, badgeColor: 'bg-red-500' },
    { key: 'forecast', label: '7-Day Forecast' },
    { key: 'whatif', label: 'What-If Simulation' },
    { key: 'effectiveness', label: 'Resolution Effectiveness' },
    { key: 'playbook', label: 'Playbook Generator' },
  ] as const

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="mb-8 flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-2 h-8 bg-indigo-500 rounded-full" />
              <h1 className="text-4xl font-extrabold tracking-tight">Ops Intelligence Platform</h1>
            </div>
            <p className="text-gray-400 text-base ml-5">AI-powered workflow monitoring & bottleneck detection — <span className="text-indigo-400 font-medium">{selectedIndustry === 'custom' && customIndustry ? `${customIndustry.charAt(0).toUpperCase() + customIndustry.slice(1)} Operations` : industryLabel}</span></p>
          </div>
          <div className="flex items-center gap-3 bg-gray-800 border border-indigo-500/40 rounded-xl px-4 py-2.5">
            <label className="text-sm text-indigo-400 font-semibold whitespace-nowrap">Industry:</label>
            <select value={selectedIndustry} onChange={e => { setSelectedIndustry(e.target.value); setCustomResult(null); setCustomError(null); setFormRows([emptyRow()]) }} className="bg-transparent text-white text-sm font-semibold focus:outline-none cursor-pointer">
              {INDUSTRIES.map(i => (<option key={i.value} value={i.value} className="bg-gray-800">{i.label}</option>))}
            </select>
            {selectedIndustry === 'custom' && <input value={customIndustry} onChange={e => setCustomIndustry(e.target.value)} placeholder="e.g. retail..." className="bg-transparent border-l border-gray-600 pl-3 text-sm text-white placeholder-gray-500 focus:outline-none w-40" />}
          </div>
        </div>

        {/* Hero */}
        <div className="bg-gradient-to-r from-indigo-900/40 via-gray-900 to-gray-900 border border-indigo-500/20 rounded-2xl px-8 py-6 mb-8">
          <p className="text-2xl font-semibold text-white mb-1">Detect bottlenecks before they become crises.</p>
          <p className="text-gray-400 text-sm max-w-2xl">AI-powered incident detection, pattern analysis, predictive forecasting, playbook generation, and outcome tracking — across any industry.</p>
        </div>

        {/* Alert banners */}
        {activeAlerts.length > 0 && (
          <div className="mb-4 p-4 rounded-xl bg-orange-500/10 border border-orange-500/30">
            <p className="text-xs font-semibold text-orange-400 uppercase tracking-wider mb-2">⚠ Cascade Risk Detected</p>
            {activeAlerts.map((a, i) => <p key={i} className="text-sm text-orange-300">{a.insight}</p>)}
          </div>
        )}
        {criticalETA.length > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30">
            <p className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">🕐 Breach Imminent</p>
            {criticalETA.map((e, i) => <p key={i} className="text-sm text-red-300">{e.insight}</p>)}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">Total incidents</p>
            <div className="flex items-baseline">{stats && <><p className="text-2xl font-bold">{stats.total}</p>{trendLabel(stats.trend)}</>}</div>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">High severity</p>
            <p className="text-2xl font-bold text-red-400">{stats?.high_severity ?? 0}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm mb-1">Open</p>
            <p className="text-2xl font-bold text-yellow-400">{stats?.open ?? 0}</p>
          </div>
        </div>

        {/* ── INTELLIGENCE ENGINE ── */}
        <div className="mb-8 bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Intelligence Engine</h2>
              <p className="text-xs text-gray-500 mt-0.5">Pattern detection · Predictive forecasting · Resolution intelligence</p>
            </div>
            {intelLoading && <div className="flex items-center gap-2 text-xs text-gray-500"><svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Analyzing…</div>}
          </div>

          <div className="flex border-b border-gray-800 px-2 overflow-x-auto">
            {intelTabs.map(tab => (
              <button key={tab.key} onClick={() => setActiveIntelTab(tab.key)} className={`px-3 py-3 text-xs font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${activeIntelTab === tab.key ? 'border-indigo-500 text-white' : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
                {tab.label}
                {'badge' in tab && tab.badge > 0 && <span className={`text-xs px-1.5 py-0.5 rounded-full text-white ${tab.badgeColor}`}>{tab.badge}</span>}
              </button>
            ))}
          </div>

          <div className="p-6">

            {/* Stage Health */}
            {activeIntelTab === 'health' && (
              <div className="space-y-3">
                {healthScores.length === 0 && !intelLoading && <p className="text-gray-500 text-sm">No health data available.</p>}
                {healthScores.map(h => (
                  <div key={h.stage} className="flex items-center gap-4">
                    <div className="w-40 text-sm text-gray-300 shrink-0">{stageLabel(h.stage)}</div>
                    <div className="flex-1 bg-gray-800 rounded-full h-2"><div className={`h-2 rounded-full ${healthBarColor(h.status)}`} style={{ width: `${h.health_score}%` }} /></div>
                    <div className={`w-12 text-right text-sm font-semibold ${healthColor(h.status)}`}>{h.health_score}</div>
                    <div className={`w-5 text-center text-sm font-bold ${trendColor(h.trend)}`}>{trendIcon(h.trend)}</div>
                    <div className={`w-16 text-xs px-2 py-0.5 rounded-full text-center ${{ healthy: 'bg-green-500/10 text-green-400', warning: 'bg-yellow-500/10 text-yellow-400', critical: 'bg-orange-500/10 text-orange-400', severe: 'bg-red-500/10 text-red-400' }[h.status]}`}>{h.status}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Recurring Patterns */}
            {activeIntelTab === 'patterns' && (
              <div className="space-y-3">
                {patterns.length === 0 && !intelLoading && <p className="text-gray-500 text-sm">No recurring patterns detected yet.</p>}
                {patterns.map((p, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${p.severity === 'high' ? 'bg-red-500/5 border-red-500/20' : p.severity === 'medium' ? 'bg-yellow-500/5 border-yellow-500/20' : 'bg-gray-800 border-gray-700'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-medium text-white mb-1">{p.insight}</p>
                        <div className="flex gap-4 text-xs text-gray-500">
                          {p.peak_hour_pct >= 30 && <span>Peak time: <span className="text-gray-300">{p.peak_hour_label} ({p.peak_hour_pct}%)</span></span>}
                          {p.peak_dow_pct >= 30 && <span>Peak day: <span className="text-gray-300">{p.peak_dow_label}s ({p.peak_dow_pct}%)</span></span>}
                        </div>
                      </div>
                      <span className={`text-xs font-semibold px-2 py-1 rounded-full shrink-0 ${p.severity === 'high' ? 'bg-red-500/20 text-red-400' : p.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'}`}>{p.breach_count} breaches</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Cascade Predictions */}
            {activeIntelTab === 'cascade' && (
              <div className="space-y-3">
                {cascades.length === 0 && !intelLoading && <p className="text-gray-500 text-sm">No cascade patterns detected yet.</p>}
                {cascades.map((c, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${c.alert ? 'bg-orange-500/10 border-orange-500/30' : 'bg-gray-800 border-gray-700'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        {c.alert && <p className="text-xs font-semibold text-orange-400 mb-1">⚠ ACTIVE RISK</p>}
                        <p className="text-sm text-gray-300">{c.insight}</p>
                        <p className="text-xs text-gray-500 mt-1">Lag: {c.lag_hours}hrs · Confidence: {c.confidence}%</p>
                      </div>
                      <div className={`text-lg font-bold shrink-0 ${c.confidence >= 70 ? 'text-red-400' : c.confidence >= 50 ? 'text-orange-400' : 'text-yellow-400'}`}>{c.confidence}%</div>
                    </div>
                    <div className="mt-2 bg-gray-700 rounded-full h-1.5"><div className={`h-1.5 rounded-full ${c.confidence >= 70 ? 'bg-red-500' : c.confidence >= 50 ? 'bg-orange-500' : 'bg-yellow-500'}`} style={{ width: `${c.confidence}%` }} /></div>
                  </div>
                ))}
              </div>
            )}

            {/* Anomaly Scores */}
            {activeIntelTab === 'anomaly' && (
              <div className="space-y-3">
                {anomalies.length === 0 && !intelLoading && <p className="text-gray-500 text-sm">No anomalies detected.</p>}
                {anomalies.map((a, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${a.flag ? 'bg-purple-500/5 border-purple-500/20' : 'bg-gray-800 border-gray-700'}`}>
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm text-gray-300">{a.insight}</p>
                        <div className="flex gap-4 text-xs text-gray-500 mt-1">
                          <span>Current: <span className={a.current_health < a.baseline_health ? 'text-red-400' : 'text-green-400'}>{a.current_health}</span></span>
                          <span>30-day baseline: <span className="text-gray-300">{a.baseline_health}</span></span>
                        </div>
                      </div>
                      {a.flag && <span className="text-xs font-semibold px-2 py-1 rounded-full bg-purple-500/20 text-purple-400 shrink-0">Anomaly: {a.anomaly_score}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ETA to Breach */}
            {activeIntelTab === 'eta' && (
              <div className="space-y-3">
                <p className="text-xs text-gray-500 mb-4">Based on health score trajectory over the last 12 hours.</p>
                {etaPredictions.length === 0 && !intelLoading && <div className="p-4 rounded-xl bg-green-500/5 border border-green-500/20"><p className="text-sm text-green-400">✓ All stages stable or improving. No breach predicted.</p></div>}
                {etaPredictions.map((e, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${urgencyColor(e.urgency)}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-semibold text-white">{stageLabel(e.stage)}</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${{ critical: 'bg-red-500/20 text-red-400', warning: 'bg-orange-500/20 text-orange-400', monitor: 'bg-yellow-500/20 text-yellow-400' }[e.urgency] ?? ''}`}>{e.urgency.toUpperCase()}</span>
                        </div>
                        <p className="text-sm text-gray-300 mb-2">{e.insight}</p>
                        {e.factors.length > 0 && <div className="flex flex-wrap gap-2">{e.factors.map((f, fi) => <span key={fi} className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">{f}</span>)}</div>}
                      </div>
                      <div className="text-right shrink-0">
                        <p className={`text-2xl font-bold ${e.urgency === 'critical' ? 'text-red-400' : e.urgency === 'warning' ? 'text-orange-400' : 'text-yellow-400'}`}>{e.eta_hours === 0 ? '!' : e.eta_hours !== null ? `${e.eta_hours}h` : '—'}</p>
                        <p className="text-xs text-gray-500">to breach</p>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-gray-500 mb-1"><span>Health: {e.current_health}</span><span>Critical: 40</span></div>
                      <div className="bg-gray-700 rounded-full h-2"><div className={`h-2 rounded-full ${e.current_health >= 70 ? 'bg-yellow-500' : e.current_health >= 50 ? 'bg-orange-500' : 'bg-red-500'}`} style={{ width: `${e.current_health}%` }} /></div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 7-Day Forecast */}
            {activeIntelTab === 'forecast' && (
              <div className="space-y-3">
                <p className="text-xs text-gray-500 mb-4">High-risk windows for the next 7 days based on 30-day historical breach patterns.</p>
                {forecast.length === 0 && !intelLoading && <div className="p-4 rounded-xl bg-green-500/5 border border-green-500/20"><p className="text-sm text-green-400">✓ No high-risk windows detected in the next 7 days.</p></div>}
                {forecast.map((f, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${f.risk === 'high' ? 'bg-red-500/5 border-red-500/20' : 'bg-yellow-500/5 border-yellow-500/20'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold text-gray-400 mb-1">{f.date} · {f.hour_label} <span className="text-gray-600">({f.days_away === 1 ? 'tomorrow' : `in ${f.days_away} days`})</span></p>
                        <p className="text-sm text-gray-300">{f.forecast}</p>
                        <p className="text-xs text-gray-500 mt-1">Avg health: {f.avg_health}/100</p>
                      </div>
                      <span className={`text-sm font-bold shrink-0 ${f.risk === 'high' ? 'text-red-400' : 'text-yellow-400'}`}>{f.breach_rate}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* What-If */}
            {activeIntelTab === 'whatif' && (
              <div>
                <p className="text-xs text-gray-500 mb-4">Simulate the impact of an operational change on a specific stage.</p>
                <div className="grid grid-cols-2 gap-4 mb-4 lg:grid-cols-4">
                  <div><label className="text-xs text-gray-500 mb-1 block">Stage</label><input value={whatIfStage} onChange={e => setWhatIfStage(e.target.value)} placeholder="e.g. security_check" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500" /></div>
                  <div><label className="text-xs text-gray-500 mb-1 block">Change type</label><select value={whatIfChange} onChange={e => setWhatIfChange(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">{WHATIF_CHANGES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}</select></div>
                  <div><label className="text-xs text-gray-500 mb-1 block">Magnitude (1–5)</label><input type="number" min={1} max={5} value={whatIfMagnitude} onChange={e => setWhatIfMagnitude(parseInt(e.target.value) || 1)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500" /></div>
                  <div className="flex items-end"><button onClick={runWhatIf} disabled={whatIfLoading || !whatIfStage} className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors">{whatIfLoading ? <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Simulating…</> : 'Run Simulation'}</button></div>
                </div>
                {whatIfRateLimit && <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm mb-4">⏳ Rate limit reached. Wait 60 seconds.</div>}
                {whatIfResult && (
                  <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
                    <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-3">{whatIfResult.change_description} — {stageLabel(whatIfResult.stage)}</p>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="bg-gray-800 rounded-lg p-3"><p className="text-xs text-gray-500 mb-2">Current</p><div className="space-y-1 text-sm"><div className="flex justify-between"><span className="text-gray-400">Queue</span><span>{whatIfResult.current.queue}</span></div><div className="flex justify-between"><span className="text-gray-400">Processing</span><span>{whatIfResult.current.processing_time}s</span></div><div className="flex justify-between"><span className="text-gray-400">Throughput</span><span>{whatIfResult.current.throughput}/hr</span></div><div className="flex justify-between"><span className="text-gray-400">Health</span><span className="text-orange-400 font-semibold">{whatIfResult.current.health}</span></div></div></div>
                      <div className="bg-gray-800 rounded-lg p-3 border border-indigo-500/20"><p className="text-xs text-gray-500 mb-2">Projected</p><div className="space-y-1 text-sm"><div className="flex justify-between"><span className="text-gray-400">Queue</span><span className="text-green-400">{whatIfResult.projected.queue}</span></div><div className="flex justify-between"><span className="text-gray-400">Processing</span><span className="text-green-400">{whatIfResult.projected.processing_time}s</span></div><div className="flex justify-between"><span className="text-gray-400">Throughput</span><span className="text-green-400">{whatIfResult.projected.throughput}/hr</span></div><div className="flex justify-between"><span className="text-gray-400">Health</span><span className="text-green-400 font-semibold">{whatIfResult.projected.health} (+{whatIfResult.health_improvement})</span></div></div></div>
                    </div>
                    <div className={`text-xs font-semibold px-3 py-1.5 rounded-lg inline-block mb-3 ${whatIfResult.would_resolve_breach ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{whatIfResult.would_resolve_breach ? '✓ Would resolve current breach' : '⚠ Would not fully resolve breach'}</div>
                    <div className="border-t border-gray-700 pt-3"><p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">AI Assessment</p><p className="text-sm text-gray-300 leading-relaxed">{whatIfResult.ai_assessment}</p></div>
                  </div>
                )}
              </div>
            )}

            {/* Resolution Effectiveness */}
            {activeIntelTab === 'effectiveness' && (
              <div className="space-y-3">
                <p className="text-xs text-gray-500 mb-4">Track whether resolutions are actually holding. Stages with high recurrence rates are treating symptoms, not root causes.</p>
                {effectiveness.length === 0 && !intelLoading && <p className="text-gray-500 text-sm">No resolution data available yet. Resolve some incidents and log outcomes to see effectiveness scores.</p>}
                {effectiveness.map((e, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${e.effectiveness === 'poor' ? 'bg-red-500/5 border-red-500/20' : e.effectiveness === 'moderate' ? 'bg-yellow-500/5 border-yellow-500/20' : 'bg-green-500/5 border-green-500/20'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-semibold text-white">{stageLabel(e.stage)}</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${effectivenessColor(e.effectiveness)}`}>{e.effectiveness}</span>
                          {e.is_recurring && <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">Recurring</span>}
                        </div>
                        <p className="text-sm text-gray-300 mb-2">{e.insight}</p>
                        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                          <span>{e.total_incidents} incidents · {e.resolution_rate}% resolved</span>
                          {e.avg_resolution_minutes && <span>Avg resolution: {e.avg_resolution_minutes}min</span>}
                          {e.avg_gap_hours && <span>Avg gap between incidents: {e.avg_gap_hours}hrs</span>}
                          {e.most_common_action && <span>Most common fix: <span className="text-gray-300 capitalize">{e.most_common_action}</span></span>}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className={`text-2xl font-bold ${e.resolution_rate >= 80 ? 'text-green-400' : e.resolution_rate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>{e.resolution_rate}%</p>
                        <p className="text-xs text-gray-500">resolved</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Playbook Generator */}
            {activeIntelTab === 'playbook' && (
              <div>
                <p className="text-xs text-gray-500 mb-4">Generate a standard operating procedure for any stage based on 30 days of incident history and outcomes.</p>
                <div className="flex gap-3 mb-4">
                  <input value={playbookStage} onChange={e => setPlaybookStage(e.target.value)} placeholder="Stage name (e.g. security_check)" className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500" />
                  <button onClick={generatePlaybook} disabled={playbookLoading || !playbookStage} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors whitespace-nowrap">
                    {playbookLoading ? <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Generating…</> : 'Generate Playbook'}
                  </button>
                </div>
                {playbookRateLimit && <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm mb-4">⏳ Rate limit reached. Wait 60 seconds.</div>}
                {playbook && (
                  <div className="p-5 rounded-xl bg-gray-800 border border-gray-700">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <p className="text-sm font-semibold text-white">{stageLabel(playbook.stage)} — Standard Operating Procedure</p>
                        <p className="text-xs text-gray-500 mt-0.5">Based on {playbook.data_summary.total_incidents} incidents · {playbook.data_summary.resolution_rate}% resolution rate · {playbook.data_summary.actions_recorded} outcomes logged</p>
                      </div>
                      <span className="text-xs text-gray-600">{new Date(playbook.data_summary.generated_at).toLocaleString()}</span>
                    </div>
                    {playbook.data_summary.best_actions.length > 0 && (
                      <div className="mb-4 p-3 rounded-lg bg-green-500/5 border border-green-500/20">
                        <p className="text-xs font-semibold text-green-400 mb-1">Most effective past actions:</p>
                        <ul className="space-y-1">{playbook.data_summary.best_actions.map((a, i) => <li key={i} className="text-xs text-green-300">✓ {a}</li>)}</ul>
                      </div>
                    )}
                    <div className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{playbook.playbook}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

          {/* LEFT — Demo Incidents */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Live Demo — Active Incidents</h2>
            <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-4">
              <p className="text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-1">Demo Scenario</p>
              <p className="text-sm text-gray-300 mb-1">{context.scenario}</p>
              <p className="text-xs text-gray-500">{context.what}</p>
            </div>

            {loading ? <p className="text-gray-400">Loading incidents...</p>
              : error ? <p className="text-red-400">Failed to load: {error}</p>
              : incidents.length === 0 ? <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-gray-500 text-sm">No incidents found.</div>
              : (
                <div className="space-y-4">
                  {incidents.map(incident => {
                    const analysis = analyses[incident.id]
                    const isResolved = incident.status === 'resolved'
                    const history = historyMap[incident.id] ?? []
                    const outcomeResult = outcomeResults[incident.id]
                    return (
                      <div key={incident.id} className={`bg-gray-900 rounded-xl p-6 border transition-all ${isResolved ? 'border-green-500/20 opacity-80' : 'border-gray-800'}`}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-lg">{stageLabel(incident.stage)}</h3>
                            {isResolved && <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full">Resolved</span>}
                          </div>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${severityColor(incident.severity)}`}>{incident.severity.toUpperCase()}</span>
                        </div>
                        <p className="text-gray-400 text-sm mb-3">{incident.description}</p>
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-4 text-xs text-gray-500">
                            <span>Status: <span className={isResolved ? 'text-green-400' : 'text-yellow-400'}>{incident.status}</span></span>
                            <span>Detected: {new Date(incident.created_at).toLocaleString()}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {!isResolved && <button onClick={() => resolveIncident(incident.id)} disabled={resolvingId === incident.id} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-600/20 hover:bg-green-600/40 text-green-400 border border-green-500/30 disabled:opacity-50 transition-colors">{resolvingId === incident.id ? 'Resolving…' : '✓ Mark Resolved'}</button>}
                            <button onClick={() => analyzeIncident(incident.id)} disabled={analysis?.loading} className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                              {analysis?.loading ? <><svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Analyzing…</> : 'Analyze with AI'}
                            </button>
                          </div>
                        </div>

                        {analysis?.rateLimit && <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm">⏳ Rate limit reached. Wait 60 seconds.</div>}
                        {analysis?.error && <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">Error: {analysis.error}</div>}

                        {/* AI Analysis with confidence score */}
                        {analysis?.result && (
                          <div className="mt-4 p-4 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">AI Analysis</p>
                              {analysis.confidence !== undefined && (
                                <div className="flex items-center gap-2">
                                  <div className="w-20 bg-gray-700 rounded-full h-1.5">
                                    <div className={`h-1.5 rounded-full ${confidenceColor(analysis.confidence)}`} style={{ width: `${analysis.confidence}%` }} />
                                  </div>
                                  <span className="text-xs text-gray-400">{analysis.confidence}% — {confidenceLabel(analysis.confidence)}</span>
                                </div>
                              )}
                            </div>
                            <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{analysis.result}</p>
                            {analysis.confidenceReason && <p className="text-xs text-gray-600 mt-2 italic">{analysis.confidenceReason}</p>}
                          </div>
                        )}

                        {/* Outcome tracking — show after resolution */}
                        {isResolved && showOutcomeId === incident.id && !outcomeResult && (
                          <div className="mt-4 p-4 rounded-lg bg-green-500/5 border border-green-500/20">
                            <p className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">What action did you take?</p>
                            <textarea value={outcomeText} onChange={e => setOutcomeText(e.target.value)} placeholder="e.g. Added 2 staff members to security check, restarted baggage conveyor..." rows={2} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-green-500 resize-none mb-2" />
                            <div className="flex items-center gap-3">
                              <input type="number" value={outcomeMinutes} onChange={e => setOutcomeMinutes(e.target.value)} placeholder="Time to resolve (min)" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-green-500 w-44" />
                              <button onClick={() => submitOutcome(incident.id)} disabled={outcomeSubmitting || !outcomeText.trim()} className="px-4 py-2 rounded-lg text-xs font-medium bg-green-600 hover:bg-green-500 disabled:opacity-50 transition-colors">{outcomeSubmitting ? 'Logging…' : 'Log Outcome'}</button>
                              <button onClick={() => setShowOutcomeId(null)} className="text-xs text-gray-600 hover:text-gray-400">Skip</button>
                            </div>
                          </div>
                        )}

                        {/* Outcome result */}
                        {outcomeResult && (
                          <div className="mt-4 p-3 rounded-lg bg-green-500/5 border border-green-500/20">
                            <p className="text-xs font-semibold text-green-400 mb-1">✓ Outcome logged — <span className="capitalize">{outcomeResult.action_category}</span> action</p>
                            {outcomeResult.improvement !== null && (
                              <p className="text-xs text-gray-400">Health {outcomeResult.health_before} → {outcomeResult.health_after} (<span className={outcomeResult.improvement >= 0 ? 'text-green-400' : 'text-red-400'}>{outcomeResult.improvement >= 0 ? '+' : ''}{outcomeResult.improvement} points</span>)</p>
                            )}
                          </div>
                        )}

                        <button onClick={() => fetchHistory(incident.id)} className="mt-3 text-xs text-gray-600 hover:text-gray-400 transition-colors">
                          {showHistoryId === incident.id ? '▲ Hide history' : '▼ View analysis history'}
                        </button>
                        {showHistoryId === incident.id && (
                          <div className="mt-2 space-y-2">
                            {history.length === 0 ? <p className="text-xs text-gray-600">No history yet.</p>
                              : history.map(log => (
                                <div key={log.id} className="p-3 rounded-lg bg-gray-800 border border-gray-700">
                                  <div className="flex items-center justify-between mb-1">
                                    <p className="text-xs text-gray-500">{new Date(log.created_at).toLocaleString()}</p>
                                    <div className="flex items-center gap-2">
                                      {log.confidence_score && (
                                        <span className="text-xs text-gray-500">{log.confidence_score}% confidence</span>
                                      )}
                                      <span className="text-xs text-gray-600 bg-gray-700 px-2 py-0.5 rounded">{log.triggered_by}</span>
                                    </div>
                                  </div>
                                  <p className="text-xs text-gray-400 whitespace-pre-wrap leading-relaxed">{log.ai_analysis}</p>
                                </div>
                              ))}
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
            <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 mb-4">
              <p className="text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-1">How it works</p>
              <p className="text-sm text-gray-300">Enter your own workflow stages and metrics. The AI detects bottlenecks and gives specific recommendations — tailored to the selected industry.</p>
            </div>
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex rounded-lg bg-gray-800 p-1 mb-6 w-fit">
                {(['form', 'csv'] as const).map(mode => (
                  <button key={mode} onClick={() => { setInputMode(mode); setCustomResult(null); setCustomError(null) }} className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${inputMode === mode ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>{mode === 'form' ? 'Simple Form' : 'Paste CSV'}</button>
                ))}
              </div>
              {inputMode === 'form' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-xs text-gray-500 px-1"><span>Stage</span><span>Queue size</span><span>Proc. time (s)</span><span>Throughput/hr</span></div>
                  {formRows.map((row, i) => (
                    <div key={i} className="grid grid-cols-4 gap-2 items-center">
                      <input value={row.stage} onChange={e => updateRow(i, 'stage', e.target.value)} placeholder={ex.stage} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500" />
                      <input type="number" value={row.queue_size} onChange={e => updateRow(i, 'queue_size', e.target.value)} placeholder={ex.queue_size} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500" />
                      <input type="number" value={row.processing_time_seconds} onChange={e => updateRow(i, 'processing_time_seconds', e.target.value)} placeholder={ex.processing_time_seconds} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500" />
                      <div className="flex gap-2">
                        <input type="number" value={row.throughput} onChange={e => updateRow(i, 'throughput', e.target.value)} placeholder={ex.throughput} className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-full" />
                        {formRows.length > 1 && <button onClick={() => removeRow(i)} className="text-gray-600 hover:text-red-400 transition-colors text-lg leading-none">×</button>}
                      </div>
                    </div>
                  ))}
                  <p className="text-xs text-gray-600 px-1">e.g. {ex.stage} · {ex.queue_size} · {ex.processing_time_seconds}s · {ex.throughput}/hr</p>
                  <button onClick={addRow} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">+ Add stage</button>
                </div>
              )}
              {inputMode === 'csv' && (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">Format: <code className="text-gray-400">stage, queue_size, processing_time_seconds, throughput</code></p>
                  <textarea value={csvText} onChange={e => setCsvText(e.target.value)} placeholder={`stage,queue_size,processing_time_seconds,throughput\n${ex.stage},${ex.queue_size},${ex.processing_time_seconds},${ex.throughput}`} rows={7} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-indigo-500 resize-none" />
                  <button onClick={downloadTemplate} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Download template CSV</button>
                </div>
              )}
              <button onClick={analyzeCustom} disabled={customLoading} className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                {customLoading ? <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Analyzing…</> : 'Analyze My Data'}
              </button>
              {customRateLimit && <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm">⏳ Rate limit reached. Wait 60 seconds.</div>}
              {customError && <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">Error: {customError}</div>}
              {customResult && (
                <div className="mt-4 space-y-4">
                  {customResult.detected_issues.length > 0 ? (
                    <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Detected Issues</p>
                      <ul className="space-y-1">{customResult.detected_issues.map((item, i) => <li key={i} className="text-sm text-yellow-300"><span className="font-medium">{stageLabel(item.stage)}:</span> <span className="text-yellow-400/80">{item.issues.join(', ')}</span></li>)}</ul>
                    </div>
                  ) : <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">No threshold violations detected.</div>}
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
