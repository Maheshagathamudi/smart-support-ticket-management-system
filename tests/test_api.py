from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def register_customer():
    email = f"{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Test Customer",
            "password": "long-test-password-123",
        },
    )
    assert response.status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "long-test-password-123"},
    ).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def test_customer_ticket_lifecycle_and_duplicate_email():
    email, headers = register_customer()
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Duplicate",
            "password": "long-test-password-123",
        },
    )
    assert duplicate.status_code == 409
    created = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": "Account access issue",
            "description": "Reset link expired",
            "priority": "high",
        },
    )
    assert created.status_code == 201
    ticket = created.json()
    assert ticket["status"] == "open"
    assert (
        client.get("/api/v1/tickets", headers=headers).json()[0]["id"] == ticket["id"]
    )
    assert (
        client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers).status_code
        == 200
    )
    comment = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=headers,
        json={"body": "I can provide more details."},
    )
    assert comment.status_code == 201
    assert (
        len(
            client.get(
                f"/api/v1/tickets/{ticket['id']}/history", headers=headers
            ).json()
        )
        == 1
    )


def test_login_rejects_bad_password():
    email, _ = register_customer()
    response = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "incorrect-password"}
    )
    assert response.status_code == 401
