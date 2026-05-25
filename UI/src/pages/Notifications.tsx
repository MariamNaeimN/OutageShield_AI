import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Ticket, ChevronRight, ChevronDown, ChevronUp, ExternalLink, Zap, Clock, Server, AlertTriangle, User } from 'lucide-react'
import { getActiveIncidents } from '../services/api'

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'

interface NotificationRecord {
  id: string
  type: string
  channel: string
  status: string
  sent_at: string
  recipient: string
  subject?: string
  message?: string
  incident_id?: string
  service?: string
}

interface TicketRecord {
  ticket_id: string
  system: string
  status: string
  priority?: string
  url: string
  created_at: string
  summary?: string
  incident_id: string
  service: string
  pagerduty_id?: string
  pagerduty_url?: string
}

interface PagerDutyRecord {
  pagerduty_id: string
  pagerduty_url: string
  incident_id: string
  service: string
  severity: number
  status: string
  summary: string
}

export default function Notifications() {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([])
  const [tickets, setTickets] = useState<TicketRecord[]>([])
  const [pagerdutyIncidents, setPagerdutyIncidents] = useState<PagerDutyRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'jira' | 'pagerduty' | 'sns'>('jira')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const incidents = await getActiveIncidents()
        const notifs: NotificationRecord[] = []
        const tix: TicketRecord[] = []
        const pdIncidents: PagerDutyRecord[] = []

        for (const inc of incidents) {
          // Extract notifications
          const raw = inc as unknown as Record<string, unknown>
          const notifStr = raw.notifications as string | undefined
          if (notifStr && typeof notifStr === 'string') {
            try {
              const n = JSON.parse(notifStr)
              notifs.push({ ...n, incident_id: inc.id, service: inc.service })
            } catch { /* skip */ }
          }

          // Extract Jira tickets
          if (inc.ticket) {
            const ticketContent = raw.ticket_content as string | undefined
            let parsed: Record<string, string> = {}
            if (ticketContent && typeof ticketContent === 'string') {
              try { parsed = JSON.parse(ticketContent) } catch { /* skip */ }
            }
            tix.push({
              ticket_id: inc.ticket.id,
              system: inc.ticket.system,
              status: inc.ticket.status,
              priority: parsed.priority || 'Critical',
              url: parsed.url || '#',
              created_at: parsed.created_at || '',
              summary: parsed.summary || `Incident on ${inc.service}`,
              incident_id: inc.id,
              service: inc.service,
              pagerduty_id: inc.pagerduty_id,
              pagerduty_url: inc.pagerduty_url
            })
          }

          // Extract PagerDuty incidents
          if (inc.pagerduty_id) {
            pdIncidents.push({
              pagerduty_id: inc.pagerduty_id,
              pagerduty_url: inc.pagerduty_url || `https://app.pagerduty.com/incidents?search=${inc.id}`,
              incident_id: inc.id,
              service: inc.service,
              severity: inc.severity,
              status: inc.status,
              summary: inc.title
            })
          }
        }

        setNotifications(notifs)
        setTickets(tix)
        setPagerdutyIncidents(pdIncidents)
      } catch {
        setNotifications([])
        setTickets([])
        setPagerdutyIncidents([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <div className="skeleton h-8 w-64 rounded-lg" />
        <div className="skeleton h-5 w-48 rounded" />
        <div className="skeleton h-10 w-56 rounded-lg" />
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-16 w-full rounded-xl" style={{ animationDelay: `${i * 60}ms` }} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h2 className="text-2xl font-bold text-white">Notifications & Tickets</h2>
        <p className="text-sm text-gray-500 mt-1">SNS alerts, Jira tickets, and PagerDuty incidents created by the agent</p>
      </div>

      {/* Tabs */}
      <div className="relative flex gap-1 bg-[#161b22] border border-gray-800 rounded-xl p-1 w-fit">
        {/* Animated sliding indicator */}
        <div
          className="absolute top-1 bottom-1 rounded-lg transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
          style={{
            left: tab === 'jira' ? '4px' : tab === 'pagerduty' ? 'calc(33.33% + 2px)' : 'calc(66.66% + 2px)',
            width: 'calc(33.33% - 4px)',
            background: tab === 'jira'
              ? 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(99,102,241,0.15))'
              : tab === 'pagerduty'
              ? 'linear-gradient(135deg, rgba(34,197,94,0.2), rgba(22,163,74,0.15))'
              : 'linear-gradient(135deg, rgba(168,85,247,0.2), rgba(139,92,246,0.15))',
            boxShadow: tab === 'jira'
              ? '0 0 12px rgba(59,130,246,0.15)'
              : tab === 'pagerduty'
              ? '0 0 12px rgba(34,197,94,0.15)'
              : '0 0 12px rgba(168,85,247,0.15)',
          }}
        />
        <button
          onClick={() => setTab('jira')}
          className={`relative z-10 flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            tab === 'jira' ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Ticket className={`w-4 h-4 transition-transform duration-200 ${tab === 'jira' ? 'scale-110' : ''}`} />
          <span>Jira</span>
          <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-200 ${
            tab === 'jira' ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-800 text-gray-500'
          }`}>{tickets.length}</span>
        </button>
        <button
          onClick={() => setTab('pagerduty')}
          className={`relative z-10 flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            tab === 'pagerduty' ? 'text-green-400' : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Zap className={`w-4 h-4 transition-transform duration-200 ${tab === 'pagerduty' ? 'scale-110' : ''}`} />
          <span>PagerDuty</span>
          <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-200 ${
            tab === 'pagerduty' ? 'bg-green-500/20 text-green-300' : 'bg-gray-800 text-gray-500'
          }`}>{pagerdutyIncidents.length}</span>
        </button>
        <button
          onClick={() => setTab('sns')}
          className={`relative z-10 flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            tab === 'sns' ? 'text-purple-400' : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Bell className={`w-4 h-4 transition-transform duration-200 ${tab === 'sns' ? 'scale-110 animate-pulse' : ''}`} />
          <span>SNS</span>
          <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-200 ${
            tab === 'sns' ? 'bg-purple-500/20 text-purple-300' : 'bg-gray-800 text-gray-500'
          }`}>{notifications.length}</span>
        </button>
      </div>

      {/* Jira Tab */}
      {tab === 'jira' && (
        <div className="space-y-2 animate-fade-in-up">
          {tickets.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500 animate-scale-in">No Jira tickets</div>
          ) : tickets.map((t, i) => (
            <div key={i} className="animate-fade-in-up" style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}>
              <ExpandableTicket ticket={t} />
            </div>
          ))}
        </div>
      )}

      {/* PagerDuty Tab */}
      {tab === 'pagerduty' && (
        <div className="space-y-2 animate-fade-in-up">
          {pagerdutyIncidents.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500 animate-scale-in">No PagerDuty incidents</div>
          ) : pagerdutyIncidents.map((pd, i) => (
            <div key={i} className="animate-fade-in-up" style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}>
              <ExpandablePagerDuty incident={pd} />
            </div>
          ))}
        </div>
      )}

      {/* SNS Tab */}
      {tab === 'sns' && (
        <div className="space-y-2 animate-fade-in-up">
          {notifications.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500 animate-scale-in">No SNS alerts</div>
          ) : notifications.map((n, i) => (
            <div key={i} className="animate-fade-in-up" style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}>
              <ExpandableNotification notif={n} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ExpandableTicket({ ticket }: { ticket: TicketRecord }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const jiraUrl = `${JIRA_BASE_URL}/browse/${ticket.ticket_id}`

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden hover:border-blue-800/50 transition-all duration-200">
      {/* Header Row */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4 min-w-0 flex-1 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <div className="w-8 h-8 bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
            <Ticket className="w-4 h-4 text-blue-400" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-blue-400">{ticket.ticket_id}</span>
              <span className="text-xs text-gray-500">— {ticket.system}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${ticket.priority === 'Critical' ? 'bg-red-900/50 text-red-300' : 'bg-orange-900/50 text-orange-300'}`}>
                {ticket.priority}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-green-900/30 text-green-300">{ticket.status}</span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{ticket.summary}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-gray-500">{ticket.service}</span>
          <a
            href={jiraUrl}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="p-1.5 rounded-md hover:bg-blue-900/30 text-gray-500 hover:text-blue-400 transition-colors"
            title="Open in Jira"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          <button onClick={() => setExpanded(!expanded)} className="p-1 text-gray-500 hover:text-gray-300">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-800/50 animate-fade-in-up">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Ticket className="w-3 h-3" />
                <span>Ticket ID</span>
              </div>
              <p className="text-sm font-medium text-blue-400">{ticket.ticket_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Server className="w-3 h-3" />
                <span>Service</span>
              </div>
              <p className="text-sm font-medium text-white">{ticket.service}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <AlertTriangle className="w-3 h-3" />
                <span>Priority</span>
              </div>
              <p className={`text-sm font-medium ${ticket.priority === 'Critical' ? 'text-red-400' : 'text-orange-400'}`}>{ticket.priority}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Clock className="w-3 h-3" />
                <span>Status</span>
              </div>
              <p className="text-sm font-medium text-green-400">{ticket.status}</p>
            </div>
          </div>
          <div className="mt-3 p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
            <p className="text-xs text-gray-500 mb-1">Summary</p>
            <p className="text-sm text-gray-300">{ticket.summary}</p>
          </div>
          <div className="mt-3 flex gap-2">
            <a
              href={jiraUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-900/30 text-blue-400 text-xs font-medium hover:bg-blue-900/50 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              Open in Jira
            </a>
            <button
              onClick={() => navigate(`/incidents/${ticket.incident_id}`)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/50 text-gray-300 text-xs font-medium hover:bg-gray-700/50 transition-colors"
            >
              <ChevronRight className="w-3 h-3" />
              View Incident
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ExpandableNotification({ notif }: { notif: NotificationRecord }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden hover:border-purple-800/50 transition-all duration-200">
      {/* Header Row */}
      <div className="flex items-center justify-between px-4 py-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-purple-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
            <Bell className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${notif.type === 'escalation' ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300'}`}>
                {notif.type}
              </span>
              <span className="text-sm text-gray-300">{notif.channel}</span>
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-300">{notif.status}</span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">{notif.recipient}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{notif.service}</span>
          <span className="text-xs text-gray-600">{notif.sent_at ? new Date(notif.sent_at).toLocaleTimeString() : ''}</span>
          <button className="p-1 text-gray-500 hover:text-gray-300">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-800/50 animate-fade-in-up">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <AlertTriangle className="w-3 h-3" />
                <span>Type</span>
              </div>
              <p className={`text-sm font-medium ${notif.type === 'escalation' ? 'text-red-400' : 'text-blue-400'}`}>{notif.type}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Bell className="w-3 h-3" />
                <span>Channel</span>
              </div>
              <p className="text-sm font-medium text-purple-400">{notif.channel}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <User className="w-3 h-3" />
                <span>Recipient</span>
              </div>
              <p className="text-sm font-medium text-white truncate">{notif.recipient}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Clock className="w-3 h-3" />
                <span>Sent At</span>
              </div>
              <p className="text-sm font-medium text-white">{notif.sent_at ? new Date(notif.sent_at).toLocaleString() : 'N/A'}</p>
            </div>
          </div>
          {notif.subject && (
            <div className="mt-3 p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <p className="text-xs text-gray-500 mb-1">Subject</p>
              <p className="text-sm text-white font-medium">{notif.subject}</p>
            </div>
          )}
          {notif.message && (
            <div className="mt-3 p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <p className="text-xs text-gray-500 mb-1">Message</p>
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-auto">{notif.message}</pre>
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => navigate(`/incidents/${notif.incident_id}`)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-900/30 text-purple-400 text-xs font-medium hover:bg-purple-900/50 transition-colors"
            >
              <ChevronRight className="w-3 h-3" />
              View Incident
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ExpandablePagerDuty({ incident }: { incident: PagerDutyRecord }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const severityColors: Record<number, string> = {
    5: 'bg-red-900/50 text-red-300',
    4: 'bg-red-900/40 text-red-300',
    3: 'bg-orange-900/50 text-orange-300',
    2: 'bg-yellow-900/50 text-yellow-300',
    1: 'bg-blue-900/50 text-blue-300'
  }
  const severityTextColors: Record<number, string> = {
    5: 'text-red-400',
    4: 'text-red-400',
    3: 'text-orange-400',
    2: 'text-yellow-400',
    1: 'text-blue-400'
  }
  const pdSeverityMap: Record<number, string> = {
    5: 'critical',
    4: 'critical',
    3: 'error',
    2: 'warning',
    1: 'info'
  }

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden hover:border-green-800/50 transition-all duration-200">
      {/* Header Row */}
      <div className="flex items-center justify-between px-4 py-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <div className="w-8 h-8 bg-green-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
            <Zap className="w-4 h-4 text-green-400" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-green-400">{incident.pagerduty_id}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${severityColors[incident.severity] || severityColors[3]}`}>
                SEV-{incident.severity}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-green-900/30 text-green-300">{incident.status}</span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{incident.summary}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-gray-500">{incident.service}</span>
          <a
            href={incident.pagerduty_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="p-1.5 rounded-md hover:bg-green-900/30 text-gray-500 hover:text-green-400 transition-colors"
            title="Open in PagerDuty"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          <button className="p-1 text-gray-500 hover:text-gray-300">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-800/50 animate-fade-in-up">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Zap className="w-3 h-3" />
                <span>PagerDuty ID</span>
              </div>
              <p className="text-sm font-medium text-green-400">{incident.pagerduty_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Server className="w-3 h-3" />
                <span>Service</span>
              </div>
              <p className="text-sm font-medium text-white">{incident.service}</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <AlertTriangle className="w-3 h-3" />
                <span>Severity</span>
              </div>
              <p className={`text-sm font-medium ${severityTextColors[incident.severity] || 'text-orange-400'}`}>
                SEV-{incident.severity} ({pdSeverityMap[incident.severity] || 'error'})
              </p>
            </div>
            <div className="p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                <Clock className="w-3 h-3" />
                <span>Status</span>
              </div>
              <p className="text-sm font-medium text-green-400">{incident.status}</p>
            </div>
          </div>
          <div className="mt-3 p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
            <p className="text-xs text-gray-500 mb-1">Incident Summary</p>
            <p className="text-sm text-gray-300">{incident.summary}</p>
          </div>
          <div className="mt-3 p-3 rounded-lg bg-gray-800/30 border border-gray-700/30">
            <p className="text-xs text-gray-500 mb-1">Linked Incident ID</p>
            <p className="text-sm text-cyan-400 font-mono">{incident.incident_id}</p>
          </div>
          <div className="mt-3 flex gap-2">
            <a
              href={incident.pagerduty_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-900/30 text-green-400 text-xs font-medium hover:bg-green-900/50 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              Open in PagerDuty
            </a>
            <button
              onClick={() => navigate(`/incidents/${incident.incident_id}`)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/50 text-gray-300 text-xs font-medium hover:bg-gray-700/50 transition-colors"
            >
              <ChevronRight className="w-3 h-3" />
              View Incident
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
