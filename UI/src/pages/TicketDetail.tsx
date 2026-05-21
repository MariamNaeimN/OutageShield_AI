import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Ticket, ExternalLink, LayoutDashboard } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'
const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'https://d2k1km1tzlio49.cloudfront.net'

export default function TicketDetail() {
  const { id } = useParams()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      try {
        const allIncidents = await getActiveIncidents()
        const found = allIncidents.find(i => i.id === id || i.id.toLowerCase() === id.toLowerCase())
        if (found) {
          setIncident(found)
        } else {
          setError(`Incident ${id} not found`)
        }
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
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <Link to="/notifications" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
          <ArrowLeft className="w-4 h-4" /> Back to Notifications
        </Link>
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300">
          {error || 'Ticket not found'}
        </div>
      </div>
    )
  }

  const raw = incident as unknown as Record<string, unknown>
  const ticketContentStr = raw.ticket_content as string | undefined
  let ticketContent: Record<string, string> = {}
  if (ticketContentStr) {
    try { ticketContent = JSON.parse(ticketContentStr) } catch { /* skip */ }
  }

  return (
    <div className="space-y-6">
      <Link to="/notifications" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
        <ArrowLeft className="w-4 h-4" /> Back to Notifications
      </Link>

      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-blue-900/30 rounded-xl flex items-center justify-center">
          <Ticket className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">Linked Ticket</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {incident.ticket?.id || 'N/A'} — {incident.ticket?.system || 'Jira'}
          </p>
        </div>
      </div>

      {/* Ticket Card */}
      <div className="bg-[#161b22] border border-gray-800 rounded-xl p-6 space-y-5">
        {/* Status Row */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-blue-400">{incident.ticket?.id}</span>
          <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-blue-900/30 text-blue-300 border border-blue-800/40">
            {incident.ticket?.status || 'Open'}
          </span>
          <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-red-900/50 text-red-300 border border-red-800/40">
            {ticketContent.priority || 'Critical'}
          </span>
          <span className="text-xs text-gray-500">{incident.ticket?.system || 'Jira'}</span>
        </div>

        {/* Title */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Summary</p>
          <p className="text-base text-white font-medium">{ticketContent.summary || incident.title || `Incident on ${incident.service}`}</p>
        </div>

        {/* Service & Incident */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Service</p>
            <p className="text-sm text-gray-200">{incident.service}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Incident ID</p>
            <Link to={`/incidents/${incident.id}`} className="text-sm text-blue-400 hover:text-blue-300">
              {incident.id}
            </Link>
          </div>
        </div>

        {/* Root Cause */}
        {incident.rootCause && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Root Cause</p>
            <p className="text-sm text-gray-300 leading-relaxed">{incident.rootCause}</p>
          </div>
        )}

        {/* Description */}
        {ticketContent.description && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Description</p>
            <pre className="text-sm text-gray-300 bg-[#0d1117] border border-gray-800 rounded-lg p-4 whitespace-pre-wrap leading-relaxed">
              {ticketContent.description.replace(/\\n/g, '\n')}
            </pre>
          </div>
        )}

        {/* Revenue & Impact */}
        <div className="grid grid-cols-3 gap-4">
          {Boolean(raw.revenue_at_risk) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
              <p className="text-[10px] font-medium text-gray-500 uppercase">Revenue at Risk</p>
              <p className="text-sm text-red-400 font-semibold mt-1">{String(raw.revenue_at_risk)}</p>
            </div>
          )}
          {Boolean(raw.affected_users) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
              <p className="text-[10px] font-medium text-gray-500 uppercase">Affected Users</p>
              <p className="text-sm text-white font-semibold mt-1">{String(raw.affected_users)}</p>
            </div>
          )}
          {Boolean(raw.sla_status) && (
            <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
              <p className="text-[10px] font-medium text-gray-500 uppercase">SLA Status</p>
              <p className={`text-sm font-semibold mt-1 ${raw.sla_status === 'At Risk' || raw.sla_status === 'Breached' ? 'text-red-400' : 'text-green-400'}`}>
                {String(raw.sla_status)}
              </p>
            </div>
          )}
        </div>

        {/* Jira Board Link */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Open in Jira</p>
          <a
            href={`${JIRA_BASE_URL}/browse/${incident.ticket?.id || ''}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 bg-blue-900/20 border border-blue-800/40 rounded-lg px-3 py-2"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            {incident.ticket?.id || 'View Ticket'} on Jira
          </a>
        </div>

        {/* Dashboard Link */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">OutageShield Dashboard</p>
          <a
            href={ticketContent.dashboard_url || `${DASHBOARD_URL}/incidents/${incident.id}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-brand-400 hover:text-brand-300 bg-brand-900/20 border border-brand-800/40 rounded-lg px-3 py-2"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            View in Dashboard
          </a>
        </div>

        {/* Ticket URL */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Ticket URL</p>
          <a
            href={`${JIRA_BASE_URL}/browse/${incident.ticket?.id || ''}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            {`${JIRA_BASE_URL}/browse/${incident.ticket?.id || ''}`}
          </a>
        </div>

        {/* Created */}
        {ticketContent.created_at && (
          <div className="pt-3 border-t border-gray-800/50">
            <p className="text-xs text-gray-600">Created: {new Date(ticketContent.created_at).toLocaleString()}</p>
          </div>
        )}
      </div>
    </div>
  )
}
