/**
 * Mirrors apps/api/app/schemas/risk.py verbatim. exposure arrives
 * pre-computed from the API — nothing here recomputes it (CLAUDE.md §4/§17;
 * see docs/adr/0013-phase-13-risk-management.md).
 */

export type RiskProbability = 'low' | 'medium' | 'high'
export type RiskImpact = 'low' | 'medium' | 'high'
export type RiskExposure = 'low' | 'medium' | 'high'
export type RiskStatus = 'open' | 'mitigating' | 'monitoring' | 'closed'

export const RISK_PROBABILITY_LEVELS: RiskProbability[] = ['low', 'medium', 'high']
export const RISK_IMPACT_LEVELS: RiskImpact[] = ['low', 'medium', 'high']
export const RISK_STATUSES: RiskStatus[] = ['open', 'mitigating', 'monitoring', 'closed']

export interface Risk {
  id: string
  project_id: string
  description: string
  cause: string | null
  potential_effect: string | null
  probability: RiskProbability
  impact: RiskImpact
  exposure: RiskExposure
  response: string | null
  owner_person_id: string | null
  status: RiskStatus
  review_date: string | null
  created_at: string
  updated_at: string
}
