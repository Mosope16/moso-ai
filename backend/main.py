"""
Moso AI — FastAPI Backend with SQLite Persistence, Ollama Integration, and Academic Research Workspaces
Local-first AI assistant and research workspace backend supporting Qwen 3.5 2B inference on CPU.
"""

import os
import io
import re
import json
import sqlite3
import datetime
import uuid
import asyncio
import secrets
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, Form, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx
import pypdf

# ---------------------------------------------------------
# Environment & Security Configuration
# ---------------------------------------------------------
def load_env_file():
    """Load key-value pairs from .env in project root if available."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_env_file()

DB_FILE = os.path.join(os.path.dirname(__file__), "moso.db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = "qwen3.5:2b"
DEFAULT_MAX_TOKENS = 256
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB limit

# Tester Access Password (set via MOSO_ACCESS_PASSWORD in environment or .env)
MOSO_ACCESS_PASSWORD = os.getenv("MOSO_ACCESS_PASSWORD", "").strip()

# Active In-Memory Sessions & Rate Limiter
ACTIVE_SESSIONS: dict[str, dict] = {}
SESSION_DURATION_HOURS = 24
RATE_LIMIT_STORE: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 120  # generous 120 reqs/min for interactive chat & polling
INFERENCE_SEMAPHORE = asyncio.Semaphore(2)  # Limit concurrent local CPU generations to 2

def check_rate_limit(client_ip: str) -> bool:
    """Sliding-window IP rate limiter to mitigate DoS/flooding attacks."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = [t for t in RATE_LIMIT_STORE.get(client_ip, []) if t > cutoff]
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        RATE_LIMIT_STORE[client_ip] = timestamps
        return False
    timestamps.append(now)
    RATE_LIMIT_STORE[client_ip] = timestamps
    return True

def is_valid_session(token: Optional[str]) -> bool:
    """Validate session token against in-memory session registry and expiration."""
    if not token or token not in ACTIVE_SESSIONS:
        return False
    session = ACTIVE_SESSIONS[token]
    if datetime.datetime.now(datetime.timezone.utc) > session["expires_at"]:
        del ACTIVE_SESSIONS[token]
        return False
    return True

def get_token_from_request(request: Request) -> Optional[str]:
    """Extract session token from Authorization header, X-Moso-Access-Token, or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    custom_header = request.headers.get("X-Moso-Access-Token")
    if custom_header:
        return custom_header.strip()
    cookie_token = request.cookies.get("moso_session")
    if cookie_token:
        return cookie_token.strip()
    return None

# Default undergraduate engineering level research assistant prompt
DEFAULT_RESEARCH_SYSTEM_PROMPT = """You are Moso Research Assistant, an expert academic and technical research partner.
Your role is to assist with rigorous literature analysis, engineering research, experimental methodologies, and technical synthesis at an undergraduate engineering level.

CORE BEHAVIORAL DIRECTIVES:
1. ACADEMIC & TECHNICAL RIGOR: Explain technical concepts clearly, precisely, and mathematically. When discussing equations, statistical measures, or algorithms, use formal notation and standard definitions.
2. CITATION & EVIDENCE GROUNDING: When document excerpts are provided, ground your answers in the cited facts. Cite the document filename and page number for every factual claim.
3. ADMIT UNVERIFIED FACTS: Never hallucinate or fabricate experimental results, author citations, or benchmark scores. If the provided papers/documents do not contain enough evidence, explicitly state: "The attached document(s) do not contain sufficient evidence to verify this claim."
4. STRUCTURED ANALYSIS: Distinguish clearly between:
   - Established Empirical Evidence (stated directly in the source documents)
   - Methodological Assumptions & Hypotheses
   - Recommendations, Caveats & Limitations
