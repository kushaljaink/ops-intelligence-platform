'use client'
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import type { Session } from '@supabase/supabase-js'

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
type AuthView = 'login' | 'signup'

type Suggestion = {
  id: string
  category: string
  title: string
  description: string | null
  submitted_at: string
}
type UploadResult = {
  filename: string
  rows_extracted: number
  column_mapping: Record<string, string>
  notes: string
  detected_issues: { stage: string; issues: string[] }[]
  ai_analysis: string
  rows: { stage: string; queue_size: number; processing_time_seconds: number; throughput: number }[]
} | null

type AgentStep = {
  step: number
  tool: string
  input: string
  finding: string
}

type AgentDecisionPoint = {
  id: string
  type: string
  question: string
  action: string
}

type AgentResult = {
  success: boolean
  industry: string
  goal: string
  steps: AgentStep[]
  output: string
  decision_points: AgentDecisionPoint[]
  investigated_at: string
  error?: string
} | null

const BACKEND = 'https://ops-intelligence-platform.onrender.com'

const INDUSTRIES = [
  { value: 'cruise',        label: 'Cruise Terminal' },
  { value: 'healthcare',    label: 'Healthcare' },
  { value: 'banking',       label: 'Banking & Finance' },
  { value: 'ecommerce',     label: 'E-commerce & Logistics' },
  { value: 'airport',       label: 'Airport Operations' },
  { value: 'construction',  label: 'Construction Management' },
  { value: 'civil',         label: 'Civil Engineering' },
  { value: 'architecture',  label: 'Architecture & Design' },
  { value: 'custom',        label: 'Custom...' },
]

