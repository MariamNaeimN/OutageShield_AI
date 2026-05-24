import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, MoreHorizontal, CheckCircle, AlertTriangle, Shield, Activity, Radio, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { getActiveIncidents, type Incident } from '../services/api'

type SortKey = 'id' | 'service' | 'severity' | 'status' | 'detectedAt' | 'businessImpact'
type SortDir = 'asc' | 'desc'

function SortTh({ label, sortKey, current, dir, onSort }: {
  label: string; sortKey: SortKey; current: SortKey; dir: SortDir; onSort: (k: SortKey) => void
}) {
  const active = current === sortKey
  return (
    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3 cursor-pointer select-none group" onClick={() => onSort(sortKey)}>
      <div className="flex items-center gap-1 hover:text-gray-200 transition-colors">
        {label}
        <span className={`transition-all duration-150 ${active ? 'text-brand-400' : 'text-gray-600 group-hover:text-gray-400'}`}>
          {active ? (dir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />) : <ChevronsUpDown className="w-3.5 h-3.5" />}
        </span>
      </div>
    </th>
  )
}

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [eventsCount, setEventsCount] = useState(0)
  const [correlationEvents, setCorrelationEvents] = useState<Record<string, unknown>[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('detectedAt')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const pageSize = 10

  const handleSort = (key: SortKey) => {
    if (sortKey === key) { setSortDir(d => d === 'asc' ? 'desc' : 'asc') }
    else { setSortKey(key); setSortDir('desc') }
    setPage(0)
  }

  const fetchData = async () => {
    try {
      const incidentData = await getActiveIncidents()
      setIncidents(incidentData)
    } catch {
      setIncidents([])
    }
    // Fetch events count and data for risk overview
    try {
      const eventsResp = await fetch((import.meta.env.VITE_API_URL || '/dev') + '/events')
      if (eventsResp.ok) {
        const eventsData = await eventsResp.json()
        setEventsCount(eventsData.count || 0)
        const allEvents = eventsData.events || []
        const correlationOnly = allEvents.filter((e: Record<string, unknown>) => 
          String(e.source || '').includes('config') || 
          String(e.source || '').includes('cloudtrail') ||
          e.severity === 'medium' || 
          e.severity === 'informational'
        )
        setCorrelationEvents(correlationOnly)
      }
    } catch { /* events endpoint might not exist */ }
    setLoading(false)
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)

    // WebSocket real-time: refresh immediately on any update
    const wsUrl = import.meta.env.VITE_WS_URL
    let ws: WebSocket | null = null
    if (wsUrl) {
      try {
        ws = new WebSocket(wsUrl)
        ws.onmessage = () => { fetchData() }
        ws.onopen = () => { console.log('[WS] Connected for real-time updates') }
      } catch (e) { console.log('[WS] Failed to connect:', e) }
    }

    return () => {
      clearInterval(interval)
      if (ws) ws.close()
    }
  }, [])

  const activeCount = incidents.filter(i => i.status !== 'Resolved').length
  const highRiskServices = new Set(incidents.filter(i => i.severity >= 4).map(i => i.service)).size

  const sortedIncidents = [...incidents].sort((a, b) => {
    let av: string | number = 0, bv: string | number = 0
    if (sortKey === 'id')             { av = a.id;             bv = b.id }
    if (sortKey === 'service')        { av = a.service;        bv = b.service }
    if (sortKey === 'severity')       { av = a.severity;       bv = b.severity }
    if (sortKey === 'status')         { av = a.status;         bv = b.status }
    if (sortKey === 'detectedAt')     { av = a.detectedAt;     bv = b.detectedAt }
    if (sortKey === 'businessImpact') { av = a.businessImpact; bv = b.businessImpact }
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Dashboard</h2>
          <p className="text-xs text-gray-500 mt-0.5">Real-time incident intelligence</p>
        </div>
        <button className="p-2 text-gray-400 hover:text-gray-200 transition-colors">
          <MoreHorizontal className="w-5 h-5" />
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 stagger-children">
        <StatCard
          label="Active Incidents"
          value={activeCount}
          color="red"
          delay={0}
          icon={<AlertTriangle className="w-5 h-5" />}
          trend={activeCount > 0 ? `${activeCount} need attention` : 'All clear'}
          sub="Non-resolved incidents"
        />
        <StatCard
          label="High Risk Services"
          value={highRiskServices}
          color="orange"
          delay={60}
          icon={<Shield className="w-5 h-5" />}
          trend={highRiskServices > 0 ? `SEV-4+ active` : 'No critical services'}
          sub="Services with SEV ≥ 4"
        />
        <StatCard
          label="Total Incidents (24h)"
          value={incidents.length}
          color="blue"
          delay={120}
          icon={<Activity className="w-5 h-5" />}
          trend={`${incidents.filter(i => i.status === 'Resolved').length} resolved`}
          sub="All incidents today"
        />
        <StatCard
          label="Raw Events"
          value={eventsCount}
          color="green"
          delay={180}
          icon={<Radio className="w-5 h-5" />}
          trend="CloudWatch alarms"
          sub="Detection signals ingested"
        />
      </div>

      {/* Active Incidents Table */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Active Incidents</h3>
          <span className="text-xs text-gray-500">{incidents.length} total</span>
        </div>
        {incidents.length === 0 ? (
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-12 text-center">
            <CheckCircle className="w-10 h-10 text-green-500 mx-auto mb-3" />
            <p className="text-gray-300">No active incidents</p>
          </div>
        ) : (
          <>
            <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-800">
                    <SortTh label="ID"              sortKey="id"             current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Source</th>
                    <SortTh label="Service"         sortKey="service"        current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Severity"        sortKey="severity"       current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Status"          sortKey="status"         current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Age"             sortKey="detectedAt"     current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Business Impact" sortKey="businessImpact" current={sortKey} dir={sortDir} onSort={handleSort} />
                  </tr>
                </thead>
                <tbody>
                  {sortedIncidents.slice(page * pageSize, (page + 1) * pageSize).map((incident, idx) => (
                    <tr
                      key={incident.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-all duration-150 animate-fade-in-up"
                      style={{ animationDelay: `${idx * 30}ms` }}
                    >
                      <td className="px-4 py-3">
                        <Link to={`/incidents/${incident.id}`} className="text-sm font-medium text-blue-400 hover:text-blue-300">
                          {incident.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-900/50 text-blue-300">aws.cloudwatch</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-300">{incident.service}</td>
                      <td className="px-4 py-3"><SeverityPill severity={incident.severity} /></td>
                      <td className="px-4 py-3"><StatusPill status={incident.status} /></td>
                      <td className="px-4 py-3 text-sm text-gray-400">{getAge(incident.detectedAt)}</td>
                      <td className="px-4 py-3"><ImpactPill impact={incident.businessImpact} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-gray-500">
                Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, sortedIncidents.length)} of {sortedIncidents.length}
              </span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-3 py-1.5 text-xs bg-gray-800 text-gray-300 rounded-lg disabled:opacity-30 hover:bg-gray-700">Previous</button>
                <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * pageSize >= sortedIncidents.length} className="px-3 py-1.5 text-xs bg-gray-800 text-gray-300 rounded-lg disabled:opacity-30 hover:bg-gray-700">Next</button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Business Impact Overview */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Business Impact Overview</h3>
        <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
          {incidents.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No data</p>
          ) : (
            (() => {
              const active = incidents.filter(i => i.status !== 'Resolved')
              const critical = active.filter(i => i.businessImpact >= 8).length
              const high = active.filter(i => i.businessImpact >= 6 && i.businessImpact < 8).length
              const medium = active.filter(i => i.businessImpact >= 4 && i.businessImpact < 6).length
              const low = active.filter(i => i.businessImpact >= 2 && i.businessImpact < 4).length
              const internal = active.filter(i => i.businessImpact < 2).length
              const total = active.length

              const chartData = [
                { name: 'Critical', value: critical, color: '#ef4444' },
                { name: 'High', value: high, color: '#f97316' },
                { name: 'Medium', value: medium, color: '#eab308' },
                { name: 'Low', value: low, color: '#22c55e' },
                { name: 'Internal', value: internal, color: '#6b7280' }
              ].filter(d => d.value > 0)

              return (
                <div className="flex items-center gap-8">
                  {/* Donut Chart */}
                  <div className="w-44 h-44 relative shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={chartData} cx="50%" cy="50%" innerRadius={50} outerRadius={72} dataKey="value" stroke="none" animationDuration={800}>
                          {chartData.map((entry, i) => (<Cell key={i} fill={entry.color} />))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold text-white">{total}</span>
                      <span className="text-[10px] text-gray-500 uppercase tracking-wider">Active</span>
                    </div>
                  </div>

                  {/* Legend + Bars */}
                  <div className="flex-1 space-y-3">
                    {[
                      { label: 'Critical', count: critical, color: 'bg-red-500', text: 'text-red-400', pct: total ? Math.round((critical/total)*100) : 0 },
                      { label: 'High', count: high, color: 'bg-orange-500', text: 'text-orange-400', pct: total ? Math.round((high/total)*100) : 0 },
                      { label: 'Medium', count: medium, color: 'bg-yellow-500', text: 'text-yellow-400', pct: total ? Math.round((medium/total)*100) : 0 },
                      { label: 'Low', count: low, color: 'bg-green-500', text: 'text-green-400', pct: total ? Math.round((low/total)*100) : 0 },
                      { label: 'Internal', count: internal, color: 'bg-gray-500', text: 'text-gray-400', pct: total ? Math.round((internal/total)*100) : 0 }
                    ].map(cat => (
                      <div key={cat.label} className="flex items-center gap-3">
                        <div className={`w-2.5 h-2.5 rounded-full ${cat.color} shrink-0`} />
                        <span className="text-sm text-gray-300 w-16">{cat.label}</span>
                        <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${cat.color} transition-all duration-700`} style={{ width: `${cat.pct}%` }} />
                        </div>
                        <span className={`text-sm font-bold w-8 text-right ${cat.text}`}>{cat.count}</span>
                        <span className="text-xs text-gray-600 w-10 text-right">{cat.pct}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })()
          )}
        </div>
      </div>

      {/* Correlation Events */}
      {correlationEvents.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Correlation Events ({correlationEvents.length})</h3>
          <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Source</th>
                  <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Service</th>
                  <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Severity</th>
                  <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {correlationEvents.map((evt, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        String(evt.source).includes('config') ? 'bg-purple-900/50 text-purple-300' :
                        String(evt.source).includes('cloudtrail') ? 'bg-blue-900/50 text-blue-300' :
                        'bg-gray-800 text-gray-300'
                      }`}>{String(evt.source || 'unknown')}</span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-300">{String(evt.service || '—')}</td>
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        evt.severity === 'critical' ? 'bg-red-900/50 text-red-300' :
                        evt.severity === 'high' ? 'bg-orange-900/50 text-orange-300' :
                        'bg-yellow-900/50 text-yellow-300'
                      }`}>{String(evt.severity || 'medium')}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{evt.timestamp ? new Date(String(evt.timestamp)).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color, delay = 0, icon, trend, sub }: {
  label: string
  value: number | string
  color: string
  delay?: number
  icon?: React.ReactNode
  trend?: string
  sub?: string
}) {
  const [hovered, setHovered] = useState(false)

  const styles: Record<string, { border: string; label: string; iconBg: string; iconColor: string; bar: string; glow: string }> = {
    red:    { border: 'border-red-900/60',    label: 'text-red-400',    iconBg: 'bg-red-900/30',    iconColor: 'text-red-400',    bar: 'bg-red-500',    glow: 'shadow-red-500/10' },
    orange: { border: 'border-orange-900/60', label: 'text-orange-400', iconBg: 'bg-orange-900/30', iconColor: 'text-orange-400', bar: 'bg-orange-500', glow: 'shadow-orange-500/10' },
    blue:   { border: 'border-blue-900/60',   label: 'text-blue-400',   iconBg: 'bg-blue-900/30',   iconColor: 'text-blue-400',   bar: 'bg-blue-500',   glow: 'shadow-blue-500/10' },
    green:  { border: 'border-green-900/60',  label: 'text-green-400',  iconBg: 'bg-green-900/30',  iconColor: 'text-green-400',  bar: 'bg-green-500',  glow: 'shadow-green-500/10' },
  }
  const s = styles[color]

  return (
    <div
      className={`relative bg-[#161b22] border ${s.border} rounded-xl p-4 cursor-default animate-fade-in-up transition-all duration-300 ${
        hovered ? `shadow-lg ${s.glow} -translate-y-1 border-opacity-80` : 'hover-lift'
      }`}
      style={{ animationDelay: `${delay}ms` }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Top row: icon + pulse dot */}
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 ${s.iconBg} rounded-xl flex items-center justify-center ${s.iconColor} transition-transform duration-300 ${hovered ? 'scale-110' : ''}`}>
          {icon}
        </div>
        <span className={`w-2 h-2 rounded-full ${s.bar} animate-pulse mt-1`} />
      </div>

      {/* Value */}
      <p className={`text-3xl font-bold text-white animate-count-up transition-all duration-300 ${hovered ? 'scale-105' : ''}`}
         style={{ animationDelay: `${delay + 100}ms`, transformOrigin: 'left' }}>
        {value}
      </p>

      {/* Label */}
      <p className={`text-xs font-medium ${s.label} mt-1`}>{label}</p>

      {/* Hover tooltip panel */}
      <div className={`overflow-hidden transition-all duration-300 ${hovered ? 'max-h-20 opacity-100 mt-3' : 'max-h-0 opacity-0'}`}>
        <div className={`h-px ${s.bar} opacity-20 mb-2`} />
        <p className="text-[11px] text-gray-300 font-medium">{trend}</p>
        <p className="text-[10px] text-gray-500 mt-0.5">{sub}</p>
      </div>
    </div>
  )
}

function SeverityPill({ severity }: { severity: number }) {
  const config: Record<number, { label: string; classes: string }> = {
    5: { label: 'CRITICAL', classes: 'bg-red-900/50 text-red-300 border-red-700/50' },
    4: { label: 'HIGH', classes: 'bg-orange-900/50 text-orange-300 border-orange-700/50' },
    3: { label: 'MEDIUM', classes: 'bg-yellow-900/50 text-yellow-300 border-yellow-700/50' },
    2: { label: 'LOW', classes: 'bg-green-900/50 text-green-300 border-green-700/50' },
    1: { label: 'INFO', classes: 'bg-gray-800/50 text-gray-300 border-gray-700/50' }
  }
  const c = config[severity] || config[3]
  return <span className={`inline-block px-2.5 py-0.5 rounded text-xs font-bold border ${c.classes}`}>{c.label}</span>
}

function StatusPill({ status }: { status: string }) {
  if (status === 'Awaiting Approval') return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-medium bg-yellow-900/30 text-yellow-300 border border-yellow-700/50">Awaiting Approval</span>
  if (status === 'Investigating') return <span className="text-sm text-gray-300">Investigating</span>
  if (status === 'Mitigating') return <span className="text-sm text-blue-300">Mitigating</span>
  return <span className="text-sm text-gray-400">{status}</span>
}

function ImpactPill({ impact }: { impact: number }) {
  if (impact >= 8) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold border bg-red-900/50 text-red-300 border-red-700/50">CRITICAL</span>
  if (impact >= 6) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold border bg-orange-900/50 text-orange-300 border-orange-700/50">HIGH</span>
  if (impact >= 4) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold border bg-yellow-900/50 text-yellow-300 border-yellow-700/50">MEDIUM</span>
  if (impact >= 2) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold border bg-green-900/50 text-green-300 border-green-700/50">LOW</span>
  return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold border bg-gray-800/50 text-gray-400 border-gray-700/50">INTERNAL</span>
}

function getAge(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}


