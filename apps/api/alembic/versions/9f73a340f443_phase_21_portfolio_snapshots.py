"""phase 21 portfolio snapshots

Revision ID: 9f73a340f443
Revises: 0f150d3fef60
Create Date: 2026-08-25 16:26:06.932179

Hand-cleaned after autogenerate: stripped the well-documented SQLite
CHECK-constraint false-positive noise (drop/recreate ops against every
other StrEnum-backed column in the schema, unrelated to this phase) —
see every prior phase's migration for the same established pattern. The
only real change is the new `portfolio_snapshots` table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f73a340f443'
down_revision: Union[str, Sequence[str], None] = '0f150d3fef60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'portfolio_snapshots',
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('framework_id', sa.Uuid(), nullable=False),
        sa.Column('framework_name', sa.String(), nullable=False),
        sa.Column(
            'framework_type',
            sa.Enum(
                'RICE', 'ICE', 'WSJF', 'MOSCOW', 'WEIGHTED',
                name='ck_portfolio_snapshots_framework_type',
                native_enum=False, create_constraint=True, length=32,
            ),
            nullable=False,
        ),
        sa.Column('entries', sa.JSON(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['framework_id'], ['prioritization_frameworks.id'],
            name=op.f('fk_portfolio_snapshots_framework_id_prioritization_frameworks'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name=op.f('fk_portfolio_snapshots_organization_id_organizations'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolio_snapshots')),
    )
    op.create_index(
        op.f('ix_portfolio_snapshots_framework_id'), 'portfolio_snapshots',
        ['framework_id'], unique=False,
    )
    op.create_index(
        op.f('ix_portfolio_snapshots_organization_id'), 'portfolio_snapshots',
        ['organization_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_portfolio_snapshots_organization_id'), table_name='portfolio_snapshots')
    op.drop_index(op.f('ix_portfolio_snapshots_framework_id'), table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')
