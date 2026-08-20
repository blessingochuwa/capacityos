"""phase 12 organizations multi tenancy

Revision ID: 6fca5b5c9b4f
Revises: 69270a626bfc
Create Date: 2026-08-20 01:27:38.674748

Hand-written, not the raw autogenerate output — see
docs/adr/0012-organizations-multi-tenancy.md for the full design. The
autogenerate diff was used only to confirm exact constraint/index/FK names;
its raw table-recreation ops (which fire unconditionally on every SQLite
batch-mode diff) are NOT reproduced verbatim here, because every one of the
13 organization-owned tables below has real data that must be backfilled to
a bootstrap organization BETWEEN adding the new organization_id column and
making it NOT NULL — a three-step sequence (nullable add -> UPDATE backfill
-> batch_alter_table to NOT NULL + FK + constraints) autogenerate cannot
express. It also additionally proposed drop/recreate pairs for
ck_allocations_allocation_unit, ck_audit_events_outcome,
ck_people_employment_status, ck_person_skills_proficiency,
ck_project_skill_requirements_min_proficiency, ck_projects_status, and
ck_scenario_operations_operation_type — the same known SQLite CHECK-
constraint text-diff false positive documented in every prior phase's
migration (ADR 0002/0004/0005/0006/0007/0010/0011); hand-writing this
migration around explicit batch_alter_table blocks avoids re-introducing
that noise entirely rather than trimming it after the fact.

downgrade()'s organization_memberships -> users.role backfill direction is
lossy for any user later given a second membership (only the FIRST
membership found is written back) — acceptable since downgrade here is a
development safety net, not a supported production rollback path (same
caveat this codebase already accepts for other irreversible-in-practice
migrations).
"""
import uuid
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fca5b5c9b4f'
down_revision: Union[str, Sequence[str], None] = '69270a626bfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ORG_NAME = "Default Organization"
DEFAULT_ORG_SLUG = "default"


