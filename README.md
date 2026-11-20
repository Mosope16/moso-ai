# Moso AI

**Moso AI** is a private, local-first AI assistant and research workspace running entirely on your own machine. No cloud accounts, no telemetry, no data leaving your device.

It is powered by **React 18**, **TypeScript**, **Vite**, **Tailwind CSS**, and a **FastAPI** backend with local **SQLite** persistence and **Ollama** inference.

---

## ✨ Features

### Chat & Inference
- **Local Ollama inference** — conversations stay on your machine.
- **Dual-model support** — `qwen3.5:4b` for complex reasoning, `qwen3.5:2b` for quick responses.
- **Model selection** — switch models per-conversation from the header dropdown or Settings modal; the active conversation immediately follows the selection.
- **Streaming responses** via Server-Sent Events with real-time token delivery and stop-generation support.
- **Thinking disabled** (`think: false`) — keeps time-to-first-token low on CPU-only hardware.

### Web Search & URL Fetching
- **Autonomous tool calling** — the model decides when external information is needed; tool execution is handled by the backend, not the frontend.
- **Web search** via DuckDuckGo and Wikipedia — no API keys required.
- **Optional providers** — Tavily (`TAVILY_API_KEY`) or Ollama-hosted search (`OLLAMA_API_KEY`) can be configured without code changes.
- **URL fetching** — sends a URL in chat and Moso AI retrieves and reads the actual page content.
- **GitHub repository inspection** — paste a GitHub URL and the model inspects file trees, READMEs, and source files.
- **SSRF protection** — all outbound requests are validated against loopback, private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), cloud metadata endpoints (`169.254.169.254`), `.internal` domains, and non-HTTP(S) schemes. Validation is re-applied on every redirect.
- **2 MB response cap and 12-second timeouts** — prevents memory exhaustion.
- **Web access toggle** — globe icon in the chat input bar toggles live retrieval on/off.
- **Live status indicators** — SSE `status` events show _Searching the web for…_ and _Reading web page…_ in real time.
- **Grounded citations** — verified source URLs appear as clickable chips beneath relevant responses.

### Evidence Grounding & Hallucination Prevention
- **Retrieval evidence contracts** — every web search, URL fetch, or document read produces a structured result with `success`, `tool`, `http_status`, `retrieved_content`, `error_type`, and more. Failed retrievals are never silently converted into successful ones.
- **Evidence gating** — before the model generates a response, the backend evaluates whether sufficient verified evidence was actually obtained. If not, the model is instructed to abstain rather than speculate.
- **Source attribution** — the model is told explicitly which information came from retrieval, which came from the user, and which is general knowledge.
- **Deterministic enforcement** — grounding rules are enforced in Python before any Ollama call. A system prompt alone is not the security boundary.

### Document Support
- **PDF, DOCX, XLSX, CSV** — upload documents to a conversation; the backend extracts text using `pypdf` and stdlib-only parsers (no external binary dependencies).
- **Document-grounded answers** — uploaded content is included in the evidence context.
- **20 MB upload limit** per file.

### Filesystem Agent *(written, integration in progress)*
- A complete local filesystem agent backend (`backend/filesystem/`) covering discovery, reading, writing, rename, move, copy, duplicate finding, document extraction, backup/undo, and terminal execution.
- Three-tier autonomy policy: auto-permitted reads/searches, auto-executed writes with backup, approval-required deletes and sensitive-path operations.
- Sensitive path protection: `.ssh`, `.gnupg`, `.aws`, browser profiles, `.env`, shell history, private key files.
- bwrap sandbox (`/usr/bin/bwrap`) tested on Arch Linux — masks `~/.ssh` and other sensitive directories with tmpfs during sandboxed execution.
- **Status:** backend package written; `main.py` integration, frontend approval UI, and test suite are next.

### Persistence & Data Integrity
- **SQLite** at `backend/moso.db` — all conversations, messages, and documents stored locally.
- **Pre-generation user message persistence** — user messages are written to SQLite before streaming begins, so a stream interruption never loses the user turn.
- **UUID-based IDs** (`conv_<uuid>`, `msg_<uuid>`) — no timestamp collisions.
- **Chronological ordering** by `created_at ASC, rowid ASC`.
- **Full conversation management** — create, list, rename, delete with cascade.

