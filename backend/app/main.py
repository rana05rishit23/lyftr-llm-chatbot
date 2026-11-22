import logging
import litellm
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .config import settings
from .db import init_db, save_message, get_session_history, get_llm_conversation_messages
from .schemas import (
    HealthResponse,
    ChatRequest,
    ChatResponse,
    ChatMetadata,
    SessionHistoryResponse,
)
from .llm_gateway import execute_chat, AllProvidersUnavailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database on startup
    await init_db()
    yield


app = FastAPI(
    title="Lyftr LLM Chatbot Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health", response_model=HealthResponse)
async def get_health():
    """
    Returns 200 once app is running, DB is reachable, and key pool loaded.
    """
    keys_count = len(settings.key_pool)
    return HealthResponse(
        status="ok",
        keys_configured=keys_count,
        cache_enabled=True,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    x_simulate_failure: str = Header(None, alias="X-Simulate-Failure"),
):
    """
    POST /chat:
    - Multi-turn conversation state stored in SQLite per session_id.
    - Automatic key pool failover (HTTP 429/5xx).
    - Response caching with LLM_CACHE vs LIVE_INFERENCE reporting.
    - X-Simulate-Failure header support for testing failovers.
    """
    # 1. Fetch conversation history for this session from SQLite
    history = await get_llm_conversation_messages(req.session_id)

    # 2. Prepare message list for LLM context:
    # System prompt + history + new user message
    sys_prompt = req.system_prompt or settings.DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": req.message})

    # 3. Execute via LiteLLM gateway (with caching & key failover)
    # If all keys fail, execute_chat raises AllProvidersUnavailable (503)
    reply, metadata_dict = await execute_chat(
        messages=messages,
        simulate_failure_header=x_simulate_failure,
    )

    # 4. Only after successful completion, record user & assistant messages to SQLite
    await save_message(
        session_id=req.session_id,
        role="user",
        content=req.message,
    )

    # Metadata for stored assistant message includes resolution_source, input_tokens, output_tokens
    stored_meta = {
        "resolution_source": metadata_dict["resolution_source"],
        "input_tokens": metadata_dict["input_tokens"],
        "output_tokens": metadata_dict["output_tokens"],
    }
    await save_message(
        session_id=req.session_id,
        role="assistant",
        content=reply,
        metadata=stored_meta,
    )

    return ChatResponse(
        session_id=req.session_id,
        reply=reply,
        metadata=ChatMetadata(**metadata_dict),
    )


@app.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_messages_endpoint(session_id: str):
    """
    Returns stored history of one session from SQLite, oldest first, without system prompt.
    Returns 404 if session is unknown.
    """
    history = await get_session_history(session_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )

    return SessionHistoryResponse(
        session_id=session_id,
        messages=history,
    )


@app.get("/debug-llm")
async def debug_llm():
    import httpx
    target_model = settings.DEFAULT_MODEL
    key_pool = settings.key_pool
    results = []
    available_models = []

    # Check available Groq models for key_1
    if key_pool:
        first_key = key_pool[0][1]
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {first_key}"},
                    timeout=10,
                )
                if res.status_code == 200:
                    available_models = [m["id"] for m in res.json().get("data", [])]
                else:
                    available_models = [f"Status {res.status_code}: {res.text}"]
        except Exception as groq_err:
            available_models = [f"Fetch error: {groq_err}"]

    for kid, k in key_pool:
        # Try first available model, or fallback
        test_model = f"groq/{available_models[0]}" if (available_models and not available_models[0].startswith("Status")) else "groq/llama3-8b-8192"
        try:
            resp = await litellm.acompletion(
                model=test_model,
                messages=[{"role": "user", "content": "hi"}],
                api_key=k,
                max_tokens=5,
            )
            results.append({"key_id": kid, "status": "ok", "reply": resp.choices[0].message.content, "model": test_model})
        except Exception as e:
            results.append({"key_id": kid, "status": "error", "error": str(e), "type": type(e).__name__, "model": test_model})
            
    return {"available_models": available_models, "results": results}


