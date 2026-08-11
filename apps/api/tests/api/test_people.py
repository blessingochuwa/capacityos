import uuid

from fastapi.testclient import TestClient


def test_create_person_returns_201_with_derived_display_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Alex Morgan"
    assert body["employment_status"] == "active"
    assert uuid.UUID(body["id"])


def test_create_person_with_explicit_display_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/people",
        json={
            "first_name": "Sam",
            "last_name": "Ade",
            "email": "sam.ade@example.com",
            "display_name": "Sami",
        },
    )
    assert response.status_code == 201
    assert response.json()["display_name"] == "Sami"


def test_create_person_with_invalid_email_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "not-an-email"},
    )
    assert response.status_code == 422


def test_create_person_missing_required_field_returns_422(client: TestClient) -> None:
    response = client.post("/api/v1/people", json={"first_name": "Alex"})
    assert response.status_code == 422


def test_duplicate_email_returns_409(client: TestClient) -> None:
    payload = {"first_name": "Alex", "last_name": "Morgan", "email": "dup@example.com"}
    assert client.post("/api/v1/people", json=payload).status_code == 201
    response = client.post("/api/v1/people", json=payload)
    assert response.status_code == 409


def test_get_person_returns_200(client: TestClient) -> None:
    created = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()
    response = client.get(f"/api/v1/people/{created['id']}")
    assert response.status_code == 200
    assert response.json()["email"] == "alex.morgan@example.com"


def test_get_nonexistent_person_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/people/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_people_returns_page_envelope(client: TestClient) -> None:
    client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    )
    response = client.get("/api/v1/people")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_update_person_partial_fields(client: TestClient) -> None:
    created = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()

    response = client.patch(f"/api/v1/people/{created['id']}", json={"job_title": "Staff Designer"})
    assert response.status_code == 200
    body = response.json()
    assert body["job_title"] == "Staff Designer"
    assert body["first_name"] == "Alex"  # untouched fields survive a partial update


def test_update_person_to_duplicate_email_returns_409(client: TestClient) -> None:
    client.post(
        "/api/v1/people",
        json={"first_name": "A", "last_name": "One", "email": "one@example.com"},
    )
    two = client.post(
        "/api/v1/people",
        json={"first_name": "B", "last_name": "Two", "email": "two@example.com"},
    ).json()

    response = client.patch(f"/api/v1/people/{two['id']}", json={"email": "one@example.com"})
    assert response.status_code == 409


def test_delete_person_returns_204_then_404(client: TestClient) -> None:
    created = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()

    assert client.delete(f"/api/v1/people/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/people/{created['id']}").status_code == 404
