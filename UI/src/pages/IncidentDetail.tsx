import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, ExternalLink, FileText, ChevronRight, Zap, Clock, Users, 
  DollarSign, AlertTriangle, CheckCircle, Target, TrendingUp, 
  Shield, Server, Bell, X, Info, Copy, Sparkles, Search, RefreshCw
} from 'lucide-react'
import { getActiveIncidents, getAIReasoning, type Incident, type RootCauseEntry, type AIReasoning } from '../services/api'

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'

export default function IncidentDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'actions' | 'ai-summary' | 'investigation'>('overview')
  const [showSnsModal, setShowSnsModal] = useState(false)
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null)
  const [aiReasoning, setAiReasoning] = useState<AIReasoning | null>(null)

  useEffect(() => {
    if (!id) return
    setIncident(null); setLoading(true); setError(null); setAiReasoning(null)
    const fetchData = async () => {
      try {
        const allIncidents = await getActiveIncidents()
        const found = allIncidents.find(i => i.id === id || i.id.toLowerCase() === id.toLowerCase())
        if (found) {
          setIncident(found)
          // Fetch AI reasoning data in parallel
          const reasoning = await getAIReasoning(found.id)
          if (reasoning) setAiReasoning(reasoning)
        }
        else setError(`Incident ${id} not found`)
      } catch (err) { setError(err instanceof Error ? err.message : 'Failed to load') }
      finally { setLoading(false) }
    }
    fetchData()
  }, [id])

  useEffect(() => {
    if (!loading && incident && location.hash === '#ticket') {
      setTimeout(() => document.getElementById('ticket')?.scrollIntoView({ behavior: 'smooth' }), 100)
    }
  }, [loading, incident, location.hash])

  const copyCmd = (text: string, cmdId: string) => {
    navigator.clipboard.writeText(text)
    setCopiedCommand(cmdId)
    setTimeout(() => setCopiedCommand(null), 2000)
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <RefreshCw className="w-6 h-6 text-brand-500 animate-spin" />
    </div>
  )


  if (error || !incident) return (
    <div className="max-w-xl mx-auto mt-16 animate-fade-in-up">
      <button onClick={() => navigate('/')} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </button>
      <div className="bg-[#161b22] border border-red-900/50 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-500 mx-auto mb-3" />
        <p className="text-red-400 text-sm">{error || 'Incident not found'}</p>
      </div>
    </div>
  )

  const raw = incident as unknown as Record<string, unknown>
  const detectedTime = new Date(incident.detectedAt)
  const diffMs = Date.now() - detectedTime.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const duration = diffHours > 0 ? `${diffHours}h ${diffMins % 60}m` : `${diffMins}m`

  const sevConfig: Record<number, { color: string; bg: string; border: string; label: string }> = {
    5: { color: 'text-red-300', bg: 'bg-red-900/50', border: 'border-red-700/50', label: 'CRITICAL' },
    4: { color: 'text-orange-300', bg: 'bg-orange-900/50', border: 'border-orange-700/50', label: 'HIGH' },
    3: { color: 'text-yellow-300', bg: 'bg-yellow-900/50', border: 'border-yellow-700/50', label: 'MEDIUM' },
    2: { color: 'text-green-300', bg: 'bg-green-900/50', border: 'border-green-700/50', label: 'LOW' },
    1: { color: 'text-gray-300', bg: 'bg-gray-800/50', border: 'border-gray-700/50', label: 'INFO' }
  }
  const sev = sevConfig[incident.severity] || sevConfig[3]

  const statusConfig: Record<string, { color: string; bg: string; icon: typeof CheckCircle }> = {
    'Resolved': { color: 'text-green-300', bg: 'bg-green-900/30', icon: CheckCircle },
    'Mitigating': { color: 'text-blue-300', bg: 'bg-blue-900/30', icon: Shield },
    'Investigating': { color: 'text-yellow-300', bg: 'bg-yellow-900/30', icon: Target },
    'Awaiting Approval': { color: 'text-purple-300', bg: 'bg-purple-900/30', icon: Clock }
  }
  const status = statusConfig[incident.status] || { color: 'text-gray-300', bg: 'bg-gray-800/30', icon: AlertTriangle }
  const StatusIcon = status.icon

  // Parse AI summary data - prefer data from ai-reasoning table, fallback to remediation_summary
  let aiSummaryData: Record<string, unknown> = {}
  const rawSummary = raw.remediation_summary || ''
  let aiGeneratedSummary = ''
  let investigationSummary = ''
  let rootCauseSummary = String(raw.root_cause || '')
  let rootCauseCategory = ''
  let rootCauseConfidence = 0
  let recommendedAction: Record<string, unknown> = {}
  let quickActions: Array<{ label: string; command: string }> = []
  
  // Get category and confidence from rootCauses if available
  if (incident.rootCauses && incident.rootCauses.length > 0) {
    const primaryCause = incident.rootCauses[0]
    rootCauseCategory = primaryCause.category || ''
    rootCauseConfidence = primaryCause.confidence || 0
    if (!rootCauseSummary) rootCauseSummary = primaryCause.description
  }
  
  // Use AI reasoning data from the dedicated table if available
  if (aiReasoning) {
    aiGeneratedSummary = aiReasoning.ai_summary || ''
    investigationSummary = aiReasoning.investigation_summary || ''
    if (aiReasoning.root_cause) rootCauseSummary = aiReasoning.root_cause
    if (aiReasoning.recommended_action) recommendedAction = aiReasoning.recommended_action as Record<string, unknown>
    if (aiReasoning.quick_actions) quickActions = aiReasoning.quick_actions
  } else if (rawSummary) {
    // Fallback to parsing remediation_summary
    try {
      const summaryStr = String(rawSummary)
      if (summaryStr.startsWith('{')) {
        // It's JSON
        aiSummaryData = JSON.parse(summaryStr)
        aiGeneratedSummary = String(aiSummaryData.ai_summary || '')
        investigationSummary = String(aiSummaryData.investigation_summary || '')
        if (aiSummaryData.root_cause) rootCauseSummary = String(aiSummaryData.root_cause)
        recommendedAction = (aiSummaryData.recommended_action as Record<string, unknown>) || {}
      } else {
        // It's plain text - use it as the summary
        aiGeneratedSummary = summaryStr
      }
    } catch {
      // Parse failed, use as plain text
      aiGeneratedSummary = String(rawSummary)
    }
  }
  
  const scoringReasoning = raw.scoring_reasoning || ''
  const agentInvestigation = raw.agent_investigation || ''


  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="p-2 rounded-lg bg-[#161b22] border border-gray-800 hover:bg-gray-800 transition-colors">
            <ArrowLeft className="w-4 h-4 text-gray-400" />
          </button>
          <nav className="hidden sm:flex items-center gap-1.5 text-xs text-gray-500">
            <Link to="/" className="hover:text-gray-300 transition-colors">Dashboard</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-blue-400 font-medium">{incident.id}</span>
          </nav>
        </div>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#161b22] border border-gray-800 text-xs">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-gray-400">Live</span>
        </span>
      </div>

      {/* Header Card */}
      <div className="bg-[#161b22] border border-gray-800 rounded-xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`px-2.5 py-1 rounded text-xs font-bold border ${sev.bg} ${sev.color} ${sev.border}`}>
              SEV-{incident.severity}
            </span>
            <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-gray-700/50 ${status.bg} ${status.color}`}>
              <StatusIcon className="w-3 h-3" />
              {incident.status}
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-900/30 text-xs font-medium text-blue-300 border border-blue-700/50">
              <Server className="w-3 h-3" />
              {incident.service}
            </span>
          </div>
          <span className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="w-3 h-3" /> {duration} ago
          </span>
        </div>
        <h1 className="text-xl font-bold text-white mb-2">{incident.title}</h1>
        <p className="text-sm text-gray-500">{detectedTime.toLocaleDateString()} {detectedTime.toLocaleTimeString()} · {incident.workflowStep}</p>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
          <StatBox icon={TrendingUp} label="Impact" value={`${incident.businessImpact}/10`} color="red" />
          <StatBox icon={Clock} label="Duration" value={duration} color="orange" />
          <StatBox icon={Users} label="Users" value={raw.affected_users ? String(raw.affected_users) : '—'} color="blue" />
          <StatBox icon={DollarSign} label="Revenue" value={raw.revenue_at_risk ? String(raw.revenue_at_risk) : '—'} color="green" />
        </div>
      </div>



      {/* Tab Navigation */}
      <div className="flex items-center gap-1 p-1 bg-[#161b22] border border-gray-800 rounded-lg w-fit">
        <TabBtn active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>Overview</TabBtn>
        <TabBtn active={activeTab === 'actions'} onClick={() => setActiveTab('actions')}>
          Actions {incident.recommendations?.length ? `(${incident.recommendations.length})` : ''}
        </TabBtn>
        <TabBtn active={activeTab === 'ai-summary'} onClick={() => setActiveTab('ai-summary')}>
          <Sparkles className="w-3.5 h-3.5 mr-1" /> AI Summary
        </TabBtn>
        <TabBtn active={activeTab === 'investigation'} onClick={() => setActiveTab('investigation')}>
          <Search className="w-3.5 h-3.5 mr-1" /> Investigation
        </TabBtn>
      </div>


      {/* Tab Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <>
              {/* Root Causes */}
              {incident.rootCauses && incident.rootCauses.length > 0 && (
                <Section title="Root Cause Analysis" icon={Target} badge={`${incident.rootCauses.length} identified`}>
                  <div className="space-y-3">
                    {incident.rootCauses.map((rc: RootCauseEntry, i: number) => (
                      <div key={i} className={`p-4 rounded-lg border ${i === 0 ? 'bg-blue-900/20 border-blue-700/50' : 'bg-gray-800/30 border-gray-700/50'}`}>
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-bold uppercase tracking-wider ${i === 0 ? 'text-blue-400' : 'text-gray-500'}`}>
                              {i === 0 ? '● Primary Cause' : `Contributing #${i + 1}`}
                            </span>
                            {rc.category && (
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                rc.category === 'capacity' ? 'bg-red-900/50 text-red-300' :
                                rc.category === 'performance' ? 'bg-orange-900/50 text-orange-300' :
                                rc.category === 'configuration' ? 'bg-amber-900/50 text-amber-300' :
                                rc.category === 'deployment' ? 'bg-sky-900/50 text-sky-300' :
                                rc.category === 'dependency' ? 'bg-purple-900/50 text-purple-300' :
                                'bg-gray-800 text-gray-400'
                              }`}>{rc.category}</span>
                            )}
                          </div>
                          <span className={`text-xs font-bold ${rc.confidence >= 80 ? 'text-green-400' : rc.confidence >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                            {rc.confidence}%
                          </span>
                        </div>
                        <p className="text-sm text-gray-300">{rc.description}</p>
                        {rc.evidence && rc.evidence.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-700/50">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-gray-600 mb-2">Evidence</p>
                            <ul className="space-y-1">
                              {rc.evidence.map((ev, j) => (
                                <li key={j} className="flex items-start gap-2 text-xs text-gray-500">
                                  <span className="mt-1.5 w-1 h-1 rounded-full bg-blue-500 shrink-0" />
                                  {ev}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Quick Links */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {incident.ticket && (
                  <QuickLink href={incident.ticket.url || incident.ticket_url || `${JIRA_BASE_URL}/browse/${incident.ticket.id}`} icon={ExternalLink} title={incident.ticket.id} subtitle={incident.ticket.system || 'Jira'} color="blue" />
                )}
                {incident.pagerduty_id && incident.pagerduty_id !== incident.ticket?.id && (
                  <QuickLink href={incident.pagerduty_url || '#'} icon={Zap} title={incident.pagerduty_id} subtitle="PagerDuty" color="green" />
                )}

                <Link to={`/postmortems?incident=${incident.id}`} className="flex items-center gap-3 p-4 rounded-lg bg-[#161b22] border border-gray-800 hover:bg-gray-800/50 transition-colors group">
                  <div className="w-10 h-10 rounded-lg bg-purple-900/30 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-purple-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors">Postmortem</p>
                    <p className="text-xs text-gray-500">View full analysis</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-600" />
                </Link>
                {incident.notifications && (() => {
                  let snsTopicName = 'outageshield-escalation-dev';
                  try {
                    const notifData = typeof incident.notifications === 'string' ? JSON.parse(incident.notifications) : incident.notifications;
                    snsTopicName = notifData?.sns_topic || 'outageshield-escalation-dev';
                  } catch { /* use default */ }
                  return (
                    <button onClick={() => setShowSnsModal(true)} className="flex items-center gap-3 p-4 rounded-lg bg-[#161b22] border border-gray-800 hover:bg-gray-800/50 transition-colors group text-left">
                      <div className="w-10 h-10 rounded-lg bg-amber-900/30 flex items-center justify-center">
                        <Bell className="w-5 h-5 text-amber-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white group-hover:text-amber-300 transition-colors">{snsTopicName}</p>
                        <p className="text-xs text-gray-500">View notification</p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-600" />
                    </button>
                  );
                })()}
              </div>
            </>
          )}


          {/* Actions Tab */}
          {activeTab === 'actions' && (
            <Section title="Recommended Actions" icon={Zap} badge={incident.recommendations?.length ? `${incident.recommendations.length} actions` : undefined}>
              {incident.recommendations && incident.recommendations.length > 0 ? (
                <div className="space-y-4">
                  {incident.recommendations.map((rec, i) => {
                    const confidence = (rec as any).confidence || rec.effectiveness * 20
                    const reasoning = (rec as any).reasoning || ''
                    const ttr = (rec as any).estimated_ttr_minutes || rec.estimatedTTR || 30
                    const isTopPick = i === 0 && confidence >= 60

                    return (
                      <div key={i} className={`p-4 rounded-lg border ${isTopPick ? 'bg-blue-900/20 border-blue-600/50' : 'bg-[#161b22] border-gray-800'}`}>
                        {/* Header row */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-gray-500">#{i + 1}</span>
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              rec.category === 'rollback' ? 'bg-sky-900/50 text-sky-300' :
                              rec.category === 'scaling' ? 'bg-emerald-900/50 text-emerald-300' :
                              rec.category === 'configuration_change' ? 'bg-amber-900/50 text-amber-300' :
                              'bg-gray-800 text-gray-400'
                            }`}>{rec.category.replace('_', ' ')}</span>
                            {isTopPick && <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-600 text-white">RECOMMENDED</span>}
                          </div>
                          <div className="flex items-center gap-3 text-xs">
                            <span className={`font-bold ${confidence >= 70 ? 'text-green-400' : confidence >= 40 ? 'text-yellow-400' : 'text-gray-500'}`}>{confidence}%</span>
                            <span className={`${rec.risk === 'low' ? 'text-green-400' : rec.risk === 'high' ? 'text-red-400' : 'text-yellow-400'}`}>{rec.risk} risk</span>
                            <span className="text-gray-500">{ttr}m TTR</span>
                          </div>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-gray-200 mb-3">{rec.description}</p>

                        {/* Evidence - simple preformatted block */}
                        {reasoning && (
                          <pre className="text-xs text-gray-400 font-mono bg-black/30 rounded p-3 overflow-x-auto whitespace-pre-wrap">{reasoning}</pre>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Zap className="w-8 h-8 text-gray-600 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No recommendations available</p>
                </div>
              )}
            </Section>
          )}


          {/* AI Summary Tab */}
          {activeTab === 'ai-summary' && (
            <Section title="AI Summary" icon={Sparkles} badge="Generated">
              {aiGeneratedSummary || scoringReasoning || rootCauseSummary ? (
                <div className="space-y-4">
                  {/* AI Generated Summary */}
                  {aiGeneratedSummary && (
                    <div className="p-4 rounded-lg bg-purple-900/20 border border-purple-700/50">
                      <div className="flex items-start gap-3">
                        <Sparkles className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-purple-400 mb-2">AI Analysis</p>
                          <p className="text-sm text-gray-200 leading-relaxed">{String(aiGeneratedSummary)}</p>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Root Cause */}
                  {rootCauseSummary ? (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Root Cause</h4>
                      <div className="p-4 rounded-lg bg-red-900/20 border border-red-700/50">
                        <div className="flex items-center gap-2 mb-2">
                          {rootCauseCategory && (
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              rootCauseCategory === 'capacity' ? 'bg-red-900/50 text-red-300' :
                              rootCauseCategory === 'performance' ? 'bg-orange-900/50 text-orange-300' :
                              rootCauseCategory === 'configuration' ? 'bg-amber-900/50 text-amber-300' :
                              rootCauseCategory === 'deployment' ? 'bg-sky-900/50 text-sky-300' :
                              rootCauseCategory === 'dependency' ? 'bg-purple-900/50 text-purple-300' :
                              'bg-gray-800 text-gray-400'
                            }`}>{rootCauseCategory}</span>
                          )}
                          {rootCauseConfidence > 0 && (
                            <span className={`text-xs font-bold ${rootCauseConfidence >= 80 ? 'text-green-400' : rootCauseConfidence >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                              (Confidence: {rootCauseConfidence}%)
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-300 leading-relaxed">{String(rootCauseSummary)}</p>
                      </div>
                    </div>
                  ) : null}
                  
                  {/* Recommended Action */}
                  {recommendedAction.description ? (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Recommended Action</h4>
                      <div className="p-4 rounded-lg bg-blue-900/20 border border-blue-700/50">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                            recommendedAction.type === 'scaling' ? 'bg-emerald-900/50 text-emerald-300' :
                            recommendedAction.type === 'rollback' ? 'bg-sky-900/50 text-sky-300' :
                            recommendedAction.type === 'configuration_change' ? 'bg-amber-900/50 text-amber-300' :
                            'bg-gray-800 text-gray-300'
                          }`}>{String(recommendedAction.type || 'manual').replace('_', ' ')}</span>
                          {recommendedAction.confidence ? (
                            <span className="text-xs text-green-400 font-bold">{String(recommendedAction.confidence)}% confidence</span>
                          ) : null}
                          {recommendedAction.estimated_ttr_minutes ? (
                            <span className="text-xs text-gray-500">~{String(recommendedAction.estimated_ttr_minutes)}m TTR</span>
                          ) : null}
                        </div>
                        <p className="text-sm text-gray-300">{String(recommendedAction.description)}</p>
                      </div>
                    </div>
                  ) : null}
                  
                  {/* Investigation Summary */}
                  {investigationSummary ? (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Investigation Summary</h4>
                      <div className="p-4 rounded-lg bg-gray-800/30 border border-gray-700/50">
                        <p className="text-sm text-gray-400">{String(investigationSummary)}</p>
                      </div>
                    </div>
                  ) : null}
                  
                  {/* Quick Actions */}
                  {quickActions && quickActions.length > 0 ? (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Quick Actions</h4>
                      <div className="space-y-3">
                        {quickActions.map((action, i) => (
                          <div key={i} className="rounded-lg bg-gray-800/30 border border-gray-700/50 overflow-hidden">
                            <div className="flex items-center justify-between px-4 py-2 bg-gray-800/50 border-b border-gray-700/50">
                              <p className="text-sm text-gray-200 font-medium">{action.label}</p>
                              <button
                                onClick={() => copyCmd(action.command, `quick-${i}`)}
                                className="flex items-center gap-1.5 px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 transition-colors text-xs"
                                title="Copy command"
                              >
                                {copiedCommand === `quick-${i}` ? (
                                  <>
                                    <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                                    <span className="text-green-400">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3.5 h-3.5 text-gray-400" />
                                    <span className="text-gray-400">Copy</span>
                                  </>
                                )}
                              </button>
                            </div>
                            <div className="p-3 overflow-x-auto">
                              <code className="text-xs text-emerald-400 font-mono whitespace-pre-wrap break-all leading-relaxed">
                                {action.command
                                  .replace(/--/g, '\n  --')
                                  .replace(/\n  --/, ' --')
                                  .replace(/\$\(/g, '\n  $(')
                                }
                              </code>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  
                  {/* Business Impact */}
                  {scoringReasoning ? (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Business Impact Analysis</h4>
                      <div className="p-4 rounded-lg bg-gray-800/30 border border-gray-700/50">
                        <p className="text-sm text-gray-300 leading-relaxed">{String(scoringReasoning)}</p>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Sparkles className="w-8 h-8 text-gray-600 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No AI summary available yet</p>
                  <p className="text-xs text-gray-600 mt-1">Summary will be generated after incident analysis completes</p>
                </div>
              )}
            </Section>
          )}

          {/* Investigation Tab */}
          {activeTab === 'investigation' && (
            <Section title="AI Investigation" icon={Search} badge="Bedrock Agent">
              {agentInvestigation ? (
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-blue-900/20 border border-blue-700/50">
                    <div className="flex items-start gap-2">
                      <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                      <p className="text-xs text-blue-300">The AI agent analyzed this incident using 6 specialized tools: incident history, logs, runbooks, deployments, traces, and config drift.</p>
                    </div>
                  </div>
                  <div className="p-4 rounded-lg bg-gray-800/30 border border-gray-700/50">
                    <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-auto">
                      {String(agentInvestigation)
                        .replace(/\[Source:\s*<REDACTED>[^\]]*\]/gi, '')
                        .replace(/<REDACTED>/gi, '')
                        .replace(/\n{3,}/g, '\n\n')
                        .trim()}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Search className="w-8 h-8 text-gray-600 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No investigation data available</p>
                </div>
              )}
            </Section>
          )}
        </div>


        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-5 sticky top-6">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-4">Status</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Status</span>
                <span className={`text-xs font-bold ${status.color}`}>{incident.status}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Workflow</span>
                <span className="text-xs text-blue-400">{incident.workflowStep}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Detected</span>
                <span className="text-xs text-gray-300">{detectedTime.toLocaleTimeString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Duration</span>
                <span className="text-xs font-bold text-orange-400">{duration}</span>
              </div>
            </div>

            <div className="h-px bg-gray-800 my-4" />

            <h3 className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-4">Impact</h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-gray-500">Severity</span>
                  <span className={`font-bold ${sev.color}`}>SEV-{incident.severity}</span>
                </div>
                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${incident.severity >= 4 ? 'bg-red-500' : incident.severity === 3 ? 'bg-orange-500' : 'bg-yellow-500'}`} style={{ width: `${(incident.severity / 5) * 100}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-gray-500">Business Impact</span>
                  <span className="font-bold text-white">{incident.businessImpact}/10</span>
                </div>
                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-red-600 to-red-400 rounded-full" style={{ width: `${(incident.businessImpact / 10) * 100}%` }} />
                </div>
              </div>
            </div>

            <div className="h-px bg-gray-800 my-4" />

            <h3 className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-3">Quick Commands</h3>
            <div className="space-y-2">
              <CmdBox label="View logs" cmd={`aws logs filter-log-events --log-group-name /aws/lambda/${incident.service}`} onCopy={copyCmd} copied={copiedCommand === 'logs'} id="logs" />
              <CmdBox label="Check metrics" cmd={`aws cloudwatch get-metric-data --metric-name Errors --namespace AWS/Lambda`} onCopy={copyCmd} copied={copiedCommand === 'metrics'} id="metrics" />
            </div>
          </div>
        </div>
      </div>


      {/* SNS Modal */}
      {showSnsModal && incident.notifications && (() => {
        let snsTopicName = 'outageshield-escalation-dev';
        try {
          const notifData = typeof incident.notifications === 'string' ? JSON.parse(incident.notifications) : incident.notifications;
          snsTopicName = notifData?.sns_topic || 'outageshield-escalation-dev';
        } catch { /* use default */ }
        return createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={() => setShowSnsModal(false)}>
          <div className="relative w-full max-w-xl max-h-[80vh] overflow-auto rounded-xl bg-[#161b22] border border-gray-800 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 z-10 flex items-center justify-between p-4 bg-[#161b22]/95 backdrop-blur border-b border-gray-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-900/30 flex items-center justify-center">
                  <Bell className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-white">{snsTopicName}</h2>
                  <p className="text-xs text-gray-500">{incident.id}</p>
                </div>
              </div>
              <button onClick={() => setShowSnsModal(false)} className="p-2 rounded-lg hover:bg-gray-800 transition-colors">
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {(() => {
                let notifData: Record<string, unknown> = {}
                try { notifData = typeof incident.notifications === 'string' ? JSON.parse(incident.notifications) : incident.notifications as Record<string, unknown> }
                catch { notifData = { raw: incident.notifications } }
                const snsTopic = notifData.sns_topic || 'outageshield-escalation-dev'
                return (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <InfoBox label="Type" value={String(notifData.type || 'escalation')} />
                      <InfoBox label="SNS Topic" value={String(snsTopic)} />
                      <InfoBox label="Recipient" value={String(notifData.recipient || 'N/A')} />
                      <InfoBox label="Sent" value={notifData.sent_at ? new Date(String(notifData.sent_at)).toLocaleString() : 'N/A'} />
                    </div>
                    {notifData.subject && (
                      <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700/50">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1">Subject</p>
                        <p className="text-sm text-white">{String(notifData.subject)}</p>
                      </div>
                    )}
                    {notifData.message && (
                      <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700/50">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Message</p>
                        <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap max-h-48 overflow-auto">{String(notifData.message)}</pre>
                      </div>
                    )}
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-green-900/20 border border-green-700/50">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-xs text-green-400 font-medium">Delivered successfully</span>
                    </div>
                  </>
                )
              })()}
            </div>
          </div>
        </div>,
        document.body
      )})()}
    </div>
  )
}


// Helper Components
function StatBox({ icon: Icon, label, value, color }: { icon: typeof Clock; label: string; value: string; color: 'red' | 'orange' | 'blue' | 'green' }) {
  const styles: Record<string, { border: string; iconBg: string; iconColor: string }> = {
    red: { border: 'border-red-900/60', iconBg: 'bg-red-900/30', iconColor: 'text-red-400' },
    orange: { border: 'border-orange-900/60', iconBg: 'bg-orange-900/30', iconColor: 'text-orange-400' },
    blue: { border: 'border-blue-900/60', iconBg: 'bg-blue-900/30', iconColor: 'text-blue-400' },
    green: { border: 'border-green-900/60', iconBg: 'bg-green-900/30', iconColor: 'text-green-400' }
  }
  const s = styles[color]
  return (
    <div className={`bg-[#161b22] border ${s.border} rounded-xl p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-7 h-7 ${s.iconBg} rounded-lg flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${s.iconColor}`} />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${active ? 'bg-gray-800 text-white' : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'}`}>
      {children}
    </button>
  )
}

function Section({ title, icon: Icon, badge, children }: { title: string; icon: typeof Target; badge?: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center">
            <Icon className="w-4 h-4 text-gray-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
        </div>
        {badge && <span className="px-2 py-1 rounded text-[10px] text-gray-500 bg-gray-800">{badge}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

function QuickLink({ href, icon: Icon, title, subtitle, color }: { href: string; icon: typeof ExternalLink; title: string; subtitle: string; color: 'blue' | 'green' }) {
  const colors = { blue: 'bg-blue-900/30 text-blue-400', green: 'bg-green-900/30 text-green-400' }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 p-4 rounded-lg bg-[#161b22] border border-gray-800 hover:bg-gray-800/50 transition-colors group">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{title}</p>
        <p className="text-xs text-gray-500">{subtitle}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-gray-600" />
    </a>
  )
}

function CmdBox({ label, cmd, onCopy, copied, id }: { label: string; cmd: string; onCopy: (cmd: string, id: string) => void; copied: boolean; id: string }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wider text-gray-600 mb-1">{label}</p>
      <div className="flex items-center gap-2 p-2 rounded bg-gray-800/50 border border-gray-700/50">
        <code className="flex-1 text-[10px] text-gray-400 font-mono truncate">{cmd}</code>
        <button onClick={() => onCopy(cmd, id)} className="p-1 rounded hover:bg-gray-700 transition-colors shrink-0">
          {copied ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-gray-500 hover:text-gray-300" />}
        </button>
      </div>
    </div>
  )
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700/50">
      <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1">{label}</p>
      <p className="text-sm text-white truncate">{value}</p>
    </div>
  )
}
