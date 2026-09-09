import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type { Risk, RiskExposure, RiskImpact, RiskProbability, RiskStatus } from '../types/risks'

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

/** Phase 47 — the org-wide Risk register's page size. The existing
 * `GET /api/v1/risks` route allows any value 1-500
 * (`Query(default=100, ge=1, le=500)`); 50 mirrors the Audit Log's own
 * `AUDIT_PAGE_SIZE` precedent — a risk register can grow without bound
 * the way an audit trail does, so this reuses real server-side
 * pagination rather than the repo's "fetch up to 500 once" convention
 * (see docs/adr/0047-org-wide-risk-register.md). */
export const RISK_REGISTER_PAGE_SIZE = 50

export interface OrgRiskFilters {
  project_id?: string
  status?: RiskStatus
  exposure?: RiskExposure
  offset?: number
}

export const risksApi = {
  listForProject: (projectId: string) =>
    apiGet<Risk[]>(`/api/v1/projects/${projectId}/risks`),

  /** GET /api/v1/risks (Phase 47) — every Risk across every project in
   * the caller's active organization, never scoped by anything the
   * client supplies: organization identity comes from the session
   * exactly like every other organization-scoped route. */
  listForOrganization: (filters: OrgRiskFilters = {}) =>
    apiGet<Page<Risk>>('/api/v1/risks', {
      project_id: filters.project_id || undefined,
      status: filters.status || undefined,
      exposure: filters.exposure || undefined,
      limit: RISK_REGISTER_PAGE_SIZE,
      offset: filters.offset ?? 0,
    }),
  create: (projectId: string, data: RiskCreateInput) =>
    apiPost<Risk>(`/api/v1/projects/${projectId}/risks`, data),
  update: (projectId: string, riskId: string, data: RiskUpdateInput) =>
    apiPatch<Risk>(`/api/v1/projects/${projectId}/risks/${riskId}`, data),
  remove: (projectId: string, riskId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/risks/${riskId}`),
}
