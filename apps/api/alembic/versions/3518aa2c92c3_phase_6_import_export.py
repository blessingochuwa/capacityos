"""phase 6 import export

Revision ID: 3518aa2c92c3
Revises: 108ebff8787e
Create Date: 2026-08-14 20:55:06.233781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3518aa2c92c3'
down_revision: Union[str, Sequence[str], None] = '108ebff8787e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Autogenerate additionally proposed drop_constraint/create_check_constraint
# operations against ck_allocations_allocation_unit, ck_people_employment_status,
# ck_projects_status, ck_scenario_operations_operation_type, and
# ck_scenarios_status — the same known SQLite CHECK-constraint text-diff
# false positive already documented in ADR 0002/0004/0005 (fires identically
# for untouched enum columns in every prior autogenerate run). Removed by
# hand below; this migration only contains the 4 new external_id columns
# and their unique indexes (docs/adr/0006-phase-6-import-export.md).


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('allocations', sa.Column('external_id', sa.String(length=200), nullable=True))
    op.create_index(op.f('ix_allocations_external_id'), 'allocations', ['external_id'], unique=True)
    op.add_column('availability_exceptions', sa.Column('external_id', sa.String(length=200), nullable=True))
    op.create_index(op.f('ix_availability_exceptions_external_id'), 'availability_exceptions', ['external_id'], unique=True)
    op.add_column('projects', sa.Column('external_id', sa.String(length=200), nullable=True))
    op.create_index(op.f('ix_projects_external_id'), 'projects', ['external_id'], unique=True)
    op.add_column('working_schedules', sa.Column('external_id', sa.String(length=200), nullable=True))
    op.create_index(op.f('ix_working_schedules_external_id'), 'working_schedules', ['external_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_working_schedules_external_id'), table_name='working_schedules')
    op.drop_column('working_schedules', 'external_id')
    op.drop_index(op.f('ix_projects_external_id'), table_name='projects')
    op.drop_column('projects', 'external_id')
    op.drop_index(op.f('ix_availability_exceptions_external_id'), table_name='availability_exceptions')
    op.drop_column('availability_exceptions', 'external_id')
    op.drop_index(op.f('ix_allocations_external_id'), table_name='allocations')
    op.drop_column('allocations', 'external_id')
