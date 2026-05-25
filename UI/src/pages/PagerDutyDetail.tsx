import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Zap, ExternalLink, LayoutDashboard, ChevronRight, Home, AlertTriangle, Server, Clock, Activity } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'https://d2k1km1tzlio49.cloudfront.net'

export default function PagerDutyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      try {
        const allIncidents = await getActiveIncidents()
        const found = allIncidents.find(i => i.id === id || i.id.toLowerCase() === id.toLowerCase())
        if (found) setIncident(found)
        else setError(`Incident ${id} not found`)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 animate-fade-in-up">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-green-500/20 border-t-green-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Zap className="w-4 h-4 text-green-400" />
          </div>
        </div>
        <p className="text-sm text-gray-500 animate-pulse">Loading PagerDuty incident...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="space-y-4 animate-fade-in-up">
        <button onClick={() => navigate('/notifications')} className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 text-sm text-gray-400 hover:text-white hover:bg-gray-700/50 transition-all duration-200">
          <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" /> Back
        </button>
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300">{error || 'PagerDuty incident not found'}</div>
      </div>
    )
  }

  const raw = incident as unknown as Record<string, unknown>
  const pagerdutyId = incident.pagerduty_id || 'N/A'
  const pagerdutyUrl = incident.pagerduty_url || `https://app.pagerduty.com/incidents?search=${incident.id}`
  
  // PagerDuty severity mapping
  const pdSeverityMap: Record<number, { label: string; color: string; bgColor: string }> = {
    5: { label: 'critical', color: 'text-red-400', bgColor: 'bg-red-900/40' },
    4: { label: 'critical', color: 'text-red-400', bgColor: 'bg-red-900/40' },
    3: { label: 'error', color: 'text-orange-400', bgColor: 'bg-orange-900/40' },
    2: { label: 'warning', color: 'text-yellow-400', bgColor: 'bg-yellow-900/40' },
    1: { label: 'info', color: 'text-blue-400', bgColor: 'bg-blue-900/40' }
  }
  const pdSeverity = pdSeverityMap[incident.severity] || pdSeverityMap[3]

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/notifications')} className="group flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/60 border border-gray-700/50 text-sm text-gray-400 hover:text-white hover:bg-gray-700/60 transition-all duration-200 backdrop-blur-sm">
            <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
            <span className="font-medium">Back</span>
          </button>
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-600">
            <Link to="/" className="flex items-center gap-1 hover:text-gray-400 transition-colors"><Home className="w-3 h-3" /><span>Dashboard</span></Link>
            <ChevronRight className="w-3 h-3" />
            <Link to="/notifications" className="hover:text-gray-400 transition-colors">Notifications</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-400 font-medium">{pagerdutyId}</span>
          </div>
        </div>
        <a
          href={pagerdutyUrl}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-900/20 border border-green-800/40 text-xs text-green-400 hover:bg-green-900/30 transition-all duration-200"
        >
          <ExternalLink className="w-3 h-3" />
          Open in PagerDuty
        </a>
      </div>

      {/* Header Card */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#161b22] via-[#161b22] to-[#0d1117] border border-gray-800/80 p-6 animate-scale-in">
        <div className="absolute top-0 right-0 w-64 h-64 bg-green-600/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative flex items-center gap-4">
          <div className="w-14 h-14 bg-gradient-to-br from-green-600 to-emerald-600 rounded-2xl flex items-center justify-center shadow-lg shadow-green-500/20 animate-float">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-white">{pagerdutyId}</h2>
              <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-green-900/30 text-green-300 border border-green-800/40">{incident.status}</span>
              <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${pdSeverity.bgColor} ${pdSeverity.color} border border-current/30`}>
                SEV-{incident.severity} ({pdSeverity.label})
              </span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{incident.service} &middot; PagerDuty Events API v2</p>
          </div>
        </div>
      </div>

      {/* PagerDuty Content */}
      <div className="bg-[#161b22] border border-gray-800 rounded-xl p-6 space-y-5 animate-slide-in-right" style={{ animationDelay: '100ms' }}>
        {/* Summary */}
        <div className="animate-fade-in-up" style={{ animationDelay: '150ms' }}>
          <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Incident Summary</p>
          <p className="text-base text-white font-semibold">{incident.title}</p>
        </div>

        {/* Key Details Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <div className="flex items-center gap-2 mb-1.5">
              <Zap className="w-3 h-3 text-green-400" />
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">PagerDuty ID</p>
            </div>
            <p className="text-sm text-green-400 font-medium">{pagerdutyId}</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <div className="flex items-center gap-2 mb-1.5">
              <Server className="w-3 h-3 text-cyan-400" />
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Service</p>
            </div>
            <p className="text-sm text-gray-200 font-medium">{incident.service}</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <div className="flex items-center gap-2 mb-1.5">
              <AlertTriangle className="w-3 h-3 text-orange-400" />
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Severity</p>
            </div>
            <p className={`text-sm font-bold ${pdSeverity.color}`}>SEV-{incident.severity} ({pdSeverity.label})</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <div className="flex items-center gap-2 mb-1.5">
              <Activity className="w-3 h-3 text-blue-400" />
              <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Status</p>
            </div>
            <p className="text-sm text-green-400 font-medium">{incident.status}</p>
          </div>
        </div>

        {/* Linked Incident */}
        <div className="animate-fade-in-up" style={{ animationDelay: '250ms' }}>
          <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Linked OutageShield Incident</p>
          <Link to={`/incidents/${incident.id}`} className="text-sm text-cyan-400 hover:text-cyan-300 font-mono transition-colors">{incident.id}</Link>
        </div>

        {/* Root Cause */}
        {incident.rootCause && (
          <div className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Root Cause</p>
            <p className="text-sm text-gray-300 leading-relaxed bg-[#0d1117] border border-gray-800 rounded-lg p-4">{incident.rootCause}</p>
          </div>
        )}

        {/* PagerDuty Event Details */}
        <div className="animate-fade-in-up" style={{ animationDelay: '350ms' }}>
          <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-2">PagerDuty Event Details</p>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Source</span>
              <span className="text-sm text-white font-medium">OutageShield AI</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Component</span>
              <span className="text-sm text-white font-medium">{incident.service}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Group</span>
              <span className="text-sm text-white font-medium">cloud-infrastructure</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Class</span>
              <span className="text-sm text-white font-medium">outage-detection</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Dedup Key</span>
              <span className="text-sm text-cyan-400 font-mono">{incident.id}</span>
            </div>
          </div>
        </div>

        {/* Business Impact */}
        <div className="grid grid-cols-3 gap-4 animate-fade-in-up" style={{ animationDelay: '400ms' }}>
          {Boolean(raw.revenue_at_risk) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
              <p className="text-[10px] font-medium text-gray-500 uppercase">Revenue at Risk</p>
              <p className="text-lg text-red-400 font-bold mt-1">{String(raw.revenue_at_risk)}</p>
            </div>
          )}
          {Boolean(raw.affected_users) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
              <p className="text-[10px] font-medium text-gray-500 uppercase">Affected Users</p>
              <p className="text-lg text-white font-bold mt-1">{Number(raw.affected_users).toLocaleString()}</p>
            </div>
          )}
          {Boolean(raw.sla_status) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
              <p className="text-[10px] font-medium text-gray-500 uppercase">SLA Status</p>
              <p className={`text-lg font-bold mt-1 ${raw.sla_status === 'At Risk' || raw.sla_status === 'Breached' ? 'text-red-400' : 'text-green-400'}`}>
                {String(raw.sla_status)}
              </p>
            </div>
          )}
        </div>

        {/* Action Links */}
        <div className="flex flex-wrap gap-3 pt-3 border-t border-gray-800/50 animate-fade-in-up" style={{ animationDelay: '450ms' }}>
          <a
            href={pagerdutyUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-green-400 hover:text-green-300 bg-green-900/20 border border-green-800/40 rounded-lg px-4 py-2.5 hover-lift transition-all duration-200"
          >
            <ExternalLink className="w-4 h-4" />
            Open in PagerDuty
          </a>
          <a
            href={`${DASHBOARD_URL}/incidents/${incident.id}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-brand-400 hover:text-brand-300 bg-brand-900/20 border border-brand-800/40 rounded-lg px-4 py-2.5 hover-lift transition-all duration-200"
          >
            <LayoutDashboard className="w-4 h-4" />
            View in Dashboard
          </a>
          <Link
            to={`/incidents/${incident.id}`}
            className="inline-flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 bg-cyan-900/20 border border-cyan-800/40 rounded-lg px-4 py-2.5 hover-lift transition-all duration-200"
          >
            <ChevronRight className="w-4 h-4" />
            View Full Incident
          </Link>
        </div>

        {/* Detected Time */}
        <p className="text-xs text-gray-600 pt-2 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Detected: {new Date(incident.detectedAt).toLocaleString()}
        </p>
      </div>
    </div>
  )
}
