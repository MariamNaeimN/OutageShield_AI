import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { ArrowLeft, RefreshCw, ExternalLink, FileText } from 'lucide-react'
import { getActiveIncidents, type Incident } from '../services/api'

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'

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
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">Remediation Recommendations</h3>
                <span className="text-xs text-gray-500">{incident.recommendations.length} actions</span>
              </div>
              <div className="space-y-2.5">
                {incident.recommendations.map((rec, i) => {
                  const icon = rec.category === 'rollback' ? '↩️' : rec.category === 'scaling' ? '📈' : rec.category === 'configuration_change' ? '⚙️' : '👤'
                  const borderColor = rec.category === 'rollback' ? 'border-l-blue-500' : rec.category === 'scaling' ? 'border-l-green-500' : rec.category === 'configuration_change' ? 'border-l-amber-500' : 'border-l-gray-500'
                  const riskColor = rec.risk === 'low' ? 'text-green-400' : rec.risk === 'medium' ? 'text-yellow-400' : 'text-red-400'
                  return (
                    <div key={i} className={`rounded-lg bg-[#0d1117] border border-gray-700/30 border-l-[3px] ${borderColor} px-4 py-3`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5 flex-1 min-w-0">
                          <span className="text-sm mt-0.5 shrink-0">{icon}</span>
                          <div className="min-w-0">
                            <p className="text-sm text-gray-200 leading-snug">{rec.description}</p>
                            {(rec as any).reasoning && (
                              <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">{(rec as any).reasoning}</p>
                            )}
                            {(rec as any).source && (
                              <span className={`inline-flex items-center gap-1 mt-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                String((rec as any).source).includes('runbook') ? 'bg-purple-500/10 text-purple-400' :
                                String((rec as any).source).includes('past_incidents') ? 'bg-blue-500/10 text-blue-400' :
                                String((rec as any).source).includes('deployment') ? 'bg-orange-500/10 text-orange-400' :
                                String((rec as any).source).includes('RCA') ? 'bg-cyan-500/10 text-cyan-400' :
                                String((rec as any).source).includes('log') ? 'bg-teal-500/10 text-teal-400' :
                                'bg-gray-500/10 text-gray-400'
                              }`}>
                                <span className="w-1 h-1 rounded-full bg-current" />
                                {(rec as any).source}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 text-xs">
                          <span className={riskColor}>{rec.risk}</span>
                          <span className="text-gray-600">|</span>
                          <span className="text-gray-400">{(rec as any).estimated_ttr_minutes || rec.estimatedTTR || '?'}m</span>
                          <span className="text-gray-600">|</span>
                          <span className="font-bold text-white">{(rec as any).confidence || rec.effectiveness * 20}%</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Agent Investigation */}
          {(() => {
            const raw = incident as unknown as Record<string, unknown>
            const investigation = raw.agent_investigation as string | undefined
            if (!investigation) return null
            return (
              <div className="bg-[#161b22] border border-purple-800/30 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
                  <h3 className="text-sm font-semibold text-white">Autonomous Agent Investigation</h3>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-900/30 text-purple-400">Bedrock Agent</span>
                </div>
                <div className="text-xs text-gray-300 bg-gray-900/50 rounded-lg p-4 leading-relaxed space-y-2">
                  {investigation.split('\n').filter(Boolean).map((line, i) => {
                    const trimmed = line.trim()
                    if (trimmed.startsWith('Investigation Summary') || trimmed.startsWith('Based on') || trimmed.startsWith('Confidence') || trimmed.startsWith('Recommended Actions')) {
                      return <p key={i} className="font-semibold text-gray-200 mt-2">{trimmed}</p>
                    }
                    if (trimmed.match(/^\d+\./)) {
                      return <p key={i} className="pl-3 text-gray-300">{trimmed}</p>
                    }
                    if (trimmed.startsWith('-')) {
                      return <p key={i} className="pl-5 text-gray-400">{trimmed}</p>
                    }
                    return <p key={i}>{trimmed}</p>
                  })}
                </div>
              </div>
            )
          })()}

          {/* Postmortem Reference */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-purple-900/25 rounded-lg flex items-center justify-center">
                  <FileText className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Postmortem Report</h3>
                  <p className="text-xs text-gray-500 mt-0.5">AI-generated analysis & prevention steps</p>
                </div>
              </div>
              <Link
                to={`/postmortems?incident=${incident.id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-900/20 border border-purple-800/40 rounded-lg text-xs text-purple-400 hover:bg-purple-900/30 transition-colors"
              >
                <FileText className="w-3 h-3" />
                View Postmortem
              </Link>
            </div>
          </div>

          {/* Ticket */}
          {incident.ticket && (
            <div id="ticket" className="bg-[#161b22] border border-gray-800 rounded-xl p-5 scroll-mt-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Linked Ticket</h3>
                <a
                  href={`${JIRA_BASE_URL}/browse/${incident.ticket.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open in Jira
                </a>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <a
                    href={`${JIRA_BASE_URL}/browse/${incident.ticket.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-blue-400 hover:text-blue-300"
                  >
                    {incident.ticket.id}
                  </a>
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
                          <a href={`${JIRA_BASE_URL}/browse/${incident.ticket?.id}`} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:text-blue-300">{`${JIRA_BASE_URL}/browse/${incident.ticket?.id}`}</a>
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
                        <a href={`${JIRA_BASE_URL}/browse/${incident.ticket?.id || ''}`} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:text-blue-300 truncate max-w-[150px]">{incident.ticket?.id || raw.ticket_url as string}</a>
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
