import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, MoreHorizontal, CheckCircle } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { getActiveIncidents, getServiceRisks, type Incident, type ServiceRisk } from '../services/api'

export default function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [serviceRisks, setServiceRisks] = useState<ServiceRisk[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [eventsCount, setEventsCount] = useState(0)
  const [correlationEvents, setCorrelationEvents] = useState<Record<string, unknown>[]>([])
  const pageSize = 10

  const fetchData = async () => {
    try {
      const [incidentData, riskData] = await Promise.all([
        getActiveIncidents(),
        getServiceRisks()
      ])
      setIncidents(incidentData)
      setServiceRisks(riskData)
      // Fetch events count and data for risk overview
      try {
        const eventsResp = await fetch((import.meta.env.VITE_API_URL || '/api') + '/events')
        if (eventsResp.ok) {
          const eventsData = await eventsResp.json()
          setEventsCount(eventsData.count || 0)
          // Show only non-alarm events (config changes, cloudtrail) — the correlation context
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
    } catch {
      setIncidents([])
      setServiceRisks([])
    } finally {
      setLoading(false)
    }
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <button className="p-2 text-gray-400 hover:text-gray-200">
          <MoreHorizontal className="w-5 h-5" />
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Active Incidents" value={activeCount} color="red" />
        <StatCard label="High Risk Services" value={highRiskServices} color="orange" />
        <StatCard label="Total Incidents (24h)" value={incidents.length} color="blue" />
        <StatCard label="Raw Events" value={eventsCount} color="green" />
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
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">ID</th>
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Service</th>
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Severity</th>
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Age</th>
                    <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Business Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.slice(page * pageSize, (page + 1) * pageSize).map(incident => (
                    <tr key={incident.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                      <td className="px-4 py-3">
                        <Link to={`/incidents/${incident.id}`} className="text-sm font-medium text-blue-400 hover:text-blue-300">
                          {incident.id}
                        </Link>
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
                Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, incidents.length)} of {incidents.length}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 text-xs bg-gray-800 text-gray-300 rounded-lg disabled:opacity-30 hover:bg-gray-700"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={(page + 1) * pageSize >= incidents.length}
                  className="px-3 py-1.5 text-xs bg-gray-800 text-gray-300 rounded-lg disabled:opacity-30 hover:bg-gray-700"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Service Risk Overview */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Service Risk Overview</h3>
        <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
          {incidents.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No data</p>
          ) : (
            <div className="flex gap-8">
              <div className="flex-1 space-y-3">
                {(() => {
                  // Use real API risk scores if available, otherwise derive from incidents
                  if (serviceRisks.length > 0 && (serviceRisks[0] as any).revenue_at_risk !== undefined) {
                    // Real Bedrock-generated risk scores + revenue from API
                    const sorted = [...serviceRisks]
                      .sort((a, b) => ((b as any).revenue_at_risk || 0) - ((a as any).revenue_at_risk || 0))
                      .slice(0, 8)
                    const maxRevenue = (sorted[0] as any)?.revenue_at_risk || 1
                    return sorted.map(svc => (
                      <div key={svc.service} className="flex items-center gap-3">
                        <span className="text-sm text-gray-300 w-36 truncate">{svc.service}</span>
                        <div className="flex-1 h-5 bg-gray-800 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${
                            svc.risk === 'Critical' ? 'bg-red-500' :
                            svc.risk === 'High' ? 'bg-orange-500' :
                            svc.risk === 'Medium' ? 'bg-yellow-500' : 'bg-green-500'
                          }`} style={{ width: `${Math.max(15, ((svc as any).revenue_at_risk / maxRevenue) * 100)}%` }} />
                        </div>
                        <span className="text-sm text-gray-400 w-20 text-right">${((svc as any).revenue_at_risk || 0).toLocaleString()}/h</span>
                      </div>
                    ))
                  }
                  // Fallback: derive from incidents
                  const svcMap = new Map<string, { count: number; maxSev: number; totalSev: number }>()
                  incidents.forEach(inc => {
                    const existing = svcMap.get(inc.service) || { count: 0, maxSev: 0, totalSev: 0 }
                    existing.count++
                    existing.totalSev += inc.severity
                    if (inc.severity > existing.maxSev) existing.maxSev = inc.severity
                    svcMap.set(inc.service, existing)
                  })
                  const scored = Array.from(svcMap.entries()).map(([name, data]) => ({
                    name,
                    score: data.totalSev * data.count,
                    maxSev: data.maxSev,
                    count: data.count
                  }))
                  const sorted = scored.sort((a, b) => b.score - a.score).slice(0, 8)
                  const maxScore = sorted[0]?.score || 1
                  return sorted.map(svc => (
                    <div key={svc.name} className="flex items-center gap-3">
                      <span className="text-sm text-gray-300 w-36 truncate">{svc.name}</span>
                      <div className="flex-1 h-5 bg-gray-800 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${svc.maxSev >= 4 ? 'bg-red-500' : svc.maxSev >= 3 ? 'bg-orange-500' : 'bg-yellow-500'}`} style={{ width: `${Math.max(15, (svc.score / maxScore) * 100)}%` }} />
                      </div>
                      <span className="text-sm text-gray-400 w-8 text-right">{svc.score}</span>
                    </div>
                  ))
                })()}
              </div>
              <div className="w-40 h-40 relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutData(serviceRisks.length > 0 ? serviceRisks : buildRisksFromIncidents(incidents))} cx="50%" cy="50%" innerRadius={45} outerRadius={65} dataKey="value" stroke="none">
                      {donutData(serviceRisks.length > 0 ? serviceRisks : buildRisksFromIncidents(incidents)).map((entry, i) => (<Cell key={i} fill={entry.color} />))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-white">{serviceRisks.length > 0 ? serviceRisks.length : incidents.length}</span>
                  <span className="text-xs text-gray-400">Total</span>
                </div>
              </div>
            </div>
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

function StatCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  const borderColors: Record<string, string> = { red: 'border-red-900/60', orange: 'border-orange-900/60', blue: 'border-blue-900/60', green: 'border-green-900/60' }
  const labelColors: Record<string, string> = { red: 'text-red-400', orange: 'text-orange-400', blue: 'text-blue-400', green: 'text-green-400' }
  return (
    <div className={`bg-[#161b22] border ${borderColors[color]} rounded-xl p-4`}>
      <p className={`text-xs font-medium ${labelColors[color]} mb-1`}>{label}</p>
      <p className="text-3xl font-bold text-white">{value}</p>
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
  if (status === 'Investigating') return <span className="text-sm text-gray-300">Investigating</span>
  if (status === 'Mitigating') return <span className="text-sm text-blue-300">Mitigating</span>
  return <span className="text-sm text-gray-400">{status}</span>
}

function ImpactPill({ impact }: { impact: number }) {
  if (impact >= 7) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-red-900/50 text-red-300 border border-red-700/50">HIGH</span>
  if (impact >= 4) return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-yellow-900/50 text-yellow-300 border border-yellow-700/50">MEDIUM</span>
  return <span className="inline-block px-2.5 py-0.5 rounded text-xs font-bold bg-green-900/50 text-green-300 border border-green-700/50">LOW</span>
}

function getAge(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function donutData(risks: ServiceRisk[]) {
  const critical = risks.filter(r => r.risk === 'Critical').length
  const high = risks.filter(r => r.risk === 'High').length
  const medium = risks.filter(r => r.risk === 'Medium').length
  const low = risks.filter(r => r.risk === 'Low').length
  return [
    { name: 'Critical', value: critical || 0, color: '#dc2626' },
    { name: 'High', value: high || 0, color: '#ea580c' },
    { name: 'Medium', value: medium || 0, color: '#d97706' },
    { name: 'Low', value: low || 0, color: '#16a34a' }
  ].filter(d => d.value > 0)
}

// No mock data — all data comes from the real API pipeline

function buildRisksFromIncidents(incidents: Incident[]): ServiceRisk[] {
  const svcMap = new Map<string, { count: number; maxSev: number }>()
  incidents.forEach(inc => {
    const existing = svcMap.get(inc.service) || { count: 0, maxSev: 0 }
    existing.count++
    if (inc.severity > existing.maxSev) existing.maxSev = inc.severity
    svcMap.set(inc.service, existing)
  })
  return Array.from(svcMap.entries()).map(([service, data]) => ({
    service,
    risk: (data.maxSev >= 4 ? 'Critical' : data.maxSev >= 3 ? 'High' : data.maxSev >= 2 ? 'Medium' : 'Low') as 'Critical' | 'High' | 'Medium' | 'Low',
    activeSignals: data.count,
    lastIncident: '',
    lastCalculated: ''
  }))
}
