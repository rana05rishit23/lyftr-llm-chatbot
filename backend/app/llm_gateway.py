import time
import json
import logging
import litellm
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException
from .config import settings

logger = logging.getLogger(__name__)

# Initialize LiteLLM in-memory cache
litellm.enable_cache(type="local")
litellm.drop_params = True


class AllProvidersUnavailable(HTTPException):
    def __init__(self):
        super().__init__(status_code=503, detail="all providers unavailable")


def parse_simulate_failure_header(header_val: str, configured_key_ids: List[str]) -> Dict[str, int]:
    """
    Parses 'key_1=429,key_2=500' or '*=429'
    Returns dict of {key_id: status_code}
    """
    sim_map: Dict[str, int] = {}
    if not header_val:
        return sim_map

    parts = [p.strip() for p in header_val.split(",") if p.strip()]
    for p in parts:
        if "=" not in p:
            continue
        target, code_str = p.split("=", 1)
        target = target.strip()
        try:
            code = int(code_str.strip())
        except ValueError:
            continue

        if target == "*":
            for kid in configured_key_ids:
                sim_map[kid] = code
        else:
            sim_map[target] = code
    return sim_map


def compute_cache_key(model: str, messages: List[Dict[str, str]]) -> str:
    """
    Deterministic cache key: model + full message list sent to LLM
    """
    return litellm.cache.get_cache_key(model=model, messages=messages)


async def execute_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    simulate_failure_header: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Executes completion with key failover, response caching, and failure simulation.
    Returns: (reply_text, metadata_dict)
    """
    target_model = model or settings.DEFAULT_MODEL
    key_pool = settings.key_pool
    configured_key_ids = [kid for kid, _ in key_pool]

    # Auto-detect provider if keys match known formats and model was left at default gemini
    if target_model == "gemini/gemini-2.0-flash":
        if any(k.startswith("gsk_") for _, k in key_pool):
            target_model = "groq/llama-3.3-70b-versatile"
            logger.info("Auto-detected Groq key format, routing to groq/llama-3.3-70b-versatile")
        elif any(k.startswith("sk-") and not k.startswith("gsk_") for _, k in key_pool):
            target_model = "openai/gpt-4o-mini"
            logger.info("Auto-detected OpenAI key format, routing to openai/gpt-4o-mini")

    # Parse failure simulations if enabled
    sim_failures: Dict[str, int] = {}
    if settings.ENABLE_FAILURE_SIMULATION and simulate_failure_header:
        sim_failures = parse_simulate_failure_header(simulate_failure_header, configured_key_ids)

    # 1. Check LiteLLM cache first
    cache_key = compute_cache_key(target_model, messages)
    start_time = time.perf_counter()

    cached_response = litellm.cache.get_cache(cache_key=cache_key)
    if cached_response is not None:
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        if isinstance(cached_response, dict):
            choices = cached_response.get("choices", [])
            if choices and isinstance(choices[0], dict):
                reply = choices[0].get("message", {}).get("content", "")
            elif choices and hasattr(choices[0], "message"):
                reply = getattr(choices[0].message, "content", "")
            else:
                reply = ""
            usage = cached_response.get("usage", {})
            if isinstance(usage, dict):
                in_tokens = usage.get("prompt_tokens", 0)
                out_tokens = usage.get("completion_tokens", 0)
            else:
                in_tokens = getattr(usage, "prompt_tokens", 0)
                out_tokens = getattr(usage, "completion_tokens", 0)
        else:
            reply = cached_response.choices[0].message.content or ""
            usage = getattr(cached_response, "usage", None)
            in_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            out_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        metadata = {
            "resolution_source": "LLM_CACHE",
            "model": target_model,
            "latency_ms": latency_ms,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "key_id": None,
            "fallback_attempts": 0,
        }
        return reply, metadata

    # 2. Cache MISS: Live inference with key pool failover
    fallback_attempts = 0
    last_exception = None

    for key_id, api_key in key_pool:
        # Check if this key should simulate failure
        if key_id in sim_failures:
            sim_status = sim_failures[key_id]
            logger.info(f"Simulating failure for {key_id}: status {sim_status}")
            fallback_attempts += 1
            last_exception = RuntimeError(f"Simulated error {sim_status} on {key_id}")
            continue

        try:
            # Check if using mock key in development/test
            if api_key.startswith("mock-") or api_key.startswith("test-"):
                # Mock inference response for testing without live credentials
                # Wait 20ms to simulate real inference latency
                await_time = 0.02
                time.sleep(await_time)
                reply_text = f"Mock response to: {messages[-1]['content']}"
                # Estimate token counts
                in_tok = sum(len(m.get("content", "").split()) * 2 for m in messages) + 10
                out_tok = len(reply_text.split()) * 2

                # Create ModelResponse to store in LiteLLM cache
                from litellm import ModelResponse, Choices, Message, Usage
                mock_resp = ModelResponse(
                    id=f"chatcmpl-{int(time.time()*1000)}",
                    choices=[Choices(message=Message(content=reply_text, role="assistant"))],
                    created=int(time.time()),
                    model=target_model,
                    usage=Usage(prompt_tokens=in_tok, completion_tokens=out_tok, total_tokens=in_tok + out_tok),
                )
                # Store in LiteLLM cache
                litellm.cache.add_cache(result=mock_resp, cache_key=cache_key)

                latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                metadata = {
                    "resolution_source": "LIVE_INFERENCE",
                    "model": target_model,
                    "latency_ms": latency_ms,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "key_id": key_id,
                    "fallback_attempts": fallback_attempts,
                }
                return reply_text, metadata

            # Real LiteLLM call
            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                api_key=api_key,
                temperature=0.2,
            )

            # Add to LiteLLM cache
            try:
                litellm.cache.add_cache(result=response, cache_key=cache_key)
            except Exception as cache_err:
                logger.warning(f"Failed to store in cache: {cache_err}")

            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            reply = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            in_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            out_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            metadata = {
                "resolution_source": "LIVE_INFERENCE",
                "model": target_model,
                "latency_ms": latency_ms,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "key_id": key_id,
                "fallback_attempts": fallback_attempts,
            }
            return reply, metadata

        except Exception as e:
            logger.warning(f"Key {key_id} failed with error: {e}. Failing over to next key...")
            fallback_attempts += 1
            last_exception = e
            continue

    # If all keys in pool failed
    logger.error("All API keys failed or were simulated to fail.")
    raise AllProvidersUnavailable()