5. CODING & EXPERIMENTATION: When assisting with Python, PyTorch, dataset preprocessing, or model evaluation (confusion matrix, ROC-AUC, precision, recall, F1-score), provide clean, idiomatic, and robust code snippets with comments. Do not assume automatic code execution.
6. MATHEMATICAL FORMATTING: Express all equations and formulas in LaTeX notation (using \\( ... \\) for inline math and \\[ ... \\] for display/aligned equations)."""

app = FastAPI(
    title="Moso AI Backend",
    version="0.2.0",
    description="Local-first FastAPI backend with SQLite persistence, academic research workspaces, and local PDF document chat",
)

# ---------------------------------------------------------
# Security and Public Testing ASGI Middleware
# ---------------------------------------------------------
class SecurityAndAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Preflight OPTIONS requests must pass through for CORS headers
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "127.0.0.1"

        # Rate Limiting
        if not check_rate_limit(client_ip):
            response = JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Please wait a moment before sending more requests.", "code": "RATE_LIMIT_EXCEEDED"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Credentials": "true",
                },
            )
            await response(scope, receive, send)
            return

        # Tester Password Authentication Check
        configured_password = os.getenv("MOSO_ACCESS_PASSWORD", "").strip()
        public_paths = {
            "/api/v1/auth/status",
            "/api/v1/auth/login",
            "/api/v1/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        }

        if configured_password and path.startswith("/api/v1") and path not in public_paths:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode("latin-1")
            custom_header = headers.get(b"x-moso-access-token", b"").decode("latin-1")
            cookie_header = headers.get(b"cookie", b"").decode("latin-1")

            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            elif custom_header:
                token = custom_header.strip()
            elif cookie_header:
                for cookie_part in cookie_header.split(";"):
                    if "=" in cookie_part:
                        k, v = cookie_part.strip().split("=", 1)
                        if k.strip() == "moso_session":
                            token = v.strip()
                            break

            if not is_valid_session(token):
                response = JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized. Tester access password required.", "code": "AUTH_REQUIRED"},
                    headers={
                        "WWW-Authenticate": "Bearer",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Credentials": "true",
                    },
                )
                await response(scope, receive, send)
                return

        # Add security headers to response
        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                out_headers = list(message.get("headers", []))
                out_headers.append((b"x-content-type-options", b"nosniff"))
                out_headers.append((b"x-frame-options", b"DENY"))
                out_headers.append((b"x-xss-protection", b"1; mode=block"))
                message["headers"] = out_headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)

# Register pure ASGI security & auth middleware
app.add_middleware(SecurityAndAuthMiddleware)

# Enable CORS for local Vite development and desktop environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # 1. Projects table
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 2. Project Notes & Findings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_notes (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'note',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_notes_project ON project_notes(project_id, category)")

    # 3. Project Activity Timeline
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_activity (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_activity_project ON project_activity(project_id, created_at)")

    # 4. Conversations table
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model TEXT NOT NULL,
            project_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # 5. Messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    # 6. Documents table
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            project_id TEXT,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            extracted_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # 7. Document Chunks table
    c.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            conversation_id TEXT,
            project_id TEXT,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # 8. Schema Migrations (safe alter table for existing databases)
    for tbl, col, col_type in [
        ("conversations", "project_id", "TEXT"),
        ("documents", "project_id", "TEXT"),
        ("document_chunks", "project_id", "TEXT"),
        ("messages", "citations", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Ensure conversation_id in documents and document_chunks is nullable (migrating older schema)
    try:
        c.execute("PRAGMA table_info(documents)")
        doc_cols = {row[1]: row[3] for row in c.fetchall()}
        if doc_cols.get("conversation_id") == 1:
            c.execute("""
                CREATE TABLE IF NOT EXISTS documents_new (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    project_id TEXT,
                    filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    page_count INTEGER NOT NULL,
                    extracted_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                INSERT INTO documents_new (id, conversation_id, project_id, filename, file_size, page_count, extracted_text, created_at)
                SELECT id, conversation_id, project_id, filename, file_size, page_count, extracted_text, created_at FROM documents
            """)
            c.execute("DROP TABLE documents")
            c.execute("ALTER TABLE documents_new RENAME TO documents")
    except Exception as e:
        print("Note: documents migration notice:", e)

    try:
        c.execute("PRAGMA table_info(document_chunks)")
        chk_cols = {row[1]: row[3] for row in c.fetchall()}
        if chk_cols.get("conversation_id") == 1:
            c.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks_new (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    conversation_id TEXT,
                    project_id TEXT,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                INSERT INTO document_chunks_new (id, document_id, conversation_id, project_id, chunk_index, page_number, content)
                SELECT id, document_id, conversation_id, project_id, chunk_index, page_number, content FROM document_chunks
            """)
            c.execute("DROP TABLE document_chunks")
            c.execute("ALTER TABLE document_chunks_new RENAME TO document_chunks")
    except Exception as e:
        print("Note: document_chunks migration notice:", e)

    # 9. Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_order ON messages(conversation_id, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_documents_conv ON documents(conversation_id, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_documents_proj ON documents(project_id, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_conv ON document_chunks(conversation_id, document_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_proj ON document_chunks(project_id, document_id)")

    # 9. SQLite FTS5 Full-Text Search Virtual Table
    try:
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                conversation_id UNINDEXED,
                project_id UNINDEXED,
                content
            )
        """)
        # Backfill existing chunks into FTS5 if any are missing
        c.execute("""
            INSERT INTO document_chunks_fts (chunk_id, document_id, conversation_id, project_id, content)
            SELECT id, document_id, conversation_id, project_id, content
            FROM document_chunks
            WHERE id NOT IN (SELECT chunk_id FROM document_chunks_fts)
        """)
    except Exception as e:
        print("Note: SQLite FTS5 initialization notice:", e)

    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------

class MessageInput(BaseModel):
    role: str
    content: str
    id: Optional[str] = None
    created_at: Optional[str] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"
    model: Optional[str] = DEFAULT_MODEL
    project_id: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL
    messages: List[MessageInput]
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS
    temperature: Optional[float] = 0.7


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = ""
    instructions: Optional[str] = ""
    custom_instructions: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    custom_instructions: Optional[str] = None


class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    category: Optional[str] = "note"  # 'note', 'finding', 'experiment', 'methodology'


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


def log_project_activity(conn: sqlite3.Connection, project_id: str, action: str, details: str):
    """Record an audit trail activity entry for a project."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO project_activity (id, project_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (f"act_{uuid.uuid4()}", project_id, action, details, now),
    )


# ---------------------------------------------------------
# Document Retrieval & Chunking Helpers
# ---------------------------------------------------------

def chunk_text_overlapping(page_text: str, page_number: int, target_words: int = 240, overlap_words: int = 40):
    """
    Split text into sensible overlapping text passages, preserving paragraph structure
    and associating every chunk with its page number.
    """
    words = page_text.split()
    if not words:
        return []

    if len(words) <= target_words:
        return [(page_number, " ".join(words))]

    step = max(1, target_words - overlap_words)
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + target_words]
        chunks.append((page_number, " ".join(chunk_words)))
        if i + target_words >= len(words):
            break
        i += step

    return chunks


