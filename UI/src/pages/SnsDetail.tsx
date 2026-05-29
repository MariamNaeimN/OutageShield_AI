import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Bell, Send, ChevronRight, Home } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

export default function SnsDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
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
      <div className="flex flex-col items-center justify-center h-64 gap-4 animate-fade-in-up">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-purple-500/20 border-t-purple-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Bell className="w-4 h-4 text-purple-400" />
          </div>
        </div>
        <p className="text-sm text-gray-500 animate-pulse">Loading notification...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="space-y-4 animate-fade-in-up">
        <button onClick={() => navigate('/notifications')} className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 text-sm text-gray-400 hover:text-white hover:bg-gray-700/50 transition-all duration-200">
          <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" /> Back
        </button>
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300">{error || 'Notification not found'}</div>
      </div>
    )
  }

  const isEscalation = String(notification?.type) === 'escalation'
  const snsTopicName = notification?.sns_topic || 'outageshield-escalation-dev'

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
            <span className="text-gray-400 font-medium">{String(snsTopicName)}</span>
          </div>
        </div>
        <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border ${isEscalation ? 'bg-red-900/20 text-red-400 border-red-800/40' : 'bg-purple-900/20 text-purple-400 border-purple-800/40'}`}>
          <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${isEscalation ? 'bg-red-500' : 'bg-purple-500'}`} />
          {isEscalation ? 'Escalation' : 'Alert'}
        </span>
      </div>

      {/* Header Card */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#161b22] via-[#161b22] to-[#0d1117] border border-gray-800/80 p-6 animate-scale-in">
        <div className={`absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl pointer-events-none ${isEscalation ? 'bg-red-600/5' : 'bg-purple-600/5'}`} />
        <div className="relative flex items-center gap-4">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg ${isEscalation ? 'bg-gradient-to-br from-red-600 to-orange-600 shadow-red-500/20' : 'bg-gradient-to-br from-purple-600 to-brand-600 shadow-purple-500/20'} animate-float`}>
            <Bell className="w-7 h-7 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{String(snsTopicName)}</h2>
            <p className="text-sm text-gray-400 mt-0.5">{incident.service} &middot; {incident.id}</p>
          </div>
        </div>
      </div>

      {/* Alert Card */}
      <div className="bg-[#161b22] border border-gray-800 rounded-xl p-6 space-y-5 animate-slide-in-right" style={{ animationDelay: '100ms' }}>
        {/* Status Row */}
        <div className="flex flex-wrap items-center gap-3">
          <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${isEscalation ? 'bg-red-900/40 text-red-300 border-red-700/50' : 'bg-blue-900/40 text-blue-300 border-blue-700/50'}`}>
            {String(notification?.type || 'alert')}
          </span>
          <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-green-900/30 text-green-300 border border-green-800/40">
            {String(notification?.status || 'sent')}
          </span>
          <span className="text-xs text-gray-500">
            {notification?.sent_at ? new Date(String(notification.sent_at)).toLocaleString() : ''}
          </span>
        </div>

        {/* Channel & Recipient */}
        <div className="grid grid-cols-2 gap-4 animate-fade-in-up" style={{ animationDelay: '150ms' }}>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">SNS Topic</p>
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4 text-purple-400" />
              <p className="text-sm text-gray-200 font-medium">{String(snsTopicName)}</p>
            </div>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Recipient</p>
            <p className="text-sm text-gray-200 font-medium">{String(notification?.recipient || 'sre-team@shopsphere.com')}</p>
          </div>
        </div>

        {/* Service & Incident */}
        <div className="grid grid-cols-2 gap-4 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Service</p>
            <p className="text-sm text-gray-200 font-medium">{incident.service}</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3">
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Incident</p>
            <Link to={`/incidents/${incident.id}`} className="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors">{incident.id}</Link>
          </div>
        </div>

        {/* Subject */}
        {Boolean(notification?.subject) && (
          <div className="animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Subject</p>
            <p className="text-base text-white font-semibold">{String(notification?.subject)}</p>
          </div>
        )}

        {/* Message */}
        {Boolean(notification?.message) && (
          <div className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Message</p>
            <pre className="text-sm text-gray-300 bg-[#0d1117] border border-gray-800 rounded-lg p-4 whitespace-pre-wrap leading-relaxed">
              {String(notification?.message).replace(/\\n/g, '\n')}
            </pre>
          </div>
        )}

        {/* Severity & Impact */}
        <div className="grid grid-cols-3 gap-4 animate-fade-in-up" style={{ animationDelay: '350ms' }}>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Severity</p>
            <p className="text-lg text-red-400 font-bold mt-1">SEV-{incident.severity}</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Business Impact</p>
            <p className="text-lg text-white font-bold mt-1">{incident.businessImpact}/10</p>
          </div>
          <div className="bg-[#0d1117] border border-gray-800 rounded-lg p-3 hover-lift">
            <p className="text-[10px] font-medium text-gray-500 uppercase">Status</p>
            <p className="text-lg text-blue-400 font-bold mt-1">{incident.status}</p>
          </div>
        </div>

        {/* Root Cause */}
        {incident.rootCause && (
          <div className="animate-fade-in-up" style={{ animationDelay: '400ms' }}>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">Root Cause</p>
            <p className="text-sm text-gray-300 leading-relaxed">{incident.rootCause}</p>
          </div>
        )}
      </div>
    </div>
  )
}