def _backfill_organization_id(table_name: str) -> None:
    """The shared 3-step sequence for every organization-owned table: add
    the column nullable (a real, cheap SQLite ALTER TABLE ADD COLUMN — no
    table rebuild), backfill every existing row to the bootstrap
    organization, then hand off to the caller's own batch_alter_table
    block to flip it NOT NULL + add the FK/index/unique-constraint changes
    together in one table rebuild."""
    op.add_column(table_name, sa.Column("organization_id", sa.Uuid(), nullable=True))
    table = sa.table(table_name, sa.column("organization_id", sa.Uuid()))
    op.execute(table.update().values(organization_id=DEFAULT_ORG_ID))


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    now = datetime.now(UTC)

    # -- 1. Organization + OrganizationMembership (the tenant root) --------

    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "organization_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "OWNER", "ADMIN", "MANAGER", "MEMBER", "VIEWER",
                name="ck_organization_memberships_role", native_enum=False,
                create_constraint=True, length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE", "REVOKED", name="ck_organization_memberships_status",
                native_enum=False, create_constraint=True, length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_organization_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_organization_memberships_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_memberships")),
        sa.UniqueConstraint(
            "user_id", "organization_id", name="uq_organization_membership_user_org"
        ),
    )
    op.create_index(
        op.f("ix_organization_memberships_organization_id"),
        "organization_memberships", ["organization_id"], unique=False,
    )
    op.create_index(
        op.f("ix_organization_memberships_user_id"),
        "organization_memberships", ["user_id"], unique=False,
    )

    # -- 2. Bootstrap organization — every pre-Phase-12 row belongs here ----

    organizations_t = sa.table(
        "organizations",
        sa.column("id", sa.Uuid()), sa.column("name", sa.String()),
        sa.column("slug", sa.String()), sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    bind.execute(
        organizations_t.insert().values(
            id=DEFAULT_ORG_ID, name=DEFAULT_ORG_NAME, slug=DEFAULT_ORG_SLUG,
            is_active=True, created_at=now, updated_at=now,
        )
    )

    # -- 3. Backfill organization_memberships from users.role BEFORE it's
    # dropped — Python-side uuid.uuid4() per row, not raw cross-dialect SQL
    # UUID generation, so this stays portable to Postgres production. ------

    users_t = sa.table("users", sa.column("id", sa.Uuid()), sa.column("role", sa.String()))
    existing_users = bind.execute(sa.select(users_t.c.id, users_t.c.role)).fetchall()
    if existing_users:
        memberships_t = sa.table(
            "organization_memberships",
            sa.column("id", sa.Uuid()), sa.column("user_id", sa.Uuid()),
            sa.column("organization_id", sa.Uuid()), sa.column("role", sa.String()),
            sa.column("status", sa.String()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        bind.execute(
            memberships_t.insert(),
            [
                {
                    "id": uuid.uuid4(),
                    "user_id": row.id,
                    "organization_id": DEFAULT_ORG_ID,
                    "role": row.role,
                    "status": "ACTIVE",
                    "created_at": now,
                    "updated_at": now,
                }
                for row in existing_users
            ],
        )

    # -- 4. users.role removed — role now lives on OrganizationMembership --

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(op.f("ck_users_role"), type_="check")
        batch_op.drop_column("role")

    # -- 5. sessions.active_organization_id — nullable, no backfill (NULL
    # means "must pick an org," a valid post-login state). -----------------

    op.add_column("sessions", sa.Column("active_organization_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_sessions_active_organization_id_organizations"),
            "organizations", ["active_organization_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_sessions_active_organization_id"), ["active_organization_id"]
        )

    # -- 6. audit_events.organization_id — nullable, no backfill (a
    # pre-organization-context event, e.g. an unknown-email login failure,
    # legitimately has none; SET NULL so the audit trail outlives the org
    # it references). -------------------------------------------------------

    op.add_column("audit_events", sa.Column("organization_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_audit_events_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_audit_events_organization_id"), ["organization_id"])

    # -- 7. The 13 organization-owned tables: NOT NULL organization_id,
    # backfilled to the bootstrap org, FK ondelete=RESTRICT, index, and
    # (where the entity had a global-unique field) a composite
    # (organization_id, field) unique constraint replacing the old one. ----

    _backfill_organization_id("people")
    with op.batch_alter_table("people") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_people_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_people_organization_id"), ["organization_id"])
        batch_op.drop_index(op.f("ix_people_email"))
        batch_op.create_index(op.f("ix_people_email"), ["email"], unique=False)
        batch_op.create_unique_constraint(
            "uq_person_organization_email", ["organization_id", "email"]
        )

    _backfill_organization_id("teams")
    with op.batch_alter_table("teams") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_teams_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_teams_organization_id"), ["organization_id"])
        batch_op.drop_constraint(op.f("uq_teams_name"), type_="unique")
        batch_op.create_unique_constraint(
            "uq_team_organization_name", ["organization_id", "name"]
        )

    _backfill_organization_id("team_memberships")
    with op.batch_alter_table("team_memberships") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_team_memberships_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_team_memberships_organization_id"), ["organization_id"]
        )

    _backfill_organization_id("projects")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_projects_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_projects_organization_id"), ["organization_id"])
        batch_op.drop_index(op.f("ix_projects_external_id"))
        batch_op.create_index(op.f("ix_projects_external_id"), ["external_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_project_organization_external_id", ["organization_id", "external_id"]
        )

    _backfill_organization_id("allocations")
    with op.batch_alter_table("allocations") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_allocations_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_allocations_organization_id"), ["organization_id"])
        batch_op.drop_index(op.f("ix_allocations_external_id"))
        batch_op.create_index(
            op.f("ix_allocations_external_id"), ["external_id"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_allocation_organization_external_id", ["organization_id", "external_id"]
        )

    _backfill_organization_id("working_schedules")
    with op.batch_alter_table("working_schedules") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_working_schedules_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_working_schedules_organization_id"), ["organization_id"]
        )
        batch_op.drop_index(op.f("ix_working_schedules_external_id"))
        batch_op.create_index(
            op.f("ix_working_schedules_external_id"), ["external_id"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_working_schedule_organization_external_id",
            ["organization_id", "external_id"],
        )

    _backfill_organization_id("availability_exceptions")
    with op.batch_alter_table("availability_exceptions") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_availability_exceptions_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_availability_exceptions_organization_id"), ["organization_id"]
        )
        batch_op.drop_index(op.f("ix_availability_exceptions_external_id"))
        batch_op.create_index(
            op.f("ix_availability_exceptions_external_id"), ["external_id"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_availability_exception_organization_external_id",
            ["organization_id", "external_id"],
        )

    _backfill_organization_id("skills")
    with op.batch_alter_table("skills") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_skills_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_skills_organization_id"), ["organization_id"])
        batch_op.drop_constraint(op.f("uq_skills_name"), type_="unique")
        batch_op.create_unique_constraint(
            "uq_skill_organization_name", ["organization_id", "name"]
        )

    _backfill_organization_id("person_skills")
    with op.batch_alter_table("person_skills") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_person_skills_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_person_skills_organization_id"), ["organization_id"])

    _backfill_organization_id("project_skill_requirements")
    with op.batch_alter_table("project_skill_requirements") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_project_skill_requirements_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_project_skill_requirements_organization_id"), ["organization_id"]
        )

    _backfill_organization_id("scenarios")
    with op.batch_alter_table("scenarios") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_scenarios_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(op.f("ix_scenarios_organization_id"), ["organization_id"])

    _backfill_organization_id("team_access_grants")
    with op.batch_alter_table("team_access_grants") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_team_access_grants_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_team_access_grants_organization_id"), ["organization_id"]
        )

    _backfill_organization_id("project_access_grants")
    with op.batch_alter_table("project_access_grants") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_project_access_grants_organization_id_organizations"),
            "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_project_access_grants_organization_id"), ["organization_id"]
        )