def retrieve_relevant_chunks(
    conv_id: Optional[str] = None,
    query: str = "",
    max_words: int = 1200,
    project_id: Optional[str] = None,
) -> List[dict]:
    """
    Retrieve relevant passages using SQLite FTS5 (BM25 ranking) with fallback
    to keyword frequency scoring. Never returns chunks from other conversations or projects.
    """
    # Compatibility guard if caller passed query in project_id position
    if project_id and len(project_id.split()) > 2 and not query:
        query = project_id
        project_id = None
    conn = get_db()
    c = conn.cursor()

    # Determine if conversation is associated with a project
    effective_project_id = project_id
    if conv_id and not effective_project_id:
        c.execute("SELECT project_id FROM conversations WHERE id = ?", (conv_id,))
        row = c.fetchone()
        if row and row["project_id"]:
            effective_project_id = row["project_id"]

    # 1. Fetch all candidate chunks for this context
    if effective_project_id and conv_id:
        c.execute("""
            SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.project_id = ? OR c.conversation_id = ?
            ORDER BY c.page_number ASC, c.chunk_index ASC
        """, (effective_project_id, conv_id))
    elif effective_project_id:
        c.execute("""
            SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.project_id = ?
            ORDER BY c.page_number ASC, c.chunk_index ASC
        """, (effective_project_id,))
    elif conv_id:
        c.execute("""
            SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.conversation_id = ?
            ORDER BY c.page_number ASC, c.chunk_index ASC
        """, (conv_id,))
    else:
        conn.close()
        return []

    rows = [dict(r) for r in c.fetchall()]
    if not rows:
        conn.close()
        return []

    total_words = sum(len(r["content"].split()) for r in rows)

    # 2. Try FTS5 BM25 Search if search terms exist
    clean_terms = [t for t in re.findall(r'\b[a-zA-Z0-9_]{3,}\b', query) if t.lower() not in {
        "the", "and", "for", "with", "that", "this", "what", "where", "when", "how", "why", "are", "can"
    }]
    fts_results = []
    if clean_terms:
        fts_match_query = " OR ".join(clean_terms)
        try:
            if effective_project_id and conv_id:
                c.execute("""
                    SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename, bm25(document_chunks_fts) as rank
                    FROM document_chunks_fts f
                    JOIN document_chunks c ON f.chunk_id = c.id
                    JOIN documents d ON c.document_id = d.id
                    WHERE document_chunks_fts MATCH ? AND (c.project_id = ? OR c.conversation_id = ?)
                    ORDER BY rank ASC
                """, (fts_match_query, effective_project_id, conv_id))
            elif effective_project_id:
                c.execute("""
                    SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename, bm25(document_chunks_fts) as rank
                    FROM document_chunks_fts f
                    JOIN document_chunks c ON f.chunk_id = c.id
                    JOIN documents d ON c.document_id = d.id
                    WHERE document_chunks_fts MATCH ? AND c.project_id = ?
                    ORDER BY rank ASC
                """, (fts_match_query, effective_project_id))
            else:
                c.execute("""
                    SELECT c.id, c.document_id, c.conversation_id, c.project_id, c.chunk_index, c.page_number, c.content, d.filename, bm25(document_chunks_fts) as rank
                    FROM document_chunks_fts f
                    JOIN document_chunks c ON f.chunk_id = c.id
                    JOIN documents d ON c.document_id = d.id
                    WHERE document_chunks_fts MATCH ? AND c.conversation_id = ?
                    ORDER BY rank ASC
                """, (fts_match_query, conv_id))
            fts_results = [dict(r) for r in c.fetchall()]
        except Exception:
            fts_results = []

    conn.close()

    # 3. If FTS5 returned results, accumulate within word budget preserving BM25 relevance rank
    if fts_results:
        selected = []
        accumulated_words = 0
        seen_ids = set()
        for chunk in fts_results:
            if chunk["id"] in seen_ids:
                continue
            seen_ids.add(chunk["id"])
            w_count = len(chunk["content"].split())
            if accumulated_words + w_count > max_words and selected:
                break
            selected.append(chunk)
            accumulated_words += w_count
        return selected

    # 4. Fallback: Term-frequency scoring across retrieved rows
    query_terms = [t.lower() for t in clean_terms]
    scored = []
    for r in rows:
        content_lower = r["content"].lower()
        score = sum(1 + 0.5 * min(content_lower.count(t), 4) for t in query_terms if t in content_lower)
        if score > 0:
            scored.append((score, r))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = []
        accumulated_words = 0
        for score, chunk in scored:
            w_count = len(chunk["content"].split())
            if accumulated_words + w_count > max_words and selected:
                break
            selected.append(chunk)
            accumulated_words += w_count
        return selected

    # Fallback default: all chunks in document order up to max_words
    selected = []
    accumulated_words = 0
    for chunk in rows:
        w_count = len(chunk["content"].split())
        if accumulated_words + w_count > max_words and selected:
            break
        selected.append(chunk)
        accumulated_words += w_count
    return selected


# ---------------------------------------------------------
# Ollama Helpers
# ---------------------------------------------------------

