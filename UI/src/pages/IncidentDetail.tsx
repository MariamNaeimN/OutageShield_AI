import { useState, useEffect } from 'react'
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ExternalLink, FileText, ChevronRight, Home, Zap } from 'lucide-react'
import { getActiveIncidents, type Incident, type RootCauseEntry } from '../services/api'

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'

export default function IncidentDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setIncident(null)
    setLoading(true)
    setError(null)
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
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-brand-500/20 border-t-brand-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Zap className="w-4 h-4 text-brand-400" />
          </div>
        </div>
        <p className="text-sm text-gray-500 animate-pulse">Loading incident data...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/')}
          className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 text-sm text-gray-400 hover:text-white hover:bg-gray-700/50 hover:border-gray-600 transition-all duration-200"
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" />
          Back to Dashboard
        </button>
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300">
          {error || 'Incident not found'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Navigation breadcrumb + back button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="group flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/60 border border-gray-700/50 text-sm text-gray-400 hover:text-white hover:bg-gray-700/60 hover:border-gray-500/60 transition-all duration-200 backdrop-blur-sm"
          >
            <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
            <span className="font-medium">Back</span>
          </button>

          {/* Breadcrumb */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-600">
            <Link to="/" className="flex items-center gap-1 hover:text-gray-400 transition-colors">
              <Home className="w-3 h-3" />
              <span>Dashboard</span>
            </Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-500">Incidents</span>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-400 font-medium">{incident.id}</span>
          </div>
        </div>

        {/* Live indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-800/40 border border-gray-700/30 text-xs text-gray-500">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          Live data
        </div>
      </div>

      {/* Header card */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#161b22] via-[#161b22] to-[#0d1117] border border-gray-800/80 p-6">
        {/* Decorative glow */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-brand-600/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-purple-600/5 rounded-full blur-3xl pointer-events-none" />

        <div className="relative">
          {/* Top row: severity + status + service */}
          <div className="flex items-center gap-2.5 mb-3 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${
              incident.severity >= 4 ? 'bg-red-900/40 text-red-300 border-red-700/50' :
              incident.severity === 3 ? 'bg-orange-900/40 text-orange-300 border-orange-700/50' :
              'bg-yellow-900/40 text-yellow-300 border-yellow-700/50'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${
                incident.severity >= 4 ? 'bg-red-400' : incident.severity === 3 ? 'bg-orange-400' : 'bg-yellow-400'
              } animate-pulse`} />
              SEV-{incident.severity}
            </span>

            <span className={`px-2.5 py-1 rounded-lg text-xs font-medium border ${
              incident.status === 'Resolved' ? 'bg-green-900/30 text-green-300 border-green-700/40' :
              incident.status === 'Mitigating' ? 'bg-blue-900/30 text-blue-300 border-blue-700/40' :
              incident.status === 'Investigating' ? 'bg-yellow-900/30 text-yellow-300 border-yellow-700/40' :
              incident.status === 'Awaiting Approval' ? 'bg-purple-900/30 text-purple-300 border-purple-700/40' :
              'bg-gray-800/60 text-gray-300 border-gray-700/40'
            }`}>
              {incident.status}
            </span>

            <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-800/60 text-gray-400 border border-gray-700/40">
              {incident.service}
            </span>

            <span className="ml-auto text-xs text-gray-600 font-mono">{incident.id}</span>
          </div>

          {/* Title */}
          <h1 className="text-xl font-bold text-white leading-snug tracking-tight">
            {incident.title}
          </h1>

          {/* Detected time */}
          <p className="mt-2 text-xs text-gray-500">
            Detected {new Date(incident.detectedAt).toLocaleString()}
            {' · '}
            <span className="text-gray-400">{incident.workflowStep}</span>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Root Cause + Recommendations */}
        <div className="col-span-2 space-y-4">
          {/* Root Cause */}
          {(incident.rootCauses?.length || incident.rootCause) && (
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3">Root Cause (AI)</h3>

              {incident.rootCauses && incident.rootCauses.length > 0 ? (
                <div className="space-y-4">
                  {incident.rootCauses.map((rc: RootCauseEntry, i: number) => {
                    const confColor =
                      rc.confidence >= 80 ? 'bg-green-500' :
                      rc.confidence >= 50 ? 'bg-yellow-500' :
                      'bg-red-500'
                    const confLabel =
                      rc.confidence >= 80 ? 'text-green-400' :
                      rc.confidence >= 50 ? 'text-yellow-400' :
                      'text-red-400'
                    return (
                      <div key={i} className={`${i > 0 ? 'border-t border-gray-700/50 pt-4' : ''}`}>
                        {incident.rootCauses!.length > 1 && (
                          <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5 block">
                            Cause #{i + 1}
                          </span>
                        )}
                        <p className="text-sm text-gray-200 leading-relaxed">{rc.description}</p>

                        {/* Confidence bar */}
                        <div className="mt-3 flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${confColor} rounded-full transition-all duration-500`}
                              style={{ width: `${rc.confidence}%` }}
                            />
                          </div>
                          <span className={`text-xs font-medium ${confLabel} w-16 text-right`}>
                            {rc.confidence}% conf.
                          </span>
                        </div>

                        {/* Evidence */}
                        {rc.evidence && rc.evidence.length > 0 && (
                          <div className="mt-3">
                            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Evidence</p>
                            <ul className="space-y-1">
                              {rc.evidence.map((ev, j) => (
                                <li key={j} className="flex items-start gap-2 text-xs text-gray-400">
                                  <span className="mt-1 w-1 h-1 rounded-full bg-brand-500 shrink-0" />
                                  <span className="leading-relaxed">{ev}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                /* Fallback: plain string root cause */
                <>
                  <p className="text-sm text-gray-300">
                    {/* If it still looks like raw JSON, show a placeholder */}
                    {incident.rootCause?.trim().startsWith('[')
                      ? 'Root cause analysis pending...'
                      : incident.rootCause}
                  </p>
                  {incident.confidence && (
                    <div className="mt-3 flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-500 rounded-full" style={{ width: `${incident.confidence}%` }} />
                      </div>
                      <span className="text-xs text-gray-400">{incident.confidence}% confidence</span>
                    </div>
                  )}
                </>
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
              {/* Summary */}
              {(() => {
                const raw = incident as unknown as Record<string, unknown>
                let summary = raw.remediation_summary as string | undefined
                if (!summary) return null
                summary = summary.replace(/^Remediation Summary:\s*/i, '').replace(/\s*Remediation Summary:\s*$/i, '').trim()
                summary = summary.replace(/,\s*\.$/, '.').replace(/,\s*$/, '').trim()
                if (!summary) return null

                // Parse structured summary
                const actionMatch = summary.match(/Action plan:\s*(.+?)(?=\.\s*Runbook|$)/i)
                const hasRunbook = /runbook available/i.test(summary)

                if (actionMatch) {
                  // Parse action plan into numbered steps
                  const actionText = actionMatch ? actionMatch[1].trim().replace(/\.$/, '') : ''
                  const actionSteps = actionText
                    ? actionText.split(/;\s*/).map(a => a.replace(/^\(\d+\)\s*/, '').trim()).filter(a => a.length > 3)
                    : []

                  return (
                    <div className="mb-4 p-5 bg-gradient-to-br from-blue-950/30 to-purple-950/20 border border-blue-800/30 rounded-xl space-y-4 animate-fade-in-up">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider">Remediation Summary</span>
                        <div className="flex items-center gap-2">
                          {hasRunbook && (
                            <span className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-purple-500/15 text-purple-400 border border-purple-700/30">📋 Runbook</span>
                          )}
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-blue-500/15 text-blue-400 border border-blue-700/30">{incident.recommendations.length} actions</span>
                        </div>
                      </div>

                      {actionSteps.length > 0 && (
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 w-6 h-6 rounded-lg bg-blue-900/30 flex items-center justify-center shrink-0 border border-blue-800/30">
                            <span className="text-xs">⚡</span>
                          </span>
                          <div className="flex-1">
                            <p className="text-[10px] font-bold text-blue-400/80 uppercase tracking-wider mb-1.5">Action Plan</p>
                            <div className="space-y-1.5">
                              {actionSteps.map((step, i) => (
                                <div key={i} className="flex items-start gap-2">
                                  <span className="w-5 h-5 rounded bg-blue-900/40 border border-blue-700/30 flex items-center justify-center text-[10px] font-bold text-blue-300 shrink-0 mt-0.5">{i + 1}</span>
                                  <p className="text-sm text-blue-100 leading-relaxed">{step}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                }

                // Fallback: plain text summary (old format)
                return (
                  <div className="mb-4 p-4 bg-blue-950/20 border border-blue-800/30 rounded-lg">
                    <p className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider mb-1.5">Remediation Summary</p>
                    <p className="text-sm text-blue-200 leading-relaxed">{summary}</p>
                  </div>
                )
              })()}
              <div className="space-y-2.5">
                {incident.recommendations.map((rec, i) => {
                  const icon = rec.category === 'rollback' ? '↩️' : rec.category === 'scaling' ? '📈' : rec.category === 'configuration_change' ? '⚙️' : '👤'
                  const borderColor = rec.category === 'rollback' ? 'border-l-blue-500' : rec.category === 'scaling' ? 'border-l-green-500' : rec.category === 'configuration_change' ? 'border-l-amber-500' : 'border-l-gray-500'
                  const riskColor = rec.risk === 'low' ? 'text-green-400' : rec.risk === 'medium' ? 'text-yellow-400' : 'text-red-400'
                  return (
                    <div
                      key={i}
                      className={`rounded-lg bg-[#0d1117] border border-gray-700/30 border-l-[3px] ${borderColor} px-4 py-3 hover-lift animate-fade-in-up`}
                      style={{ animationDelay: `${i * 60}ms` }}
                    >
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
                                String((rec as any).source) === 'agent_advice' ? 'bg-gray-500/10 text-gray-400' :
                                'bg-gray-500/10 text-gray-400'
                              }`}>
                                <span className="w-1 h-1 rounded-full bg-current" />
                                {(() => {
                                  const src = String((rec as any).source)
                                  if (src === 'agent_advice') return 'Agent Advice'
                                  if (src === 'insufficient_evidence') return 'Low Evidence'
                                  if (src === 'RCA') return 'Root Cause Analysis'
                                  if (src.startsWith('AGENT:')) return src.replace('AGENT:', 'Agent: ').replace(/_/g, ' ')
                                  return src.replace(/_/g, ' ')
                                })()}
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

            // Replace <REDACTED> with meaningful source names
            const cleanedInvestigation = investigation
              .replace(/\[Source:\s*<REDACTED>\s*\/OpenSearch\]/gi, '[Source: OpenSearch Logs]')
              .replace(/\[Source:\s*<REDACTED>\]/gi, '[Source: Agent Tool]')
              .replace(/<REDACTED>\/OpenSearch/gi, 'OpenSearch Logs')
              .replace(/<REDACTED>/gi, 'Agent Tool')
              // Strip Remediation Summary and everything after (anywhere in text)
              .replace(/\s*Remediation Summary[\s\S]*$/i, '')
              .replace(/\s*recommended_actions:[\s\S]*$/i, '')
              // Strip agent meta-text like "This concludes the investigation..."
              .replace(/This concludes the investigation[\s\S]*$/i, '')
              .replace(/I have (?:now )?(?:completed|provided|finished)[\s\S]*$/i, '')
              // Strip "No data found from" orphan text (source tag was stripped leaving the prefix)
              .replace(/No data found from\s*\.?/gi, '')
              // Map XML-style section tags to [Source: X] equivalents
              .replace(/<investigation_summary>/gi, '')
              .replace(/<\/investigation_summary>/gi, '')
              .replace(/<similar_incidents>/gi,    '\n[Source: Incident History DB]\n')
              .replace(/<\/similar_incidents>/gi,  '')
              .replace(/<log_findings>/gi,         '\n[Source: OpenSearch Logs]\n')
              .replace(/<\/log_findings>/gi,       '')
              .replace(/<deployment_correlation>/gi, '\n[Source: Deployment History]\n')
              .replace(/<\/deployment_correlation>/gi, '')
              .replace(/<runbook_findings>/gi,     '\n[Source: Runbook DB]\n')
              .replace(/<\/runbook_findings>/gi,   '')
              .replace(/<recommended_actions>[\s\S]*?<\/recommended_actions>/gi, '')
              .replace(/<\/?[a-z_]+>/gi, '')
              // Map plain-text snake_case section labels
              .replace(/^Similar_incidents:\s*$/gim,       '[Source: Incident History DB]')
              .replace(/^Log_findings:\s*$/gim,            '[Source: OpenSearch Logs]')
              .replace(/^Deployment_correlation:\s*$/gim,  '[Source: Deployment History]')
              .replace(/^Runbook_findings:\s*$/gim,        '[Source: Runbook DB]')
              .replace(/^Similar_incidents:/gim,           '[Source: Incident History DB]')
              .replace(/^Log_findings:/gim,                '[Source: OpenSearch Logs]')
              .replace(/^Deployment_correlation:/gim,      '[Source: Deployment History]')
              .replace(/^Runbook_findings:/gim,            '[Source: Runbook DB]')
              // Collapse multiple blank lines
              .replace(/\n{3,}/g, '\n\n')

            // Parse sections using [Source: X] tags as reliable section boundaries
            // Build a map of source label → section config
            const SOURCE_MAP: Record<string, { title: string; icon: string; color: string }> = {
              'incident history': { title: 'Past Incidents',            icon: '🔍', color: 'border-l-blue-500'   },
              'opensearch':       { title: 'Log Analysis (OpenSearch)', icon: '📊', color: 'border-l-teal-500'   },
              'runbook':          { title: 'Runbook',                   icon: '📋', color: 'border-l-purple-500' },
              'deployment':       { title: 'Deployment Correlation',    icon: '🚀', color: 'border-l-orange-500' },
              'agent advice':     { title: 'Agent Advice',              icon: '💡', color: 'border-l-yellow-500' },
            }

            const resolveSource = (tag: string): string => {
              const lower = tag.toLowerCase()
              for (const key of Object.keys(SOURCE_MAP)) {
                if (lower.includes(key)) return key
              }
              return 'summary'
            }

            // If the text starts with content before any [Source:] tag,
            // try to infer the section from keywords in the opening block
            const firstSourceIdx = cleanedInvestigation.search(/\[Source:/i)
            let textToParse = cleanedInvestigation
            if (firstSourceIdx > 50) {
              // There's a meaningful opening block — check what it's about
              const opening = cleanedInvestigation.slice(0, firstSourceIdx).toLowerCase()
              let inferredTag = ''
              if (opening.includes('deployment') || opening.includes('connection pool') || opening.includes('config')) {
                inferredTag = '[Source: Deployment History]\n'
              } else if (opening.includes('past incident') || opening.includes('similar incident')) {
                inferredTag = '[Source: Incident History DB]\n'
              } else if (opening.includes('runbook')) {
                inferredTag = '[Source: Runbook DB]\n'
              } else if (opening.includes('opensearch') || opening.includes('alarm') || opening.includes('log')) {
                inferredTag = '[Source: OpenSearch Logs]\n'
              }
              if (inferredTag) {
                textToParse = inferredTag + cleanedInvestigation
              }
            }

            const sectionMap = new Map<string, { title: string; icon: string; color: string; items: string[] }>()
            sectionMap.set('summary', { title: 'Summary', icon: '📝', color: 'border-l-gray-500', items: [] })
            let currentKey = 'summary'

            textToParse.split('\n').forEach(line => {
              const trimmed = line.trim()
              if (!trimmed) return

              // Detect [Source: X] tag — may be at start OR inline at end of line
              const sourceMatch = trimmed.match(/^\[Source:\s*([^\]]+)\]/i)
              if (sourceMatch) {
                const key = resolveSource(sourceMatch[1])
                currentKey = key
                if (!sectionMap.has(key)) {
                  const cfg = SOURCE_MAP[key] ?? { title: sourceMatch[1], icon: '📌', color: 'border-l-gray-500' }
                  sectionMap.set(key, { ...cfg, items: [] })
                }
                const rest = trimmed.replace(/^\[Source:[^\]]+\]\s*/i, '').trim()
                if (rest && rest.length > 3) {
                  // Dedup check for content on same line as source tag
                  const normalizedRest = rest.replace(/\s+/g, ' ').toLowerCase()
                  const restPrefix = normalizedRest.slice(0, 80)
                  const sec = sectionMap.get(currentKey)
                  if (sec && !sec.items.some(item => {
                    const norm = item.replace(/\s+/g, ' ').toLowerCase()
                    return norm === normalizedRest || (restPrefix.length >= 40 && norm.startsWith(restPrefix))
                  })) {
                    sec.items.push(rest)
                  }
                }
                return
              }

              // Detect inline [Source: X] tag at end of line — e.g. "Similar Incidents: No past incidents found. [Source: Incident History DB]"
              const inlineSourceMatch = trimmed.match(/\[Source:\s*([^\]]+)\]\s*$/i)
              if (inlineSourceMatch) {
                const key = resolveSource(inlineSourceMatch[1])
                // Switch section for subsequent lines
                currentKey = key
                if (!sectionMap.has(key)) {
                  const cfg = SOURCE_MAP[key] ?? { title: inlineSourceMatch[1], icon: '📌', color: 'border-l-gray-500' }
                  sectionMap.set(key, { ...cfg, items: [] })
                }
                // Add the content before the tag as an item
                const content = trimmed
                  .replace(/\[Source:[^\]]*\]\s*$/i, '')
                  .replace(/^(Similar Incidents?|Log Findings?|Deployment Correlation|Runbook Findings?):\s*/i, '')
                  .trim()
                if (content && content.length > 3) sectionMap.get(currentKey)?.items.push(content)
                return
              }

              // Skip section-header-only lines
              if (trimmed.match(/^Investigation Summary:\s*$/i)) return
              if (trimmed.match(/^Remediation Summary:/i)) return

              // Detect plain-text section label lines (no [Source:] tag)
              const sectionLabelMatch = trimmed.match(/^(Similar Incidents?|Log Findings?|Deployment Correlation|Runbook Findings?|Past Incidents?):\s*(.*)/i)
              if (sectionLabelMatch) {
                const label = sectionLabelMatch[1].toLowerCase()
                const rest = sectionLabelMatch[2].trim()
                if (label.includes('similar') || label.includes('past incident')) {
                  currentKey = 'incident history'
                  if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['incident history'], items: [] })
                } else if (label.includes('log')) {
                  currentKey = 'opensearch'
                  if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['opensearch'], items: [] })
                } else if (label.includes('deployment')) {
                  currentKey = 'deployment'
                  if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['deployment'], items: [] })
                } else if (label.includes('runbook')) {
                  currentKey = 'runbook'
                  if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['runbook'], items: [] })
                }
                if (rest && rest.length > 3 && !rest.toLowerCase().includes('no past incidents found') && !rest.toLowerCase().includes('no similar')) {
                  sectionMap.get(currentKey)?.items.push(rest)
                }
                return
              }

              // Detect legacy numbered/keyword section headers (fallback for older format)
              if (trimmed.match(/similar past incidents/i) && !trimmed.startsWith('-')) {
                currentKey = 'incident history'
                if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['incident history'], items: [] })
                return
              }
              if (trimmed.match(/^log.?findings/i) || (trimmed.match(/log findings|opensearch log/i) && !trimmed.startsWith('-'))) {
                currentKey = 'opensearch'
                if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['opensearch'], items: [] })
                return
              }
              if (trimmed.match(/^runbook.?findings/i) || (trimmed.match(/runbook findings|runbook for/i) && !trimmed.startsWith('-'))) {
                currentKey = 'runbook'
                if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['runbook'], items: [] })
                return
              }
              if (trimmed.match(/^deployment.?correlation/i) || (trimmed.match(/deployment correlation|deployment history/i) && !trimmed.startsWith('-'))) {
                currentKey = 'deployment'
                if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['deployment'], items: [] })
                return
              }
              if (trimmed.match(/^similar.?incidents/i) && !trimmed.startsWith('-')) {
                currentKey = 'incident history'
                if (!sectionMap.has(currentKey)) sectionMap.set(currentKey, { ...SOURCE_MAP['incident history'], items: [] })
                return
              }

              // Content line — strip leading bullet/number and any inline [Source:] tags
              const clean = trimmed
                .replace(/^[-•]\s*/, '')
                .replace(/^\d+\.\s*/, '')
                .replace(/\[Source:[^\]]*\]\s*/gi, '')
                .trim()
              // Skip noise lines
              if (!clean || clean.length <= 3) return
              if (/^no data found/i.test(clean)) return
              if (/^no similar past incidents/i.test(clean)) return
              if (/^no information available/i.test(clean)) return
              if (/^similar past incidents:/i.test(clean) && clean.length < 30) return
              // Skip lines that are just a source label echoed back (e.g. "Deployment History." "Runbook DB.")
              if (/^(deployment history|runbook db|incident history db|opensearch logs?)\.?$/i.test(clean)) return
              // Deduplicate — don't add if already in this section (agent often repeats content)
              // Normalize whitespace for comparison, also check first 80 chars for near-duplicates
              const normalizedClean = clean.replace(/\s+/g, ' ').toLowerCase()
              const cleanPrefix = normalizedClean.slice(0, 80)
              const existing = sectionMap.get(currentKey)
              if (existing && !existing.items.some(item => {
                const norm = item.replace(/\s+/g, ' ').toLowerCase()
                return norm === normalizedClean || (cleanPrefix.length >= 40 && norm.startsWith(cleanPrefix))
              })) {
                existing.items.push(clean)
              }
            })

            // Remove empty sections and summary if other sections exist
            const sections = Array.from(sectionMap.values()).filter(s => s.items.length > 0)
            if (sections.length > 1) {
              const idx = sections.findIndex(s => s.title === 'Summary')
              if (idx >= 0 && sections[idx].items.length <= 1) sections.splice(idx, 1)
            }

            // Add brief notes for sources that appear in recommendations but not in investigation
            if (incident.recommendations && incident.recommendations.length > 0) {
              const recSources = new Set(incident.recommendations.map(r => (r as any).source || ''))
              const sectionKeys = new Set(sections.map(s => s.title))

              const getRecContent = (source: string) => {
                const rec = incident.recommendations.find(r => (r as any).source === source)
                if (!rec) return []
                const items: string[] = []
                if (rec.description) items.push(rec.description)
                if ((rec as any).reasoning) items.push((rec as any).reasoning)
                return items
              }

              if (recSources.has('AGENT:log_patterns') && !sectionKeys.has('Log Analysis (OpenSearch)')) {
                const items = getRecContent('AGENT:log_patterns')
                if (items.length > 0) sections.push({ title: 'Log Analysis (OpenSearch)', icon: '📊', color: 'border-l-teal-500', items })
              }
              if (recSources.has('AGENT:runbook') && !sectionKeys.has('Runbook')) {
                const items = getRecContent('AGENT:runbook')
                if (items.length > 0) sections.push({ title: 'Runbook', icon: '📋', color: 'border-l-purple-500', items })
              }
              if (recSources.has('AGENT:past_incidents') && !sectionKeys.has('Past Incidents')) {
                const items = getRecContent('AGENT:past_incidents')
                if (items.length > 0) sections.push({ title: 'Past Incidents', icon: '🔍', color: 'border-l-blue-500', items })
              }
              if (recSources.has('AGENT:deployment_correlation') && !sectionKeys.has('Deployment Correlation')) {
                const items = getRecContent('AGENT:deployment_correlation')
                if (items.length > 0) sections.push({ title: 'Deployment Correlation', icon: '🚀', color: 'border-l-orange-500', items })
              }
              if (recSources.has('agent_advice') && !sectionKeys.has('Agent Advice')) {
                const items = getRecContent('agent_advice')
                if (items.length > 0) sections.push({ title: 'Agent Advice', icon: '💡', color: 'border-l-yellow-500', items })
              }
            }

            // If no sections remain after all processing, don't render the card
            if (sections.length === 0) return null

            return (
              <div className="bg-[#161b22] border border-purple-800/30 rounded-xl p-5 scan-line">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse pulse-ring" />
                  <h3 className="text-sm font-semibold text-white">Autonomous Agent Investigation</h3>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-900/30 text-purple-400">Bedrock Agent</span>
                </div>

                <div className="space-y-3">
                  {sections.map((section, i) => (
                    <div
                      key={i}
                      className={`border-l-[3px] ${section.color} bg-gray-900/30 rounded-r-lg px-4 py-3 animate-fade-in-up`}
                      style={{ animationDelay: `${i * 80}ms` }}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-sm">{section.icon}</span>
                        <span className="text-xs font-semibold text-gray-200">{section.title}</span>
                      </div>
                      <div className="space-y-1 pl-6">
                        {section.items.map((item, j) => (
                          <p key={j} className="text-xs text-gray-400 leading-relaxed">{item}</p>
                        ))}
                      </div>
                    </div>
                  ))}
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
            <div id="ticket" className="bg-[#161b22] border border-gray-800 rounded-xl p-5 scroll-mt-6 hover-lift animate-fade-in-up" style={{ animationDelay: '100ms' }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-blue-900/25 flex items-center justify-center">
                    <ExternalLink className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                  <h3 className="text-sm font-semibold text-white">Linked Ticket</h3>
                </div>
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
                <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5 hover-lift animate-fade-in-up" style={{ animationDelay: '150ms' }}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${notif.type === 'escalation' ? 'bg-red-900/25' : 'bg-purple-900/25'}`}>
                      <span className="text-sm">{notif.type === 'escalation' ? '🚨' : '🔔'}</span>
                    </div>
                    <h3 className="text-sm font-semibold text-white">SNS Notification</h3>
                    <span className={`ml-auto px-2 py-0.5 rounded text-[10px] font-bold ${notif.type === 'escalation' ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300'}`}>
                      {notif.type || 'alert'}
                    </span>
                  </div>
                  <div className="space-y-2 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
                    <div className="flex items-center gap-3">
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
