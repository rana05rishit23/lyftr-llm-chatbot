import pytest


@pytest.mark.asyncio
async def test_failover_single_key(client):
    # Simulate key_1 returning 429 -> should fail over to key_2
    headers = {"X-Simulate-Failure": "key_1=429"}
    payload = {"session_id": "failover-sess-1", "message": "Test failover single key"}
    response = await client.post("/chat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1
    assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"


@pytest.mark.asyncio
async def test_failover_server_error(client):
    # Simulate key_1 returning 500 -> should fail over to key_2
    headers = {"X-Simulate-Failure": "key_1=500"}
    payload = {"session_id": "failover-sess-2", "message": "Test failover server error"}
    response = await client.post("/chat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1


@pytest.mark.asyncio
async def test_all_keys_fail_503(client):
    session_id = "failover-sess-all"
    headers = {"X-Simulate-Failure": "*=429"}
    payload = {"session_id": session_id, "message": "Test all keys failing"}
    response = await client.post("/chat", json=payload, headers=headers)
    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "all providers unavailable"

    # Verify that failed 503 request was NOT added to session history
    hist_resp = await client.get(f"/sessions/{session_id}/messages")
    assert hist_resp.status_code == 404
