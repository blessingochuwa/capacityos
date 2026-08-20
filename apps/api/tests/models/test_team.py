import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.organization import Organization
from tests.factories import make_organization, make_person, make_team, make_team_membership


def test_create_valid_team(db_session: Session, organization: Organization) -> None:
    team = make_team(db_session, organization=organization)
    assert team.id is not None
    assert team.name == "Creative"


def test_team_name_must_be_unique(db_session: Session, organization: Organization) -> None:
    make_team(db_session, organization=organization, name="Creative")
    with pytest.raises(IntegrityError):
        make_team(db_session, organization=organization, name="Creative")


def test_team_name_can_repeat_across_organizations(db_session: Session) -> None:
    """Phase 12: Team.name uniqueness is scoped to (organization_id, name)."""
    org_a = make_organization(db_session, slug="org-a")
    org_b = make_organization(db_session, slug="org-b")
    make_team(db_session, organization=org_a, name="Creative")
    make_team(db_session, organization=org_b, name="Creative")


def test_person_can_join_a_team(db_session: Session, organization: Organization) -> None:
    person = make_person(db_session, organization=organization)
    team = make_team(db_session, organization=organization)
    membership = make_team_membership(
        db_session, organization=organization, person=person, team=team
    )

    assert membership.id is not None
    assert person.team_memberships == [membership]
    assert team.memberships == [membership]


def test_person_can_belong_to_multiple_teams(
    db_session: Session, organization: Organization
) -> None:
    person = make_person(db_session, organization=organization)
    design = make_team(db_session, organization=organization, name="Design")
    engineering = make_team(db_session, organization=organization, name="Engineering")
    make_team_membership(db_session, organization=organization, person=person, team=design)
    make_team_membership(db_session, organization=organization, person=person, team=engineering)

    assert len(person.team_memberships) == 2


def test_duplicate_team_membership_is_rejected(
    db_session: Session, organization: Organization
) -> None:
    person = make_person(db_session, organization=organization)
    team = make_team(db_session, organization=organization)
    make_team_membership(db_session, organization=organization, person=person, team=team)

    with pytest.raises(IntegrityError):
        make_team_membership(db_session, organization=organization, person=person, team=team)


def test_deleting_person_cascades_to_team_membership(
    db_session: Session, organization: Organization
) -> None:
    person = make_person(db_session, organization=organization)
    team = make_team(db_session, organization=organization)
    make_team_membership(db_session, organization=organization, person=person, team=team)

    db_session.delete(person)
    db_session.flush()

    assert team.memberships == []
