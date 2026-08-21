"""phase 14 stakeholder management

Revision ID: c756ff8bebe5
Revises: 4ad14ba4eb50
Create Date: 2026-08-21 14:20:04.871524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Autogenerate additionally proposed drop_constraint/create_check_constraint
# operations against ck_allocations_allocation_unit, ck_audit_events_outcome,
# ck_organization_memberships_role, ck_organization_memberships_status,
# ck_people_employment_status, ck_person_skills_proficiency,
# ck_project_skill_requirements_min_proficiency, ck_projects_status,
# ck_risks_impact, ck_risks_probability, ck_risks_status,
# ck_scenario_operations_operation_type, ck_scenarios_status, and
# ck_users_status — the same known SQLite CHECK-constraint text-diff false
# positive already documented in ADR 0002/0004/0005/0006/0007/0010/0011/
# 0012/0013 (fires identically for untouched enum columns in every prior
# autogenerate run). Removed by hand below; this migration only contains
# the one new `stakeholders` table and its indexes/constraints (docs/adr/
# 0014-phase-14-stakeholder-management.md).


# revision identifiers, used by Alembic.
revision: str = 'c756ff8bebe5'
down_revision: Union[str, Sequence[str], None] = '4ad14ba4eb50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('stakeholders',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('person_id', sa.Uuid(), nullable=True),
    sa.Column('role', sa.String(length=200), nullable=False),
    sa.Column('influence', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='ck_stakeholders_influence', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('interest', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='ck_stakeholders_interest', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('decision_authority', sa.Enum('DECISION_MAKER', 'ADVISOR', 'INFORMED', name='ck_stakeholders_decision_authority', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('communication_needs', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_stakeholders_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['person_id'], ['people.id'], name=op.f('fk_stakeholders_person_id_people'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_stakeholders_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stakeholders')),
    sa.UniqueConstraint('project_id', 'person_id', name='uq_stakeholder_project_person')
    )
    op.create_index(op.f('ix_stakeholders_organization_id'), 'stakeholders', ['organization_id'], unique=False)
    op.create_index(op.f('ix_stakeholders_person_id'), 'stakeholders', ['person_id'], unique=False)
    op.create_index(op.f('ix_stakeholders_project_id'), 'stakeholders', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_stakeholders_project_id'), table_name='stakeholders')
    op.drop_index(op.f('ix_stakeholders_person_id'), table_name='stakeholders')
    op.drop_index(op.f('ix_stakeholders_organization_id'), table_name='stakeholders')
    op.drop_table('stakeholders')
