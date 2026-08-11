import uuid

from fastapi.testclient import TestClient


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def test_create_team_returns_201(client: TestClient) -> None:
    response = client.post("/api/v1/teams", json={"name": "Creative"})
    assert response.status_code == 201
    assert response.json()["name"] == "Creative"


def test_duplicate_team_name_returns_409(client: TestClient) -> None:
    client.post("/api/v1/teams", json={"name": "Creative"})
    response = client.post("/api/v1/teams", json={"name": "Creative"})
    assert response.status_code == 409


def test_get_nonexistent_team_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/teams/{uuid.uuid4()}").status_code == 404


def test_add_member_returns_201(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    person = _create_person(client)

    response = client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})
    assert response.status_code == 201
    assert response.json()["person_id"] == person["id"]
    assert response.json()["team_id"] == team["id"]


def test_add_member_to_nonexistent_team_returns_404(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        f"/api/v1/teams/{uuid.uuid4()}/members", json={"person_id": person["id"]}
    )
    assert response.status_code == 404


def test_add_nonexistent_person_as_member_returns_404(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    response = client.post(
        f"/api/v1/teams/{team['id']}/members", json={"person_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_add_duplicate_member_returns_409(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    person = _create_person(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})
    assert response.status_code == 409


def test_list_members(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    person = _create_person(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.get(f"/api/v1/teams/{team['id']}/members")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_remove_member_returns_204_then_empty_list(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    person = _create_person(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.delete(f"/api/v1/teams/{team['id']}/members/{person['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/teams/{team['id']}/members").json() == []


def test_remove_nonexistent_member_returns_404(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    person = _create_person(client)
    response = client.delete(f"/api/v1/teams/{team['id']}/members/{person['id']}")
    assert response.status_code == 404