async def check_ollama_status() -> dict:
    """Check if Ollama service is reachable and query its installed models."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name") for m in models]
                has_default_model = any(DEFAULT_MODEL in name for name in model_names)
                return {
                    "connected": True,
                    "models": models,
                    "model_names": model_names,
                    "has_default_model": has_default_model,
                    "error": None,
                }
            return {
                "connected": False,
                "models": [],
                "model_names": [],
                "has_default_model": False,
                "error": f"Ollama HTTP {resp.status_code}",
            }
    except Exception as e:
        return {
            "connected": False,
            "models": [],
            "model_names": [],
            "has_default_model": False,
            "error": str(e),
        }


# ---------------------------------------------------------
# Authentication & Tester Access Endpoints
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    password: str


@app.get("/api/v1/auth/status")
async def get_auth_status(request: Request):
    """
    Report whether public tester password protection is enabled on this instance
    and whether the requesting client has an active authenticated session.
    GET /api/v1/auth/status
    """
    configured_password = os.getenv("MOSO_ACCESS_PASSWORD", "").strip()
    if not configured_password:
        return {"auth_required": False, "authenticated": True}

    token = get_token_from_request(request)
    is_auth = is_valid_session(token)
    return {
        "auth_required": True,
        "authenticated": is_auth,
    }


@app.post("/api/v1/auth/login")
async def login(req: LoginRequest, response: Response):
    """
    Authenticate against the tester access password.
    Returns a secure session token and sets an HTTP-only session cookie.
    POST /api/v1/auth/login
    """
    configured_password = os.getenv("MOSO_ACCESS_PASSWORD", "").strip()
    if not configured_password:
        return {"status": "ok", "auth_required": False, "token": "not_required"}

    if not secrets.compare_digest(req.password.strip(), configured_password):
        await asyncio.sleep(0.4)  # Small delay to mitigate brute force timing attacks
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Incorrect tester access password.", "code": "INVALID_PASSWORD"},
        )

    token = secrets.token_hex(32)
    now = datetime.datetime.now(datetime.timezone.utc)
    ACTIVE_SESSIONS[token] = {
        "created_at": now.isoformat(),
        "expires_at": now + datetime.timedelta(hours=SESSION_DURATION_HOURS),
    }

    response.set_cookie(
        key="moso_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=SESSION_DURATION_HOURS * 3600,
    )

    return {
        "status": "ok",
        "token": token,
        "expires_in_hours": SESSION_DURATION_HOURS,
    }


@app.post("/api/v1/auth/logout")
async def logout(request: Request, response: Response):
    """
    Invalidate the current session and clear session cookie.
    POST /api/v1/auth/logout
    """
    token = get_token_from_request(request)
    if token and token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
    response.delete_cookie("moso_session")
    return {"status": "ok"}


# ---------------------------------------------------------
# Core Health & Models Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/health")
async def health_check():
    """
    Check backend connectivity, Ollama status, and SQLite database health.
    GET /api/v1/health
    """
    ollama_info = await check_ollama_status()

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) as count FROM conversations")
        conv_count = c.fetchone()["count"]
        c.execute("SELECT COUNT(*) as count FROM projects")
        proj_count = c.fetchone()["count"]
        db_ok = True
    except Exception:
        conv_count = 0
        proj_count = 0
        db_ok = False
    finally:
        conn.close()

    is_healthy = db_ok and ollama_info["connected"]
    status_str = "ok" if is_healthy else ("degraded" if db_ok else "error")

    return {
        "status": status_str,
        "ollama_connected": ollama_info["connected"],
        "active_model": DEFAULT_MODEL,
        "model_available": ollama_info["has_default_model"],
        "models_count": len(ollama_info["models"]),
        "database": "sqlite",
        "database_connected": db_ok,
        "conversation_count": conv_count,
        "project_count": proj_count,
        "device_mode": "cpu",
        "version": "0.2.0",
    }


@app.get("/api/v1/models")
async def get_models():
    """
    Return available Ollama models.
    GET /api/v1/models
    """
    status_info = await check_ollama_status()
    installed_models = []

    for m in status_info.get("models", []):
        m_name = m.get("name", "")
        size_bytes = m.get("size", 0)
        size_gb = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "2.0 GB"
        is_default = (m_name == DEFAULT_MODEL) or (DEFAULT_MODEL in m_name)

        installed_models.append({
            "id": m_name,
            "name": f"Qwen 3.5 2B" if DEFAULT_MODEL in m_name else m_name,
            "size": size_gb,
            "is_default": is_default,
            "is_local": True,
            "description": "Default local-first SLM, optimized for CPU inference" if is_default else "Installed Ollama model",
            "modified_at": m.get("modified_at", ""),
        })

    if not installed_models:
        installed_models.append({
            "id": DEFAULT_MODEL,
            "name": "Qwen 3.5 2B (Expected)",
            "size": "2.0 GB",
            "is_default": True,
            "is_local": True,
            "description": "Local model (Service currently offline)",
            "modified_at": "",
        })

    return {
        "connected": status_info["connected"],
        "models": installed_models,
        "default_model": DEFAULT_MODEL,
        "error": status_info["error"],
    }


# ---------------------------------------------------------
# Project Workspace Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/projects")
async def list_projects():
    """
    List all research project workspaces with stats.
    GET /api/v1/projects
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            p.id, p.name, p.description, p.instructions, p.created_at, p.updated_at,
            (SELECT COUNT(*) FROM documents WHERE project_id = p.id) as document_count,
            (SELECT COUNT(*) FROM conversations WHERE project_id = p.id) as conversation_count,
            (SELECT COUNT(*) FROM project_notes WHERE project_id = p.id) as note_count
        FROM projects p
        ORDER BY p.updated_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.post("/api/v1/projects", status_code=status.HTTP_200_OK)
async def create_project(req: CreateProjectRequest):
    """
    Create a new academic research project workspace.
    POST /api/v1/projects
    """
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    project_id = f"proj_{uuid.uuid4()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    inst = (req.custom_instructions or req.instructions or "").strip()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects (id, name, description, instructions, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, name, req.description or "", inst, now, now),
    )
    log_project_activity(conn, project_id, "project_created", f"Created research project '{name}'")
    conn.commit()
    conn.close()

    return {
        "id": project_id,
        "name": name,
        "description": req.description or "",
        "instructions": inst,
        "custom_instructions": inst,
        "created_at": now,
        "updated_at": now,
        "document_count": 0,
        "conversation_count": 0,
        "note_count": 0,
    }


@app.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str):
    """
    Retrieve project details, including documents, conversations, notes, and activity.
    GET /api/v1/projects/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    proj = c.fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    result = dict(proj)
    result["custom_instructions"] = result.get("instructions", "")

    # Fetch documents
    c.execute("""
        SELECT id, project_id, filename, file_size, page_count, created_at
        FROM documents
        WHERE project_id = ?
        ORDER BY created_at DESC
    """, (project_id,))
    result["documents"] = [dict(r) for r in c.fetchall()]

    # Fetch conversations
    c.execute("""
        SELECT id, title, model, project_id, created_at, updated_at
        FROM conversations
        WHERE project_id = ?
        ORDER BY updated_at DESC
    """, (project_id,))
    result["conversations"] = [dict(r) for r in c.fetchall()]

    # Fetch notes & findings
    c.execute("""
        SELECT id, project_id, title, content, category, created_at, updated_at
        FROM project_notes
        WHERE project_id = ?
        ORDER BY updated_at DESC
    """, (project_id,))
    result["notes"] = [dict(r) for r in c.fetchall()]

    # Fetch recent activity
    c.execute("""
        SELECT id, project_id, action, details, created_at
        FROM project_activity
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    """, (project_id,))
    result["activity"] = [dict(r) for r in c.fetchall()]

    result["document_count"] = len(result["documents"])
    result["conversation_count"] = len(result["conversations"])
    result["note_count"] = len(result["notes"])

    conn.close()
    return result


@app.patch("/api/v1/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest):
    """
    Update project metadata and research instructions.
    PATCH /api/v1/projects/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    proj = c.fetchone()
    if not proj:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_name = req.name.strip() if req.name is not None else proj["name"]
    new_desc = req.description if req.description is not None else proj["description"]
    new_inst = (
        req.custom_instructions
        if req.custom_instructions is not None
        else (req.instructions if req.instructions is not None else proj["instructions"])
    )

    if not new_name:
        conn.close()
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    c.execute(
        "UPDATE projects SET name = ?, description = ?, instructions = ?, updated_at = ? WHERE id = ?",
        (new_name, new_desc, new_inst, now, project_id),
    )
    log_project_activity(conn, project_id, "project_updated", f"Updated project settings")
    conn.commit()
    conn.close()

    return {
        "id": project_id,
        "name": new_name,
        "description": new_desc,
        "instructions": new_inst,
        "custom_instructions": new_inst,
        "updated_at": now,
    }


