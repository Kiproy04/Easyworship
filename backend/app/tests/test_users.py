import pytest
from httpx import AsyncClient
from faker import Faker

fake = Faker()

@pytest.mark.asyncio
async def test_register_new_user_success(client: AsyncClient):
    """Verify that a new user can register with a complete profile."""
    payload = {
        "email": fake.email(),
        "password": "fakepassword123$",
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "phone": fake.phone_number()
    }
    
    # Execute the request against the sandboxed test server
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Depending on your FastAPI router setup, this might be 200 OK or 201 Created
    assert response.status_code in [200, 201]
    
    data = response.json()
    
    # Verify the database saved and returned the correct data
    assert data["email"] == payload["email"]
    assert data["first_name"] == payload["first_name"]
    assert data["last_name"] == payload["last_name"]
    assert "id" in data
    
    # 🛡️ SECURITY CHECK: Ensure the hashed password doesn't leak in the response!
    assert "password" not in data
    assert "hashed_password" not in data

@pytest.mark.asyncio
async def test_register_duplicate_user_fails(client: AsyncClient):
    """Verify that registering an already existing email returns an error."""
    payload = {
        "email": "duplicate@example.com",
        "password": "L345678$",
        "first_name": "Clone",
        "last_name": "Two",
        "phone": "0799999999"
    }
    
    # 1. Register the user successfully the first time
    first_response = await client.post("/api/v1/auth/register", json=payload)
    assert first_response.status_code in [200, 201]
    
    # 2. Attempt to register the exact same user again
    second_response = await client.post("/api/v1/auth/register", json=payload)
    
    # The API should gracefully reject this with a 400 (or 409 Conflict)
    assert second_response.status_code in [400, 409]
    
    # Optional: Verify the error message contains a specific keyword
    error_detail = second_response.json().get("detail", "").lower()
    assert "registered" in error_detail or "exists" in error_detail