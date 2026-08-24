"""phase 20 scenario priority comparison

Revision ID: 0f150d3fef60
Revises: 9fbd652ddd0b
Create Date: 2026-08-24 22:30:03.227092

Hand-cleaned after autogenerate: stripped the well-documented SQLite
CHECK-constraint false-positive noise (drop/recreate ops against every
other StrEnum-backed column in the schema, unrelated to this phase) —
see every prior phase's migration for the same established pattern. The
only real change is the new `scenario_priority_overrides` table — a
brand-new table's CHECK constraints are created natively by CREATE
TABLE, so (unlike Phase 18's ALTER-an-existing-table case) no
batch_alter_table workaround is needed here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f150d3fef60'
down_revision: Union[str, Sequence[str], None] = '9fbd652ddd0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'scenario_priority_overrides',
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('scenario_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('framework_id', sa.Uuid(), nullable=False),
        sa.Column('values', sa.JSON(), nullable=False),
        sa.Column(
            'category',
            sa.Enum(
                'MUST', 'SHOULD', 'COULD', 'WONT',
                name='ck_scenario_priority_overrides_category',
                native_enum=False, create_constraint=True, length=32,
            ),
            nullable=True,
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['framework_id'], ['prioritization_frameworks.id'],
            name=op.f('fk_scenario_priority_overrides_framework_id_prioritization_frameworks'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name=op.f('fk_scenario_priority_overrides_organization_id_organizations'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_scenario_priority_overrides_project_id_projects'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['scenario_id'], ['scenarios.id'],
            name=op.f('fk_scenario_priority_overrides_scenario_id_scenarios'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_scenario_priority_overrides')),
        sa.UniqueConstraint(
            'scenario_id', 'project_id', 'framework_id',
            name='uq_scenario_priority_override_scenario_project_framework',
        ),
    )
    op.create_index(
        op.f('ix_scenario_priority_overrides_framework_id'), 'scenario_priority_overrides',
        ['framework_id'], unique=False,
    )
    op.create_index(
        op.f('ix_scenario_priority_overrides_organization_id'), 'scenario_priority_overrides',
        ['organization_id'], unique=False,
    )
    op.create_index(
        op.f('ix_scenario_priority_overrides_project_id'), 'scenario_priority_overrides',
        ['project_id'], unique=False,
    )
    op.create_index(
        op.f('ix_scenario_priority_overrides_scenario_id'), 'scenario_priority_overrides',
        ['scenario_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_scenario_priority_overrides_scenario_id'), table_name='scenario_priority_overrides')
    op.drop_index(op.f('ix_scenario_priority_overrides_project_id'), table_name='scenario_priority_overrides')
    op.drop_index(op.f('ix_scenario_priority_overrides_organization_id'), table_name='scenario_priority_overrides')
    op.drop_index(op.f('ix_scenario_priority_overrides_framework_id'), table_name='scenario_priority_overrides')
    op.drop_table('scenario_priority_overrides')
