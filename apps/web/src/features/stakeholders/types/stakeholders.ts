/**
 * Mirrors apps/api/app/schemas/stakeholder.py verbatim. No score/health
 * value is computed anywhere — every field here is exactly what the API
 * stores (CLAUDE.md §16/§17: no false-precision numeric model).
 */

export type StakeholderInfluence = 'low' | 'medium' | 'high'
export type StakeholderInterest = 'low' | 'medium' | 'high'
export type StakeholderDecisionAuthority = 'decision_maker' | 'advisor' | 'informed'

export const STAKEHOLDER_INFLUENCE_LEVELS: StakeholderInfluence[] = ['low', 'medium', 'high']
export const STAKEHOLDER_INTEREST_LEVELS: StakeholderInterest[] = ['low', 'medium', 'high']
export const STAKEHOLDER_DECISION_AUTHORITY_LEVELS: StakeholderDecisionAuthority[] = [
  'decision_maker',
  'advisor',
  'informed',
]

export interface Stakeholder {
  id: string
  project_id: string
  name: string
  person_id: string | null
  role: string
  influence: StakeholderInfluence
  interest: StakeholderInterest
  decision_authority: StakeholderDecisionAuthority
  communication_needs: string | null
  created_at: string
  updated_at: string
}
