"""Import every model so they register on Base.metadata.

Required for Alembic autogenerate and for SQLAlchemy to resolve the string
class names used in relationship() across modules — every model module must
be imported somewhere before the mapper configuration is used.
"""

from app.models.allocation import Allocation
from app.models.audit_event import AuditEvent
from app.models.availability_exception import AvailabilityException
from app.models.person import Person
from app.models.person_skill import PersonSkill
from app.models.project import Project
from app.models.project_skill_requirement import ProjectSkillRequirement
from app.models.scenario import Scenario, ScenarioOperation
from app.models.session import UserSession
from app.models.skill import Skill
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry

__all__ = [
    "Allocation",
    "AuditEvent",
    "AvailabilityException",
    "Person",
    "PersonSkill",
    "Project",
    "ProjectSkillRequirement",
    "Scenario",
    "ScenarioOperation",
    "Skill",
    "Team",
    "TeamMembership",
    "User",
    "UserSession",
    "WorkingSchedule",
    "WorkingScheduleEntry",
]
