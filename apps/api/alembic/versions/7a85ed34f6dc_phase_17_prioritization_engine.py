"""phase 17 prioritization engine

Revision ID: 7a85ed34f6dc
Revises: c756ff8bebe5
Create Date: 2026-08-24 17:16:42.696722

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
# ck_scenario_operations_operation_type, ck_scenarios_status,
# ck_stakeholders_decision_authority, ck_stakeholders_influence,
# ck_stakeholders_interest, and ck_users_status — the same known SQLite
# CHECK-constraint text-diff false positive already documented in ADR
# 0002/0004/0005/0006/0007/0010/0011/0012/0013/0014 (fires identically for
# untouched enum columns in every prior autogenerate run). Removed by hand
# below; this migration only contains the four new prioritization tables
# and their indexes/constraints (docs/PRD-phase-17-prioritization.md,
# docs/adr/0017-prioritization-engine.md). None of the four new tables'
# own enum-shaped columns (framework_type) has create_constraint=True — see
# PrioritizationFrameworkType's docstring — so this migration introduces no
# new CHECK constraint at all, only the false-positive noise against
# EXISTING ones.


# revision identifiers, used by Alembic.
revision: str = '7a85ed34f6dc'
down_revision: Union[str, Sequence[str], None] = 'c756ff8bebe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('prioritization_frameworks',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('framework_type', sa.Enum('RICE', 'WEIGHTED', name='ck_prioritization_frameworks_framework_type', native_enum=False, length=32), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_prioritization_frameworks_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prioritization_frameworks')),
    sa.UniqueConstraint('organization_id', 'name', name='uq_prioritization_framework_organization_name')
    )
    op.create_index(op.f('ix_prioritization_frameworks_organization_id'), 'prioritization_frameworks', ['organization_id'], unique=False)
    op.create_table('prioritization_criteria',
    sa.Column('framework_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('weight', sa.Numeric(precision=6, scale=3), nullable=True),
    sa.Column('is_editable', sa.Boolean(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['framework_id'], ['prioritization_frameworks.id'], name=op.f('fk_prioritization_criteria_framework_id_prioritization_frameworks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_prioritization_criteria_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prioritization_criteria')),
    sa.UniqueConstraint('framework_id', 'key', name='uq_prioritization_criterion_framework_key')
    )
    op.create_index(op.f('ix_prioritization_criteria_framework_id'), 'prioritization_criteria', ['framework_id'], unique=False)
    op.create_index(op.f('ix_prioritization_criteria_organization_id'), 'prioritization_criteria', ['organization_id'], unique=False)
    op.create_table('project_priority_scores',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('framework_id', sa.Uuid(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['framework_id'], ['prioritization_frameworks.id'], name=op.f('fk_project_priority_scores_framework_id_prioritization_frameworks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_project_priority_scores_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_priority_scores_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_priority_scores')),
    sa.UniqueConstraint('project_id', 'framework_id', name='uq_project_priority_score_project_framework')
    )
    op.create_index(op.f('ix_project_priority_scores_framework_id'), 'project_priority_scores', ['framework_id'], unique=False)
    op.create_index(op.f('ix_project_priority_scores_organization_id'), 'project_priority_scores', ['organization_id'], unique=False)
    op.create_index(op.f('ix_project_priority_scores_project_id'), 'project_priority_scores', ['project_id'], unique=False)
    op.create_table('project_priority_criterion_values',
    sa.Column('score_id', sa.Uuid(), nullable=False),
    sa.Column('criterion_id', sa.Uuid(), nullable=False),
    sa.Column('value', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['criterion_id'], ['prioritization_criteria.id'], name=op.f('fk_project_priority_criterion_values_criterion_id_prioritization_criteria'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['score_id'], ['project_priority_scores.id'], name=op.f('fk_project_priority_criterion_values_score_id_project_priority_scores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_priority_criterion_values')),
    sa.UniqueConstraint('score_id', 'criterion_id', name='uq_priority_criterion_value_score_criterion')
    )
    op.create_index(op.f('ix_project_priority_criterion_values_criterion_id'), 'project_priority_criterion_values', ['criterion_id'], unique=False)
    op.create_index(op.f('ix_project_priority_criterion_values_score_id'), 'project_priority_criterion_values', ['score_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_project_priority_criterion_values_score_id'), table_name='project_priority_criterion_values')
    op.drop_index(op.f('ix_project_priority_criterion_values_criterion_id'), table_name='project_priority_criterion_values')
    op.drop_table('project_priority_criterion_values')
    op.drop_index(op.f('ix_project_priority_scores_project_id'), table_name='project_priority_scores')
    op.drop_index(op.f('ix_project_priority_scores_organization_id'), table_name='project_priority_scores')
    op.drop_index(op.f('ix_project_priority_scores_framework_id'), table_name='project_priority_scores')
    op.drop_table('project_priority_scores')
    op.drop_index(op.f('ix_prioritization_criteria_organization_id'), table_name='prioritization_criteria')
    op.drop_index(op.f('ix_prioritization_criteria_framework_id'), table_name='prioritization_criteria')
    op.drop_table('prioritization_criteria')
    op.drop_index(op.f('ix_prioritization_frameworks_organization_id'), table_name='prioritization_frameworks')
    op.drop_table('prioritization_frameworks')
