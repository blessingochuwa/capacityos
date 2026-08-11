import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import make_person, make_team, make_team_membership


def test_create_valid_team(db_session: Session) -> None:
    team = make_team(db_session)
    assert team.id is not None
    assert team.name == "Creative"


def test_team_name_must_be_unique(db_session: Session) -> None:
    make_team(db_session, name="Creative")
    with pytest.raises(IntegrityError):
        make_team(db_session, name="Creative")


def test_person_can_join_a_team(db_session: Session) -> None:
    person = make_person(db_session)
    team = make_team(db_session)
    membership = make_team_membership(db_session, person=person, team=team)

    assert membership.id is not None
    assert person.team_memberships == [membership]
    assert team.memberships == [membership]


def test_person_can_belong_to_multiple_teams(db_session: Session) -> None:
    person = make_person(db_session)
    design = make_team(db_session, name="Design")
    engineering = make_team(db_session, name="Engineering")
    make_team_membership(db_session, person=person, team=design)
    make_team_membership(db_session, person=person, team=engineering)

    assert len(person.team_memberships) == 2


def test_duplicate_team_membership_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    team = make_team(db_session)
    make_team_membership(db_session, person=person, team=team)

    with pytest.raises(IntegrityError):
        make_team_membership(db_session, person=person, team=team)


def test_deleting_person_cascades_to_team_membership(db_session: Session) -> None:
    person = make_person(db_session)
    team = make_team(db_session)
    make_team_membership(db_session, person=person, team=team)

    db_session.delete(person)
    db_session.flush()

    assert team.memberships == []
