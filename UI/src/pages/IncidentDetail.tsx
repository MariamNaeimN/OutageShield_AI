import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ExternalLink, FileText, ChevronRight, Home, Zap, Clock, Users, DollarSign, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Target, TrendingUp, Shield, Activity, Server, BookOpen, Bell, X, History, Search, FileCode, GitBranch, Cpu, Settings, AlertCircle, Info } from 'lucide-react'
import { getActiveIncidents, type Incident, type RootCauseEntry } from '../services/api'

// Investigation section type with enhanced structure
interface InvestigationSection {
  key: string
  title: string
  icon: typeof History
  color: string
  bgColor: string
  borderColor: string
  items: InvestigationItem[]
  summary?: string
}

interface InvestigationItem {
  type: 'incident' | 'log' | 'runbook' | 'deployment' | 'trace' | 'config' | 'insight' | 'text'
  title?: string
  description: string
  metadata?: Record<string, string | number>
  severity?: 'critical' | 'warning' | 'info' | 'success'
}

const JIRA_BASE_URL = 'https://corpinfollc.atlassian.net'

export default function IncidentDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    rootCause: true,
    actions: true,
    investigation: false,
    notification: true
  })
  const [showSnsModal, setShowSnsModal] = useState(false)
  const [expandedInvestigationSections, setExpandedInvestigationSections] = useState<Record<string, boolean>>({})

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }
  
  const toggleInvestigationSection = (key: string) => {
    setExpandedInvestigationSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  useEffect(() => {
    if (!id) return
    setIncident(null)
    setLoading(true)
    setError(null)
    const fetchData = async () => {
      try {
        const allIncidents = await getActiveIncidents()
        const found = allIncidents.find(i => i.id === id || i.id.toLowerCase() === id.toLowerCase())
        if (found) setIncident(found)
        else setError(`Incident ${id} not found`)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  useEffect(() => {
    if (!loading && incident && location.hash === '#ticket') {
      setTimeout(() => {
        document.getElementById('ticket')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }, [loading, incident, location.hash])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-full border-3 border-gray-700 border-t-brand-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Activity className="w-6 h-6 text-brand-400 animate-pulse" />
          </div>
        </div>
        <p className="text-sm text-gray-400">Loading incident details...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="max-w-2xl mx-auto mt-12 space-y-6">
        <button onClick={() => navigate('/')} className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
        <div className="bg-red-950/30 border border-red-800/50 rounded-2xl p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-white mb-2">Incident Not Found</h2>
          <p className="text-sm text-gray-400">{error || 'The requested incident could not be loaded.'}</p>
        </div>
      </div>
    )
  }

  // Access incident directly - notifications is now part of the Incident interface
  const raw = incident as unknown as Record<string, unknown>  // For backward compatibility with other raw fields
  
  // Debug: log notifications field
  console.log('[IncidentDetail] incident.id:', incident.id)
  console.log('[IncidentDetail] incident.notifications:', incident.notifications ? 'EXISTS' : 'MISSING', typeof incident.notifications)
  if (incident.notifications) {
    console.log('[IncidentDetail] notifications value:', String(incident.notifications).slice(0, 100))
  }
  
  const detectedTime = new Date(incident.detectedAt)
  const diffMs = Date.now() - detectedTime.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const timeAgo = diffHours > 0 ? `${diffHours}h ${diffMins % 60}m` : `${diffMins}m`

  // Parse investigation sections with enhanced structure
  const investigationSections: InvestigationSection[] = raw.agent_investigation 
    ? parseInvestigationEnhanced(raw.agent_investigation as string)
    : []
  const hasInvestigation: boolean = investigationSections.length > 0
  const totalInvestigationItems = investigationSections.reduce((sum, s) => sum + s.items.length, 0)

  const severityColors: Record<number, { bg: string; text: string; border: string; label: string }> = {
    5: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/40', label: 'Critical' },
    4: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', label: 'High' },
    3: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', label: 'Medium' },
    2: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', label: 'Low' },
    1: { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30', label: 'Info' }
  }
  const sev = severityColors[incident.severity] || severityColors[3]

  const statusColors: Record<string, { bg: string; text: string; icon: typeof CheckCircle }> = {
    'Resolved': { bg: 'bg-green-500/15', text: 'text-green-400', icon: CheckCircle },
    'Mitigating': { bg: 'bg-blue-500/15', text: 'text-blue-400', icon: Shield },
    'Investigating': { bg: 'bg-yellow-500/15', text: 'text-yellow-400', icon: Target },
    'Awaiting Approval': { bg: 'bg-purple-500/15', text: 'text-purple-400', icon: Clock }
  }
  const status = statusColors[incident.status] || { bg: 'bg-gray-500/15', text: 'text-gray-400', icon: AlertTriangle }
  const StatusIcon = status.icon


  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="group flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-800/50 border border-gray-700/50 text-sm text-gray-300 hover:text-white hover:bg-gray-700/50 hover:border-gray-600 transition-all">
            <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
            Back
          </button>
          <nav className="hidden md:flex items-center gap-2 text-sm text-gray-500">
            <Link to="/" className="flex items-center gap-1.5 hover:text-gray-300 transition-colors">
              <Home className="w-4 h-4" />
              Dashboard
            </Link>
            <ChevronRight className="w-4 h-4" />
            <span className="text-gray-400">Incidents</span>
            <ChevronRight className="w-4 h-4" />
            <span className="text-white font-medium">{incident.id}</span>
          </nav>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-400 font-medium">Live</span>
        </div>
      </div>

      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 border border-gray-700/50">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-600/5 via-transparent to-purple-600/5" />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4" />
        
        <div className="relative p-8">
          {/* Status Badges */}
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold ${sev.bg} ${sev.text} border ${sev.border}`}>
              <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
              SEV-{incident.severity} • {sev.label}
            </span>
            <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${status.bg} ${status.text}`}>
              <StatusIcon className="w-4 h-4" />
              {incident.status}
            </span>
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-gray-800/80 text-gray-300 border border-gray-700/50">
              <Server className="w-4 h-4" />
              {incident.service}
            </span>
          </div>

          {/* Title */}
          <h1 className="text-3xl font-bold text-white mb-3 leading-tight">{incident.title}</h1>
          <p className="text-gray-400 mb-8">
            Detected {detectedTime.toLocaleDateString()} at {detectedTime.toLocaleTimeString()} • {incident.workflowStep}
          </p>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard icon={Clock} label="Duration" value={timeAgo} color="orange" />
            <MetricCard icon={TrendingUp} label="Business Impact" value={`${incident.businessImpact}/10`} color="red" />
            <MetricCard icon={Users} label="Affected Users" value={raw.affected_users ? String(raw.affected_users).toLocaleString() : '—'} color="blue" />
            <MetricCard icon={DollarSign} label="Revenue at Risk" value={raw.revenue_at_risk ? String(raw.revenue_at_risk) : '—'} color="green" />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Left Column */}
        <div className="xl:col-span-2 space-y-6">
          
          {/* Root Cause Card */}
          {(incident.rootCauses && incident.rootCauses.length > 0) || incident.rootCause ? (
            <Card>
              <CardHeader 
                icon={Target} 
                title="Root Cause Analysis" 
                subtitle="AI-identified causes"
                badge={incident.rootCauses && incident.rootCauses.length > 0 ? `${incident.rootCauses.length} cause${incident.rootCauses.length > 1 ? 's' : ''}` : undefined}
                expanded={expandedSections.rootCause}
                onToggle={() => toggleSection('rootCause')}
                color="cyan"
              />
              
              {expandedSections.rootCause && incident.rootCauses && incident.rootCauses.length > 0 ? (
                <div className="p-6 pt-0 space-y-4">
                  {incident.rootCauses.map((rc: RootCauseEntry, i: number) => (
                    <div key={i} className={`p-5 rounded-2xl ${i === 0 ? 'bg-gradient-to-r from-cyan-950/40 to-cyan-900/20 border border-cyan-800/30' : 'bg-gray-800/30 border border-gray-700/30'}`}>
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex items-center gap-2">
                          {i === 0 && <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-cyan-500/20 text-cyan-400">Primary</span>}
                          {i > 0 && <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-gray-700 text-gray-400">Contributing #{i + 1}</span>}
                        </div>
                        <ConfidenceBadge value={rc.confidence} />
                      </div>
                      <p className="text-sm text-gray-200 leading-relaxed">{rc.description}</p>
                      <div className="mt-4 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all duration-700 ${rc.confidence >= 80 ? 'bg-green-500' : rc.confidence >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                          style={{ width: `${rc.confidence}%` }}
                        />
                      </div>
                      {rc.evidence && rc.evidence.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-gray-700/50">
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Evidence</p>
                          <ul className="space-y-1.5">
                            {rc.evidence.map((ev, j) => (
                              <li key={j} className="flex items-start gap-2 text-xs text-gray-400">
                                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-cyan-500 shrink-0" />
                                {ev}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : null}
            </Card>
          ) : null}


          {/* Recommended Actions Card */}
          {incident.recommendations && incident.recommendations.length > 0 ? (
            <Card>
              <CardHeader 
                icon={Zap} 
                title="Recommended Actions" 
                subtitle="AI-generated remediation steps"
                badge={`${incident.recommendations.length} action${incident.recommendations.length > 1 ? 's' : ''}`}
                expanded={expandedSections.actions}
                onToggle={() => toggleSection('actions')}
                color="blue"
              />
              
              {expandedSections.actions ? (
                <div className="p-6 pt-0">
                  {/* Action Cards */}
                  <div className="space-y-3">
                    {incident.recommendations.map((rec, i) => {
                      const categoryConfig: Record<string, { icon: string; color: string; label: string }> = {
                        'rollback': { icon: '↩️', color: 'blue', label: 'Rollback' },
                        'scaling': { icon: '📈', color: 'green', label: 'Scaling' },
                        'configuration_change': { icon: '⚙️', color: 'amber', label: 'Config' },
                        'manual': { icon: '👤', color: 'gray', label: 'Manual' }
                      }
                      const cat = categoryConfig[rec.category] || categoryConfig['manual']
                      const riskColors = { low: 'text-green-400 bg-green-500/10', medium: 'text-yellow-400 bg-yellow-500/10', high: 'text-red-400 bg-red-500/10' }
                      const risk = riskColors[rec.risk as keyof typeof riskColors] || riskColors.medium
                      const borderColors = { rollback: 'border-l-blue-500', scaling: 'border-l-green-500', configuration_change: 'border-l-amber-500', manual: 'border-l-gray-500' }
                      const border = borderColors[rec.category as keyof typeof borderColors] || borderColors.manual

                      return (
                        <div key={i} className={`rounded-2xl bg-gray-800/30 border border-gray-700/30 border-l-4 ${border} overflow-hidden hover:bg-gray-800/50 transition-colors`}>
                          <div className="p-5">
                            <div className="flex items-start gap-4">
                              <span className="text-2xl shrink-0">{cat.icon}</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-gray-100 leading-relaxed font-medium">{rec.description}</p>
                                {(rec as any).reasoning && (
                                  <p className="text-xs text-gray-500 mt-2 leading-relaxed">{(rec as any).reasoning}</p>
                                )}
                              </div>
                            </div>
                            
                            <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-gray-700/30">
                              <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold bg-${cat.color}-500/10 text-${cat.color}-400 border border-${cat.color}-500/20`}>{cat.label}</span>
                              <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${risk}`}>{rec.risk} risk</span>
                              <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-700/50 text-gray-400">⏱ {(rec as any).estimated_ttr_minutes || rec.estimatedTTR || '?'}m</span>
                              <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-brand-500/10 text-brand-400">{(rec as any).confidence || rec.effectiveness * 20}%</span>
                              {(rec as any).source && (
                                <span className="ml-auto px-2.5 py-1 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-400">
                                  🤖 {String((rec as any).source).replace('AGENT:', '').replace(/_/g, ' ')}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}
            </Card>
          ) : null}
          {/* Investigation Section - Redesigned */}
          {hasInvestigation ? (
            <Card>
              <CardHeader 
                icon={BookOpen} 
                title="Technical Investigation" 
                subtitle={`AI Agent analyzed ${investigationSections.length} data sources`}
                badge={`${totalInvestigationItems} findings`}
                expanded={expandedSections.investigation}
                onToggle={() => toggleSection('investigation')}
                color="purple"
              />
              
              {expandedSections.investigation ? (
                <div className="p-6 pt-0">
                  {/* Investigation Summary Bar */}
                  <div className="flex flex-wrap gap-2 mb-6 p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                    {investigationSections.map((section) => {
                      const SectionIcon = section.icon
                      return (
                        <button
                          key={section.key}
                          onClick={() => toggleInvestigationSection(section.key)}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                            expandedInvestigationSections[section.key] 
                              ? `${section.bgColor} ${section.color} ring-2 ring-current/30` 
                              : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                          }`}
                        >
                          <SectionIcon className="w-3.5 h-3.5" />
                          {section.title}
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            expandedInvestigationSections[section.key] ? 'bg-white/20' : 'bg-gray-600'
                          }`}>
                            {section.items.length}
                          </span>
                        </button>
                      )
                    })}
                  </div>

                  {/* Investigation Sections */}
                  <div className="space-y-4">
                    {investigationSections.map((section) => {
                      const SectionIcon = section.icon
                      const isExpanded = expandedInvestigationSections[section.key] ?? true
                      
                      return (
                        <div 
                          key={section.key} 
                          className={`rounded-2xl border overflow-hidden transition-all ${section.borderColor} bg-gray-800/20`}
                        >
                          {/* Section Header */}
                          <button
                            onClick={() => toggleInvestigationSection(section.key)}
                            className="w-full flex items-center justify-between p-4 hover:bg-gray-800/30 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-xl ${section.bgColor} flex items-center justify-center`}>
                                <SectionIcon className={`w-5 h-5 ${section.color}`} />
                              </div>
                              <div className="text-left">
                                <h4 className="text-sm font-semibold text-white">{section.title}</h4>
                                {section.summary && (
                                  <p className="text-xs text-gray-500 mt-0.5">{section.summary}</p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${section.bgColor} ${section.color}`}>
                                {section.items.length} {section.items.length === 1 ? 'item' : 'items'}
                              </span>
                              {isExpanded ? (
                                <ChevronUp className="w-4 h-4 text-gray-500" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                              )}
                            </div>
                          </button>

                          {/* Section Content */}
                          {isExpanded && (
                            <div className="px-4 pb-4 space-y-2">
                              {section.items.map((item, idx) => (
                                <InvestigationItemCard key={idx} item={item} />
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}
            </Card>
          ) : null}

          {/* Quick Links */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link to={`/postmortems?incident=${incident.id}`} className="group flex items-center gap-4 p-5 rounded-2xl bg-gray-800/30 border border-gray-700/30 hover:bg-purple-950/20 hover:border-purple-700/40 transition-all">
              <div className="w-12 h-12 rounded-xl bg-purple-500/15 flex items-center justify-center group-hover:bg-purple-500/25 transition-colors">
                <FileText className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white group-hover:text-purple-300 transition-colors">View Postmortem</h3>
                <p className="text-xs text-gray-500">Full analysis & prevention steps</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-600 ml-auto group-hover:text-purple-400 group-hover:translate-x-1 transition-all" />
            </Link>

            {incident.ticket && (
              <a href={`${JIRA_BASE_URL}/browse/${incident.ticket.id}`} target="_blank" rel="noreferrer" className="group flex items-center gap-4 p-5 rounded-2xl bg-gray-800/30 border border-gray-700/30 hover:bg-blue-950/20 hover:border-blue-700/40 transition-all">
                <div className="w-12 h-12 rounded-xl bg-blue-500/15 flex items-center justify-center group-hover:bg-blue-500/25 transition-colors">
                  <ExternalLink className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-blue-300 transition-colors">{incident.ticket.id}</h3>
                  <p className="text-xs text-gray-500">Open in Jira</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600 ml-auto group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
              </a>
            )}

            {/* PagerDuty Link */}
            {incident.pagerduty_id && (
              <a href={incident.pagerduty_url || `https://app.pagerduty.com/incidents?search=${incident.id}`} target="_blank" rel="noreferrer" className="group flex items-center gap-4 p-5 rounded-2xl bg-gray-800/30 border border-gray-700/30 hover:bg-green-950/20 hover:border-green-700/40 transition-all">
                <div className="w-12 h-12 rounded-xl bg-green-500/15 flex items-center justify-center group-hover:bg-green-500/25 transition-colors">
                  <Zap className="w-6 h-6 text-green-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-green-300 transition-colors">{incident.pagerduty_id}</h3>
                  <p className="text-xs text-gray-500">Open in PagerDuty</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600 ml-auto group-hover:text-green-400 group-hover:translate-x-1 transition-all" />
              </a>
            )}

            {/* SNS Notification Button */}
            {incident.notifications ? (
              <button 
                onClick={() => {
                  console.log('[SNS Button] Clicked! Opening modal...')
                  console.log('[SNS Button] notifications:', incident.notifications)
                  setShowSnsModal(true)
                }}
                className="group flex items-center gap-4 p-5 rounded-2xl bg-gray-800/30 border border-gray-700/30 hover:bg-amber-950/20 hover:border-amber-700/40 transition-all text-left"
              >
                <div className="w-12 h-12 rounded-xl bg-amber-500/15 flex items-center justify-center group-hover:bg-amber-500/25 transition-colors">
                  <Bell className="w-6 h-6 text-amber-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-amber-300 transition-colors">SNS Notification</h3>
                  <p className="text-xs text-gray-500">View alert details</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600 ml-auto group-hover:text-amber-400 group-hover:translate-x-1 transition-all" />
              </button>
            ) : (
              <div className="p-5 rounded-2xl bg-gray-800/20 border border-gray-700/20 text-gray-500 text-sm">
                No SNS notification data
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          {/* Status Overview */}
          <Card className="sticky top-6">
            <div className="p-6 space-y-6">
              <div>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Status Overview</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Current Status</span>
                    <span className={`px-3 py-1.5 rounded-lg text-xs font-bold ${status.bg} ${status.text}`}>{incident.status}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Workflow</span>
                    <span className="text-sm text-brand-400 font-medium">{incident.workflowStep}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Detected</span>
                    <span className="text-sm text-gray-300">{detectedTime.toLocaleTimeString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Duration</span>
                    <span className="text-sm font-semibold text-orange-400">{timeAgo}</span>
                  </div>
                </div>
              </div>

              <div className="h-px bg-gray-700/50" />

              <div>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Impact Scores</h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-gray-400">Severity</span>
                      <span className={`font-bold ${sev.text}`}>SEV-{incident.severity}</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${incident.severity >= 4 ? 'bg-red-500' : incident.severity === 3 ? 'bg-orange-500' : 'bg-yellow-500'}`} style={{ width: `${(incident.severity / 5) * 100}%` }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-gray-400">Business Impact</span>
                      <span className="font-bold text-white">{incident.businessImpact}/10</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-red-500 to-red-400 rounded-full" style={{ width: `${(incident.businessImpact / 10) * 100}%` }} />
                    </div>
                  </div>
                </div>
              </div>

              {(raw.revenue_at_risk !== undefined || raw.affected_users !== undefined || raw.sla_status !== undefined) ? (
                <>
                  <div className="h-px bg-gray-700/50" />
                  <div>
                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Business Details</h3>
                    <div className="space-y-3">
                      {raw.revenue_at_risk !== undefined ? (
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-400">Revenue at Risk</span>
                          <span className="text-sm font-bold text-red-400">{String(raw.revenue_at_risk)}</span>
                        </div>
                      ) : null}
                      {raw.affected_users !== undefined ? (
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-400">Affected Users</span>
                          <span className="text-sm font-bold text-white">{String(raw.affected_users).toLocaleString()}</span>
                        </div>
                      ) : null}
                      {raw.sla_status !== undefined ? (
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-400">SLA Status</span>
                          <span className={`text-sm font-bold ${raw.sla_status === 'At Risk' ? 'text-red-400' : 'text-green-400'}`}>{String(raw.sla_status)}</span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </Card>
        </div>
      </div>

      {/* SNS Notification Modal - Using Portal to render outside main content */}
      {showSnsModal && incident.notifications ? createPortal(
        (() => {
        console.log('[SNS Modal] Rendering modal via portal');
        return (
        <div 
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" 
          onClick={() => setShowSnsModal(false)}
        >
          <div 
            className="relative w-full max-w-2xl max-h-[80vh] overflow-auto rounded-3xl bg-gray-900 border border-gray-700/50 shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between p-6 bg-gray-900/95 backdrop-blur border-b border-gray-700/50">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
                  <Bell className="w-6 h-6 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">SNS Notification Details</h2>
                  <p className="text-sm text-gray-400">Alert sent for incident {incident.id}</p>
                </div>
              </div>
              <button 
                onClick={() => setShowSnsModal(false)}
                className="p-2 rounded-xl hover:bg-gray-800 transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              {(() => {
                let notifData: Record<string, unknown> = {}
                try {
                  notifData = typeof incident.notifications === 'string' 
                    ? JSON.parse(incident.notifications) 
                    : incident.notifications as Record<string, unknown>
                } catch {
                  notifData = { raw: incident.notifications }
                }

                return (
                  <>
                    {/* Notification Info */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Type</p>
                        <p className="text-sm font-semibold text-amber-400">{String(notifData.type || 'Alert').replace(/_/g, ' ')}</p>
                      </div>
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Channel</p>
                        <p className="text-sm font-semibold text-cyan-400">{String(notifData.channel || 'SNS')}</p>
                      </div>
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Recipient</p>
                        <p className="text-sm font-medium text-white">{String(notifData.recipient || 'N/A')}</p>
                      </div>
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Sent At</p>
                        <p className="text-sm font-medium text-white">
                          {notifData.sent_at ? new Date(String(notifData.sent_at)).toLocaleString() : 'N/A'}
                        </p>
                      </div>
                    </div>

                    {/* Subject */}
                    {notifData.subject ? (
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Subject</p>
                        <p className="text-sm text-white font-medium">{String(notifData.subject)}</p>
                      </div>
                    ) : null}

                    {/* Message Content */}
                    {notifData.message ? (
                      <div className="p-4 rounded-xl bg-gray-800/30 border border-gray-700/30">
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Message Content</p>
                        <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed bg-gray-900/50 p-4 rounded-lg overflow-auto max-h-64">
                          {String(notifData.message)}
                        </pre>
                      </div>
                    ) : null}

                    {/* Ticket Info */}
                    {notifData.ticket_id ? (
                      <div className="flex items-center gap-3 p-4 rounded-xl bg-blue-950/30 border border-blue-800/30">
                        <ExternalLink className="w-5 h-5 text-blue-400" />
                        <div>
                          <p className="text-xs text-gray-500">Linked Ticket</p>
                          <a 
                            href={String(notifData.ticket_url || `${JIRA_BASE_URL}/browse/${notifData.ticket_id}`)} 
                            target="_blank" 
                            rel="noreferrer"
                            className="text-sm font-semibold text-blue-400 hover:text-blue-300"
                          >
                            {String(notifData.ticket_id)}
                          </a>
                        </div>
                      </div>
                    ) : null}

                    {/* Status */}
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-green-950/30 border border-green-800/30">
                      <CheckCircle className="w-5 h-5 text-green-400" />
                      <span className="text-sm text-green-400 font-medium">Notification delivered successfully</span>
                    </div>
                  </>
                )
              })()}
            </div>
          </div>
        </div>
        )
      })(),
      document.body
      ) : null}
    </div>
  )
}


// Reusable Components
function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl bg-gray-900/50 border border-gray-700/50 overflow-hidden ${className}`}>
      {children}
    </div>
  )
}

function CardHeader({ icon: Icon, title, subtitle, badge, expanded, onToggle, color }: {
  icon: typeof Target
  title: string
  subtitle: string
  badge?: string
  expanded: boolean
  onToggle: () => void
  color: 'cyan' | 'blue' | 'purple'
}) {
  const colors = {
    cyan: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
    blue: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    purple: 'bg-purple-500/15 text-purple-400 border-purple-500/30'
  }
  return (
    <button onClick={onToggle} className="w-full p-6 flex items-center justify-between hover:bg-gray-800/30 transition-colors">
      <div className="flex items-center gap-4">
        <div className={`w-11 h-11 rounded-xl ${colors[color]} border flex items-center justify-center`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="text-left">
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="text-xs text-gray-500">{subtitle}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {badge && <span className={`px-3 py-1 rounded-full text-xs font-semibold ${colors[color]}`}>{badge}</span>}
        {expanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
      </div>
    </button>
  )
}

function MetricCard({ icon: Icon, label, value, color }: { icon: typeof Clock; label: string; value: string; color: 'orange' | 'red' | 'blue' | 'green' }) {
  const colors = {
    orange: 'bg-orange-500/10 border-orange-500/20 text-orange-400',
    red: 'bg-red-500/10 border-red-500/20 text-red-400',
    blue: 'bg-blue-500/10 border-blue-500/20 text-blue-400',
    green: 'bg-green-500/10 border-green-500/20 text-green-400'
  }
  return (
    <div className={`flex items-center gap-4 p-4 rounded-2xl ${colors[color]} border`}>
      <div className="w-12 h-12 rounded-xl bg-current/10 flex items-center justify-center">
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wider">{label}</p>
        <p className="text-xl font-bold text-white">{value}</p>
      </div>
    </div>
  )
}

function ConfidenceBadge({ value }: { value: number }) {
  const color = value >= 80 ? 'text-green-400 bg-green-500/15' : value >= 50 ? 'text-yellow-400 bg-yellow-500/15' : 'text-red-400 bg-red-500/15'
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-bold ${color}`}>
      {value}% confidence
    </span>
  )
}

// Investigation Item Card Component
function InvestigationItemCard({ item }: { item: InvestigationItem }) {
  const severityStyles = {
    critical: 'border-l-red-500 bg-red-950/20',
    warning: 'border-l-yellow-500 bg-yellow-950/20',
    info: 'border-l-blue-500 bg-blue-950/20',
    success: 'border-l-green-500 bg-green-950/20'
  }
  
  const severityIcons = {
    critical: AlertCircle,
    warning: AlertTriangle,
    info: Info,
    success: CheckCircle
  }
  
  const style = item.severity ? severityStyles[item.severity] : 'border-l-gray-600 bg-gray-800/30'
  const SeverityIcon = item.severity ? severityIcons[item.severity] : null
  
  return (
    <div className={`rounded-xl border-l-4 ${style} p-4`}>
      <div className="flex items-start gap-3">
        {SeverityIcon && (
          <SeverityIcon className={`w-4 h-4 mt-0.5 shrink-0 ${
            item.severity === 'critical' ? 'text-red-400' :
            item.severity === 'warning' ? 'text-yellow-400' :
            item.severity === 'info' ? 'text-blue-400' : 'text-green-400'
          }`} />
        )}
        <div className="flex-1 min-w-0">
          {item.title && (
            <p className="text-sm font-medium text-white mb-1">{item.title}</p>
          )}
          <p className="text-sm text-gray-400 leading-relaxed">{item.description}</p>
          
          {/* Metadata Tags */}
          {item.metadata && Object.keys(item.metadata).length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {Object.entries(item.metadata).map(([key, value]) => (
                <span 
                  key={key} 
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs bg-gray-700/50 text-gray-400"
                >
                  <span className="text-gray-500">{key}:</span>
                  <span className="font-medium text-gray-300">{value}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Enhanced Investigation Parser
function parseInvestigationEnhanced(investigation: string): InvestigationSection[] {
  // Helper to check if text is a "no data" message
  const isNoDataMessage = (text: string): boolean => {
    const lower = text.toLowerCase().trim()
    return (
      /^no\s+.*\s+found/i.test(lower) ||
      /^no\s+relevant/i.test(lower) ||
      /^no\s+data/i.test(lower) ||
      /^no\s+similar/i.test(lower) ||
      /^no\s+matching/i.test(lower) ||
      /^no\s+results/i.test(lower) ||
      /^no\s+incidents/i.test(lower) ||
      /^no\s+records/i.test(lower) ||
      /^no\s+information/i.test(lower) ||
      /^could\s+not\s+find/i.test(lower) ||
      /^unable\s+to\s+find/i.test(lower) ||
      /^nothing\s+found/i.test(lower) ||
      /no relevant data/i.test(lower) ||
      /no data found/i.test(lower) ||
      /no results found/i.test(lower)
    )
  }

  const cleaned = investigation
    .replace(/\[Source:\s*<REDACTED>\s*\/OpenSearch\]/gi, '[Source: OpenSearch Logs]')
    .replace(/\[Source:\s*<REDACTED>\]/gi, '[Source: Agent Tool]')
    .replace(/<REDACTED>/gi, '')
    .replace(/\s*Remediation Summary[\s\S]*$/i, '')
    .replace(/\s*recommended_actions:[\s\S]*$/i, '')
    .replace(/This concludes the investigation[\s\S]*$/i, '')
    .replace(/I have (?:now )?(?:completed|provided|finished)[\s\S]*$/i, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\n{3,}/g, '\n\n')

  // Enhanced source configuration with Lucide icons
  const SOURCE_CONFIG: Record<string, { 
    key: string
    title: string
    icon: typeof History
    color: string
    bgColor: string
    borderColor: string
  }> = {
    'incident history': { 
      key: 'incidents',
      title: 'Past Incidents', 
      icon: History, 
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/15',
      borderColor: 'border-blue-500/30'
    },
    'opensearch': { 
      key: 'logs',
      title: 'Log Analysis', 
      icon: Search, 
      color: 'text-teal-400',
      bgColor: 'bg-teal-500/15',
      borderColor: 'border-teal-500/30'
    },
    'runbook': { 
      key: 'runbook',
      title: 'Runbook', 
      icon: FileCode, 
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/15',
      borderColor: 'border-purple-500/30'
    },
    'deployment': { 
      key: 'deployments',
      title: 'Deployment History', 
      icon: GitBranch, 
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/15',
      borderColor: 'border-orange-500/30'
    },
    'x-ray': { 
      key: 'xray',
      title: 'X-Ray Traces', 
      icon: Cpu, 
      color: 'text-pink-400',
      bgColor: 'bg-pink-500/15',
      borderColor: 'border-pink-500/30'
    },
    'trace': { 
      key: 'xray',
      title: 'X-Ray Traces', 
      icon: Cpu, 
      color: 'text-pink-400',
      bgColor: 'bg-pink-500/15',
      borderColor: 'border-pink-500/30'
    },
    'config': { 
      key: 'config',
      title: 'AWS Config', 
      icon: Settings, 
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/15',
      borderColor: 'border-amber-500/30'
    },
    'drift': { 
      key: 'config',
      title: 'AWS Config', 
      icon: Settings, 
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/15',
      borderColor: 'border-amber-500/30'
    }
  }

  const sectionMap = new Map<string, InvestigationSection>()
  let currentKey = 'general'

  // Helper to parse item with metadata
  const parseItem = (text: string, sectionKey: string): InvestigationItem => {
    const item: InvestigationItem = {
      type: 'text',
      description: text
    }

    // Parse incident references
    const incidentMatch = text.match(/^(INC-[A-Z0-9]+):\s*(.+?)(?:\s*\((.+)\))?$/i)
    if (incidentMatch) {
      item.type = 'incident'
      item.title = incidentMatch[1]
      item.description = incidentMatch[2]
      if (incidentMatch[3]) {
        const metaParts = incidentMatch[3].split(',').map(p => p.trim())
        item.metadata = {}
        metaParts.forEach(part => {
          const [key, val] = part.split(':').map(s => s.trim())
          if (key && val) item.metadata![key] = val
        })
      }
      item.severity = 'info'
      return item
    }

    // Parse log entries
    const logMatch = text.match(/^(.+?):\s*(.+?)(?:\s*\((\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\)]*)\))?$/i)
    if (logMatch && sectionKey === 'logs') {
      item.type = 'log'
      item.title = logMatch[1]
      item.description = logMatch[2]
      if (logMatch[3]) {
        item.metadata = { timestamp: new Date(logMatch[3]).toLocaleString() }
      }
      // Determine severity based on content
      if (/error|fault|fail|critical/i.test(text)) item.severity = 'critical'
      else if (/warn|threshold|exceeded/i.test(text)) item.severity = 'warning'
      else item.severity = 'info'
      return item
    }

    // Parse runbook entries
    if (sectionKey === 'runbook') {
      item.type = 'runbook'
      if (/^runbook:/i.test(text)) {
        item.title = text.replace(/^runbook:\s*/i, '')
        item.description = 'Recommended troubleshooting guide'
      } else if (/^category:/i.test(text) || /estimated ttr/i.test(text)) {
        const parts = text.split(',').map(p => p.trim())
        item.metadata = {}
        parts.forEach(part => {
          const [key, val] = part.split(':').map(s => s?.trim())
          if (key && val) item.metadata![key] = val
        })
        item.description = 'Runbook metadata'
      }
      item.severity = 'info'
      return item
    }

    // Parse deployment entries
    if (sectionKey === 'deployments') {
      item.type = 'deployment'
      const deployMatch = text.match(/^Deploy\s+(deploy-[a-z0-9]+):\s*v?([^\s]+)\s*\(([^)]+)\)\s*-?\s*(.*)$/i)
      if (deployMatch) {
        item.title = `${deployMatch[1]} - ${deployMatch[2]}`
        item.description = deployMatch[4] || 'Deployment'
        item.metadata = { status: deployMatch[3] }
        item.severity = deployMatch[3] === 'completed' ? 'success' : 'warning'
      } else if (/config:/i.test(text)) {
        item.title = 'Configuration Change'
        item.description = text.replace(/^config:\s*/i, '')
        item.severity = 'warning'
      }
      return item
    }

    // Parse X-Ray traces
    if (sectionKey === 'xray') {
      item.type = 'trace'
      const traceMatch = text.match(/^(1-[a-f0-9-]+):\s*(\d+)ms(?:,\s*HTTP\s*(\d+))?/i)
      if (traceMatch) {
        item.title = traceMatch[1]
        item.description = `Response time: ${traceMatch[2]}ms`
        item.metadata = { duration: `${traceMatch[2]}ms` }
        if (traceMatch[3]) {
          item.metadata.status = `HTTP ${traceMatch[3]}`
          item.severity = parseInt(traceMatch[3]) >= 500 ? 'critical' : 'warning'
        }
      } else if (/insight|fault|latency|error rate/i.test(text)) {
        item.title = 'X-Ray Insight'
        item.description = text.replace(/^x-ray insights?:\s*/i, '')
        item.severity = /fault|error/i.test(text) ? 'critical' : 'warning'
      }
      return item
    }

    // Parse AWS Config entries
    if (sectionKey === 'config') {
      item.type = 'config'
      if (/non-compliant/i.test(text)) {
        item.title = 'Non-Compliant Resource'
        item.description = text
        item.severity = 'warning'
      } else if (/rule:/i.test(text)) {
        item.title = 'Config Rule'
        item.description = text.replace(/^rule:\s*/i, '')
        item.severity = 'info'
      } else if (/config enabled/i.test(text)) {
        item.severity = 'success'
      }
      return item
    }

    // Default severity based on content
    if (/error|fault|fail|critical|exceeded/i.test(text)) item.severity = 'critical'
    else if (/warn|high|increased|anomaly/i.test(text)) item.severity = 'warning'
    else if (/success|completed|resolved/i.test(text)) item.severity = 'success'
    else item.severity = 'info'

    return item
  }

  cleaned.split('\n').forEach(line => {
    const trimmed = line.trim()
    if (!trimmed || trimmed.length < 5) return
    
    // Skip any line that contains "no data" type messages
    if (isNoDataMessage(trimmed)) return

    const sourceMatch = trimmed.match(/\[Source:\s*([^\]]+)\]/i)
    if (sourceMatch) {
      const tag = sourceMatch[1].toLowerCase()
      for (const [key, cfg] of Object.entries(SOURCE_CONFIG)) {
        if (tag.includes(key)) {
          currentKey = cfg.key
          if (!sectionMap.has(cfg.key)) {
            sectionMap.set(cfg.key, { ...cfg, items: [] })
          }
          break
        }
      }
      const rest = trimmed.replace(/\[Source:[^\]]+\]\s*/gi, '').trim()
      if (rest && rest.length > 10 && !isNoDataMessage(rest)) {
        const section = sectionMap.get(currentKey)
        if (section) {
          section.items.push(parseItem(rest, currentKey))
        }
      }
      return
    }

    // Skip noise
    if (/^based on the/i.test(trimmed)) return
    if (/^rollback|^revert|^scale|^apply the fix/i.test(trimmed)) return

    const clean = trimmed.replace(/^[-•]\s*/, '').replace(/^\d+\.\s*/, '').trim()
    if (clean.length > 10 && !isNoDataMessage(clean)) {
      const section = sectionMap.get(currentKey)
      if (section && !section.items.some(i => i.description.toLowerCase() === clean.toLowerCase())) {
        section.items.push(parseItem(clean, currentKey))
      }
    }
  })

  // Generate summaries for each section
  const sections = Array.from(sectionMap.values()).filter(s => s.items.length > 0)
  sections.forEach(section => {
    const criticalCount = section.items.filter(i => i.severity === 'critical').length
    const warningCount = section.items.filter(i => i.severity === 'warning').length
    
    if (criticalCount > 0) {
      section.summary = `${criticalCount} critical finding${criticalCount > 1 ? 's' : ''}`
    } else if (warningCount > 0) {
      section.summary = `${warningCount} warning${warningCount > 1 ? 's' : ''}`
    }
  })

  return sections
}
