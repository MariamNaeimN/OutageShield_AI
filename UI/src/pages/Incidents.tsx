import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Filter, Search, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

type SortKey = 'id' | 'service' | 'severity' | 'status' | 'detectedAt' | 'businessImpact'
type SortDir = 'asc' | 'desc'

function SortHeader({ label, sortKey, current, dir, onSort }: {
  label: string
  sortKey: SortKey
  current: SortKey
  dir: SortDir
  onSort: (k: SortKey) => void
}) {
  const active = current === sortKey
  return (
    <th
      className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3 cursor-pointer select-none group"
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1 hover:text-gray-200 transition-colors">
        {label}
        <span className={`transition-all duration-150 ${active ? 'text-brand-400' : 'text-gray-600 group-hover:text-gray-400'}`}>
          {active
            ? dir === 'asc'
              ? <ChevronUp className="w-3.5 h-3.5" />
              : <ChevronDown className="w-3.5 h-3.5" />
            : <ChevronsUpDown className="w-3.5 h-3.5" />
          }
        </span>
      </div>
    </th>
  )
}

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('detectedAt')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

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

  const filtered = incidents
    .filter(i => {
      if (search) {
        const q = search.toLowerCase()
        return i.id.toLowerCase().includes(q) || i.service.toLowerCase().includes(q) || i.title.toLowerCase().includes(q)
      }
      return true
    })
    .sort((a, b) => {
      let av: string | number = 0
      let bv: string | number = 0
      if (sortKey === 'id')            { av = a.id;             bv = b.id }
      if (sortKey === 'service')       { av = a.service;        bv = b.service }
      if (sortKey === 'severity')      { av = a.severity;       bv = b.severity }
      if (sortKey === 'status')        { av = a.status;         bv = b.status }
      if (sortKey === 'detectedAt')    { av = a.detectedAt;     bv = b.detectedAt }
      if (sortKey === 'businessImpact'){ av = a.businessImpact; bv = b.businessImpact }
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })

  if (loading) {
    return (
      <div className="space-y-5 animate-fade-in-up">
        <div className="flex items-center justify-between">
          <div className="skeleton h-8 w-32 rounded-lg" />
          <div className="skeleton h-6 w-24 rounded-full" />
        </div>
        <div className="skeleton h-10 w-72 rounded-lg" />
        <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/50" style={{ animationDelay: `${i * 50}ms` }}>
              <div className="skeleton h-4 w-28 rounded" />
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-5 w-16 rounded-full" />
              <div className="skeleton h-5 w-20 rounded-full" />
              <div className="skeleton h-4 w-12 rounded" />
              <div className="skeleton h-5 w-16 rounded-full" />
              <div className="skeleton h-4 w-40 rounded" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Incidents</h2>
          <p className="text-xs text-gray-500 mt-0.5">All active and recent incidents</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800/60 border border-gray-700/40 rounded-full text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            {filtered.length} incidents
          </span>
        </div>
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
            className="w-full pl-9 pr-3 py-2 bg-[#161b22] border border-gray-800 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 transition-all duration-200"
          />
        </div>
        <button
          onClick={fetchData}
          className="p-2 text-gray-400 hover:text-gray-200 bg-[#161b22] border border-gray-800 rounded-lg hover:bg-gray-800/60 transition-all duration-150 hover:rotate-180"
          style={{ transition: 'all 0.3s ease' }}
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="bg-[#161b22] border border-gray-800 rounded-xl p-12 text-center animate-scale-in">
          <Filter className="w-8 h-8 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No incidents found</p>
          <p className="text-xs text-gray-600 mt-1">Push test data to see incidents here</p>
        </div>
      ) : (
        <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden animate-scale-in">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <SortHeader label="ID"             sortKey="id"             current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Service"        sortKey="service"        current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Severity"       sortKey="severity"       current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Status"         sortKey="status"         current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Age"            sortKey="detectedAt"     current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortHeader label="Business Impact" sortKey="businessImpact" current={sortKey} dir={sortDir} onSort={handleSort} />
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Root Cause</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((incident, idx) => (
                <tr
                  key={incident.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-all duration-150 animate-fade-in-up"
                  style={{ animationDelay: `${Math.min(idx * 25, 500)}ms` }}
                >
                  <td className="px-4 py-3">
                    <Link to={`/incidents/${incident.id}`} className="text-sm font-medium text-blue-400 hover:text-blue-300 transition-colors">
                      {incident.id.toUpperCase()}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">{incident.service}</td>
                  <td className="px-4 py-3"><SeverityPill severity={incident.severity} /></td>
                  <td className="px-4 py-3"><StatusPill status={incident.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-400">{getAge(incident.detectedAt)}</td>
                  <td className="px-4 py-3"><ImpactPill impact={incident.businessImpact} /></td>
                  <td className="px-4 py-3 text-sm text-gray-400 max-w-[200px] truncate">{incident.rootCause || '—'}</td>
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
