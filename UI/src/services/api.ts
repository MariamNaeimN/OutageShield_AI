/**
 * OutageShield AI — API Service
 * Fetches data from the Dashboard API Gateway backend.
 * All data comes from the real pipeline (DynamoDB, OpenSearch, Step Functions).
 */

const API_BASE = import.meta.env.VITE_API_URL || '/dev'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface RootCauseEntry {
  description: string
  confidence: number
  evidence?: string[]
}

export interface Incident {
  id: string
  service: string
  title: string
  severity: 1 | 2 | 3 | 4 | 5
  businessImpact: number
  status: 'Detected' | 'Investigating' | 'Mitigating' | 'Resolved' | 'Awaiting Approval'
  detectedAt: string
  resolvedAt?: string
  rootCause?: string
  rootCauses?: RootCauseEntry[]
  confidence?: number
  recommendations: Recommendation[]
  ticket?: { id: string; system: string; status: string }
  workflowStep: string
  workflowId?: string
  // Raw fields from DynamoDB for detail page
  notifications?: string
  ticket_content?: string
  revenue_at_risk?: string
  affected_users?: string | number
  sla_status?: string
  ticket_url?: string
  agent_investigation?: string
  remediation_summary?: string
  // PagerDuty integration
  pagerduty_id?: string
  pagerduty_url?: string
}

export interface Recommendation {
  category: 'rollback' | 'scaling' | 'configuration_change' | 'manual_intervention'
  description: string
  effectiveness: number
  risk: 'low' | 'medium' | 'high'
  estimatedTTR: number
  reasoning?: string
  source?: string
  confidence?: number
  evidence?: string
}

export interface ServiceRisk {
  service: string
  risk: 'Low' | 'Medium' | 'High' | 'Critical'
  risk_score?: number
  revenue_at_risk?: number
  activeSignals: number
  max_severity?: number
  lastIncident: string
  lastCalculated?: string
}

export interface TimelineEvent {
  timestamp: string
  type: 'alert' | 'deployment' | 'config_change' | 'workflow' | 'notification' | 'remediation'
  description: string
}

export interface Postmortem {
  id: string
  incidentId: string
  title: string
  service: string
  severity: number
  resolvedAt: string
  duration: string
  rootCause: string
  prevention: string[]
  impactSummary: string
  summary?: string
  evidence: string[]
  scoringReasoning?: string
}

export interface ApprovalResponse {
  approvalId: string
  decision: 'approved' | 'rejected'
}

// ─────────────────────────────────────────────────────────────────────────────
// API Calls
// ─────────────────────────────────────────────────────────────────────────────