def downgrade() -> None:
    """Downgrade schema. Development safety net only — see this module's
    docstring for the lossy users.role backfill direction."""
    with op.batch_alter_table("project_access_grants") as batch_op:
        batch_op.drop_index(op.f("ix_project_access_grants_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_project_access_grants_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("team_access_grants") as batch_op:
        batch_op.drop_index(op.f("ix_team_access_grants_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_team_access_grants_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("scenarios") as batch_op:
        batch_op.drop_index(op.f("ix_scenarios_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_scenarios_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("project_skill_requirements") as batch_op:
        batch_op.drop_index(op.f("ix_project_skill_requirements_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_project_skill_requirements_organization_id_organizations"),
            type_="foreignkey",
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("person_skills") as batch_op:
        batch_op.drop_index(op.f("ix_person_skills_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_person_skills_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_constraint("uq_skill_organization_name", type_="unique")
        batch_op.create_unique_constraint(op.f("uq_skills_name"), ["name"])
        batch_op.drop_index(op.f("ix_skills_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_skills_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("availability_exceptions") as batch_op:
        batch_op.drop_constraint(
            "uq_availability_exception_organization_external_id", type_="unique"
        )
        batch_op.drop_index(op.f("ix_availability_exceptions_external_id"))
        batch_op.create_index(
            op.f("ix_availability_exceptions_external_id"), ["external_id"], unique=True
        )
        batch_op.drop_index(op.f("ix_availability_exceptions_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_availability_exceptions_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("working_schedules") as batch_op:
        batch_op.drop_constraint(
            "uq_working_schedule_organization_external_id", type_="unique"
        )
        batch_op.drop_index(op.f("ix_working_schedules_external_id"))
        batch_op.create_index(
            op.f("ix_working_schedules_external_id"), ["external_id"], unique=True
        )
        batch_op.drop_index(op.f("ix_working_schedules_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_working_schedules_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("allocations") as batch_op:
        batch_op.drop_constraint("uq_allocation_organization_external_id", type_="unique")
        batch_op.drop_index(op.f("ix_allocations_external_id"))
        batch_op.create_index(
            op.f("ix_allocations_external_id"), ["external_id"], unique=True
        )
        batch_op.drop_index(op.f("ix_allocations_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_allocations_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("uq_project_organization_external_id", type_="unique")
        batch_op.drop_index(op.f("ix_projects_external_id"))
        batch_op.create_index(op.f("ix_projects_external_id"), ["external_id"], unique=True)
        batch_op.drop_index(op.f("ix_projects_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_projects_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("team_memberships") as batch_op:
        batch_op.drop_index(op.f("ix_team_memberships_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_team_memberships_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint("uq_team_organization_name", type_="unique")
        batch_op.create_unique_constraint(op.f("uq_teams_name"), ["name"])
        batch_op.drop_index(op.f("ix_teams_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_teams_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("people") as batch_op:
        batch_op.drop_constraint("uq_person_organization_email", type_="unique")
        batch_op.drop_index(op.f("ix_people_email"))
        batch_op.create_index(op.f("ix_people_email"), ["email"], unique=True)
        batch_op.drop_index(op.f("ix_people_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_people_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index(op.f("ix_audit_events_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_audit_events_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index(op.f("ix_sessions_active_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_sessions_active_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("active_organization_id")

    # Lossy: writes back only the FIRST membership found per user (a user
    # given a second membership after upgrade has no single "the" role to
    # restore) — see this module's docstring.
    bind = op.get_bind()
    memberships_t = sa.table(
        "organization_memberships",
        sa.column("user_id", sa.Uuid()), sa.column("role", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    memberships = bind.execute(
        sa.select(memberships_t.c.user_id, memberships_t.c.role)
        .order_by(memberships_t.c.created_at)
    ).fetchall()
    role_by_user: dict[uuid.UUID, str] = {}
    for row in memberships:
        role_by_user.setdefault(row.user_id, row.role)

    op.add_column(
        "users", sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer")
    )
    users_t = sa.table("users", sa.column("id", sa.Uuid()), sa.column("role", sa.String()))
    for user_id, role in role_by_user.items():
        bind.execute(users_t.update().where(users_t.c.id == user_id).values(role=role))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role", server_default=None)
        batch_op.create_check_constraint(
            op.f("ck_users_role"), "role IN ('OWNER', 'ADMIN', 'MANAGER', 'MEMBER', 'VIEWER')"
        )

    op.drop_index(op.f("ix_organization_memberships_user_id"), table_name="organization_memberships")
    op.drop_index(
        op.f("ix_organization_memberships_organization_id"), table_name="organization_memberships"
    )
    op.drop_table("organization_memberships")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
