"""Response contracts for Phase 7 skill-aware capacity/coverage endpoints.

Facts (required_hours, proficiency) and derived values (qualified_available_
hours, coverage_ratio, gap_hours) are kept as distinct fields throughout —
never merged into one blob (CLAUDE.md §4, same discipline as
app/schemas/capacity.py and app/schemas/insights.py). See
docs/adr/0007-phase-7-skills-bottleneck-analysis.md.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import SkillProficiency


class QualifiedPersonRead(BaseModel):
    person_id: uuid.UUID
    person_label: str
    proficiency: SkillProficiency
    qualified_available_hours: Decimal
    """max(remaining_capacity, 0) for this person over the queried period —
    a Phase 7 derived quantity distinct from Phase 2's remaining_capacity
    (which is never clamped). A fully-booked qualified person still counts
    as a holder of the skill but contributes 0 here, since they have no
    spare capacity left to take on qualified work."""


class SkillCoverageRead(BaseModel):
    requirement_id: uuid.UUID
    skill_id: uuid.UUID
    skill_label: str
    required_hours: Decimal
    minimum_proficiency: SkillProficiency | None
    qualified_available_hours: Decimal
    coverage_ratio: Decimal | None
    """qualified_available_hours / required_hours. Always set — required_hours
    is enforced > 0 at the model level (ck_project_skill_requirement_hours_positive),
    so there is no division-by-zero case to guard against here."""
    gap_hours: Decimal
    qualified_people: list[QualifiedPersonRead]


class ProjectSkillCoverageRead(BaseModel):
    project_id: uuid.UUID
    project_label: str
    start_date: date
    end_date: date
    requirements: list[SkillCoverageRead]
    """Empty list distinguishes "no skill requirements configured" from
    "requirements exist" — callers check len(), never an invented status
    enum (Phase 7 UX requirement: healthy vs not-configured vs uncovered
    must never be conflated)."""


class TeamSkillCapacityEntryRead(BaseModel):
    skill_id: uuid.UUID
    skill_label: str
    qualified_available_hours: Decimal
    qualified_people: list[QualifiedPersonRead]
    """Supply only — no "required hours" field. Team has no stored or
    derivable skill demand of its own (only Project does, via
    ProjectSkillRequirement); see the ADR for why a team-level demand
    aggregation was deliberately not invented."""


class TeamSkillCapacityRead(BaseModel):
    team_id: uuid.UUID
    team_label: str
    start_date: date
    end_date: date
    skills: list[TeamSkillCapacityEntryRead]
    """Empty list means no team member currently holds any active skill."""
