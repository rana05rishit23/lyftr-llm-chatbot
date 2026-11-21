# Lyftr AI — Full-Stack LLM Chatbot with Key Failover and Response Caching

Production-grade full-stack conversational AI application built with **React**, **FastAPI**, **LiteLLM**, and **SQLite**, implementing automatic multi-key failover and deterministic response caching.

---

## 1. Live URLs

- **Frontend:** `[DEPLOYED_FRONTEND_URL]` *(e.g. Vercel / Netlify)*
- **Backend:** `[DEPLOYED_BACKEND_URL]` *(e.g. Render / Railway)*
- **API Health Check:** `[DEPLOYED_BACKEND_URL]/health`
- **Demo Video:** `[LINK_TO_2-3_MIN_DEMO_VIDEO]`

---

## 2. Run locally: with Docker and without

### Option A: With Docker (Recommended)

Prerequisites: Docker & Docker Compose installed.

```bash
# 1. Clone repository
git clone https://github.com/rana05rishit23/lyftr-llm-chatbot.git
cd lyftr-llm-chatbot

# 2. Configure environment variables
cp .env.example .env
# Edit .env with your LLM_API_KEYS (e.g. Gemini API keys)

# 3. Start stack locally with Makefile
make up
```

- **Frontend UI:** `http://localhost:3000`
- **Backend API:** `http://localhost:8000`
- **API Documentation:** `http://localhost:8000/docs`

To stop the containers:
```bash
make down
```

### Option B: Without Docker

#### 1. Backend (Python 3.11+)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
cp ../.env.example .env

# Run FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend (Node.js 18+)

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

#### 3. Run Backend Test Suite

```bash
python -m pytest backend/tests -v
```

---

## 3. Design decisions: key fallback, caching, SQLite session storage

### A. Key Pool & Automatic Fallback
- **Pool Management:** Configured via `LLM_API_KEYS` containing at least 2 comma-separated keys. Each key is deterministically assigned an identifier (`key_1`, `key_2`, ...).
- **Graceful Failover:** When a provider encounters HTTP 429 (rate limits), quota exhaustion, or 5xx server errors, the gateway transparently routes the request to the next available key in the pool.
- **Failover Accounting:** The system reports `key_id` (the key that answered) and `fallback_attempts` (how many keys failed before success). `key_id` is set to `null` on cache hits to avoid attributing cached responses to any specific key.
- **Resilience:** If every key in the pool fails, the service returns a clean HTTP 503 `{"detail": "all providers unavailable"}` without recording any partial or broken messages to the database.

### B. Response Caching
- **Deterministic Cache Key:** Powered by LiteLLM's local cache. The cache key is computed from `model` + the complete ordered message history (`system_prompt` + previous turns + current message).
- **Zero-Latency Hits:** Identical first messages across different sessions immediately resolve to `LLM_CACHE`.
- **Cache Contract:** Cache hits return identical reply text, preserved input/output token counts from the original request, `key_id = null`, and `fallback_attempts = 0`. Different messages or conversation branches always bypass the cache and execute live inference.

### C. SQLite Session Storage
- **Lightweight & Self-Contained:** Zero external infrastructure dependencies (no Redis or PostgreSQL).
- **Container Persistence:** Database resides under a Docker named volume (`/data/app.db`) mapped to `DATABASE_URL`, ensuring session history persists across container restarts and redeployments.
- **Session Isolation:** All turns are grouped by client-generated `session_id`. Messages from session A never leak into session B.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

### A. How to Verify Automatic Key Failover
Use the built-in UI Failover simulation toolbar, or send the `X-Simulate-Failure` header via `curl`:

```bash
# 1. Simulate key_1 returning 429: should fail over to key_2 (returns 200, key_id="key_2")
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "test-sim-1", "message": "Hello from curl"}'

# 2. Simulate all keys failing: returns 503 {"detail": "all providers unavailable"}
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "test-sim-2", "message": "Will fail"}'
```

### B. How to Verify Response Caching
1. In the web interface (or `curl`), send `"What is the capital of France?"`.
   - Result: Shows `LIVE_INFERENCE`, `key_id = "key_1"`, and response latency (e.g., `812 ms`).
2. Refresh the browser page (initiating a new session) and ask the identical question: `"What is the capital of France?"`.
   - Result: Instantly returns with `LLM_CACHE`, `key_id = null`, and latency under `10 ms`.
3. Ask a modified question: `"What is the capital of Germany?"`.
   - Result: Resolves via `LIVE_INFERENCE`.

### C. How to Verify Token Tracking
- Every assistant message displays its prompt tokens (`meta-input-tokens`) and completion tokens (`meta-output-tokens`).
- Token counts are calculated **per-request only** (never an accumulated running total), fulfilling the strict assignment specification.

---

## 5. Setup Used: your editor and AI tools

- **Editor & IDE:** Visual Studio Code on Windows 11.
- **AI Coding Assistants:** Claude Opus 4.6 & Gemini 3.8 via Google DeepMind Antigravity agentic environment for rapid scaffolding, architectural reviews, and automated contract testing.
- **Tooling:** Python `pytest` & `httpx` for test-driven contract validation; Vite + React TypeScript for frontend rendering.

---

## 6. Bonus features (if any): what you added beyond the requirements and why

1. **Interactive Failover Simulation Toolbar in UI:**
   - *Why:* Allowed one-click demonstration of simulated rate limits (`key_1=429`), server errors (`key_1=500`), and total outages (`*=429`) directly in the UI without needing terminal `curl` commands during the video recording.
2. **Session Health & Key Pool Monitor:**
   - *Why:* Live header badges displaying configured active keys in the pool and LiteLLM cache status fetched dynamically from `GET /health`.
3. **Collapsible System Prompt Drawer:**
   - *Why:* Implemented the optional `system-prompt-input` field with instant session-level prompt customization (e.g. instructing the assistant to answer in specific personas or formats).
4. **Resilient Typing Indicator & Graceful Error Cards:**
   - *Why:* Ensured that any network glitch, 422 validation error, or 503 outage renders an accessible, user-friendly alert card instead of ever leaving the user on a blank screen.
