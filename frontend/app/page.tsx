'use client'
import { useEffect, useState } from 'react'

export default function Home() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(r => r.json())
      .then(d => setStatus(d.status))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Ops Intelligence Platform</h1>
        <p className="text-gray-400 mb-8">
          Early warning · Diagnosis · Action for operations teams
        </p>
        <div className="flex gap-4 justify-center">
          <span className="px-4 py-2 bg-green-500/20 text-green-400 rounded-full text-sm">
            Frontend online
          </span>
          <span className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-full text-sm">
            API: {status}
          </span>
        </div>
      </div>
    </main>
  )
}