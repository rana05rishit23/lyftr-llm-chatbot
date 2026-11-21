import pytest


@pytest.mark.asyncio
async def test_chat_success(client):
    payload = {
        "session_id": "test-session-1",
        "message": "What is the capital of France?",
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-1"
    assert "reply" in data and len(data["reply"]) > 0

    meta = data["metadata"]
    assert meta["resolution_source"] in ["LIVE_INFERENCE", "LLM_CACHE"]
    assert "gemini" in meta["model"] or len(meta["model"]) > 0
    assert meta["latency_ms"] >= 0
    assert meta["input_tokens"] > 0
    assert meta["output_tokens"] > 0
    assert meta["key_id"] in ["key_1", "key_2", None]
    assert meta["fallback_attempts"] >= 0


@pytest.mark.asyncio
async def test_chat_validation_empty_message(client):
    payload = {
        "session_id": "test-session-val",
        "message": "   ",
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_chat_validation_message_too_long(client):
    payload = {
        "session_id": "test-session-val",
        "message": "a" * 4001,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_chat_validation_missing_session_id(client):
    payload = {
        "message": "Hello without session",
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_failed_request_not_added_to_history(client):
    session_id = "test-session-failed"
    # Send an invalid request
    await client.post("/chat", json={"session_id": session_id, "message": "   "})
    # Check history endpoint: should return 404 because nothing was stored
    hist_resp = await client.get(f"/sessions/{session_id}/messages")
    assert hist_resp.status_code == 404
