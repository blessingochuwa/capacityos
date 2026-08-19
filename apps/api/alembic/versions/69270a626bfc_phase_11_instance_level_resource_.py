"""phase 11 instance level resource authorization

Revision ID: 69270a626bfc
Revises: 332ca8583f5f
Create Date: 2026-08-19 21:11:18.967287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Autogenerate additionally proposed drop_constraint/create_check_constraint
# operations against ck_allocations_allocation_unit, ck_audit_events_outcome,
# ck_people_employment_status, ck_person_skills_proficiency,
# ck_project_skill_requirements_min_proficiency, ck_projects_status,
# ck_scenario_operations_operation_type, ck_scenarios_status, ck_users_role,
# and ck_users_status — the same known SQLite CHECK-constraint text-diff
# false positive already documented in ADR 0002/0004/0005/0006/0007/0010
# (fires identically for untouched enum columns in every prior autogenerate
# run). Removed by hand below; this migration only contains the 2 new
# tables (team_access_grants, project_access_grants) and their
# indexes/constraints (docs/adr/0011-instance-level-resource-authorization.md).


# revision identifiers, used by Alembic.
revision: str = '69270a626bfc'
down_revision: Union[str, Sequence[str], None] = '332ca8583f5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('project_access_grants',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('granted_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], name=op.f('fk_project_access_grants_granted_by_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_access_grants_project_id_projects'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_project_access_grants_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_access_grants')),
    sa.UniqueConstraint('user_id', 'project_id', name='uq_project_access_grant_user_project')
    )
    op.create_index(op.f('ix_project_access_grants_project_id'), 'project_access_grants', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_access_grants_user_id'), 'project_access_grants', ['user_id'], unique=False)
    op.create_table('team_access_grants',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('team_id', sa.Uuid(), nullable=False),
    sa.Column('granted_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], name=op.f('fk_team_access_grants_granted_by_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name=op.f('fk_team_access_grants_team_id_teams'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_team_access_grants_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_team_access_grants')),
    sa.UniqueConstraint('user_id', 'team_id', name='uq_team_access_grant_user_team')
    )
    op.create_index(op.f('ix_team_access_grants_team_id'), 'team_access_grants', ['team_id'], unique=False)
    op.create_index(op.f('ix_team_access_grants_user_id'), 'team_access_grants', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_team_access_grants_user_id'), table_name='team_access_grants')
    op.drop_index(op.f('ix_team_access_grants_team_id'), table_name='team_access_grants')
    op.drop_table('team_access_grants')
    op.drop_index(op.f('ix_project_access_grants_user_id'), table_name='project_access_grants')
    op.drop_index(op.f('ix_project_access_grants_project_id'), table_name='project_access_grants')
    op.drop_table('project_access_grants')
