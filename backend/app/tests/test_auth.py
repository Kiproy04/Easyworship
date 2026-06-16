import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    """Verify that your baseline system health check endpoint responds successfully."""
    response = await client.get("/health")  # Switch this path to a real baseline endpoint you have (like /health, /, or /api/v1/auth/me)
    
    # If the endpoint exists and works, it should return a 200 OK or a 401 Unauthorized (if fully guarded)
    # Change this assertion to match your expected baseline endpoint result behavior!
    assert response.status_code in [200, 401]