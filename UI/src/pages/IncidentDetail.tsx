import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

export default function IncidentDetail() {
  const { id } = useParams()
  const location = useLocation()
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
          setError(`Incident ${id} not found in ${allIncidents.length} incidents`)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  // Scroll to ticket section if hash is #ticket
  useEffect(() => {
    if (!loading && incident && location.hash === '#ticket') {
      setTimeout(() => {
        document.getElementById('ticket')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }, [loading, incident, location.hash])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300">
          {error || 'Incident not found'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </Link>

      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white">{incident.title}</h2>
        <div className="flex items-center gap-3 mt-2">
          <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-red-900/50 text-red-300 border border-red-700/50">
            SEV-{incident.severity}
          </span>
          <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-purple-900/30 text-purple-300 border border-purple-700/50">
            {incident.status}
          </span>
          <span className="text-sm text-gray-500">{incident.service}</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Root Cause + Recommendations */}
        <div className="col-span-2 space-y-4">
          {/* Root Cause */}
          {incident.rootCause && (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-2">Root Cause (AI)</h3>
              <p className="text-sm text-gray-300">{incident.rootCause}</p>
              {incident.confidence && (
                <div className="mt-3 flex items-center gap-2">
                  <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-brand-500 rounded-full" style={{ width: `${incident.confidence}%` }} />
                  </div>
                  <span className="text-xs text-gray-400">{incident.confidence}% confidence</span>
                </div>
              )}
            </div>
          )}

          {/* Recommendations */}
          {incident.recommendations && incident.recommendations.length > 0 && (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3">Recommendations</h3>
              <div className="space-y-2">
                {incident.recommendations.map((rec, i) => (
                  <div key={i} className="p-3 rounded-lg border border-gray-800 bg-gray-800/30">
                    <p className="text-sm text-gray-200">{rec.description}</p>
                    <div className="flex gap-4 mt-1 text-xs text-gray-500">
                      <span>Confidence: {(rec as any).confidence || rec.effectiveness}%</span>
                      {(rec as any).evidence && <span className="text-gray-600 truncate max-w-xs">{(rec as any).evidence}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ticket */}
          {incident.ticket && (
            <div id="ticket" className="bg-[#161b22] border border-gray-800 rounded-xl p-5 scroll-mt-6">
              <h3 className="text-sm font-semibold text-white mb-3">Linked Ticket</h3>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-blue-400">{incident.ticket.id}</span>
                  <span className="text-xs text-gray-500">•</span>
                  <span className="text-xs text-gray-400">{incident.ticket.system}</span>
                  <span className="text-xs text-gray-500">•</span>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-900/30 text-blue-300">{incident.ticket.status}</span>
                </div>
                {(() => {
                  const raw = incident as unknown as Record<string, unknown>
                  const tc = raw.ticket_content as string | undefined
                  if (!tc) return null
                  try {
                    const content = JSON.parse(tc)
                    return (
                      <div className="mt-3 space-y-2 text-sm">
                        <div>
                          <p className="text-xs text-gray-500">Title</p>
                          <p className="text-gray-200 font-medium">{content.summary || incident.title}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Root Cause</p>
                          <p className="text-gray-300">{incident.rootCause || 'Pending analysis'}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Description</p>
                          <pre className="text-gray-300 text-xs bg-gray-900 rounded p-3 mt-1 whitespace-pre-wrap">{content.description?.replace(/\\n/g, '\n')}</pre>
                        </div>
                        <div className="flex gap-6">
                          <div>
                            <p className="text-xs text-gray-500">Priority</p>
                            <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-900/50 text-red-300">{content.priority}</span>
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Ticket URL</p>
                          <a href={content.url} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:text-blue-300">{content.url}</a>
                        </div>
                      </div>
                    )
                  } catch { return null }
                })()}
              </div>
            </div>
          )}

          {/* SNS Notification */}
          {(() => {
            const raw = incident as unknown as Record<string, unknown>
            const notifStr = raw.notifications as string | undefined
            if (!notifStr) return null
            try {
              const notif = JSON.parse(notifStr)
              return (
                <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-white mb-3">SNS Notification</h3>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${notif.type === 'escalation' ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300'}`}>
                        {notif.type || 'alert'}
                      </span>
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-300">
                        {notif.status || 'sent'}
                      </span>
                      <span className="text-xs text-gray-500">{notif.channel || 'SNS'}</span>
                    </div>
                    {notif.recipient && (
                      <div>
                        <p className="text-xs text-gray-500">Recipient</p>
                        <p className="text-sm text-gray-300">{notif.recipient}</p>
                      </div>
                    )}
                    {notif.subject && (
                      <div>
                        <p className="text-xs text-gray-500">Subject</p>
                        <p className="text-sm text-gray-200 font-medium">{notif.subject}</p>
                      </div>
                    )}
                    {notif.message && (
                      <div>
                        <p className="text-xs text-gray-500">Message</p>
                        <pre className="text-xs text-gray-300 bg-gray-900 rounded p-3 mt-1 whitespace-pre-wrap">{notif.message.replace(/\\n/g, '\n')}</pre>
                      </div>
                    )}
                    {notif.sent_at && (
                      <p className="text-xs text-gray-600 mt-2">Sent: {new Date(notif.sent_at).toLocaleString()}</p>
                    )}
                  </div>
                </div>
              )
            } catch { return null }
          })()}
        </div>

        {/* Right: Scores */}
        <div className="space-y-4">
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">Impact</h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-400">Severity</span>
                  <span className="text-white font-medium">{incident.severity}/5</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-500 rounded-full" style={{ width: `${(incident.severity / 5) * 100}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-400">Business Impact</span>
                  <span className="text-white font-medium">{incident.businessImpact}/10</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div className="h-full bg-red-500 rounded-full" style={{ width: `${(incident.businessImpact / 10) * 100}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Revenue at Risk + Extra Fields */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">Business Details</h3>
            <div className="space-y-2 text-sm">
              {(() => {
                const raw = incident as unknown as Record<string, unknown>
                return (
                  <>
                    {raw.revenue_at_risk && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Revenue at Risk</span>
                        <span className="text-red-400 font-medium">{raw.revenue_at_risk as string}</span>
                      </div>
                    )}
                    {raw.affected_users && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Affected Users</span>
                        <span className="text-white">{String(raw.affected_users).toLocaleString()}</span>
                      </div>
                    )}
                    {raw.sla_status && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">SLA Status</span>
                        <span className={`font-medium ${raw.sla_status === 'At Risk' ? 'text-red-400' : 'text-green-400'}`}>{raw.sla_status as string}</span>
                      </div>
                    )}
                    {raw.ticket_url && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Ticket URL</span>
                        <a href={raw.ticket_url as string} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:text-blue-300 truncate max-w-[150px]">{raw.ticket_url as string}</a>
                      </div>
                    )}
                  </>
                )
              })()}
            </div>
          </div>

          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Workflow Step</h3>
            <p className="text-sm text-brand-400">{incident.workflowStep}</p>
          </div>

          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Detected</h3>
            <p className="text-sm text-gray-300">{new Date(incident.detectedAt).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