### Research Workspaces *(Projects)*
- Create named research projects with notes and document attachments.
- Activity feed per project.

### Auth & Access Control
- Optional `MOSO_ACCESS_PASSWORD` — when set, all API endpoints require a session cookie obtained via `POST /api/v1/auth/login`. The health endpoint is always public.
- Cookie-based session, logout clears the session.

### Privacy & Zero Telemetry
- All prompts, completions, and histories remain local.
- No third-party analytics, no external model APIs unless you explicitly configure them.

---

## 🖥️ System Requirements

| Component | Requirement |
|---|---|
| OS | Arch Linux (tested), other Linux distributions should work |
| CPU | Intel Core i5 or better (no GPU required) |
| RAM | 8 GB minimum; 16 GB recommended for `qwen3.5:4b` |
| Ollama | Latest stable — `ollama.com` |
| Python | 3.11+ (project tested on 3.14) |
| Node.js | 18+ |
| bwrap | `bubblewrap` from your package manager (optional, for filesystem sandboxing) |

---

## 🚀 Setup

### 1. Install Ollama and pull models

```bash
# Install Ollama (follow https://ollama.com/download)
# Then pull the models:
ollama pull qwen3.5:4b   # default — better reasoning
ollama pull qwen3.5:2b   # lighter — faster responses
```

Confirm both are available:

```bash
ollama list
```

### 2. Install bwrap (optional — for filesystem sandboxing)

```bash
sudo pacman -S bubblewrap   # Arch Linux
# or: sudo apt install bubblewrap  (Debian/Ubuntu)
```

### 3. Set up the Python virtual environment

The project ships with a `.venv` already configured. If you are starting fresh:

```bash
cd "/path/to/Moso AI"
python -m venv .venv
.venv/bin/python -m ensurepip
.venv/bin/pip install fastapi uvicorn httpx pypdf pydantic
```

> **Note:** The venv may not have a `pip` binary. Use `.venv/bin/python -m pip` or `.venv/bin/python -m ensurepip` to bootstrap it.

### 4. Configure environment (optional)

Create a `.env` file in the project root to override defaults:

```env
# Default model (qwen3.5:4b or qwen3.5:2b)
MOSO_DEFAULT_MODEL=qwen3.5:4b

# Optional access password — restricts all API endpoints
# MOSO_ACCESS_PASSWORD=your-secure-password

# Optional web search providers
# TAVILY_API_KEY=tvly-...
# OLLAMA_API_KEY=...

# Ollama host (if not running on default port)
# OLLAMA_HOST=http://localhost:11434
```

Do **not** commit `.env` to version control.

### 5. Start the backend

```bash
cd "/path/to/Moso AI"
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

For development with auto-reload:

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 6. Start the frontend

```bash
npm install   # first time only
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## 🧪 Test Suites

```bash
# Core API, SQLite, SSE streaming
.venv/bin/python backend/test_suite.py

# Web search and URL fetching
.venv/bin/python backend/test_web_suite.py

# PDF and document extraction
.venv/bin/python backend/test_pdf_suite.py

# Public forwarding and SSRF protection
.venv/bin/python backend/test_public_forwarding_suite.py

# Evidence grounding and hallucination prevention
.venv/bin/python backend/test_evidence_grounding_suite.py
```

All suites must pass before committing backend changes.

**Current status:** 8/8 · 6/6 · 11/11 · 5/5 · 16/16 ✓

Frontend build:

```bash
npm run build   # must produce 0 errors
```

---

## 📡 API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/auth/status` | Returns whether a password is configured and whether the session is authenticated |
| `POST` | `/api/v1/auth/login` | Authenticate with `MOSO_ACCESS_PASSWORD`; sets session cookie |
| `POST` | `/api/v1/auth/logout` | Clear session cookie |

