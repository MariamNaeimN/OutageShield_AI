import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Ticket, RefreshCw, ChevronRight } from 'lucide-react'
import { getActiveIncidents } from '../services/api'

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
    return <div className="flex items-center justify-center h-64"><RefreshCw className="w-6 h-6 text-brand-500 animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Notifications & Tickets</h2>
        <p className="text-sm text-gray-500 mt-1">SNS alerts and Jira tickets created by the agent</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#161b22] border border-gray-800 rounded-lg p-0.5 w-fit">
        <button onClick={() => setTab('tickets')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${tab === 'tickets' ? 'bg-blue-900/40 text-blue-400' : 'text-gray-400 hover:text-gray-200'}`}>
          <Ticket className="w-4 h-4 inline mr-2" />Tickets ({tickets.length})
        </button>
        <button onClick={() => setTab('sns')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${tab === 'sns' ? 'bg-blue-900/40 text-blue-400' : 'text-gray-400 hover:text-gray-200'}`}>
          <Bell className="w-4 h-4 inline mr-2" />SNS Alerts ({notifications.length})
        </button>
      </div>

      {/* Tickets Tab */}
      {tab === 'tickets' && (
        <div className="space-y-2">
          {tickets.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500">No tickets</div>
          ) : tickets.map((t, i) => (
            <ExpandableTicket key={i} ticket={t} />
          ))}
        </div>
      )}

      {/* SNS Tab */}
      {tab === 'sns' && (
        <div className="space-y-2">
          {notifications.length === 0 ? (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-8 text-center text-gray-500">No SNS alerts</div>
          ) : notifications.map((n, i) => (
            <ExpandableNotification key={i} notif={n} />
          ))}
        </div>
      )}
    </div>
  )
}

function ExpandableTicket({ ticket }: { ticket: TicketRecord }) {
  const navigate = useNavigate()
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden cursor-pointer hover:border-blue-800/50 transition-colors" onClick={() => navigate(`/tickets/${ticket.incident_id}`)}>
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4">
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
          <ChevronRight className="w-4 h-4 text-gray-600" />
        </div>
      </div>
    </div>
  )
}

function ExpandableNotification({ notif }: { notif: NotificationRecord }) {
  const navigate = useNavigate()
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden cursor-pointer hover:border-purple-800/50 transition-colors" onClick={() => navigate(`/sns/${notif.incident_id}`)}>
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
