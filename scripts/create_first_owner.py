"""Creates the very first Owner account (Phase 10, revised Phase 12) —
operator-run, one-time bootstrap. There is no open self-registration in
CapacityOS (CLAUDE.md §25/§27: no fake authentication, no auto-created
admin, no hardcoded development credential) — this script is the only way
an Owner account is ever created without an existing Owner/Admin to create
it through the API.

Usage (from apps/api, so DATABASE_URL/.env resolve the same way the API
itself resolves them):

    uv run alembic upgrade head   # once, if not already applied
    uv run python ../../scripts/create_first_owner.py

Prompts interactively for email / display name / password — the password is
read via getpass (never echoed to the terminal, never logged). For
scripted/CI bootstrap only, CAPACITYOS_OWNER_EMAIL / CAPACITYOS_OWNER_NAME /
CAPACITYOS_OWNER_PASSWORD may be set instead; never commit a real value for
these anywhere, and prefer the interactive prompt for a real deployment.

Phase 12: role no longer lives on User — this script creates the account
AND its Owner membership in the bootstrap "Default Organization" the
Phase-12 migration always creates (fixed id, slug "default"). Refuses to
run if that organization already has an active Owner — this script
bootstraps the very first one only. Every subsequent user, and every
additional Owner (in this or any other organization), is created through
POST /api/v1/users plus POST /api/v1/organizations/{id}/memberships by an
existing Owner/Admin (see docs/adr/0012-organizations-multi-tenancy.md),
which is also how a second Owner should be created before this script's
output is ever considered a single point of failure.

Built via the same service layer the API itself uses (UserService,
OrganizationMembershipService), never raw SQL or direct model construction
— this script goes through the identical validation and password-hashing
path a real API request would.
"""

from __future__ import annotations

import getpass
import os
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.exceptions import ConflictError  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.repositories.organization import OrganizationRepository  # noqa: E402
from app.repositories.organization_membership import (  # noqa: E402
    OrganizationMembershipRepository,
)
from app.repositories.person import PersonRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.schemas.organization_membership import MembershipCreate  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services.organization_membership import OrganizationMembershipService  # noqa: E402
from app.services.user import UserService  # noqa: E402

DEFAULT_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def main() -> None:
    session = SessionLocal()
    try:
        organization_repository = OrganizationRepository(session)
        membership_repository = OrganizationMembershipRepository(session)

        organization = organization_repository.get(DEFAULT_ORGANIZATION_ID)
        if organization is None:
            print(
                "The default organization does not exist yet — run "
                "`uv run alembic upgrade head` first.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if membership_repository.count_active_owners(organization.id) > 0:
            print(
                f"'{organization.name}' already has an active Owner. This script only "
                "bootstraps the very first Owner — create additional users (including "
                "further Owners) via POST /api/v1/users and POST /api/v1/organizations/"
                "{id}/memberships as an existing Owner/Admin.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        email = (os.environ.get("CAPACITYOS_OWNER_EMAIL") or input("Owner email: ")).strip()
        display_name = (
            os.environ.get("CAPACITYOS_OWNER_NAME") or input("Owner display name: ")
        ).strip()
        password = os.environ.get("CAPACITYOS_OWNER_PASSWORD") or getpass.getpass(
            "Owner password (input hidden): "
        )
        if len(password) < 10:
            print("Password must be at least 10 characters.", file=sys.stderr)
            raise SystemExit(1)

        user_service = UserService(UserRepository(session), PersonRepository(session))
        try:
            user = user_service.create(
                organization.id,
                UserCreate(
                    email=email,  # type: ignore[arg-type]
                    password=password,
                    display_name=display_name,
                ),
            )
        except ConflictError as exc:
            print(f"Could not create the account: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        membership_service = OrganizationMembershipService(
            membership_repository, UserRepository(session)
        )
        membership_service.add_member(
            organization.id, MembershipCreate(email=user.email, role=UserRole.OWNER)  # type: ignore[arg-type]
        )

        session.commit()
        print(
            f"Owner account created: {user.email} ({user.id}) "
            f"in organization '{organization.name}' ({organization.slug})"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
