import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type {
  Stakeholder,
  StakeholderDecisionAuthority,
  StakeholderInfluence,
  StakeholderInterest,
} from '../types/stakeholders'

export interface StakeholderCreateInput {
  name: string
  person_id?: string | null
  role: string
  influence?: StakeholderInfluence
  interest?: StakeholderInterest
  decision_authority?: StakeholderDecisionAuthority
  communication_needs?: string | null
}

export type StakeholderUpdateInput = Partial<StakeholderCreateInput>

export const stakeholdersApi = {
  listForProject: (projectId: string) =>
    apiGet<Stakeholder[]>(`/api/v1/projects/${projectId}/stakeholders`),
  create: (projectId: string, data: StakeholderCreateInput) =>
    apiPost<Stakeholder>(`/api/v1/projects/${projectId}/stakeholders`, data),
  update: (projectId: string, stakeholderId: string, data: StakeholderUpdateInput) =>
    apiPatch<Stakeholder>(
      `/api/v1/projects/${projectId}/stakeholders/${stakeholderId}`,
      data,
    ),
  remove: (projectId: string, stakeholderId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/stakeholders/${stakeholderId}`),
}
