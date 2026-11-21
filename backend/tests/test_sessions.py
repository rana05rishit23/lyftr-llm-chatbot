import pytest


@pytest.mark.asyncio
async def test_session_not_found(client):
    response = await client.get("/sessions/unknown-session-xyz/messages")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "session not found"


@pytest.mark.asyncio
async def test_multi_turn_history(client):
    session_id = "test-multi-turn-sess"

    # Turn 1
    resp1 = await client.post("/chat", json={"session_id": session_id, "message": "My name is Alice."})
    assert resp1.status_code == 200

    # Turn 2
    resp2 = await client.post("/chat", json={"session_id": session_id, "message": "What is my name?"})
    assert resp2.status_code == 200

    # Retrieve history
    hist_resp = await client.get(f"/sessions/{session_id}/messages")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["session_id"] == session_id

    messages = hist["messages"]
    assert len(messages) == 4  # 2 user + 2 assistant
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "My name is Alice."
    assert messages[1]["role"] == "assistant"
    assert "metadata" in messages[1]
    assert "resolution_source" in messages[1]["metadata"]
    assert "input_tokens" in messages[1]["metadata"]
    assert "output_tokens" in messages[1]["metadata"]

    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "What is my name?"
    assert messages[3]["role"] == "assistant"


@pytest.mark.asyncio
async def test_session_isolation(client):
    # Session A
    await client.post("/chat", json={"session_id": "sess-A", "message": "Message for A"})
    # Session B
    await client.post("/chat", json={"session_id": "sess-B", "message": "Message for B"})

    hist_a = (await client.get("/sessions/sess-A/messages")).json()["messages"]
    hist_b = (await client.get("/sessions/sess-B/messages")).json()["messages"]

    assert len(hist_a) == 2
    assert hist_a[0]["content"] == "Message for A"

    assert len(hist_b) == 2
    assert hist_b[0]["content"] == "Message for B"
