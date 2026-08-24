"""phase 18 prioritization frameworks and dependencies

Revision ID: 9fbd652ddd0b
Revises: 7a85ed34f6dc
Create Date: 2026-08-24 19:22:05.086841

Hand-cleaned after autogenerate: stripped the well-documented SQLite
CHECK-constraint false-positive noise (drop/recreate ops against every
other StrEnum-backed column in the schema, unrelated to this phase) —
see every prior phase's migration for the same established pattern. The
only real changes are the new `project_dependencies` table and the new
`project_priority_scores.category` column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fbd652ddd0b'
down_revision: Union[str, Sequence[str], None] = '7a85ed34f6dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'project_dependencies',
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('from_project_id', sa.Uuid(), nullable=False),
        sa.Column('to_project_id', sa.Uuid(), nullable=False),
        sa.Column(
            'dependency_type',
            sa.Enum(
                'BLOCKS', 'RELATED', 'ENABLES',
                name='ck_project_dependencies_dependency_type',
                native_enum=False, create_constraint=True, length=32,
            ),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ['from_project_id'], ['projects.id'],
            name=op.f('fk_project_dependencies_from_project_id_projects'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name=op.f('fk_project_dependencies_organization_id_organizations'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['to_project_id'], ['projects.id'],
            name=op.f('fk_project_dependencies_to_project_id_projects'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_project_dependencies')),
        sa.UniqueConstraint(
            'from_project_id', 'to_project_id', 'dependency_type',
            name='uq_project_dependency_from_to_type',
        ),
    )
    op.create_index(
        op.f('ix_project_dependencies_from_project_id'), 'project_dependencies',
        ['from_project_id'], unique=False,
    )
    op.create_index(
        op.f('ix_project_dependencies_organization_id'), 'project_dependencies',
        ['organization_id'], unique=False,
    )
    op.create_index(
        op.f('ix_project_dependencies_to_project_id'), 'project_dependencies',
        ['to_project_id'], unique=False,
    )
    # batch_alter_table (SQLite copy-and-move) rather than a plain
    # op.add_column: SQLite's ALTER TABLE ADD COLUMN cannot attach a
    # table-level CHECK constraint (Alembic silently skips it and only
    # warns — see alembic/ddl/sqlite.py), which would leave `category`
    # enforced only at the Pydantic/application layer and not at the
    # database layer, unlike every other CHECK-constrained enum column in
    # this schema.
    with op.batch_alter_table('project_priority_scores') as batch_op:
        batch_op.add_column(
            sa.Column(
                'category',
                sa.Enum(
                    'MUST', 'SHOULD', 'COULD', 'WONT',
                    name='ck_project_priority_scores_category',
                    native_enum=False, create_constraint=True, length=32,
                ),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('project_priority_scores') as batch_op:
        # The CHECK constraint must be dropped explicitly before the
        # column it references — batch mode's table rebuild otherwise
        # tries to recreate the constraint against a column that's no
        # longer there ("no such column: category").
        batch_op.drop_constraint('ck_project_priority_scores_category', type_='check')
        batch_op.drop_column('category')
    op.drop_index(op.f('ix_project_dependencies_to_project_id'), table_name='project_dependencies')
    op.drop_index(op.f('ix_project_dependencies_organization_id'), table_name='project_dependencies')
    op.drop_index(op.f('ix_project_dependencies_from_project_id'), table_name='project_dependencies')
    op.drop_table('project_dependencies')