async function fetchJson<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`
  console.log(`[API] Fetching: ${url}`)
  const response = await fetch(url, {
    method: 'GET',
    mode: 'cors',
    headers: {
      'Accept': 'application/json'
    }
  })

  if (!response.ok) {
    console.error(`[API] Error: ${response.status} ${response.statusText}`)
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }

  const data = await response.json()
  console.log(`[API] Success: ${path}`, data?.count || data?.length || 'ok')
  return data
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

// ─────────────────────────────────────────────────────────────────────────────
// Incidents
// ─────────────────────────────────────────────────────────────────────────────

export async function getActiveIncidents(): Promise<Incident[]> {
  const data = await fetchJson<{ incidents: Record<string, unknown>[]; count: number }>('/incidents')
  return data.incidents
    .map(raw => {
      try {
        return mapIncident(raw)
      } catch (e) {
        console.error('[mapIncident] failed for', raw?.incident_id, e)
        return null
      }
    })
    .filter((i): i is Incident => i !== null)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapIncident(raw: any): Incident {
  // Parse root_cause: may be a JSON array of {description, confidence, evidence}
  // or a plain object/array already parsed by the JSON response
  const rawRootCause = raw.root_causes_raw ?? raw.root_cause ?? raw.rootCause ?? raw.root_causes ?? ''
  let rootCause = ''
  let rootCauses: RootCauseEntry[] | undefined

  const tryParseRootCauses = (value: unknown): RootCauseEntry[] | null => {
    let arr: any[] | null = null
    if (Array.isArray(value)) {
      arr = value
    } else if (typeof value === 'string') {
      let trimmed = value.trim()
      // Handle double-encoded JSON (string inside a string)
      if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
        try { trimmed = JSON.parse(trimmed) } catch { /* not double-encoded */ }
      }
      if (typeof trimmed === 'string' && trimmed.startsWith('[')) {
        try { arr = JSON.parse(trimmed) } catch { /* not valid JSON */ }
      }
    }
    if (!arr || arr.length === 0) return null

    // Check if the first item's description is itself a JSON array (double-encoded RCA)
    const firstDesc = arr[0]?.description
    if (typeof firstDesc === 'string' && firstDesc.trim().startsWith('[')) {
      try {
        const inner = JSON.parse(firstDesc.trim())
        if (Array.isArray(inner) && inner.length > 0 && inner[0]?.description) {
          arr = inner // use the inner array instead
        }
      } catch { /* keep outer array */ }
    }

    // Must look like RCA entries (have description field)
    if (!arr[0]?.description) return null

    // Filter out parse-error entries
    const filtered = arr
      .filter((item: any) => {
        const desc = String(item.description || '')
        return !desc.trim().startsWith('[') && !desc.trim().startsWith('{') && !desc.includes('Parse error:')
      })
      .map((item: any) => ({
        description: String(item.description || ''),
        confidence: Number(item.confidence ?? 0),
        evidence: Array.isArray(item.evidence)
          ? item.evidence.map(String)
          : item.evidence && !String(item.evidence).includes('Parse error:')
            ? [String(item.evidence)]
            : []
      }))
      .filter(item => item.description.length > 0)
    return filtered.length > 0 ? filtered : null
  }

  const parsed = tryParseRootCauses(rawRootCause)
  if (parsed && parsed.length > 0) {
    rootCauses = parsed
    rootCause = parsed[0].description
  } else {
    rootCause = typeof rawRootCause === 'string' ? rawRootCause : ''
  }

  // Debug: log raw root cause field so we can see what's coming from the API
  // console.log('[mapIncident] root_cause raw:', JSON.stringify(rawRootCause).slice(0, 200), '| parsed:', !!parsed)

  const result: Incident = {
    id: raw.incident_id || raw.id || '',
    service: raw.service || '',
    title: raw.title || '',
    severity: Number(raw.severity_score || raw.severity || 3) as 1|2|3|4|5,
    businessImpact: Number(raw.business_impact_score || raw.businessImpact || 5),
    status: raw.status || 'Detected',
    detectedAt: raw.created_at || raw.detectedAt || new Date().toISOString(),
    rootCause,
    rootCauses,
    confidence: raw.confidence ? Number(raw.confidence) : undefined,
    recommendations: parseRecommendations(raw.recommendations_raw || raw.recommendations),
    ticket: raw.ticket_id ? { id: raw.ticket_id, system: raw.ticket_system || 'Jira', status: raw.ticket_status || 'Open' } : undefined,
    workflowStep: raw.workflow_step || raw.workflowStep || 'unknown',
    // Preserve raw fields for detail page
    notifications: raw.notifications,
    ticket_content: raw.ticket_content,
    revenue_at_risk: raw.revenue_at_risk,
    affected_users: raw.affected_users,
    sla_status: raw.sla_status,
    ticket_url: raw.ticket_url,
    agent_investigation: raw.agent_investigation,
    remediation_summary: raw.remediation_summary,
    // PagerDuty integration
    pagerduty_id: raw.pagerduty_id,
    pagerduty_url: raw.pagerduty_url
  }
  
  // Debug: log notifications field
  if (result.notifications) {
    console.log(`[mapIncident] ${result.id} has notifications:`, typeof result.notifications, String(result.notifications).slice(0, 50))
  }
  
  return result
}

function parseRecommendations(raw: unknown): Recommendation[] {
  if (!raw) return []
  let parsed: any[] = []
  if (typeof raw === 'string') {
    try { parsed = JSON.parse(raw) } catch { return [] }
  } else if (Array.isArray(raw)) {
    parsed = raw
  } else {
    return []
  }
  // Filter out RCA entries (they have description+confidence+evidence but no category)
  // Only return actual recommendations that have a category field
  const validCategories = ['rollback', 'scaling', 'configuration_change', 'manual_intervention', 'manual', 'config']
  return parsed.filter(item => item.category && validCategories.includes(item.category))
}

export async function getIncidentById(id: string): Promise<Incident> {
  return fetchJson<Incident>(`/incidents/${id}`)
}

export async function getIncidentTimeline(id: string): Promise<TimelineEvent[]> {
  const data = await fetchJson<{ events: TimelineEvent[] }>(`/incidents/${id}/timeline`)
  return data.events
}

// ─────────────────────────────────────────────────────────────────────────────
// Service Risk
// ─────────────────────────────────────────────────────────────────────────────

export async function getServiceRisks(): Promise<ServiceRisk[]> {
  const data = await fetchJson<{ services: ServiceRisk[] }>('/risk')
  return data.services
}

// ─────────────────────────────────────────────────────────────────────────────
// Postmortems
// ─────────────────────────────────────────────────────────────────────────────

export async function getPostmortems(): Promise<Postmortem[]> {
  const data = await fetchJson<{ postmortems: Record<string, unknown>[]; count?: number }>('/postmortems')
  if (!data.postmortems || !Array.isArray(data.postmortems)) return []
  return data.postmortems.map((raw: Record<string, unknown>) => {
    // Postmortem content might be nested in a 'postmortem' field
    const nested = (typeof raw.postmortem === 'object' && raw.postmortem !== null)
      ? raw.postmortem as Record<string, unknown>
      : {}

    return {
      id: (raw.postmortem_id || raw.id || '') as string,
      incidentId: (raw.incident_id || '') as string,
      // Use incident_id as title fallback if title has placeholder "service"
      title: (() => {
        const t = String(raw.title || nested.summary || raw.summary || '')
        if (t.toLowerCase().includes('postmortem: service incident') || t === '') {
          return `Postmortem: ${raw.incident_id || 'Incident'}`
        }
        return t
      })(),
      // Use actual service name, fallback to extracting from incident_id
      service: (() => {
        const svc = String(raw.service || nested.summary || '')
        return (svc === 'service' || svc === '' || svc === 'unknown') ? 'api' : svc
      })(),
      severity: Number(raw.severity || 4),
      resolvedAt: (raw.created_at || '') as string,
      duration: (nested.duration || raw.duration || 'Unknown') as string,
      rootCause: (nested.root_cause || raw.root_cause || '') as string,
      prevention: parsePrevention(nested.prevention || raw.prevention),
      impactSummary: (() => {
        const imp = nested.impact || raw.impact_summary
        if (!imp) return (raw.summary || nested.summary || '') as string
        if (typeof imp === 'string') {
          // If it's a placeholder like "Affected users: 0, Revenue at risk: Unknown", use summary instead
          if (imp.includes('Revenue at risk: Unknown') && imp.includes('Affected users: 0')) {
            return String(raw.summary || nested.summary || imp)
          }
          return imp
        }
        if (typeof imp === 'object' && imp !== null) {
          const obj = imp as Record<string, unknown>
          const parts = []
          // revenue_at_risk may be a string like "$2,850/hour (5%...)" — use as-is
          const rev = obj.revenue_at_risk
          const users = obj.affected_users
          if (users && Number(users) > 0) parts.push(`${Number(users).toLocaleString()} users affected`)
          if (rev && rev !== 'Unknown' && rev !== '0') {
            // If it's already a formatted string, use it directly
            parts.push(typeof rev === 'string' ? rev : `$${Number(rev).toLocaleString()}/hour revenue at risk`)
          }
          return parts.length > 0 ? parts.join(' · ') : String(raw.summary || nested.summary || '')
        }
        return String(imp)
      })(),
      summary: (raw.summary || nested.summary || '') as string,
      evidence: [],
      scoringReasoning: (raw.scoring_reasoning || nested.scoring_reasoning || '') as string
    }
  })
}

function parsePrevention(raw: unknown): string[] {
  if (!raw) return []
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return [raw] }
  }
  if (Array.isArray(raw)) return raw
  return []
}

export async function getPostmortemByIncident(incidentId: string): Promise<Postmortem | null> {
  try {
    return await fetchJson<Postmortem>(`/postmortems/${incidentId}`)
  } catch {
    return null
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Approval (Human-in-the-Loop)
// ─────────────────────────────────────────────────────────────────────────────

export async function approveRemediation(approvalId: string, responder: string): Promise<ApprovalResponse> {
  return postJson<ApprovalResponse>(`/approve/${approvalId}`, {
    decision: 'approved',
    responder
  })
}

export async function rejectRemediation(approvalId: string, responder: string): Promise<ApprovalResponse> {
  return postJson<ApprovalResponse>(`/approve/${approvalId}`, {
    decision: 'rejected',
    responder
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Stats
// ─────────────────────────────────────────────────────────────────────────────

export async function getDashboardStats(): Promise<{
  activeCount: number
  criticalCount: number
  awaitingApproval: number
  resolvedToday: number
}> {
  return fetchJson('/stats')
}
