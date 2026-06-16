import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Helper — register a user and return their access token."""
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "L345678$",
        "first_name": "Test",
        "last_name": "User",
    })
    login = await client.post("/api/v1/auth/token", data={
        "username": email,
        "password": "L345678$",
    })
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_create_org_success(client: AsyncClient):
    token = await _register_and_login(client, "org_creator@example.com")
    response = await client.post(
        "/api/v1/orgs",
        json={"name": "Nairobi Chapel", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nairobi Chapel"
    assert data["slug"] == "nairobi-chapel"
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_create_org_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/orgs",
        json={"name": "Unauthorised Church", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_creator_becomes_super_admin(client: AsyncClient):
    token = await _register_and_login(client, "superadmin@example.com")
    await client.post(
        "/api/v1/orgs",
        json={"name": "Grace Church", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
        headers={"Authorization": f"Bearer {token}"},
    )
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    orgs = me.json()["orgs"]
    assert len(orgs) == 1
    assert orgs[0]["role"] == "super_admin"


@pytest.mark.asyncio
async def test_slug_auto_generated(client: AsyncClient):
    token = await _register_and_login(client, "slug@example.com")
    response = await client.post(
        "/api/v1/orgs",
        json={"name": "St. Peter's Church", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "st-peters-church"


@pytest.mark.asyncio
async def test_get_my_orgs(client: AsyncClient):
    token = await _register_and_login(client, "myorgs@example.com")
    await client.post(
        "/api/v1/orgs",
        json={"name": "My Church", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.get(
        "/api/v1/orgs/mine",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_cannot_access_other_org(client: AsyncClient):
    """Critical — cross-org isolation test."""
    token_a = await _register_and_login(client, "org_a@example.com")
    token_b = await _register_and_login(client, "org_b@example.com")

    # A creates an org
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Org A Church", "country": "KE",
              "timezone": "Africa/Nairobi", "currency": "KES"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    org_id = org.json()["id"]

    # B tries to access A's org — must get 403
    response = await client.get(
        f"/api/v1/orgs/{org_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403