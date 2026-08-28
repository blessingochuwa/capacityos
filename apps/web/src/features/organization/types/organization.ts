/**
 * Mirrors apps/api/app/schemas/organization.py::OrganizationRead verbatim —
 * see src/types/entities.ts's header comment for why these types are
 * hand-written, not generated (Phase 30).
 *
 * `slug` is a stable identity key that apps/api treats as immutable
 * (OrganizationUpdate excludes it); `is_active` is a soft-delete flag with
 * no reactivation path anywhere in the backend, so this UI reads it but
 * never writes it (deactivation is deferred — see
 * docs/adr/0030-organization-settings-ui.md).
 */
export interface Organization {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
  updated_at: string
}
