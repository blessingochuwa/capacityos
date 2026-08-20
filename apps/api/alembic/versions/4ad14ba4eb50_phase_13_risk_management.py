"""phase 13 risk management

Revision ID: 4ad14ba4eb50
Revises: 6fca5b5c9b4f
Create Date: 2026-08-20 23:19:19.074543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Autogenerate additionally proposed drop_constraint/create_check_constraint
# operations against ck_allocations_allocation_unit, ck_audit_events_outcome,
# ck_organization_memberships_role, ck_organization_memberships_status,
# ck_people_employment_status, ck_person_skills_proficiency,
# ck_project_skill_requirements_min_proficiency, ck_projects_status,
# ck_scenario_operations_operation_type, ck_scenarios_status, and
# ck_users_status — the same known SQLite CHECK-constraint text-diff false
# positive already documented in ADR 0002/0004/0005/0006/0007/0010/0011/0012
# (fires identically for untouched enum columns in every prior autogenerate
# run). Removed by hand below; this migration only contains the one new
# `risks` table and its indexes (docs/adr/0013-phase-13-risk-management.md).


# revision identifiers, used by Alembic.
revision: str = '4ad14ba4eb50'
down_revision: Union[str, Sequence[str], None] = '6fca5b5c9b4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('risks',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('cause', sa.Text(), nullable=True),
    sa.Column('potential_effect', sa.Text(), nullable=True),
    sa.Column('probability', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='ck_risks_probability', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('impact', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='ck_risks_impact', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('owner_person_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'MITIGATING', 'MONITORING', 'CLOSED', name='ck_risks_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('review_date', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_risks_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['owner_person_id'], ['people.id'], name=op.f('fk_risks_owner_person_id_people'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_risks_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_risks'))
    )
    op.create_index(op.f('ix_risks_organization_id'), 'risks', ['organization_id'], unique=False)
    op.create_index(op.f('ix_risks_owner_person_id'), 'risks', ['owner_person_id'], unique=False)
    op.create_index(op.f('ix_risks_project_id'), 'risks', ['project_id'], unique=False)
    op.create_index(op.f('ix_risks_status'), 'risks', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_risks_status'), table_name='risks')
    op.drop_index(op.f('ix_risks_project_id'), table_name='risks')
    op.drop_index(op.f('ix_risks_owner_person_id'), table_name='risks')
    op.drop_index(op.f('ix_risks_organization_id'), table_name='risks')
    op.drop_table('risks')
