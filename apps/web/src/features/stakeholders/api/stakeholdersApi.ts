import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
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

/** Phase 48 — the org-wide Stakeholder register's page size, matching the
 * Risk register's RISK_REGISTER_PAGE_SIZE and the Audit Log's
 * AUDIT_PAGE_SIZE: a register spanning every project can grow without
 * bound, so it pages server-side rather than fetching everything once
 * (see docs/adr/0048-org-wide-stakeholder-register.md). */
export const STAKEHOLDER_REGISTER_PAGE_SIZE = 50

export interface OrgStakeholderFilters {
  project_id?: string
  influence?: StakeholderInfluence
  interest?: StakeholderInterest
  decision_authority?: StakeholderDecisionAuthority
  offset?: number
}

export const stakeholdersApi = {
  listForProject: (projectId: string) =>
    apiGet<Stakeholder[]>(`/api/v1/projects/${projectId}/stakeholders`),

  /** GET /api/v1/stakeholders (Phase 48) — every Stakeholder across every
   * project in the caller's active organization. Organization identity
   * comes from the session, never from anything the client sends. */
  listForOrganization: (filters: OrgStakeholderFilters = {}) =>
    apiGet<Page<Stakeholder>>('/api/v1/stakeholders', {
      project_id: filters.project_id || undefined,
      influence: filters.influence || undefined,
      interest: filters.interest || undefined,
      decision_authority: filters.decision_authority || undefined,
      limit: STAKEHOLDER_REGISTER_PAGE_SIZE,
      offset: filters.offset ?? 0,
    }),
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
