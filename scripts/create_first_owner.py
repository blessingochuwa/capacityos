"""Creates the very first Owner account (Phase 10) — operator-run, one-time
bootstrap. There is no open self-registration in CapacityOS (CLAUDE.md
§25/§27: no fake authentication, no auto-created admin, no hardcoded
development credential) — this script is the only way an Owner account is
ever created without an existing Owner/Admin to create it through the API.

Usage (from apps/api, so DATABASE_URL/.env resolve the same way the API
itself resolves them):

    uv run alembic upgrade head   # once, if not already applied
    uv run python ../../scripts/create_first_owner.py

Prompts interactively for email / display name / password — the password is
read via getpass (never echoed to the terminal, never logged). For
scripted/CI bootstrap only, CAPACITYOS_OWNER_EMAIL / CAPACITYOS_OWNER_NAME /
CAPACITYOS_OWNER_PASSWORD may be set instead; never commit a real value for
these anywhere, and prefer the interactive prompt for a real deployment.

Refuses to run if an Owner account already exists — this script bootstraps
the very first one only. Every subsequent user, including additional
Owners, is created through POST /api/v1/users by an existing Owner/Admin
(see docs/adr/0010-authentication-rbac-audit.md), which is also how a
second Owner should be created before this script's output is ever
considered a single point of failure.

Built via the same service/repository layer POST /api/v1/users itself
uses (UserService/UserRepository), never raw SQL or direct model
construction — this script goes through the identical validation and
password-hashing path a real API request would.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.exceptions import ConflictError  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.repositories.person import PersonRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services.user import UserService  # noqa: E402


def main() -> None:
    session = SessionLocal()
    try:
        user_repository = UserRepository(session)
        if user_repository.count_by_role(UserRole.OWNER) > 0:
            print(
                "An active Owner account already exists. This script only bootstraps "
                "the very first Owner — create additional users (including further "
                "Owners) via POST /api/v1/users as an existing Owner/Admin.",
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

        service = UserService(user_repository, PersonRepository(session))
        try:
            user = service.create(
                UserCreate(
                    email=email,  # type: ignore[arg-type]
                    password=password,
                    display_name=display_name,
                    role=UserRole.OWNER,
                )
            )
        except ConflictError as exc:
            print(f"Could not create the account: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        session.commit()
        print(f"Owner account created: {user.email} ({user.id})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
