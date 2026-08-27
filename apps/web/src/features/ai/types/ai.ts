/**
 * Mirrors apps/api/app/schemas/ai.py verbatim. AI never computes a capacity,
 * signal, or scenario number itself — everything here is either the fixed
 * request shape sent to the deterministic-facts-only /api/v1/ai/* endpoints,
 * or the structured, provenance-checked response they return. See
 * docs/adr/0008-phase-8-ai-insight-layer.md.
 */

export type AISourceReferenceType =
  | 'signal'
  | 'capacity'
  | 'scenario'
  | 'skill_coverage'
  | 'priority_score'
  | 'snapshot_comparison'

export interface AISourceReference {
  type: AISourceReferenceType
  entity_id: string
  description: string
}

/** Never a numeric probability — an LLM logit isn't a calibrated
 * reliability metric. A category the model chooses to convey how directly
 * its context supports a claim, not a statistic. */
export type AIConfidence = 'high' | 'medium' | 'low'

export interface AIClaim {
  text: string
  source_references: AISourceReference[]
}

export interface AIRecommendation {
  /** Always phrased as a suggestion to consider, never an instruction to
   * act — render verbatim, never as an imperative or a to-do item. */
  recommendation: string
  rationale: string
  source_references: AISourceReference[]
  assumptions: string[]
}

export interface AIInsightResponse {
  summary: string
  key_findings: AIClaim[]
  risks: AIClaim[]
  recommendations: AIRecommendation[]
  confidence: AIConfidence
  generated_at: string
  provider: string
  model: string
}

export type AIResponseStatus = 'ok' | 'unavailable' | 'error'

export interface AIResponseEnvelope {
  status: AIResponseStatus
  response: AIInsightResponse | null
  message: string | null
}

export type AIScopeEntityType = 'person' | 'team' | 'project'

export interface AIScope {
  entity_type: AIScopeEntityType
  entity_id: string
}

export interface AISummaryRequest {
  scope: AIScope
  start_date: string
  end_date: string
}

export interface AIExplainSignalRequest {
  scope: AIScope
  signal_type: string
  start_date: string
  end_date: string
}

export interface AIExplainScenarioRequest {
  scenario_id: string
}

export interface AIExplainPriorityRequest {
  project_id: string
  score_id: string
}

export interface AIExplainSnapshotComparisonRequest {
  from_snapshot_id: string
  to_snapshot_id: string
}

export interface AIAskRequest {
  scope: AIScope
  start_date: string
  end_date: string
  question: string
}

export interface AIStatusRead {
  available: boolean
  provider: string
  model: string | null
}