const INDUSTRY_CONTEXT: Record<string, { scenario: string; what: string; example: WorkflowRow }> = {
  cruise: { scenario: 'A cruise terminal processing 3,000 passengers for embarkation', what: 'Each incident represents a boarding workflow stage where metrics have breached operational thresholds.', example: { stage: 'baggage_drop', queue_size: '65', processing_time_seconds: '420', throughput: '6' } },
  healthcare: {
    scenario: 'A hospital emergency department managing patient flow during a high-demand shift',
    what: 'Each incident represents a patient care stage where wait times, bed occupancy, or throughput have exceeded safe clinical thresholds. ED boarding time above 4 hours triggers mandatory diversion protocols.',
    example: { stage: 'ed_triage', queue_size: '28', processing_time_seconds: '180', throughput: '8' },
  },
  banking: { scenario: 'A retail bank processing loan applications during peak season', what: 'Each incident represents a processing stage where backlog or SLA thresholds have been breached.', example: { stage: 'loan_verification', queue_size: '140', processing_time_seconds: '720', throughput: '3' } },
  ecommerce: { scenario: 'A fulfilment warehouse during a high-volume sales event', what: 'Each incident represents a fulfilment stage where pick rates or queue sizes have hit critical levels.', example: { stage: 'warehouse_picking', queue_size: '320', processing_time_seconds: '250', throughput: '30' } },
  airport: { scenario: 'An international airport terminal during morning peak hours', what: 'Each incident represents a passenger processing stage where throughput or wait times have exceeded safe thresholds.', example: { stage: 'security_screening', queue_size: '95', processing_time_seconds: '300', throughput: '14' } },
  construction: {
    scenario: 'A construction site managing a multi-phase commercial build',
    what: 'Each incident represents a site workflow stage where crew queues, task processing times, or daily output rates have breached operational thresholds.',
    example: { stage: 'material_delivery', queue_size: '8', processing_time_seconds: '320', throughput: '1' },
  },
  civil: {
    scenario: 'A civil engineering project managing road and drainage infrastructure',
    what: 'Each incident represents a field operation stage where equipment queues, cycle times, or completion rates have exceeded safe limits.',
    example: { stage: 'earthworks', queue_size: '12', processing_time_seconds: '550', throughput: '1' },
  },
  architecture: {
    scenario: 'An architecture firm managing a pipeline of active design projects',
    what: 'Each incident represents a project workflow stage where revision backlogs, review times, or approval throughput have hit critical levels.',
    example: { stage: 'design_review', queue_size: '15', processing_time_seconds: '800', throughput: '0' },
  },
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
  const [session, setSession] = useState<Session | null>(null)
  const [showAuth, setShowAuth] = useState(false)
  const [authView, setAuthView] = useState<AuthView>('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [authSuccess, setAuthSuccess] = useState<string | null>(null)
  const [userApiKey, setUserApiKey] = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [showAbout, setShowAbout] = useState(false)
  const [showConnect, setShowConnect] = useState(false)
  const [connectInfo, setConnectInfo] = useState<{webhook_url: string; curl_example: string; python_example: string; javascript_example: string} | null>(null)
  const [connectSnippet, setConnectSnippet] = useState<'curl' | 'python' | 'javascript'>('curl')
  const [testLoading, setTestLoading] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [showSuggest, setShowSuggest] = useState(false)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [suggestTitle, setSuggestTitle] = useState('')
  const [suggestCategory, setSuggestCategory] = useState('feature')
  const [suggestDescription, setSuggestDescription] = useState('')
  const [suggestSubmitting, setSuggestSubmitting] = useState(false)
  const [suggestSuccess, setSuggestSuccess] = useState(false)
  const [suggestError, setSuggestError] = useState<string | null>(null)
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

  // Upload
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadResult>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadRateLimit, setUploadRateLimit] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [activeInputTab, setActiveInputTab] = useState<'form' | 'csv' | 'upload'>('form')

  // Agent
  const [agentRunning, setAgentRunning] = useState(false)
  const [agentResult, setAgentResult] = useState<AgentResult>(null)
  const [agentError, setAgentError] = useState<string | null>(null)
  const [agentGoal, setAgentGoal] = useState('')
  const [decisionResponses, setDecisionResponses] = useState<Record<string, boolean | null>>({})
  const [decisionLoading, setDecisionLoading] = useState<string | null>(null)
  const [decisionResults, setDecisionResults] = useState<Record<string, string>>({})
  const [agentRateLimit, setAgentRateLimit] = useState(false)

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
      fetch(`${BACKEND}/incidents?industry=${industry}`, { headers: getAuthHeaders() }).then(r => r.json()),
      fetch(`${BACKEND}/incidents/stats?industry=${industry}`, { headers: getAuthHeaders() }).then(r => r.json()),
    ])
      .then(([incData, statsData]) => { setIncidents(incData.incidents ?? []); setStats(statsData); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }

  useEffect(() => {
    // Auth listener
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session?.access_token) fetchUserApiKey(session.access_token)
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session?.access_token) fetchUserApiKey(session.access_token)
    })
    return () => subscription.unsubscribe()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    fetchData(industryValue)
    fetchIntelligence(industryValue)
    setWhatIfStage(''); setWhatIfResult(null); setPlaybook(null); setPlaybookStage('')
    fetchSuggestions()
    fetchConnectInfo()
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

  const runAgent = async () => {
    setAgentRunning(true)
    setAgentResult(null)
    setAgentError(null)
    setAgentRateLimit(false)
    setDecisionResponses({})
    setDecisionResults({})
    try {
      const r = await fetch(`${BACKEND}/agent/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry: industryValue, goal: agentGoal || undefined }),
      })
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setAgentRateLimit(true); return }
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      if (!d.success) throw new Error(d.error || 'Investigation failed')
      setAgentResult(d)
    } catch (e: unknown) {
      setAgentError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setAgentRunning(false)
    }
  }

  const handleDecision = async (decisionId: string, approved: boolean) => {
    if (!agentResult) return
    setDecisionLoading(decisionId)
    setDecisionResponses(prev => ({ ...prev, [decisionId]: approved }))
    try {
      const r = await fetch(`${BACKEND}/agent/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_id: decisionId,
          approved,
          investigation_output: agentResult.output,
          industry: industryValue,
        }),
      })
      const d = await r.json()
      setDecisionResults(prev => ({ ...prev, [decisionId]: approved ? (d.message || 'Action completed successfully') : 'Skipped' }))
    } catch (e) { console.error(e) }
    finally { setDecisionLoading(null) }
  }

  const toolIcon = (tool: string) => {
    const icons: Record<string, string> = {
      check_health_scores: '🏥',
      get_cascade_predictions: '📈',
      get_recurring_patterns: '🔄',
      get_eta_to_breach: '⏱',
      get_open_incidents: '🚨',
      analyze_specific_incident: '🔍',
    }
    return icons[tool] || '🤖'
  }

  const toolLabel = (tool: string) => tool.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

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

  const submitSuggestion = async () => {
    if (!suggestTitle.trim()) return
    setSuggestSubmitting(true)
    setSuggestError(null)
    try {
      const r = await fetch(`${BACKEND}/suggestions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: suggestCategory, title: suggestTitle, description: suggestDescription }),
      })
      if (!r.ok) throw new Error('Submission failed')
      setSuggestSuccess(true)
      setSuggestTitle('')
      setSuggestDescription('')
      setSuggestCategory('feature')
      fetchSuggestions()
    } catch (e) {
      setSuggestError('Failed to submit. Please try again.')
    } finally {
      setSuggestSubmitting(false)
    }
  }

  const fetchSuggestions = async () => {
    try {
      const r = await fetch(`${BACKEND}/suggestions`)
      const d = await r.json()
      setSuggestions(d.suggestions ?? [])
    } catch { /* ignore */ }
  }

  const getAuthHeaders = (): Record<string, string> => {
    if (!session?.access_token) return {}
    return { Authorization: `Bearer ${session.access_token}` }
  }

  const handleAuth = async () => {
    setAuthLoading(true)
    setAuthError(null)
    setAuthSuccess(null)
    try {
      if (authView === 'signup') {
        const { error } = await supabase.auth.signUp({ email: authEmail, password: authPassword })
        if (error) throw error
        setAuthSuccess('Check your email to confirm your account, then log in.')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: authEmail, password: authPassword })
        if (error) throw error
        setShowAuth(false)
      }
    } catch (e: unknown) {
      setAuthError(e instanceof Error ? e.message : 'Authentication failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
    setUserApiKey(null)
  }

  const fetchUserApiKey = async (token: string) => {
    try {
      const r = await fetch(`${BACKEND}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const d = await r.json()
      if (d.api_key) setUserApiKey(d.api_key)
    } catch { /* ignore */ }
  }

  const fetchConnectInfo = async () => {
    try {
      const r = await fetch(`${BACKEND}/connect-info`)
      const d = await r.json()
      setConnectInfo(d)
    } catch { /* ignore */ }
  }

  const runTestWebhook = async () => {
    setTestLoading(true)
    setTestResult(null)
    try {
      const r = await fetch(`${BACKEND}/test-webhook?industry=${industryValue}`, { method: 'POST' })
      const d = await r.json()
      if (d.success) {
        setTestResult(`✓ ${d.message}. Refresh the page to see the new incident.`)
        fetchData(industryValue)
      } else {
        setTestResult('Test failed. Check backend logs.')
      }
    } catch {
      setTestResult('Could not reach backend. Wake it up first.')
    } finally {
      setTestLoading(false)
    }
  }

  const analyzeUpload = async () => {
    if (!uploadFile) return
    setUploadLoading(true)
    setUploadResult(null)
    setUploadError(null)
    setUploadRateLimit(false)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      formData.append('industry', industryValue)
      const r = await fetch(`${BACKEND}/extract-and-analyze`, { method: 'POST', body: formData })
      const d = await r.json()
      if (r.status === 429 || d.detail?.startsWith('GROQ_RATE_LIMIT')) { setUploadRateLimit(true); return }
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      setUploadResult(d)
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setUploadLoading(false)
    }
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
    <>
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-2 h-8 bg-indigo-500 rounded-full" />
            <h1 className="text-4xl font-extrabold tracking-tight">Ops Intelligence Platform</h1>
          </div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-gray-400 text-base ml-5">AI-powered workflow monitoring & bottleneck detection — <span className="text-indigo-400 font-medium">{selectedIndustry === 'custom' && customIndustry ? `${customIndustry.charAt(0).toUpperCase() + customIndustry.slice(1)} Operations` : industryLabel}</span></p>
            <div className="flex items-center gap-2 shrink-0">
              {session ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowConnect(true)}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-green-600/20 border border-green-500/40 text-xs text-green-400 font-medium transition-colors"
                  >
                    <span>✓</span>
                    <span>{session.user.email?.split('@')[0]}</span>
                  </button>
                  <button onClick={handleSignOut} className="px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-xs text-gray-400 hover:text-white transition-colors">
                    Sign out
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => { setShowAuth(true); setAuthView('login') }}
                  className="flex items-center gap-2 px-4 py-2 rounded-full text-sm text-gray-400 hover:text-white bg-gray-800 border border-gray-700 hover:border-indigo-500/40 transition-colors"
                >
                  <span>👤</span>
                  <span>Sign in</span>
                </button>
              )}
              <button
                onClick={() => setShowConnect(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold text-green-400 hover:text-white bg-green-500/10 hover:bg-green-600 border border-green-500/40 hover:border-green-500 transition-colors"
              >
                <span>🔗</span>
                <span>Connect</span>
              </button>
              <button
                onClick={() => setShowAbout(true)}
                className="flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-500 border border-indigo-400 shadow-lg shadow-indigo-500/40 transition-colors"
              >
                <span>✦</span>
                <span>How It Works</span>
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 ml-5">
              {INDUSTRIES.filter(i => i.value !== 'custom').map(i => (
                <button
                  key={i.value}
                  onClick={() => { setSelectedIndustry(i.value); setCustomResult(null); setCustomError(null); setFormRows([emptyRow()]) }}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                    selectedIndustry === i.value
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30'
                      : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 border border-gray-700'
                  }`}
                >
                  {i.label}
                </button>
              ))}
              <button
                onClick={() => { setSelectedIndustry('custom'); setCustomResult(null); setCustomError(null); setFormRows([emptyRow()]) }}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  selectedIndustry === 'custom'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30'
                    : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 border border-gray-700'
                }`}
              >
                Custom…
              </button>
              {selectedIndustry === 'custom' && (
                <input
                  value={customIndustry}
                  onChange={e => setCustomIndustry(e.target.value)}
                  placeholder="e.g. retail..."
                  className="bg-gray-800 border border-gray-600 rounded-full px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-40"
                />
              )}
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

          <div className="flex border-b border-gray-800 px-6 flex-wrap">
            {intelTabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveIntelTab(tab.key)}
                className={`px-3 py-3 text-xs font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
                  activeIntelTab === tab.key
                    ? 'border-indigo-500 text-white'
                    : 'highlight' in tab && (tab as any).highlight
                    ? 'border-transparent'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                }`}
              >
                {'highlight' in tab && (tab as any).highlight ? (
                  <span className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    activeIntelTab === tab.key
                      ? 'bg-indigo-600 text-white'
                      : 'bg-indigo-600 text-white hover:bg-indigo-500'
                  }`}>
                    {tab.label}
                  </span>
                ) : (
                  <>
                    {tab.label}
                    {'badge' in tab && tab.badge > 0 && (
                      <span className={`text-xs px-1.5 py-0.5 rounded-full text-white ${'badgeColor' in tab ? tab.badgeColor : 'bg-gray-500'}`}>
                        {tab.badge}
                      </span>
                    )}
                  </>
                )}
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

            {/* Community */}

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

          {/* AI Agent — standalone section below tabs */}
          <div className="border-t border-gray-800 p-6">
            <div className="flex flex-col items-center text-center mb-5">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">🤖</span>
                <h3 className="text-base font-semibold text-white">AI Investigation Agent</h3>
              </div>
              <p className="text-xs text-gray-400 max-w-lg">The agent autonomously investigates your operation using 5 tools — health scores, cascade risks, patterns, open incidents, and ETAs. At every consequential step, <span className="text-indigo-400 font-medium">you decide</span> whether it proceeds.</p>
            </div>

            <div className="flex gap-3 mb-5 max-w-2xl mx-auto">
              <input
                value={agentGoal}
                onChange={e => setAgentGoal(e.target.value)}
                placeholder="Optional: give the agent a specific goal (e.g. 'Focus on security_check stage')"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={runAgent}
                disabled={agentRunning}
                className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors whitespace-nowrap shadow-lg shadow-indigo-500/30"
              >
                {agentRunning ? (
                  <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Investigating…</>
                ) : '🔍 Run Investigation'}
              </button>
            </div>
            <p className="text-xs text-gray-600 text-center mb-5">Investigation takes 20–40 seconds. The agent will call multiple tools before surfacing findings.</p>

            {agentRateLimit && <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm mb-4 max-w-2xl mx-auto">⏳ Rate limit reached. Wait 60 seconds and try again.</div>}
            {agentError && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm mb-4 max-w-2xl mx-auto">Error: {agentError}</div>}

            {agentResult && (
              <div className="space-y-4 max-w-3xl mx-auto">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Investigation Steps — {agentResult.steps.length} tool calls made</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {agentResult.steps.map((step, i) => (
                    <div key={i} className="flex gap-3 p-3 rounded-lg bg-gray-800 border border-gray-700">
                      <div className="text-lg shrink-0">{({'check_health_scores':'🏥','get_open_incidents':'🚨','get_cascade_predictions':'📈','get_eta_to_breach':'⏱','get_recurring_patterns':'🔄'} as Record<string,string>)[step.tool] ?? '🤖'}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-indigo-400">Step {step.step}</span>
                          <span className="text-xs text-gray-300">{step.tool.replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase())}</span>
                          {step.input && <span className="text-xs text-gray-600">→ {step.input}</span>}
                        </div>
                        <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">{step.finding}</p>
                      </div>
                      <div className="text-green-400 text-xs shrink-0">✓</div>
                    </div>
                  ))}
                </div>

                <div className="p-5 rounded-xl bg-gray-800 border border-gray-700">
                  <p className="text-xs font-semibold text-white uppercase tracking-wider mb-3">🧠 Agent Findings & Recommendations</p>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{agentResult.output}</p>
                  <p className="text-xs text-gray-600 mt-3">Investigated at {new Date(agentResult.investigated_at).toLocaleString()}</p>
                </div>

                {agentResult.decision_points.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">⚡ Your Decisions — The agent is waiting for your input</p>
                    <div className="space-y-3">
                      {agentResult.decision_points.map((dp) => {
                        const response = decisionResponses[dp.id]
                        const result = decisionResults[dp.id]
                        const isLoading = decisionLoading === dp.id
                        return (
                          <div key={dp.id} className={`p-4 rounded-xl border transition-all ${response === true ? 'bg-green-500/5 border-green-500/20' : response === false ? 'bg-gray-800 border-gray-700 opacity-60' : 'bg-indigo-500/5 border-indigo-500/30'}`}>
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1">
                                <p className="text-sm text-white mb-1">{dp.question}</p>
                                {result && <p className="text-xs text-gray-400 mt-1">✓ {result}</p>}
                              </div>
                              {response === null || response === undefined ? (
                                <div className="flex gap-2 shrink-0">
                                  <button onClick={() => handleDecision(dp.id, true)} disabled={isLoading} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-600 hover:bg-green-500 disabled:opacity-50 transition-colors">{isLoading ? '…' : '✓ Yes'}</button>
                                  <button onClick={() => handleDecision(dp.id, false)} disabled={isLoading} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-700 hover:bg-gray-600 disabled:opacity-50 transition-colors">Skip</button>
                                </div>
                              ) : (
                                <span className={`text-xs px-2 py-1 rounded-full shrink-0 ${response ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-500'}`}>{response ? 'Approved' : 'Skipped'}</span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
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
              <p className="text-sm text-gray-300">Enter your workflow stages and metrics, or upload any Excel/CSV — the AI will automatically map your columns and analyze your data.</p>
            </div>

            <button onClick={() => setShowGuide(prev => !prev)} className="flex items-center gap-2 text-xs text-indigo-400 hover:text-indigo-300 transition-colors mb-3">
              <span>{showGuide ? '▲' : '▼'}</span>
              What data do I need? What columns should my file have?
            </button>

            {showGuide && (
              <div className="mb-4 p-4 rounded-xl bg-gray-800 border border-gray-700 space-y-3">
                <p className="text-xs font-semibold text-white">Your file or form needs 4 things per stage:</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-gray-700/50">
                    <p className="text-xs font-semibold text-indigo-400 mb-1">Stage Name</p>
                    <p className="text-xs text-gray-400">The name of the workflow step</p>
                    <p className="text-xs text-gray-500 mt-1">e.g. security_check, triage, loan_review</p>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-700/50">
                    <p className="text-xs font-semibold text-yellow-400 mb-1">Queue Size</p>
                    <p className="text-xs text-gray-400">How many items are waiting</p>
                    <p className="text-xs text-gray-500 mt-1">e.g. patients waiting, orders in backlog</p>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-700/50">
                    <p className="text-xs font-semibold text-orange-400 mb-1">Processing Time (seconds)</p>
                    <p className="text-xs text-gray-400">How long each item takes to process</p>
                    <p className="text-xs text-gray-500 mt-1">e.g. avg handle time, cycle time</p>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-700/50">
                    <p className="text-xs font-semibold text-green-400 mb-1">Throughput (per hour)</p>
                    <p className="text-xs text-gray-400">How many items complete per hour</p>
                    <p className="text-xs text-gray-500 mt-1">e.g. loans approved/hr, orders shipped/hr</p>
                  </div>
                </div>
                <div className="border-t border-gray-700 pt-3">
                  <p className="text-xs font-semibold text-gray-400 mb-2">Industry examples:</p>
                  <div className="space-y-1 text-xs text-gray-500">
                    <p><span className="text-gray-300">Healthcare:</span> Stage=triage · Queue=28 · Processing=180s · Throughput=8/hr</p>
                    <p><span className="text-gray-300">Banking:</span> Stage=loan_review · Queue=140 · Processing=720s · Throughput=3/hr</p>
                    <p><span className="text-gray-300">Construction:</span> Stage=site_inspection · Queue=8 · Processing=320s · Throughput=1/hr</p>
                  </div>
                </div>
                <p className="text-xs text-gray-600">💡 If you upload a file, the AI will automatically figure out which of your columns map to these fields — your columns don't need to be named exactly this way.</p>
              </div>
            )}

            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex rounded-lg bg-gray-800 p-1 mb-6 w-fit">
                {(['form', 'csv', 'upload'] as const).map(mode => (
                  <button key={mode} onClick={() => { setActiveInputTab(mode); setCustomResult(null); setCustomError(null); setUploadResult(null); setUploadError(null) }} className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${activeInputTab === mode ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                    {mode === 'form' ? 'Simple Form' : mode === 'csv' ? 'Paste CSV' : '📁 Upload File'}
                  </button>
                ))}
              </div>

              {activeInputTab === 'form' && (
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

              {activeInputTab === 'csv' && (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">Format: <code className="text-gray-400">stage, queue_size, processing_time_seconds, throughput</code></p>
                  <textarea value={csvText} onChange={e => setCsvText(e.target.value)} placeholder={`stage,queue_size,processing_time_seconds,throughput\n${ex.stage},${ex.queue_size},${ex.processing_time_seconds},${ex.throughput}`} rows={7} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-indigo-500 resize-none" />
                  <button onClick={downloadTemplate} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Download template CSV</button>
                </div>
              )}

              {activeInputTab === 'upload' && (
                <div className="space-y-4">
                  <div
                    className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center hover:border-indigo-500/50 transition-colors cursor-pointer"
                    onClick={() => document.getElementById('file-upload')?.click()}
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => { e.preventDefault(); const file = e.dataTransfer.files[0]; if (file) setUploadFile(file) }}
                  >
                    <input id="file-upload" type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={e => { const file = e.target.files?.[0]; if (file) setUploadFile(file) }} />
                    <div className="text-3xl mb-2">📁</div>
                    {uploadFile ? (
                      <div>
                        <p className="text-sm font-medium text-white">{uploadFile.name}</p>
                        <p className="text-xs text-gray-500 mt-1">{(uploadFile.size / 1024).toFixed(1)} KB · Click to change</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm text-gray-300 mb-1">Drop your file here or click to browse</p>
                        <p className="text-xs text-gray-500">Supports CSV, Excel (.xlsx, .xls)</p>
                        <p className="text-xs text-gray-600 mt-2">The AI will automatically map your columns — no specific format required</p>
                      </div>
                    )}
                  </div>
                  {uploadFile && (
                    <div className="p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/20 text-xs text-gray-400 space-y-1">
                      <p className="font-semibold text-indigo-400 mb-1">What happens next:</p>
                      <p>1. Your file is sent to the AI</p>
                      <p>2. AI identifies which columns are stage / queue / processing time / throughput</p>
                      <p>3. Extracts the data and runs threshold analysis</p>
                      <p>4. Returns bottleneck detection and recommendations</p>
                    </div>
                  )}
                </div>
              )}

              {(activeInputTab === 'form' || activeInputTab === 'csv') && (
                <button onClick={analyzeCustom} disabled={customLoading} className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                  {customLoading ? <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Analyzing…</> : 'Analyze My Data'}
                </button>
              )}

              {activeInputTab === 'upload' && (
                <button onClick={analyzeUpload} disabled={uploadLoading || !uploadFile} className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                  {uploadLoading ? <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>AI is reading your file…</> : '🤖 Upload & Analyze with AI'}
                </button>
              )}

              {(customRateLimit || uploadRateLimit) && <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm">⏳ Rate limit reached. Wait 60 seconds and try again.</div>}
              {customError && <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">Error: {customError}</div>}
              {uploadError && <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">Error: {uploadError}</div>}

              {uploadResult && (
                <div className="mt-4 space-y-4">
                  <div className="p-3 rounded-lg bg-gray-800 border border-gray-700">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">AI Column Mapping — {uploadResult.filename}</p>
                    <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                      {Object.entries(uploadResult.column_mapping).map(([field, col]) => (
                        <div key={field} className="flex items-center gap-2">
                          <span className="text-gray-500 capitalize">{field.replace(/_/g, ' ')}:</span>
                          <span className="text-indigo-400 font-medium">"{col}"</span>
                        </div>
                      ))}
                    </div>
                    {uploadResult.notes && <p className="text-xs text-gray-600 italic">{uploadResult.notes}</p>}
                    <p className="text-xs text-gray-600 mt-1">{uploadResult.rows_extracted} rows extracted</p>
                  </div>
                  {uploadResult.detected_issues.length > 0 ? (
                    <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Detected Issues</p>
                      <ul className="space-y-1">{uploadResult.detected_issues.map((item, i) => (<li key={i} className="text-sm text-yellow-300"><span className="font-medium">{item.stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</span> <span className="text-yellow-400/80">{item.issues.join(', ')}</span></li>))}</ul>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">No threshold violations detected.</div>
                  )}
                  <div className="p-4 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                    <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">AI Recommendations</p>
                    <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{uploadResult.ai_analysis}</p>
                  </div>
                </div>
              )}

              {customResult && (
                <div className="mt-4 space-y-4">
                  {customResult.detected_issues.length > 0 ? (
                    <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Detected Issues</p>
                      <ul className="space-y-1">{customResult.detected_issues.map((item, i) => (<li key={i} className="text-sm text-yellow-300"><span className="font-medium">{stageLabel(item.stage)}:</span> <span className="text-yellow-400/80">{item.issues.join(', ')}</span></li>))}</ul>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">No threshold violations detected.</div>
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

      {/* ── IDEAS & FEEDBACK SECTION ── */}
      <div className="max-w-7xl mx-auto mt-16 mb-8 bg-gray-900 rounded-3xl border border-gray-800 overflow-hidden">
        {/* Big pill header */}
        <div className="flex justify-center pt-10 pb-6">
          <div className="flex items-center gap-0 bg-gray-800 rounded-full border border-gray-700 overflow-hidden text-sm font-semibold">
            <span className="px-6 py-3 text-indigo-400 border-r border-gray-700">💡 Ideas &amp; Feedback</span>
            <span className="px-6 py-3 text-purple-400 border-r border-gray-700">✦ Shape This Platform</span>
            <span className="px-6 py-3 text-pink-400">🙋 Have an Idea?</span>
          </div>
        </div>
        <p className="text-center text-gray-500 text-sm mb-10">Suggestions from people using this platform. Drop yours below — every idea is read.</p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 px-10 pb-10">
          {/* Submit form */}
          <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
            <p className="text-base font-bold text-white mb-4">Submit an Idea</p>
            <div className="space-y-4">
              <div className="flex gap-2 flex-wrap">
                {['feature', 'industry', 'improvement', 'bug'].map(cat => (
                  <button
                    key={cat}
                    onClick={() => setSuggestCategory(cat)}
                    className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors capitalize ${suggestCategory === cat ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30' : 'bg-gray-700 text-gray-400 hover:text-white border border-gray-600'}`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
              <input
                value={suggestTitle}
                onChange={e => { setSuggestTitle(e.target.value); setSuggestSuccess(false) }}
                placeholder="What's your idea? (required)"
                className="w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
              <textarea
                value={suggestDescription}
                onChange={e => setSuggestDescription(e.target.value)}
                placeholder="More details... (optional)"
                rows={4}
                className="w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none"
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={submitSuggestion}
                  disabled={suggestSubmitting || !suggestTitle.trim()}
                  className="px-6 py-2.5 rounded-full text-sm font-bold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors shadow-lg shadow-indigo-500/30"
                >
                  {suggestSubmitting ? 'Submitting…' : 'Submit Idea'}
                </button>
                <a href="https://github.com/kushaljaink/ops-intelligence-platform/issues/new" target="_blank" rel="noreferrer" className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">Open GitHub Issue →</a>
              </div>
              {suggestSuccess && <p className="text-sm text-green-400">✓ Submitted! Thank you.</p>}
              {suggestError && <p className="text-sm text-red-400">{suggestError}</p>}
            </div>
          </div>

          {/* Suggestions list */}
          <div className="space-y-3 overflow-y-auto max-h-96">
            {suggestions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-16 text-center">
                <p className="text-4xl mb-3">💬</p>
                <p className="text-gray-400 font-medium">No ideas yet.</p>
                <p className="text-gray-600 text-sm mt-1">Be the first to shape this platform.</p>
              </div>
            ) : suggestions.map(s => (
              <div key={s.id} className="p-4 rounded-xl bg-gray-800 border border-gray-700">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                        s.category === 'feature' ? 'bg-indigo-500/20 text-indigo-400' :
                        s.category === 'industry' ? 'bg-green-500/20 text-green-400' :
                        s.category === 'improvement' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>{s.category}</span>
                    </div>
                    <p className="text-sm font-medium text-white">{s.title}</p>
                    {s.description && <p className="text-xs text-gray-400 mt-1 leading-relaxed">{s.description}</p>}
                  </div>
                  <p className="text-xs text-gray-600 shrink-0">{new Date(s.submitted_at).toLocaleDateString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>

    {showAuth && (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowAuth(false)} />
        <div className="relative w-full max-w-sm bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-white">{authView === 'login' ? 'Sign in' : 'Create account'}</h2>
            <button onClick={() => setShowAuth(false)} className="text-gray-500 hover:text-white text-2xl leading-none">×</button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Email</label>
              <input
                type="email"
                value={authEmail}
                onChange={e => setAuthEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAuth()}
                placeholder="you@example.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Password</label>
              <input
                type="password"
                value={authPassword}
                onChange={e => setAuthPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAuth()}
                placeholder="••••••••"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            {authError && <p className="text-xs text-red-400">{authError}</p>}
            {authSuccess && <p className="text-xs text-green-400">{authSuccess}</p>}
            <button
              onClick={handleAuth}
              disabled={authLoading || !authEmail || !authPassword}
              className="w-full py-2.5 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {authLoading ? 'Please wait…' : authView === 'login' ? 'Sign in' : 'Create account'}
            </button>
            <p className="text-xs text-center text-gray-500">
              {authView === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
              <button
                onClick={() => { setAuthView(authView === 'login' ? 'signup' : 'login'); setAuthError(null); setAuthSuccess(null) }}
                className="text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                {authView === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
          {authView === 'login' && (
            <div className="mt-4 pt-4 border-t border-gray-800">
              <p className="text-xs text-gray-600 text-center">Sign in to connect your own operational data and keep it private from other visitors.</p>
            </div>
          )}
        </div>
      </div>
    )}

    {showConnect && (
      <div className="fixed inset-0 z-50 flex justify-end">
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowConnect(false)} />
        <div className="relative w-full max-w-2xl h-full bg-gray-900 border-l border-gray-700 shadow-2xl flex flex-col">
          <div className="flex items-start justify-between p-6 border-b border-gray-800 shrink-0">
            <div>
              <h2 className="text-xl font-bold text-white mb-1">Connect Your System</h2>
              <p className="text-sm text-gray-400">Send real operational data from any system — no SDK required.</p>
            </div>
            <button onClick={() => setShowConnect(false)} className="text-gray-500 hover:text-white transition-colors text-2xl leading-none">×</button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6">

            <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
              <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">How it works</p>
              <div className="space-y-2 text-xs text-gray-400">
                <p>1. Your system sends a POST request with metric data (queue size, processing time, throughput)</p>
                <p>2. The platform compares against industry thresholds and calculates a health score</p>
                <p>3. If thresholds are breached, an incident is automatically created on the dashboard</p>
                <p>4. The AI agent can then investigate your real incident on demand</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-white uppercase tracking-wider mb-3">What data to send</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  {field: 'stage', desc: 'Name of the workflow step', example: 'ed_triage, loan_review'},
                  {field: 'queue_size', desc: 'Items currently waiting', example: '45 (patients, orders, tasks)'},
                  {field: 'processing_time_seconds', desc: 'How long each item takes', example: '280 (seconds)'},
                  {field: 'throughput', desc: 'Output per hour', example: '8 (patients/hr, loans/hr)'},
                  {field: 'industry', desc: 'Your industry key', example: 'healthcare, banking, construction'},
                ].map(f => (
                  <div key={f.field} className="p-2 rounded-lg bg-gray-800 border border-gray-700">
                    <p className="text-indigo-400 font-mono mb-0.5">{f.field}</p>
                    <p className="text-gray-400">{f.desc}</p>
                    <p className="text-gray-600 italic">{f.example}</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-white uppercase tracking-wider mb-2">Your Webhook URL</p>
              <div className="flex items-center gap-2 p-3 rounded-lg bg-gray-800 border border-gray-700">
                <code className="text-green-400 text-xs flex-1 break-all">{connectInfo?.webhook_url ?? 'https://ops-intelligence-platform.onrender.com/webhook/events'}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(connectInfo?.webhook_url ?? '')}
                  className="text-xs text-gray-500 hover:text-white transition-colors whitespace-nowrap px-2 py-1 rounded bg-gray-700"
                >Copy</button>
              </div>
            </div>

            {session && userApiKey && (
              <div>
                <p className="text-xs font-semibold text-white uppercase tracking-wider mb-2">Your API Key</p>
                <p className="text-xs text-gray-500 mb-2">Add this to your webhook requests so your data stays private and linked to your account.</p>
                <div className="flex items-center gap-2 p-3 rounded-lg bg-gray-800 border border-green-500/30">
                  <code className="text-green-400 text-xs flex-1 break-all">
                    {showApiKey ? userApiKey : '••••••••••••••••••••••••••••••••'}
                  </code>
                  <button onClick={() => setShowApiKey(prev => !prev)} className="text-xs text-gray-500 hover:text-white px-2 py-1 rounded bg-gray-700">
                    {showApiKey ? 'Hide' : 'Show'}
                  </button>
                  <button onClick={() => navigator.clipboard.writeText(userApiKey)} className="text-xs text-gray-500 hover:text-white px-2 py-1 rounded bg-gray-700">
                    Copy
                  </button>
                </div>
                <p className="text-xs text-gray-600 mt-2">Add <code className="text-gray-400">&quot;api_key&quot;: &quot;your_key&quot;</code> to your webhook JSON body.</p>
              </div>
            )}

            {!session && (
              <div className="p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
                <p className="text-xs text-gray-400">
                  <button onClick={() => { setShowConnect(false); setShowAuth(true); setAuthView('login') }} className="text-indigo-400 hover:text-indigo-300 transition-colors">Sign in</button>
                  {' '}to get a personal API key and keep your operational data private.
                </p>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-white uppercase tracking-wider">Code Examples</p>
                <div className="flex rounded-lg bg-gray-800 p-0.5">
                  {(['curl', 'python', 'javascript'] as const).map(lang => (
                    <button key={lang} onClick={() => setConnectSnippet(lang)} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${connectSnippet === lang ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>{lang}</button>
                  ))}
                </div>
              </div>
              <div className="relative">
                <pre className="p-4 rounded-xl bg-gray-800 border border-gray-700 text-xs text-green-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">
                  {connectSnippet === 'curl' && (connectInfo?.curl_example ?? 'Loading...')}
                  {connectSnippet === 'python' && (connectInfo?.python_example ?? 'Loading...')}
                  {connectSnippet === 'javascript' && (connectInfo?.javascript_example ?? 'Loading...')}
                </pre>
                <button
                  onClick={() => {
                    const text = connectSnippet === 'curl' ? connectInfo?.curl_example : connectSnippet === 'python' ? connectInfo?.python_example : connectInfo?.javascript_example
                    if (text) navigator.clipboard.writeText(text)
                  }}
                  className="absolute top-2 right-2 text-xs text-gray-500 hover:text-white bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded transition-colors"
                >Copy</button>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gray-800 border border-gray-700">
              <p className="text-xs font-semibold text-white mb-1">Test Your Connection</p>
              <p className="text-xs text-gray-400 mb-3">Send a sample {industryLabel} event right now to see how the platform responds.</p>
              <button
                onClick={runTestWebhook}
                disabled={testLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-500 disabled:opacity-50 transition-colors"
              >
                {testLoading ? (
                  <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" /></svg>Sending test event…</>
                ) : '⚡ Send Test Event'}
              </button>
              {testResult && (
                <p className={`mt-3 text-xs ${testResult.startsWith('✓') ? 'text-green-400' : 'text-red-400'}`}>{testResult}</p>
              )}
            </div>

            <div>
              <p className="text-xs font-semibold text-white uppercase tracking-wider mb-3">Ideas for what to connect</p>
              <div className="space-y-2 text-xs">
                {[
                  {icon: '🏥', title: 'Hospital Systems', desc: 'Epic, Cerner, or custom EHR — send patient flow metrics every 15 min'},
                  {icon: '🏗️', title: 'Construction PM Tools', desc: 'Procore, Buildertrend — send crew queue and task completion rates daily'},
                  {icon: '🏦', title: 'Banking Middleware', desc: 'Kafka topics, queue managers — stream processing times as they happen'},
                  {icon: '📦', title: 'Warehouse Systems', desc: 'WMS exports — send pick rates and dispatch queue every hour'},
                  {icon: '✈️', title: 'Airport Ops', desc: 'AODB or custom ground ops system — send gate and check-in throughput'},
                  {icon: '⏰', title: 'Cron Job', desc: 'A simple cron that queries your database every 30 min and posts metrics'},
                ].map(idea => (
                  <div key={idea.title} className="flex gap-3 p-2 rounded-lg bg-gray-800/50">
                    <span className="text-lg shrink-0">{idea.icon}</span>
                    <div><p className="text-white font-medium">{idea.title}</p><p className="text-gray-500">{idea.desc}</p></div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    )}

    {showAbout && (
      <div className="fixed inset-0 z-50 flex justify-end">
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowAbout(false)} />
        <div className="relative w-full max-w-2xl h-full bg-gray-900 border-l border-gray-700 shadow-2xl flex flex-col">
          <div className="flex items-start justify-between p-6 border-b border-gray-800 shrink-0">
            <div>
              <h2 className="text-xl font-bold text-white mb-1">Ops Intelligence Platform</h2>
              <p className="text-sm text-indigo-400">Built by Kushal Jain · March 2026</p>
              <div className="flex items-center gap-3 mt-2">
                <a href="https://ops-intelligence-platform.vercel.app" target="_blank" rel="noreferrer" className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">🌐 Live Demo</a>
                <a href="https://ops-intelligence-platform.onrender.com/docs" target="_blank" rel="noreferrer" className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">🔌 API Docs</a>
                <a href="https://github.com/kushaljaink/ops-intelligence-platform" target="_blank" rel="noreferrer" className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">📁 GitHub</a>
              </div>
            </div>
            <button onClick={() => setShowAbout(false)} className="text-gray-500 hover:text-white transition-colors text-2xl leading-none">×</button>
          </div>
          <div className="flex-1 overflow-y-auto p-6 space-y-8">
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">What It Does</h3>
              <p className="text-sm text-gray-300 leading-relaxed mb-3">A platform that watches operational workflows, detects when something is going wrong, figures out why, predicts what breaks next, and tells humans exactly what to do — <span className="text-white font-medium">before the situation becomes a crisis.</span></p>
              <p className="text-sm text-gray-400 leading-relaxed">Anyone can visit the live URL, select their industry, explore real incident data, and get AI-powered root cause analysis and recommended actions in under 3 seconds — with zero setup.</p>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">8 Industries Supported</h3>
              <div className="grid grid-cols-2 gap-2">
                {[{name:'Cruise Terminal',stages:'Baggage Drop → Security → Biometrics'},{name:'Healthcare',stages:'Triage → Bed Allocation → Diagnostics'},{name:'Banking & Finance',stages:'Loan Verification → KYC → Approval'},{name:'E-commerce & Logistics',stages:'Warehouse → Dispatch → Returns'},{name:'Airport Operations',stages:'Check-in → Security → Boarding'},{name:'Construction Management',stages:'Material Delivery → Framing → Inspection'},{name:'Civil Engineering',stages:'Earthworks → Quality Check → Drainage'},{name:'Architecture & Design',stages:'Design Review → Permit → Revision'}].map(ind => (
                  <div key={ind.name} className="p-3 rounded-lg bg-gray-800 border border-gray-700">
                    <p className="text-xs font-semibold text-white mb-1">{ind.name}</p>
                    <p className="text-xs text-gray-500">{ind.stages}</p>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">Intelligence Engine — 5 Phases</h3>
              <div className="space-y-3">
                {[{phase:'Phase 1',title:'Data Foundation',desc:'30 days of realistic historical metrics seeded per industry with built-in patterns — Monday material delivery spikes, Thursday/Friday cruise terminal failures, Monday/Friday architecture deadline rushes.'},{phase:'Phase 2',title:'Pattern Intelligence',desc:'Stage health scores (0–100), recurring pattern detection from 30-day history, cascade prediction between stages with confidence %, and anomaly scoring vs 30-day baseline.'},{phase:'Phase 3',title:'Predictive Intelligence',desc:'ETA to breach using linear regression on health trajectories, 7-day capacity forecasting from historical breach patterns, and what-if simulation for operational changes.'},{phase:'Phase 4',title:'Recommendation Intelligence',desc:'Confidence scoring on every AI analysis, outcome tracking after resolution, resolution effectiveness per stage, and AI-generated SOPs grounded in actual past incident data.'},{phase:'Phase 5',title:'Human-in-the-Loop AI Agent',desc:'An autonomous agent using 5 tools to investigate the operation — health scores, cascade risks, ETAs, patterns, open incidents — then surfaces every consequential decision to the user before acting.'}].map(p => (
                  <div key={p.phase} className="flex gap-3 p-3 rounded-lg bg-gray-800 border border-gray-700">
                    <span className="text-xs font-bold text-indigo-400 shrink-0 w-16">{p.phase}</span>
                    <div><p className="text-xs font-semibold text-white mb-1">{p.title}</p><p className="text-xs text-gray-400 leading-relaxed">{p.desc}</p></div>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">What Companies Did Before This</h3>
              <div className="space-y-2">
                {[{tier:'Tier 1',label:'Basic Dashboards',desc:'Numbers on a screen. A human looks at them, recognizes something is bad, and reacts. By then, the damage is done.'},{tier:'Tier 2',label:'Alert Systems',desc:'Threshold breached → email sent. Still reactive. No context, no root cause, no cascade prediction.'},{tier:'Tier 3',label:'BI Tools (Tableau, PowerBI)',desc:'Beautiful historical reports. Great for board meetings. Useless for real-time operations. They tell you what happened, not what is about to happen.'},{tier:'Tier 4',label:'Enterprise Platforms (ServiceNow)',desc:'$50k–$500k/year, months of integration, built for IT incidents. No predictive or AI reasoning layer.'}].map(t => (
                  <div key={t.tier} className="flex gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
                    <span className="text-xs font-bold text-gray-600 shrink-0 w-12">{t.tier}</span>
                    <div><p className="text-xs font-semibold text-gray-300 mb-0.5">{t.label}</p><p className="text-xs text-gray-500 leading-relaxed">{t.desc}</p></div>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">How It's Different From Claude / ChatGPT</h3>
              <p className="text-xs text-gray-400 leading-relaxed mb-3">Claude and ChatGPT are general-purpose AI assistants. This platform is a <span className="text-white font-medium">domain-specific AI system</span> built on top of an LLM — using Groq not as the product, but as the reasoning engine inside a larger system with its own data layer, business logic, pattern detection, and human-in-the-loop control flow.</p>
              <div className="rounded-xl overflow-hidden border border-gray-700">
                <table className="w-full text-xs">
                  <thead><tr className="bg-gray-800"><th className="text-left px-3 py-2 text-gray-500 font-medium"></th><th className="text-left px-3 py-2 text-gray-400 font-medium">Claude / ChatGPT</th><th className="text-left px-3 py-2 text-indigo-400 font-medium">This Platform</th></tr></thead>
                  <tbody className="divide-y divide-gray-800">
                    {[['What it knows','Everything generally','Your specific operational data'],['How triggered','You ask it','Monitors and acts autonomously'],['Memory','Per conversation','30 days persistent in database'],['Output','Generic text answers','Specific numbers, predictions, SOPs'],['Integration','Standalone chat','Live data, webhooks, file upload'],['Role of AI','The product','The reasoning engine inside a larger system']].map(([label,before,after]) => (
                      <tr key={label} className="bg-gray-900/50"><td className="px-3 py-2 text-gray-500">{label}</td><td className="px-3 py-2 text-gray-400">{before}</td><td className="px-3 py-2 text-indigo-300">{after}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">Additional Features</h3>
              <div className="space-y-2">
                {[
                  {
                    icon: '📁',
                    title: 'File Upload with AI Column Mapping',
                    desc: 'Upload any Excel or CSV file — Groq automatically identifies which of your columns map to stage, queue size, processing time, and throughput. Your file does not need to be formatted in any specific way.'
                  },
                  {
                    icon: '💬',
                    title: 'Community Suggestions',
                    desc: 'Built-in feedback system on the dashboard. Anyone can submit improvement ideas, new industry requests, or bug reports. All suggestions are visible to everyone in real time.'
                  },
                  {
                    icon: '🔔',
                    title: 'Email Alerts',
                    desc: 'HIGH severity incidents and new community suggestions trigger instant email notifications via Resend — so critical issues and new ideas are never missed.'
                  },
                  {
                    icon: '🔗',
                    title: 'Webhook Ingestion',
                    desc: 'POST /webhook/events accepts live operational data from any external system. Automatically creates incidents and triggers AI analysis for HIGH severity events — no manual input needed.'
                  },
                  {
                    icon: '📋',
                    title: 'Audit Trail',
                    desc: 'Every AI analysis, agent investigation, and resolution outcome is logged with timestamps and stored in Supabase — giving a full history of what was detected, analyzed, and actioned.'
                  },
                ].map(f => (
                  <div key={f.title} className="flex gap-3 p-3 rounded-lg bg-gray-800 border border-gray-700">
                    <span className="text-lg shrink-0">{f.icon}</span>
                    <div>
                      <p className="text-xs font-semibold text-white mb-0.5">{f.title}</p>
                      <p className="text-xs text-gray-400 leading-relaxed">{f.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">Tech Stack</h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[{label:'Frontend',value:'Next.js 16 + TypeScript + Tailwind'},{label:'Backend',value:'FastAPI (Python) on Render'},{label:'Database',value:'Supabase (PostgreSQL)'},{label:'AI — Production',value:'Groq llama-3.3-70b-versatile'},{label:'AI — Local Dev',value:'Ollama + llama3.2'},{label:'Agent',value:'Groq native tool-calling API'},{label:'Frontend Hosting',value:'Vercel (auto-deploy)'},{label:'Version Control',value:'GitHub'}].map(t => (
                  <div key={t.label} className="flex gap-2 p-2 rounded-lg bg-gray-800">
                    <span className="text-gray-500 shrink-0">{t.label}:</span>
                    <span className="text-gray-300">{t.value}</span>
                  </div>
                ))}
              </div>
            </section>
            <section className="border-t border-gray-800 pt-6">
              <div className="flex items-center gap-4 p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
                <div className="w-12 h-12 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shrink-0">KJ</div>
                <div>
                  <p className="text-sm font-semibold text-white">Kushal Jain</p>
                  <p className="text-xs text-gray-400 mt-0.5">Built end-to-end · March 2026</p>
                  <p className="text-xs text-gray-500 mt-1">VS Code + Claude Code + Claude.ai</p>
                  <div className="flex items-center gap-3 mt-2">
                    <a href="https://github.com/kushaljaink/ops-intelligence-platform" target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">GitHub →</a>
                    <a href="https://ops-intelligence-platform.vercel.app" target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Live Site →</a>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
