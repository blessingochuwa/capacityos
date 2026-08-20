import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Risk, RiskImpact, RiskProbability, RiskStatus } from '../types/risks'

export interface RiskCreateInput {
  description: string
  cause?: string
  potential_effect?: string
  probability?: RiskProbability
  impact?: RiskImpact
  response?: string
  owner_person_id?: string | null
  status?: RiskStatus
  review_date?: string | null
}

export type RiskUpdateInput = Partial<RiskCreateInput>

export const risksApi = {
  listForProject: (projectId: string) =>
    apiGet<Risk[]>(`/api/v1/projects/${projectId}/risks`),
  create: (projectId: string, data: RiskCreateInput) =>
    apiPost<Risk>(`/api/v1/projects/${projectId}/risks`, data),
  update: (projectId: string, riskId: string, data: RiskUpdateInput) =>
    apiPatch<Risk>(`/api/v1/projects/${projectId}/risks/${riskId}`, data),
  remove: (projectId: string, riskId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/risks/${riskId}`),
}
