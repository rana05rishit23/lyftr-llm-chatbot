import pytest


@pytest.mark.asyncio
async def test_cache_hit_on_same_first_message(client):
    msg = "Explain photosynthesis in one sentence."

    # Call 1 in Session 1: Should be LIVE_INFERENCE
    resp1 = await client.post("/chat", json={"session_id": "cache-sess-1", "message": msg})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert data1["metadata"]["key_id"] in ["key_1", "key_2"]
    reply1 = data1["reply"]

    # Call 2 in a new Session 2 with the identical first message: Must return LLM_CACHE
    resp2 = await client.post("/chat", json={"session_id": "cache-sess-2", "message": msg})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["metadata"]["resolution_source"] == "LLM_CACHE"
    assert data2["metadata"]["key_id"] is None
    assert data2["metadata"]["fallback_attempts"] == 0
    assert data2["reply"] == reply1  # Identical reply text
    # Latency of cache hit should be faster
    assert data2["metadata"]["latency_ms"] <= data1["metadata"]["latency_ms"] + 50


@pytest.mark.asyncio
async def test_different_message_never_comes_from_cache(client):
    resp1 = await client.post("/chat", json={"session_id": "diff-sess-1", "message": "Tell me a joke."})
    assert resp1.status_code == 200
    assert resp1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    resp2 = await client.post("/chat", json={"session_id": "diff-sess-2", "message": "Tell me a completely different story."})
    assert resp2.status_code == 200
    assert resp2.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