@app.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    """
    Delete a project and safely cascade all its conversations, documents, notes, and activity.
    DELETE /api/v1/projects/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Clean up associated items
    c.execute("DELETE FROM document_chunks_fts WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM document_chunks WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM documents WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM project_notes WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM project_activity WHERE project_id = ?", (project_id,))

    # Clean up project conversations and messages
    c.execute("SELECT id FROM conversations WHERE project_id = ?", (project_id,))
    conv_ids = [r["id"] for r in c.fetchall()]
    for cid in conv_ids:
        c.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        c.execute("DELETE FROM conversations WHERE id = ?", (cid,))

    c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted", "id": project_id, "deleted": True}


# ---------------------------------------------------------
# Project Notes & Findings Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/projects/{project_id}/notes")
async def list_project_notes(project_id: str, category: Optional[str] = None):
    """
    List research notes and findings for a project.
    GET /api/v1/projects/{id}/notes
    """
    conn = get_db()
    c = conn.cursor()
    if category:
        c.execute("""
            SELECT id, project_id, title, content, category, created_at, updated_at
            FROM project_notes
            WHERE project_id = ? AND category = ?
            ORDER BY updated_at DESC
        """, (project_id, category))
    else:
        c.execute("""
            SELECT id, project_id, title, content, category, created_at, updated_at
            FROM project_notes
            WHERE project_id = ?
            ORDER BY updated_at DESC
        """, (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.post("/api/v1/projects/{project_id}/notes", status_code=status.HTTP_201_CREATED)
async def create_project_note(project_id: str, req: CreateNoteRequest):
    """
    Create a saved research note, important finding, or experiment record.
    POST /api/v1/projects/{id}/notes
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    note_id = f"note_{uuid.uuid4()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    category = req.category if req.category in {"note", "finding", "experiment", "methodology"} else "note"

    c.execute(
        "INSERT INTO project_notes (id, project_id, title, content, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (note_id, project_id, req.title.strip(), req.content.strip(), category, now, now),
    )
    log_project_activity(conn, project_id, "note_saved", f"Added {category}: '{req.title.strip()[:40]}'")
    conn.commit()
    conn.close()

    return {
        "id": note_id,
        "project_id": project_id,
        "title": req.title.strip(),
        "content": req.content.strip(),
        "category": category,
        "created_at": now,
        "updated_at": now,
    }


@app.patch("/api/v1/projects/{project_id}/notes/{note_id}")
async def update_project_note(project_id: str, note_id: str, req: UpdateNoteRequest):
    """
    Update a research note or finding.
    PATCH /api/v1/projects/{id}/notes/{note_id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM project_notes WHERE id = ? AND project_id = ?", (note_id, project_id))
    note = c.fetchone()
    if not note:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_title = req.title.strip() if req.title is not None else note["title"]
    new_content = req.content.strip() if req.content is not None else note["content"]
    new_category = req.category if req.category is not None else note["category"]

    c.execute(
        "UPDATE project_notes SET title = ?, content = ?, category = ?, updated_at = ? WHERE id = ?",
        (new_title, new_content, new_category, now, note_id),
    )
    log_project_activity(conn, project_id, "note_updated", f"Updated note: '{new_title[:40]}'")
    conn.commit()
    conn.close()

    return {
        "id": note_id,
        "project_id": project_id,
        "title": new_title,
        "content": new_content,
        "category": new_category,
        "updated_at": now,
    }


@app.delete("/api/v1/projects/{project_id}/notes/{note_id}")
async def delete_project_note(project_id: str, note_id: str):
    """
    Delete a research note.
    DELETE /api/v1/projects/{id}/notes/{note_id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT title FROM project_notes WHERE id = ? AND project_id = ?", (note_id, project_id))
    note = c.fetchone()
    if not note:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")

    c.execute("DELETE FROM project_notes WHERE id = ?", (note_id,))
    log_project_activity(conn, project_id, "note_deleted", f"Deleted note: '{note['title'][:40]}'")
    conn.commit()
    conn.close()

    return {"status": "deleted", "id": note_id, "deleted": True}


@app.get("/api/v1/projects/{project_id}/activity")
async def get_project_activity(project_id: str):
    """
    Get audit history and activity timeline for a research project.
    GET /api/v1/projects/{id}/activity
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, project_id, action, details, created_at
        FROM project_activity
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 100
    """, (project_id,))
    raw_rows = [dict(r) for r in c.fetchall()]
    conn.close()
    rows = []
    for r in raw_rows:
        d = dict(r)
        d["action_type"] = d.get("action", "")
        d["description"] = d.get("details", "")
        rows.append(d)
    return rows


