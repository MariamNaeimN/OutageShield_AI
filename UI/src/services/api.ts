/**
 * OutageShield AI — API Service
 * Fetches data from the Dashboard API Gateway backend.
 * All data comes from the real pipeline (DynamoDB, OpenSearch, Step Functions).
 */

const API_BASE = import.meta.env.VITE_API_URL || '/dev'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

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
  confidence?: number
  recommendations: Recommendation[]
  ticket?: { id: string; system: string; status: string }
  workflowStep: string
  workflowId?: string
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
  return data.incidents.map(mapIncident)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapIncident(raw: any): Incident {
  // Clean root_cause: if it's a JSON array string, extract the first description
  let rootCause = raw.root_cause || raw.rootCause || ''
  if (typeof rootCause === 'string' && rootCause.trim().startsWith('[')) {
    try {
      const parsed = JSON.parse(rootCause)
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].description) {
        rootCause = parsed[0].description
      }
    } catch { /* keep as-is */ }
  }

  return {
    id: raw.incident_id || raw.id || '',
    service: raw.service || '',
    title: raw.title || '',
    severity: Number(raw.severity_score || raw.severity || 3) as 1|2|3|4|5,
    businessImpact: Number(raw.business_impact_score || raw.businessImpact || 5),
    status: raw.status || 'Detected',
    detectedAt: raw.created_at || raw.detectedAt || new Date().toISOString(),
    rootCause,
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
    agent_investigation: raw.agent_investigation
  } as Incident & { notifications?: string; ticket_content?: string; revenue_at_risk?: string; affected_users?: string; sla_status?: string; ticket_url?: string; agent_investigation?: string }
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
  return parsed.filter(item => item.category && ['rollback', 'scaling', 'configuration_change', 'manual_intervention'].includes(item.category))
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
      title: (raw.title || nested.summary || raw.summary || '') as string,
      service: (raw.service || nested.summary || '') as string,
      severity: Number(raw.severity || 4),
      resolvedAt: (raw.created_at || '') as string,
      duration: (nested.duration || raw.duration || 'Unknown') as string,
      rootCause: (nested.root_cause || raw.root_cause || '') as string,
      prevention: parsePrevention(nested.prevention || raw.prevention),
      impactSummary: (nested.impact || raw.impact_summary || '') as string,
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
