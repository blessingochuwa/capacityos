import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { useMemberships } from '@/features/members/hooks/useMemberships'
import { AUDIT_PAGE_SIZE } from '../api/auditApi'
import { AuditEventsTable } from '../components/AuditEventsTable'
import { AuditFilterBar } from '../components/AuditFilterBar'
import { useAuditEvents } from '../hooks/useAuditEvents'

/** Converts a `datetime-local` input value ("2026-01-15T09:30", local
 * time — the browser's own interpretation, no timezone reinterpretation
 * of any kind performed here) to the ISO instant apps/api's `start`/`end`
 * query parameters expect. Empty string (no filter set) stays undefined. */
function toIsoInstant(datetimeLocalValue: string): string | undefined {
  if (!datetimeLocalValue) return undefined
  return new Date(datetimeLocalValue).toISOString()
}

/**
 * "What happened, when, and who did it?" — a read-only history view over
 * the existing Phase 10 AuditEvent trail (apps/api/app/api/v1/audit.py),
 * the first UI this application has ever had for it (Phase 41's audit
 * found it fully backend-ready with zero frontend consumer). Reuses the
 * existing `GET /api/v1/audit` contract exactly: already
 * `Permission.AUDIT_READ`-gated (Admin/Owner), already scoped to the
 * caller's active organization server-side, already offset/limit-
 * paginated with a real `total`. This page adds no new backend
 * capability — see docs/adr/0043-audit-log-ui.md.
 *
 * Gated by `can('audit.read')` for UX only, mirroring
 * features/users/views/UsersPage.tsx exactly — the backend re-checks the
 * same permission on every request and is the real boundary
 * (CLAUDE.md §21).
 */
export function AuditLogPage() {
  const { can } = useAuth()

  if (!can('audit.read')) {
    return (
      <div className="space-y-6">
        <PageHeader title="Audit log" />
        <ViewOnlyNotice message="Your role doesn't include permission to view the audit log." />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit log"
        description="A history of security-relevant and mutating activity in this organization — logins, permission denials, and record changes."
      />

      <Card>
        <CardHeader
          title="Events"
          description="Most recent first. Filter by actor, action, resource type, or a date range."
        />
        <CardBody className="space-y-4">
          <AuditLogManager />
        </CardBody>
      </Card>
    </div>
  )
}

function AuditLogManager() {
  const { user } = useAuth()
  const organizationId = user?.active_organization?.id

  const [actorFilter, setActorFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [resourceTypeFilter, setResourceTypeFilter] = useState('')
  const [startInput, setStartInput] = useState('')
  const [endInput, setEndInput] = useState('')
  const [offset, setOffset] = useState(0)

  /** The active organization's full roster (active + revoked — Phase 28's
   * membersApi.list already returns both), reused as-is for the actor
   * picker's option list rather than deriving one from only the
   * currently-loaded page of audit events, which would silently omit
   * anyone whose most recent action falls outside the current page. */
  const membershipsQuery = useMemberships(organizationId)
  const actorOptions = useMemo(
    () =>
      (membershipsQuery.data?.items ?? [])
        .map((membership) => ({
          value: membership.user_id,
          label: `${membership.display_name} (${membership.email})`,
        }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [membershipsQuery.data],
  )

  const filters = {
    actor_user_id: actorFilter || undefined,
    action: actionFilter.trim() || undefined,
    resource_type: resourceTypeFilter.trim() || undefined,
    start: toIsoInstant(startInput),
    end: toIsoInstant(endInput),
    offset,
  }
  const eventsQuery = useAuditEvents(filters)

  function resetToFirstPage() {
    setOffset(0)
  }

  const isFiltered = Boolean(
    actorFilter || actionFilter || resourceTypeFilter || startInput || endInput,
  )
  const total = eventsQuery.data?.total ?? 0
  const hasPrevious = offset > 0
  const hasNext = offset + AUDIT_PAGE_SIZE < total

  return (
    <div className="space-y-4">
      <AuditFilterBar
        actorOptions={actorOptions}
        actorValue={actorFilter}
        onActorChange={(value) => {
          setActorFilter(value)
          resetToFirstPage()
        }}
        actionValue={actionFilter}
        onActionChange={(value) => {
          setActionFilter(value)
          resetToFirstPage()
        }}
        resourceTypeValue={resourceTypeFilter}
        onResourceTypeChange={(value) => {
          setResourceTypeFilter(value)
          resetToFirstPage()
        }}
        startValue={startInput}
        onStartChange={(value) => {
          setStartInput(value)
          resetToFirstPage()
        }}
        endValue={endInput}
        onEndChange={(value) => {
          setEndInput(value)
          resetToFirstPage()
        }}
      />

      <QueryBoundary query={eventsQuery} loadingLabel="Loading audit events…">
        {(page) => (
          <div className="space-y-3">
            <AuditEventsTable events={page.items} isFiltered={isFiltered} />
            {page.total > 0 ? (
              <div className="flex items-center justify-between gap-4 text-xs text-slate-400">
                <span>
                  Showing {offset + 1}–{Math.min(offset + AUDIT_PAGE_SIZE, page.total)} of{' '}
                  {page.total} event{page.total === 1 ? '' : 's'}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => setOffset((prev) => Math.max(prev - AUDIT_PAGE_SIZE, 0))}
                    disabled={!hasPrevious}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setOffset((prev) => prev + AUDIT_PAGE_SIZE)}
                    disabled={!hasNext}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
