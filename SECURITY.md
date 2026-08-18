# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in CapacityOS, please report it privately rather than opening a public issue. Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any relevant logs, screenshots, or proof-of-concept code

We will acknowledge reports and work on a fix before any public disclosure. Please allow reasonable time for a fix to be developed and released before disclosing publicly.

## Supported versions

CapacityOS is currently in early development (Phase 0 — no tagged releases yet). Security fixes are applied to the `main` branch until a formal release and support policy is established.

## Security principles

This project follows the security rules defined in [CLAUDE.md §27](./CLAUDE.md):

- No secrets, tokens, or credentials are committed to the repository.
- Backend secrets are never exposed to the frontend.
- Access tokens are never logged.
- Arbitrary uploaded code is never executed.
- Production stack traces are never exposed to clients.
- Environment variables are used for configuration; `.env` is git-ignored, `.env.example` documents required variables without real values.

## Authentication and authorization (Phase 10)

CapacityOS uses httpOnly, Secure-in-production session cookies (opaque,
random tokens — never JWTs, never a signed/encrypted value, so there is no
`SESSION_SECRET_KEY` to leak) and Argon2id password hashing. A five-role
RBAC model (Owner/Admin/Manager/Member/Viewer) is enforced on every
mutating API route through one centralized permission check. Every
mutation, login event, and permission denial is recorded in an
append-only audit log. See
[docs/adr/0010-authentication-rbac-audit.md](./docs/adr/0010-authentication-rbac-audit.md)
for the full authentication architecture, threat model, and known
limitations (no distributed rate limiting, no instance-level "only your
own team" authorization yet).

There is no open self-registration. The first Owner account is created
via `scripts/create_first_owner.py`, run once by an operator — never a
hardcoded or auto-created credential.
