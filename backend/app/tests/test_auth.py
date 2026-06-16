import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "L345678$",
        "first_name": "Login",
        "last_name": "User",
    })
    # Then login
    response = await client.post("/api/v1/auth/token", data={
        "username": "login@example.com",
        "password": "L345678$",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "L345678$",
        "first_name": "Wrong",
        "last_name": "Pass",
    })
    response = await client.post("/api/v1/auth/token", data={
        "username": "wrongpass@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(client: AsyncClient):
    # Register
    await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "L345678$",
        "first_name": "Me",
        "last_name": "User",
    })
    # Login
    login = await client.post("/api/v1/auth/token", data={
        "username": "me@example.com",
        "password": "L345678$",
    })
    token = login.json()["access_token"]

    # Hit /me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["first_name"] == "Me"
    assert "orgs" in data


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com",
        "password": "L345678$",
        "first_name": "Refresh",
        "last_name": "User",
    })
    login = await client.post("/api/v1/auth/token", data={
        "username": "refresh@example.com",
        "password": "L345678$",
    })
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()