### Core

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health check — SQLite status, Ollama connectivity, default model |
| `GET` | `/api/v1/models` | List installed Ollama models |

### Conversations

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/conversations` | List all conversations, ordered by most recently updated |
| `POST` | `/api/v1/conversations` | Create a new conversation |
| `GET` | `/api/v1/conversations/{id}` | Get conversation with full chronological message history |
| `PATCH` | `/api/v1/conversations/{id}` | Rename conversation title or update active model |
| `DELETE` | `/api/v1/conversations/{id}` | Delete conversation and all associated messages |

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat` | Stream an assistant response via SSE with optional tool calling |

The chat endpoint accepts:

```json
{
  "conversation_id": "conv_...",
  "message": "What is the weather in Lagos?",
  "model": "qwen3.5:4b",
  "enable_web": true,
  "max_tokens": 512
}
```

SSE event types emitted:

| Event | Payload | Description |
|---|---|---|
| *(default)* | `{"token": "..."}` | Streaming token |
| `status` | `{"message": "Searching the web for..."}` | Tool execution status |
| `citations` | `[{"url": "...", "title": "...", "domain": "..."}]` | Grounded source citations |
| `done` | `{"message_id": "...", "model": "..."}` | Generation complete |
| `error` | `{"error": "..."}` | Structured error |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents` | Upload PDF/DOCX/XLSX/CSV to a conversation or project |
| `GET` | `/api/v1/conversations/{id}/documents` | List documents attached to a conversation |
| `GET` | `/api/v1/projects/{id}/documents` | List documents attached to a project |
| `DELETE` | `/api/v1/documents/{id}` | Delete an uploaded document |

### Direct Tool Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/tools/web-search` | Execute a web search directly (`query`, `max_results`) |
| `POST` | `/api/v1/tools/web-fetch` | Fetch and extract a web page directly (`url`) |
| `POST` | `/api/v1/tools/github-inspect` | Inspect a GitHub repository or file (`url`) |