# ---------------------------------------------------------
# Conversation Management Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/conversations")
async def list_conversations(project_id: Optional[str] = None):
    """
    List conversations, optionally filtered by project_id.
    GET /api/v1/conversations
    """
    conn = get_db()
    c = conn.cursor()
    if project_id:
        c.execute("""
            SELECT 
                c.id, c.title, c.model, c.project_id, c.created_at, c.updated_at,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                (SELECT COUNT(*) FROM documents WHERE conversation_id = c.id) as document_count
            FROM conversations c
            WHERE c.project_id = ?
            ORDER BY c.updated_at DESC
        """, (project_id,))
    else:
        c.execute("""
            SELECT 
                c.id, c.title, c.model, c.project_id, c.created_at, c.updated_at,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                (SELECT COUNT(*) FROM documents WHERE conversation_id = c.id) as document_count
            FROM conversations c
            WHERE c.project_id IS NULL
            ORDER BY c.updated_at DESC
        """)
    rows = [dict(r) for r in c.fetchall()]

    for conv in rows:
        c.execute(
            "SELECT id, filename, file_size, page_count FROM documents WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv["id"],)
        )
        conv["documents"] = [dict(d) for d in c.fetchall()]

    conn.close()
    return rows


@app.post("/api/v1/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(req: CreateConversationRequest):
    """
    Create a new conversation, optionally associated with a project.
    POST /api/v1/conversations
    """
    conv_id = f"conv_{uuid.uuid4()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    model = req.model or DEFAULT_MODEL
    title = (req.title or "New Conversation").strip()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO conversations (id, title, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, title, model, req.project_id, now, now),
    )
    if req.project_id:
        log_project_activity(conn, req.project_id, "conversation_started", f"Started conversation '{title}'")
    conn.commit()
    conn.close()

    return {
        "id": conv_id,
        "title": title,
        "model": model,
        "project_id": req.project_id,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "document_count": 0,
        "documents": [],
    }


@app.get("/api/v1/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """
    Retrieve a single conversation and its full message history and attached documents.
    GET /api/v1/conversations/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, model, project_id, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    c.execute("""
        SELECT id, role, content, citations, created_at 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC, rowid ASC
    """, (conv_id,))
    raw_messages = [dict(r) for r in c.fetchall()]

    messages = []
    for m in raw_messages:
        citations = []
        if m.get("citations"):
            try:
                citations = json.loads(m["citations"])
            except Exception:
                citations = []
        messages.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "citations": citations,
            "created_at": m["created_at"],
        })

    c.execute("""
        SELECT id, conversation_id, project_id, filename, file_size, page_count, created_at 
        FROM documents 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    """, (conv_id,))
    documents = [dict(r) for r in c.fetchall()]
    conn.close()

    result = dict(conv)
    result["messages"] = messages
    result["documents"] = documents
    result["message_count"] = len(messages)
    result["document_count"] = len(documents)
    return result


@app.patch("/api/v1/conversations/{conv_id}")
async def update_conversation(conv_id: str, req: UpdateConversationRequest):
    """
    Update / rename a conversation.
    PATCH /api/v1/conversations/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, model, project_id, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_title = req.title.strip() if req.title is not None else conv["title"]
    new_model = req.model.strip() if req.model is not None else conv["model"]

    c.execute(
        "UPDATE conversations SET title = ?, model = ?, updated_at = ? WHERE id = ?",
        (new_title, new_model, now, conv_id),
    )
    conn.commit()
    conn.close()

    return {
        "id": conv_id,
        "title": new_title,
        "model": new_model,
        "project_id": conv["project_id"],
        "created_at": conv["created_at"],
        "updated_at": now,
    }


@app.delete("/api/v1/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """
    Delete a conversation and all its messages and documents.
    DELETE /api/v1/conversations/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, project_id FROM conversations WHERE id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    c.execute("DELETE FROM document_chunks_fts WHERE conversation_id = ?", (conv_id,))
    c.execute("DELETE FROM document_chunks WHERE conversation_id = ?", (conv_id,))
    c.execute("DELETE FROM documents WHERE conversation_id = ?", (conv_id,))
    c.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    c.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted", "id": conv_id}


# ---------------------------------------------------------
# Document Endpoints
# ---------------------------------------------------------

