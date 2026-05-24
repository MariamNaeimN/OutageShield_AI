import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Ticket, ChevronRight, ExternalLink } from 'lucide-react'
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
}

export default function Notifications() {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([])
  const [tickets, setTickets] = useState<TicketRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'tickets' | 'sns'>('tickets')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const incidents = await getActiveIncidents()
        const notifs: NotificationRecord[] = []
        const tix: TicketRecord[] = []

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

          // Extract tickets
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
              service: inc.service
            })
          }
        }

        setNotifications(notifs)
        setTickets(tix)
      } catch {
        setNotifications([])
        setTickets([])
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
        <p className="text-sm text-gray-500 mt-1">SNS alerts and Jira tickets created by the agent</p>
      </div>

      {/* Tabs */}
      <div className="relative flex gap-1 bg-[#161b22] border border-gray-800 rounded-xl p-1 w-fit">
        {/* Animated sliding indicator */}
        <div
          className="absolute top-1 bottom-1 rounded-lg transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
          style={{
            left: tab === 'tickets' ? '4px' : '50%',
            width: 'calc(50% - 4px)',
            background: tab === 'tickets'
              ? 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(99,102,241,0.15))'
              : 'linear-gradient(135deg, rgba(168,85,247,0.2), rgba(139,92,246,0.15))',
            boxShadow: tab === 'tickets'
              ? '0 0 12px rgba(59,130,246,0.15)'
              : '0 0 12px rgba(168,85,247,0.15)',
          }}
        />
        <button
          onClick={() => setTab('tickets')}
          className={`relative z-10 flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            tab === 'tickets' ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Ticket className={`w-4 h-4 transition-transform duration-200 ${tab === 'tickets' ? 'scale-110' : ''}`} />
          <span>Tickets</span>
          <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-200 ${
            tab === 'tickets' ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-800 text-gray-500'
          }`}>{tickets.length}</span>
        </button>
        <button
          onClick={() => setTab('sns')}
          className={`relative z-10 flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
            tab === 'sns' ? 'text-purple-400' : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Bell className={`w-4 h-4 transition-transform duration-200 ${tab === 'sns' ? 'scale-110 animate-pulse' : ''}`} />
          <span>SNS Alerts</span>
          <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold transition-all duration-200 ${
            tab === 'sns' ? 'bg-purple-500/20 text-purple-300' : 'bg-gray-800 text-gray-500'
          }`}>{notifications.length}</span>
        </button>
      </div>

      {/* Tickets Tab */}
      {tab === 'tickets' && (
        <div className="space-y-2 animate-fade-in-up">
          {tickets.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500 animate-scale-in">No tickets</div>
          ) : tickets.map((t, i) => (
            <div key={i} className="animate-fade-in-up" style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}>
              <ExpandableTicket ticket={t} />
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
  const jiraUrl = `${JIRA_BASE_URL}/browse/${ticket.ticket_id}`

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden hover:border-blue-800/50 hover-lift transition-all duration-200">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4 min-w-0 flex-1 cursor-pointer" onClick={() => navigate(`/tickets/${ticket.incident_id}`)}>
          <div className="w-8 h-8 bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
            <Ticket className="w-4 h-4 text-blue-400" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
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
          <ChevronRight className="w-4 h-4 text-gray-600 cursor-pointer" onClick={() => navigate(`/tickets/${ticket.incident_id}`)} />
        </div>
      </div>
    </div>
  )
}

function ExpandableNotification({ notif }: { notif: NotificationRecord }) {
  const navigate = useNavigate()
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden cursor-pointer hover:border-purple-800/50 hover-lift transition-all duration-200" onClick={() => navigate(`/sns/${notif.incident_id}`)}>
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${notif.type === 'escalation' ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300'}`}>
            {notif.type}
          </span>
          <span className="text-sm text-gray-300">{notif.channel}</span>
          <span className="text-sm text-gray-400">{notif.recipient}</span>
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-300">{notif.status}</span>
          {notif.subject && <span className="text-xs text-gray-500 hidden md:inline">{notif.subject}</span>}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-600">{notif.sent_at ? new Date(notif.sent_at).toLocaleTimeString() : ''}</span>
          <ChevronRight className="w-4 h-4 text-gray-600" />
        </div>
      </div>
    </div>
  )
}
