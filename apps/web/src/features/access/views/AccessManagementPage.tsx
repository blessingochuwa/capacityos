import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { ProjectAccessSection } from '../components/ProjectAccessSection'
import { TeamAccessSection } from '../components/TeamAccessSection'

/**
 * "Which Managers can manage this specific Team/Project?" (Phase 11) —
 * grant/revoke UI for the instance-level scope layered on top of Phase
 * 10's role-based permissions. Owner/Admin always have unrestricted
 * authority (role-based, not grant-based) and are the only roles that can
 * reach this page at all — the backend independently enforces the same
 * boundary (Permission.ACCESS_MANAGE) regardless of what renders here. See
 * docs/adr/0011-instance-level-resource-authorization.md.
 */
export function AccessManagementPage() {
  const { can } = useAuth()

  if (!can('access.manage')) {
    return (
      <div className="space-y-6">
        <PageHeader title="Access management" />
        <ViewOnlyNotice message="Your role doesn't include permission to manage instance-level access." />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Access management"
        description="Grant or revoke a Manager's authority to create, edit, or delete a specific team or project. Reads stay available to every role regardless — this only controls write/delete authority on the selected resource."
      />

      <Card>
        <CardHeader
          title="Team access"
          description="Who can update this team, delete it, or add/remove its members."
        />
        <CardBody>
          <TeamAccessSection />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Project access"
          description="Who can update this project, delete it, manage its skill requirements, or create/edit/delete allocations under it."
        />
        <CardBody>
          <ProjectAccessSection />
        </CardBody>
      </Card>
    </div>
  )
}
