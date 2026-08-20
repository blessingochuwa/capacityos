import { apiPost } from '@/api/client'
import type { OrganizationSummary } from '../types/auth'

export interface OrganizationCreateInput {
  name: string
  slug: string
}

/** Mirrors apps/api/app/schemas/organization.py::OrganizationRead — only
 * the fields SelectOrganizationPage needs after creating an organization
 * (it immediately switches into it, which needs only the id). */
export interface OrganizationRead extends OrganizationSummary {
  is_active: boolean
  created_at: string
  updated_at: string
}

export const organizationsApi = {
  /** Any authenticated user may call this — the caller becomes the new
   * organization's Owner. See docs/adr/0012-organizations-multi-tenancy.md. */
  create: (data: OrganizationCreateInput) =>
    apiPost<OrganizationRead>('/api/v1/organizations', data),
}
