'use client'
import { useEffect, useState } from 'react'

type Incident = {
  id: string
  stage: string
  severity: string
  description: string
  status: string
  created_at: string
}

export default function Home() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/incidents')
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
  }, [])

  const severityColor = (severity: string) => {
    if (severity === 'high') return 'bg-red-500/20 text-red-400 border border-red-500/30'
    if (severity === 'medium') return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
    return 'bg-green-500/20 text-green-400 border border-green-500/30'
  }

  const stageLabel = (stage: string) => {
    return stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      {/* Header */}
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Ops Intelligence Platform</h1>
          <p className="text-gray-400">CruiseOps AI — Live incident monitoring</p>
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

        {/* Incidents list */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Active Incidents</h2>
          {loading ? (
            <p className="text-gray-400">Loading incidents...</p>
          ) : error ? (
            <p className="text-red-400">Failed to load incidents: {error}</p>
          ) : (
            <div className="space-y-4">
              {incidents.map(incident => (
                <div key={incident.id} className="bg-gray-900 rounded-xl p-6 border border-gray-800">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-lg">{stageLabel(incident.stage)}</h3>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${severityColor(incident.severity)}`}>
                      {incident.severity.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm mb-3">{incident.description}</p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>Status: <span className="text-yellow-400">{incident.status}</span></span>
                    <span>Detected: {new Date(incident.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
