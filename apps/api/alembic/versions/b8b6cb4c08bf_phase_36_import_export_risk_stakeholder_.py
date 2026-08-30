"""phase 36 import export risk stakeholder prioritization

Revision ID: b8b6cb4c08bf
Revises: 9f73a340f443
Create Date: 2026-08-29 16:43:17.661745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8b6cb4c08bf'
down_revision: Union[str, Sequence[str], None] = '9f73a340f443'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Autogenerate additionally proposed drop_constraint/create_check_constraint
# operations against every other enum-CHECK-constrained column in the
# schema — the same known SQLite CHECK-constraint text-diff false positive
# already documented in ADR 0002/0004/0005/0006 (fires identically for
# untouched enum columns in every prior autogenerate run). Removed by hand
# below; this migration only contains the new risks.external_id column and
# its index/unique constraint (docs/adr/0036-import-export-risk-stakeholder-prioritization.md),
# matching Project/Allocation/WorkingSchedule/AvailabilityException's exact
# (organization_id, external_id) shape from Phase 6/12. Uses batch mode —
# SQLite cannot ALTER a table to add a named UNIQUE constraint directly
# (see the Phase 12 migration's identical use of batch_alter_table for
# Project's own organization_id+external_id constraint).


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("risks") as batch_op:
        batch_op.add_column(sa.Column('external_id', sa.String(length=200), nullable=True))
        batch_op.create_index(op.f('ix_risks_external_id'), ['external_id'], unique=False)
        batch_op.create_unique_constraint(
            'uq_risk_organization_external_id', ['organization_id', 'external_id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("risks") as batch_op:
        batch_op.drop_constraint('uq_risk_organization_external_id', type_='unique')
        batch_op.drop_index(op.f('ix_risks_external_id'))
        batch_op.drop_column('external_id')