@app.post("/api/v1/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    conv_id_query: Optional[str] = Query(None, alias="conversation_id"),
    proj_id_query: Optional[str] = Query(None, alias="project_id"),
):
    """
    Accept PDF upload, validate MIME type, file extension, and actual PDF magic bytes.
    Extract text locally, chunk, index into FTS5, and associate with conversation/project.
    POST /api/v1/documents
    """
    raw_name = file.filename or "uploaded.pdf"
    # Security: sanitize filename against path traversal and control characters
    base_name = os.path.basename(raw_name)
    sanitized_name = re.sub(r'[^a-zA-Z0-9_\-\. ]', '_', base_name)
    if not sanitized_name.lower().endswith(".pdf"):
        sanitized_name += ".pdf"
    filename = sanitized_name
    eff_conv_id = conversation_id or conv_id_query
    eff_project_id = project_id or proj_id_query

    # 1. Validate file extension
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files (.pdf) are supported.",
        )

    # 2. Read file content with strict size check (20 MB max)
    file_bytes = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 20 MB limit.",
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )

    # 3. Validate PDF magic bytes header (%PDF-)
    header_sample = file_bytes[:1024]
    if b"%PDF-" not in header_sample:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF header. The file does not have a genuine PDF signature.",
        )

    # 4. Extract text safely using pypdf
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed or unreadable PDF document: {str(e)}",
        )

    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password-protected PDF files cannot be processed. Please decrypt before uploading.",
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password-protected PDF files cannot be processed. Please decrypt before uploading.",
            )

    page_count = len(reader.pages)
    if page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The PDF contains no pages.",
        )

    extracted_chunks = []
    total_text_chars = 0
    full_text_accumulator = ""

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = page_text.strip()
        if not page_text:
            continue

        total_text_chars += len(page_text)
        full_text_accumulator += f"\n[Page {page_idx}]\n" + page_text

        # Overlapping chunk extraction (~240 words per chunk with 40-word overlap)
        page_chunks = chunk_text_overlapping(page_text, page_idx, target_words=240, overlap_words=40)
        extracted_chunks.extend(page_chunks)

    # Scanned PDF detection
    if total_text_chars == 0 or not extracted_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable text found in PDF. This document appears to be scanned or image-only and requires OCR (Optical Character Recognition) to extract text, which is not supported in this offline local phase.",
        )

    conn = get_db()
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conv_id = eff_conv_id
    eff_project_id = eff_project_id

    # If project_id provided, ensure project exists
    if eff_project_id:
        c.execute("SELECT id FROM projects WHERE id = ?", (eff_project_id,))
        if not c.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail=f"Project '{eff_project_id}' not found")

    # If attached to a conversation
    if conv_id:
        c.execute("SELECT id, project_id FROM conversations WHERE id = ?", (conv_id,))
        conv_row = c.fetchone()
        if not conv_row:
            c.execute(
                "INSERT INTO conversations (id, title, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, f"Document: {filename[:30]}", DEFAULT_MODEL, eff_project_id, now, now),
            )
        elif not eff_project_id and conv_row["project_id"]:
            eff_project_id = conv_row["project_id"]
    elif not eff_project_id:
        # Create a new conversation if neither was supplied
        conv_id = f"conv_{uuid.uuid4()}"
        c.execute(
            "INSERT INTO conversations (id, title, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, f"Document: {filename[:30]}", DEFAULT_MODEL, None, now, now),
        )

    # Store document record & chunks in SQLite
    doc_id = f"doc_{uuid.uuid4()}"
    c.execute(
        "INSERT INTO documents (id, conversation_id, project_id, filename, file_size, page_count, extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, conv_id, eff_project_id, filename, len(file_bytes), page_count, full_text_accumulator, now),
    )

    for chunk_idx, (page_num, chunk_text) in enumerate(extracted_chunks):
        chk_id = f"chk_{uuid.uuid4()}"
        c.execute(
            "INSERT INTO document_chunks (id, document_id, conversation_id, project_id, chunk_index, page_number, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chk_id, doc_id, conv_id, eff_project_id, chunk_idx, page_num, chunk_text),
        )
        try:
            c.execute(
                "INSERT INTO document_chunks_fts (chunk_id, document_id, conversation_id, project_id, content) VALUES (?, ?, ?, ?, ?)",
                (chk_id, doc_id, conv_id, eff_project_id, chunk_text),
            )
        except Exception:
            pass

    if conv_id:
        c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))

    if eff_project_id:
        c.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, eff_project_id))
        log_project_activity(conn, eff_project_id, "document_uploaded", f"Ingested paper '{filename}' ({page_count} pages)")

    conn.commit()
    conn.close()

    return {
        "id": doc_id,
        "conversation_id": conv_id,
        "project_id": eff_project_id,
        "filename": filename,
        "file_size": len(file_bytes),
        "page_count": page_count,
        "char_count": total_text_chars,
        "chunk_count": len(extracted_chunks),
        "status": "ready",
        "extraction_status": "success",
        "created_at": now,
    }