### Research Projects

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/projects` | List all research projects |
| `POST` | `/api/v1/projects` | Create a project |
| `GET` | `/api/v1/projects/{id}` | Get project details |
| `PATCH` | `/api/v1/projects/{id}` | Update project title or description |
| `DELETE` | `/api/v1/projects/{id}` | Delete project |
| `GET` | `/api/v1/projects/{id}/notes` | List notes in a project |
| `POST` | `/api/v1/projects/{id}/notes` | Create a note |
| `PATCH` | `/api/v1/projects/{id}/notes/{note_id}` | Update a note |
| `DELETE` | `/api/v1/projects/{id}/notes/{note_id}` | Delete a note |
| `GET` | `/api/v1/projects/{id}/activity` | Project activity feed |

---

## 🗂️ Project Structure

```
Moso AI/
├── backend/
│   ├── main.py                        # FastAPI app — all routes, chat loop, tool calling
│   ├── moso.db                        # SQLite database (gitignored)
│   │
│   ├── verification/                  # Evidence grounding & hallucination prevention
│   │   ├── classifier.py              # Query intent and task-type classification
│   │   ├── prompt_builder.py          # System prompt construction per task type
│   │   ├── evidence_gating.py         # Pre-generation evidence evaluation
│   │   ├── claim_validator.py         # Post-generation claim checking
│   │   ├── verifier.py                # Response verifier
│   │   ├── reference_engine.py        # Source reference management
│   │   ├── context_manager.py         # Token budget and context window management
│   │   ├── bible_engine.py            # Retrieval evidence contract definitions
│   │   └── tools.py                   # Verification tool schemas
│   │
│   ├── web/                           # Web retrieval tools
│   │   ├── search.py                  # DuckDuckGo, Wikipedia, Tavily providers
│   │   ├── fetch.py                   # SSRF-safe URL fetcher and HTML extractor
│   │   ├── github.py                  # GitHub repository inspector
│   │   ├── security.py                # URL validation and SSRF defence
│   │   ├── evidence.py                # EvidenceContract schema
│   │   └── tools.py                   # Ollama tool schemas and dispatcher
│   │
│   ├── filesystem/                    # Local filesystem agent (integration in progress)
│   │   ├── security.py                # Path validation, autonomy policy, sensitive-path list
│   │   ├── sandbox.py                 # bwrap sandbox wrapper and terminal allowlist
│   │   ├── documents.py               # PDF, DOCX, XLSX, CSV, image metadata readers
│   │   ├── history.py                 # SQLite-backed backup and undo engine
│   │   ├── operations.py              # All 20 filesystem tool implementations
│   │   └── tools.py                   # Ollama tool schemas and dispatcher
│   │
│   ├── test_suite.py                  # Core API and persistence tests (8 tests)
│   ├── test_web_suite.py              # Web search and fetch tests (6 tests)
│   ├── test_pdf_suite.py              # Document extraction tests (11 tests)
│   ├── test_public_forwarding_suite.py # SSRF protection tests (5 tests)
│   └── test_evidence_grounding_suite.py # Evidence grounding tests (16 tests)
│
├── src/
│   ├── components/
│   │   ├── auth/TesterPasswordModal.tsx
│   │   ├── chat/ChatArea.tsx           # Main chat surface with SSE event handling
│   │   ├── chat/WelcomeScreen.tsx
│   │   ├── header/Header.tsx           # Model selector dropdown (desktop + mobile)
│   │   ├── input/ChatInput.tsx         # Message input with web toggle
│   │   ├── message/MessageItem.tsx     # Message renderer with citation chips
│   │   ├── message/MarkdownRenderer.tsx
│   │   ├── project/ProjectWorkspace.tsx
│   │   ├── settings/SettingsModal.tsx  # Model selection, web toggle, preferences
│   │   ├── sidebar/Sidebar.tsx
│   │   └── ui/                         # Badge, Button, Input, Modal primitives
│   │
│   ├── context/AppContext.tsx          # Global state — conversations, model, auth
│   ├── services/api.ts                 # Typed API client
│   ├── services/mockService.ts         # Local-storage mock (dev mode)
│   ├── types/index.ts                  # Shared TypeScript types
│   └── utils/                          # cn(), date helpers
│
├── .venv/                             # Python virtual environment (not committed)
├── .env                               # Local secrets (not committed)
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

---

## 🔒 Security Model

| Layer | Enforcement |
|---|---|
| Outbound web requests | URL validated in Python before every HTTP call and on every redirect |
| Private network access | Blocked: loopback, RFC-1918 ranges, link-local, cloud metadata |
| Filesystem access | Python path validation rejects traversal and symlink escape before any tool executes |
| Sensitive paths | `.ssh`, `.gnupg`, `.aws`, browser profiles, `.env`, shell history, `*.pem`, `*.key` are blocked |
| Terminal execution | Allowlist-only; `shell=True` is never used; arbitrary shell access is not granted to the model |
| bwrap sandbox | Sensitive directories masked with tmpfs during sandboxed terminal execution |
| System prompt | Used for behaviour guidance only — not the security boundary |
| Access password | `MOSO_ACCESS_PASSWORD` restricts all API routes via session cookie when set |

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `MOSO_DEFAULT_MODEL` | `qwen3.5:4b` | Default Ollama model identifier |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server base URL |
| `MOSO_ACCESS_PASSWORD` | *(unset)* | Optional API access password |
| `TAVILY_API_KEY` | *(unset)* | Optional Tavily search API key |
| `OLLAMA_API_KEY` | *(unset)* | Optional Ollama-hosted search API key |

---

## 🗺️ Roadmap

- [ ] Filesystem agent — `main.py` integration, approval SSE events, REST endpoints
- [ ] Frontend — `ApprovalCard` component for filesystem operation approval
- [ ] Frontend — `FileActivityPanel` with operation history and undo
- [ ] Filesystem agent — full test suite (`test_filesystem_suite.py`)
- [ ] Background task support (long-running filesystem operations)
- [ ] Voice input
- [ ] Mobile-optimised layout improvements

---

## 📄 Licence

Private repository — all rights reserved.
