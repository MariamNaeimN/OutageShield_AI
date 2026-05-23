import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Filter, Search } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchData = async () => {
    try {
      const data = await getActiveIncidents()
      setIncidents(data)
    } catch {
      setIncidents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const filtered = incidents.filter(i => {
    if (search) {
      const q = search.toLowerCase()
      return i.id.toLowerCase().includes(q) || i.service.toLowerCase().includes(q) || i.title.toLowerCase().includes(q)
    }
    return true
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Incidents</h2>
        <span className="text-sm text-gray-500">{filtered.length} incidents</span>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by ID, service, or title..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[#161b22] border border-gray-800 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-600"
          />
        </div>
        <button onClick={fetchData} className="p-2 text-gray-400 hover:text-gray-200 bg-[#161b22] border border-gray-800 rounded-lg">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="bg-[#161b22] border border-gray-800 rounded-xl p-12 text-center">
          <Filter className="w-8 h-8 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No incidents found</p>
          <p className="text-xs text-gray-600 mt-1">Push test data to see incidents here</p>
        </div>
      ) : (
        <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">ID</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Service</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Severity</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Status</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Age</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Business Impact</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Root Cause</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(incident => (
                <tr key={incident.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/incidents/${incident.id}`} className="text-sm font-medium text-blue-400 hover:text-blue-300">
                      {incident.id.toUpperCase()}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">{incident.service}</td>
                  <td className="px-4 py-3">
                    <SeverityPill severity={incident.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={incident.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">{getAge(incident.detectedAt)}</td>
                  <td className="px-4 py-3">
                    <ImpactPill impact={incident.businessImpact} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400 max-w-[200px] truncate">
                    {incident.rootCause || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SeverityPill({ severity }: { severity: number }) {
  const config: Record<number, { label: string; classes: string }> = {
    5: { label: 'CRITICAL', classes: 'bg-red-900/50 text-red-300 border-red-700/50' },
    4: { label: 'CRITICAL', classes: 'bg-red-900/50 text-red-300 border-red-700/50' },
    3: { label: 'HIGH', classes: 'bg-orange-900/50 text-orange-300 border-orange-700/50' },
    2: { label: 'MEDIUM', classes: 'bg-yellow-900/50 text-yellow-300 border-yellow-700/50' },
    1: { label: 'LOW', classes: 'bg-green-900/50 text-green-300 border-green-700/50' }
  }
  const c = config[severity] || config[2]
  return <span className={`inline-block px-2.5 py-0.5 rounded text-xs font-bold border ${c.classes}`}>{c.label}</span>
}

function StatusPill({ status }: { status: string }) {
  if (status === 'Awaiting Approval') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-yellow-900/30 text-yellow-300 border border-yellow-700/50">Awaiting Approval</span>
  if (status === 'Investigating') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-purple-900/30 text-purple-300 border border-purple-700/50">Investigating</span>
  if (status === 'Mitigating') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-blue-900/30 text-blue-300 border border-blue-700/50">Mitigating</span>
  if (status === 'Resolved') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-300 border border-green-700/50">Resolved</span>
  if (status === 'Detected') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-gray-800 text-gray-300 border border-gray-700">Detected</span>
  return <span className="text-sm text-gray-400">{status}</span>
}

function ImpactPill({ impact }: { impact: number }) {
  if (impact >= 8) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-red-900/50 text-red-300 border border-red-700/50">CRITICAL</span>
  if (impact >= 6) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-orange-900/50 text-orange-300 border border-orange-700/50">HIGH</span>
  if (impact >= 4) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-yellow-900/50 text-yellow-300 border border-yellow-700/50">MEDIUM</span>
  if (impact >= 2) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-green-900/50 text-green-300 border border-green-700/50">LOW</span>
  return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-gray-800/50 text-gray-400 border border-gray-700/50">INTERNAL</span>
}

function getAge(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}
