# Moso AI

**Moso AI** is a personal, privacy-native AI assistant designed to run locally first, with optional cloud AI integration in the future.

Powered by **React 18**, **TypeScript**, **Vite**, **Tailwind CSS**, and a **FastAPI** backend with local **SQLite** persistence and **Ollama** inference (using **Qwen 3.5 2B** on CPU).

---

## 🌟 Key Features

### 1. Robust Persistence & Data Integrity
- **SQLite Database**: Persistent storage located at `backend/moso.db`.
- **Pre-Generation User Persistence**: User messages are immediately saved to SQLite before generation starts, preventing data loss on stream interruptions.
- **Reliable UUIDs**: All conversation and message IDs use UUIDs (`conv_<uuid>` and `msg_<uuid>`) instead of timestamp-based keys to eliminate collisions.
- **Chronological Ordering**: Ordered by `created_at ASC, rowid ASC` for determinism.
- **Full Conversation Management**:
  - `POST /api/v1/conversations`: Create conversation.
  - `GET /api/v1/conversations`: List all sessions sorted by `updated_at DESC` with message counts.
  - `GET /api/v1/conversations/{id}`: Retrieve session with full message history.
  - `PATCH /api/v1/conversations/{id}`: In-place title renaming.
  - `DELETE /api/v1/conversations/{id}`: Cascade deletion of conversation and messages.

### 2. High-Performance SSE Streaming & Cancellation
- **Proper Server-Sent Events (SSE)**: Standardized protocol sending `data: {"token": "..."}`, `event: done`, `data: [DONE]`, and structured `event: error`.
- **Stop Generation Support**: Immediately aborts upstream Ollama processing on client disconnect, saving any partial content generated so far without corrupting the database.
- **Structured Error Handling**: Backend failures (Ollama unreachable, missing models) yield structured SSE error events and HTTP 503/404 statuses rather than masking exceptions as ordinary assistant chat text.

### 3. CPU-Tuned Ollama Integration
- **Default Model**: Exact model identifier `qwen3.5:2b`.
- **Optimized for Intel Core i5 / Iris Xe**: Disables unnecessary internal thinking tokens (`think: false`), keeping responses snappy (under 1.5s time-to-first-token) and within a default 256-token limit.
- **Dynamic Model Retrieval**: `GET /api/v1/models` fetches installed models dynamically from Ollama.

### 4. Privacy & Zero Telemetry
- **Local-Only Operation**: All prompts, completions, and chat histories remain strictly local.
- **Separated Dev Mock Mode**: Mock mode is completely decoupled from real backend mode; browser LocalStorage is used for mocks, while SQLite is used for real execution. The UI transparently indicates the active storage mode.

---

## 🚀 Quickstart

### 1. Ensure Ollama is Running

Make sure Ollama is installed and running locally with `qwen3.5:2b`:

```bash
ollama list
# Should display qwen3.5:2b
```

### 2. Start the FastAPI Backend

Using the provided virtual environment:

```bash
# In the project root
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The backend health check will be accessible at:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 3. Start the Frontend

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Run the Automated Verification Suite

Run the full end-to-end test suite verifying all routes, SQLite persistence, SSE streaming, and error handling:

```bash
.venv/bin/python backend/test_suite.py
.venv/bin/python backend/test_stop_cancellation.py
```

### 5. Build for Production

```bash
npm run build
```
The optimized bundle will be created in `dist/`.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health, SQLite status, and Ollama connectivity |
| `GET` | `/api/v1/models` | List locally installed Ollama models dynamically |
| `GET` | `/api/v1/conversations` | List all conversations ordered by recent activity |
| `POST` | `/api/v1/conversations` | Create a new conversation |
| `GET` | `/api/v1/conversations/{id}` | Get conversation with all chronological messages |
| `PATCH` | `/api/v1/conversations/{id}` | Update / rename conversation title |
| `DELETE` | `/api/v1/conversations/{id}` | Delete conversation and cascade delete messages |
| `POST` | `/api/v1/chat` | Stream assistant completion using Server-Sent Events |
# moso-ai