@app.get("/api/v1/conversations/{conv_id}/documents")
async def get_conversation_documents(conv_id: str):
    """List all documents associated with a conversation."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, conversation_id, project_id, filename, file_size, page_count, created_at 
        FROM documents 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    """, (conv_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/v1/projects/{project_id}/documents")
async def get_project_documents(project_id: str):
    """List all documents associated with a project."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, conversation_id, project_id, filename, file_size, page_count, created_at 
        FROM documents 
        WHERE project_id = ? 
        ORDER BY created_at ASC
    """, (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its associated chunks from SQLite."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, conversation_id, project_id, filename FROM documents WHERE id = ?", (doc_id,))
    doc = c.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    c.execute("DELETE FROM document_chunks_fts WHERE document_id = ?", (doc_id,))
    c.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
    c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    if doc["project_id"]:
        log_project_activity(conn, doc["project_id"], "document_deleted", f"Removed document '{doc['filename']}'")

    conn.commit()
    conn.close()

    return {"status": "deleted", "id": doc_id}


# ---------------------------------------------------------
# Chat Streaming Endpoint
# ---------------------------------------------------------

@app.post("/api/v1/chat")
async def stream_chat(req: ChatRequest, request: Request):
    """
    Stream assistant chat completion via Server-Sent Events (SSE).
    Supports:
    - RAG retrieval over project documents and conversation documents via FTS5
    - Undergraduate engineering level research assistant system prompts when in a project
    - Citation extraction, emission via SSE, and persistence to SQLite
    - Safe Stop cancellation handling
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    target_model = req.model or DEFAULT_MODEL
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = get_db()
    c = conn.cursor()

    # 1. Resolve conversation and project context
    conv_id = req.conversation_id
    project_id = req.project_id
    project_instructions = ""

    if conv_id:
        c.execute("SELECT id, project_id FROM conversations WHERE id = ?", (conv_id,))
        conv_row = c.fetchone()
        if not conv_row:
            c.execute(
                "INSERT INTO conversations (id, title, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, "New Conversation", target_model, project_id, now, now),
            )
            conn.commit()
        elif conv_row["project_id"] and not project_id:
            project_id = conv_row["project_id"]
    else:
        conv_id = f"conv_{uuid.uuid4()}"
        c.execute(
            "INSERT INTO conversations (id, title, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, "New Conversation", target_model, project_id, now, now),
        )
        conn.commit()

    if project_id:
        c.execute("SELECT name, instructions FROM projects WHERE id = ?", (project_id,))
        proj_row = c.fetchone()
        if proj_row and proj_row["instructions"]:
            project_instructions = proj_row["instructions"].strip()

    # 2. Save latest user message before generation starts
    latest_user_msg = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if latest_user_msg:
        user_msg_id = latest_user_msg.id if (latest_user_msg.id and not latest_user_msg.id.startswith("usr-")) else f"msg_{uuid.uuid4()}"
        user_msg_time = latest_user_msg.created_at or now

        c.execute("SELECT id FROM messages WHERE id = ?", (user_msg_id,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_msg_id, conv_id, "user", latest_user_msg.content, user_msg_time),
            )

        # Auto-update conversation title if default
        c.execute("SELECT title FROM conversations WHERE id = ?", (conv_id,))
        current_title = c.fetchone()["title"]
        if current_title in ("New Conversation", "Untitled Conversation"):
            first_words = latest_user_msg.content.strip().split("\n")[0][:36]
            new_title = first_words + ("..." if len(latest_user_msg.content.strip()) > 36 else "")
            c.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conv_id))

        c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        conn.commit()

    conn.close()

    # 3. Retrieve relevant document chunks using FTS5 / BM25
    user_query = latest_user_msg.content if latest_user_msg else ""
    relevant_chunks = retrieve_relevant_chunks(conv_id=conv_id, project_id=project_id, query=user_query, max_words=1200)

    # 4. Build citations list
    citations = [
        {
            "id": chk["id"],
            "document_id": chk["document_id"],
            "filename": chk["filename"],
            "page_number": chk["page_number"],
            "excerpt": chk["content"][:240].strip() + ("..." if len(chk["content"]) > 240 else ""),
        }
        for chk in relevant_chunks
    ]

    # 5. SSE Streaming Generator
    async def event_generator():
        ollama_url = f"{OLLAMA_HOST}/api/chat"

        # Prepare system prompt
        system_prompts = []
        if project_id:
            # Use dedicated undergraduate engineering research assistant system prompt
            system_prompts.append(DEFAULT_RESEARCH_SYSTEM_PROMPT)
            if project_instructions:
                system_prompts.append(f"PROJECT RESEARCH INSTRUCTIONS:\n{project_instructions}")

        if relevant_chunks:
            chunk_excerpts = []
            for chk in relevant_chunks:
                chunk_excerpts.append(
                    f"[Source: {chk['filename']}, Page {chk['page_number']}]:\n{chk['content']}"
                )
            context_block = "\n\n---\n\n".join(chunk_excerpts)
            doc_grounding_prompt = f"""You have access to the following excerpts from documents in this workspace:

---
{context_block}
---

CITATION & EVIDENCE INSTRUCTIONS:
1. Ground your answer in the provided document excerpts above.
2. Explicitly cite the source filename and page number for every supported factual statement.
3. If the provided excerpts do not contain enough evidence to answer the question, clearly state: "The attached document(s) do not contain sufficient evidence to answer this question."
4. Do not invent citations, equations, or benchmark figures not present in the excerpts."""
            system_prompts.append(doc_grounding_prompt)

        base_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        if system_prompts:
            ollama_messages = [{"role": "system", "content": "\n\n".join(system_prompts)}] + base_messages
        else:
            ollama_messages = base_messages

        ollama_payload = {
            "model": target_model,
            "messages": ollama_messages,
            "stream": True,
            "think": False,
            "options": {
                "num_predict": req.max_tokens or DEFAULT_MAX_TOKENS,
                "temperature": req.temperature if req.temperature is not None else 0.7,
            },
        }

        full_content = ""
        client_cancelled = False
        error_occurred = False
        assistant_msg_id = f"msg_{uuid.uuid4()}"

        # Emit citations event if document evidence is used
        if citations:
            yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"

        # Concurrency protection: throttle simultaneous CPU inferences
        try:
            await asyncio.wait_for(INFERENCE_SEMAPHORE.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            yield f"event: error\ndata: {json.dumps({'error': 'Local inference engine is at full capacity. Please wait a few seconds and retry.', 'code': 'INFERENCE_BUSY'})}\n\n"
            return

        try:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=10.0)) as client:
                    async with client.stream("POST", ollama_url, json=ollama_payload) as resp:
                        if resp.status_code != 200:
                            err_text = await resp.aread()
                            error_occurred = True
                            yield f"event: error\ndata: {json.dumps({'error': f'Ollama error {resp.status_code}: {err_text.decode()}', 'code': 'OLLAMA_HTTP_ERROR'})}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if await request.is_disconnected():
                                client_cancelled = True
                                break

                            if not line or not line.strip():
                                continue

                            try:
                                data = json.loads(line)
                                delta = data.get("message", {}).get("content", "")

                                if delta:
                                    full_content += delta
                                    yield f"event: token\ndata: {json.dumps({'token': delta})}\n\n"

                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue

            except httpx.ConnectError:
                error_occurred = True
                yield f"event: error\ndata: {json.dumps({'error': f'Failed to connect to Ollama at {OLLAMA_HOST}. Ensure service is running.', 'code': 'OLLAMA_CONNECT_ERROR'})}\n\n"
            except asyncio.CancelledError:
                client_cancelled = True
            except Exception as e:
                error_occurred = True
                yield f"event: error\ndata: {json.dumps({'error': str(e), 'code': 'INTERNAL_GENERATION_ERROR'})}\n\n"

            # Persist assistant response in SQLite with citations
            if full_content and not error_occurred:
                try:
                    conn_save = get_db()
                    c_save = conn_save.cursor()
                    now_finish = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    citations_json = json.dumps(citations) if citations else None
                    c_save.execute(
                        "INSERT INTO messages (id, conversation_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (assistant_msg_id, conv_id, "assistant", full_content, citations_json, now_finish),
                    )
                    c_save.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_finish, conv_id))
                    conn_save.commit()
                    conn_save.close()
                except Exception as e:
                    print("Failed to save assistant message to SQLite:", e)

            if not client_cancelled and not error_occurred:
                yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg_id, 'finish_reason': 'stop', 'content': full_content, 'citations': citations})}\n\n"
                yield "data: [DONE]\n\n"
        finally:
            INFERENCE_SEMAPHORE.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
