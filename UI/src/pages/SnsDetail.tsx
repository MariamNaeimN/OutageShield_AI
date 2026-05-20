import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Bell, Send } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

export default function SnsDetail() {
  const { id } = useParams()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notification, setNotification] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      try {
        const allIncidents = await getActiveIncidents()
        const found = allIncidents.find(i => i.id === id || i.id.toLowerCase() === id.toLowerCase())
        if (found) {
          setIncident(found)
          // Parse notification data
          const raw = found as unknown as Record<string, unknown>
          const notifStr = raw.notifications as string | undefined
          if (notifStr && typeof notifStr === 'string') {
            try { setNotification(JSON.parse(notifStr)) } catch { /* skip */ }
          }
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
          {error || 'Notification not found'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link to="/notifications" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
        <ArrowLeft className="w-4 h-4" /> Back to Notifications
      </Link>

      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-purple-900/30 rounded-xl flex items-center justify-center">
          <Bell className="w-6 h-6 text-purple-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">SNS Alert Details</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Notification for {incident.service}
          </p>
        </div>
      </div>

      {/* Alert Card */}
      <div className="bg-[#161b22] border border-gray-800 rounded-xl p-6 space-y-5">
        {/* Status Row */}
        <div className="flex flex-wrap items-center gap-3">
          <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
            String(notification?.type) === 'escalation' ? 'bg-red-900/50 text-red-300 border border-red-800/40' : 'bg-blue-900/50 text-blue-300 border border-blue-800/40'
          }`}>
            {String(notification?.type || 'alert')}
          </span>
          <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-300 border border-green-800/40">
            {String(notification?.status || 'sent')}
          </span>
          <span className="text-xs text-gray-500">
            {notification?.sent_at ? new Date(String(notification.sent_at)).toLocaleString() : ''}
          </span>
        </div>

        {/* Channel & Recipient */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Channel</p>
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4 text-gray-400" />
              <p className="text-sm text-gray-200">{String(notification?.channel || 'SNS')}</p>
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Recipient</p>
            <p className="text-sm text-gray-200">{String(notification?.recipient || 'sre-team@shopsphere.com')}</p>
          </div>
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

        {/* Subject */}
        {Boolean(notification?.subject) && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Subject</p>
            <p className="text-base text-white font-medium">{String(notification?.subject)}</p>
          </div>
        )}

        {/* Message */}
        {Boolean(notification?.message) && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Message</p>
            <pre className="text-sm text-gray-300 bg-[#0d1117] border border-gray-800 rounded-lg p-4 whitespace-pre-wrap leading-relaxed">
              {String(notification?.message).replace(/\\n/g, '\n')}
            </pre>
          </div>
        )}

        {/* Severity & Impact */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Severity</p>
            <p className="text-sm text-red-400 font-semibold mt-1">SEV-{incident.severity}</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Business Impact</p>
            <p className="text-sm text-white font-semibold mt-1">{incident.businessImpact}/10</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Status</p>
            <p className="text-sm text-blue-400 font-semibold mt-1">{incident.status}</p>
          </div>
        </div>

        {/* Root Cause */}
        {incident.rootCause && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Root Cause</p>
            <p className="text-sm text-gray-300 leading-relaxed">{incident.rootCause}</p>
          </div>
        )}
      </div>
    </div>
  )
}
