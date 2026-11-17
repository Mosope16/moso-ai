"""
Moso AI — FastAPI Backend with SQLite Persistence, Ollama Integration, and Local PDF Processing
Local-first AI assistant backend supporting Qwen 3.5 2B inference on CPU with document chat.
"""

import os
import io
import re
import json
import sqlite3
import datetime
import uuid
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
import pypdf

DB_FILE = os.path.join(os.path.dirname(__file__), "moso.db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = "qwen3.5:2b"
DEFAULT_MAX_TOKENS = 256
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB limit

app = FastAPI(
    title="Moso AI Backend",
    version="0.1.0",
    description="Local-first FastAPI backend with SQLite persistence, Ollama SSE streaming, and local PDF document chat",
)

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conv_order 
        ON messages(conversation_id, created_at)
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            extracted_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_conv 
        ON documents(conversation_id, created_at)
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_conv 
        ON document_chunks(conversation_id, document_id)
    """)
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


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL
    messages: List[MessageInput]
    stream: Optional[bool] = True
    max_tokens: Optional[int] = Field(default=DEFAULT_MAX_TOKENS, ge=16, le=8192)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)


# ---------------------------------------------------------
# Lightweight Document Retrieval Helper
# ---------------------------------------------------------

def retrieve_relevant_chunks(conv_id: str, query: str, max_words: int = 1200) -> List[dict]:
    """
    Retrieve the most relevant document chunks for the given conversation and query.
    Uses a lightweight term-overlap ranker with stopword filtering.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            c.id, c.document_id, c.chunk_index, c.page_number, c.content, d.filename
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.conversation_id = ?
        ORDER BY c.page_number ASC, c.chunk_index ASC
    """, (conv_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not rows:
        return []

    total_words = sum(len(r["content"].split()) for r in rows)
    # If the total text is compact, return all chunks in order
    if total_words <= max_words:
        return rows

    # Term filtering for relevance scoring
    stopwords = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with",
        "is", "are", "was", "were", "what", "how", "why", "who", "when", "where",
        "can", "could", "would", "should", "does", "do", "did", "this", "that",
        "these", "those", "it", "its", "from", "by", "as", "about", "tell", "me"
    }
    query_terms = [
        t for t in re.findall(r'\b\w+\b', query.lower())
        if len(t) > 2 and t not in stopwords
    ]

    if not query_terms:
        # Fallback: take earliest chunks up to limit
        selected = []
        accumulated = 0
        for r in rows:
            w_count = len(r["content"].split())
            if accumulated + w_count > max_words and selected:
                break
            selected.append(r)
            accumulated += w_count
        return selected

    # Score each chunk based on query term frequency
    scored = []
    for r in rows:
        content_lower = r["content"].lower()
        score = 0
        for term in query_terms:
            occurrences = content_lower.count(term)
            if occurrences > 0:
                score += (1 + 0.5 * min(occurrences, 4))
        if score > 0:
            scored.append((score, r))

    # Sort by relevance score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = []
    accumulated_words = 0
    for score, chunk in scored:
        w_count = len(chunk["content"].split())
        if accumulated_words + w_count > max_words and selected:
            break
        selected.append(chunk)
        accumulated_words += w_count

    # If no chunk matched query terms, take first chunks
    if not selected:
        selected = rows[:3]

    # Re-sort selected chunks by original page and position order
    selected.sort(key=lambda x: (x["page_number"], x["chunk_index"]))
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
                }
    except Exception:
        pass
    return {
        "connected": False,
        "models": [],
        "model_names": [],
        "has_default_model": False,
    }


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/health")
async def health_check():
    """
    Check backend health, SQLite status, and Ollama connectivity.
    GET /api/v1/health
    """
    ollama_info = await check_ollama_status()

    # Verify SQLite database connectivity
    db_ok = False
    conv_count = 0
    doc_count = 0
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM conversations")
        conv_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM documents")
        doc_count = c.fetchone()[0]
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

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
        "document_count": doc_count,
        "device_mode": "cpu",
        "version": "0.1.0",
    }


@app.get("/api/v1/models")
async def get_models():
    """
    Retrieve installed models dynamically from local Ollama service.
    GET /api/v1/models
    """
    ollama_info = await check_ollama_status()

    if not ollama_info["connected"]:
        return [
            {
                "id": DEFAULT_MODEL,
                "name": "Qwen 3.5 2B",
                "description": "Default local model (Ollama currently disconnected)",
                "size": "1.9 GB",
                "parameters": "2B",
                "family": "qwen35",
                "provider": "ollama",
                "is_local": True,
                "is_default": True,
                "is_available": False,
            }
        ]

    models_list = []
    raw_models = ollama_info["models"]

    for om in raw_models:
        name = om.get("name", "")
        details = om.get("details", {})
        size_bytes = om.get("size", 0)
        size_str = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "Local"
        param_size = details.get("parameter_size", "2B")
        family = details.get("family", "qwen")

        is_default = (name == DEFAULT_MODEL)

        models_list.append({
            "id": name,
            "name": "Qwen 3.5 2B" if name == DEFAULT_MODEL else name.replace(":", " ").title(),
            "description": f"Local Ollama Model ({param_size})",
            "size": size_str,
            "parameters": param_size,
            "family": family,
            "provider": "ollama",
            "is_local": True,
            "is_default": is_default,
            "is_available": True,
            "context_length": details.get("context_length", 262144),
        })

    models_list.sort(key=lambda m: (not m["is_default"], m["name"]))
    return models_list


@app.get("/api/v1/conversations")
async def list_conversations():
    """
    Retrieve all conversations ordered by updated_at DESC.
    GET /api/v1/conversations
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            c.id, 
            c.title, 
            c.model, 
            c.created_at, 
            c.updated_at,
            (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as message_count,
            (SELECT COUNT(*) FROM documents d WHERE d.conversation_id = c.id) as document_count
        FROM conversations c 
        ORDER BY c.updated_at DESC
    """)
    rows = c.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


@app.post("/api/v1/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(req: CreateConversationRequest):
    """
    Create a new conversation.
    POST /api/v1/conversations
    """
    conv_id = f"conv_{uuid.uuid4()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    title = (req.title or "New Conversation").strip()
    model = (req.model or DEFAULT_MODEL).strip()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, title, model, now, now),
    )
    conn.commit()
    conn.close()

    return {
        "id": conv_id,
        "title": title,
        "model": model,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "document_count": 0,
        "messages": [],
        "documents": [],
    }


@app.get("/api/v1/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """
    Retrieve a conversation, its messages, and attached documents.
    GET /api/v1/conversations/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, model, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    c.execute(
        "SELECT id, conversation_id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC",
        (conv_id,),
    )
    messages = [dict(row) for row in c.fetchall()]

    c.execute(
        "SELECT id, conversation_id, filename, file_size, page_count, created_at FROM documents WHERE conversation_id = ? ORDER BY created_at ASC",
        (conv_id,),
    )
    documents = [dict(row) for row in c.fetchall()]
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
    c.execute("SELECT id, title, model, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,))
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
    c.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

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
    conversation_id: Optional[str] = Form(None)
):
    """
    Accept PDF upload, validate, extract text, chunk, and store in SQLite.
    POST /api/v1/documents
    """
    filename = file.filename or "uploaded.pdf"

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
                    detail="Password-protected PDF files cannot be processed.",
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password-protected PDF files cannot be processed.",
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

        # Segment page text into clean paragraph passages of ~300 words
        paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [page_text]

        curr_chunk = ""
        for p in paragraphs:
            if curr_chunk and (len(curr_chunk.split()) + len(p.split()) > 350):
                extracted_chunks.append((page_idx, curr_chunk))
                curr_chunk = p
            else:
                curr_chunk = (curr_chunk + "\n\n" + p).strip() if curr_chunk else p
        if curr_chunk:
            extracted_chunks.append((page_idx, curr_chunk))

    if total_text_chars == 0 or not extracted_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable text found in PDF. Scanned or image-only documents without OCR are not supported.",
        )

    # 5. Ensure conversation exists in SQLite
    conn = get_db()
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conv_id = conversation_id

    if conv_id:
        c.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, f"Document: {filename[:30]}", DEFAULT_MODEL, now, now),
            )
            conn.commit()
    else:
        conv_id = f"conv_{uuid.uuid4()}"
        c.execute(
            "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, f"Document: {filename[:30]}", DEFAULT_MODEL, now, now),
        )
        conn.commit()

    # 6. Store document record & chunks in SQLite
    doc_id = f"doc_{uuid.uuid4()}"
    c.execute(
        "INSERT INTO documents (id, conversation_id, filename, file_size, page_count, extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (doc_id, conv_id, filename, len(file_bytes), page_count, full_text_accumulator, now),
    )

    for chunk_idx, (page_num, chunk_text) in enumerate(extracted_chunks):
        c.execute(
            "INSERT INTO document_chunks (id, document_id, conversation_id, chunk_index, page_number, content) VALUES (?, ?, ?, ?, ?, ?)",
            (f"chk_{uuid.uuid4()}", doc_id, conv_id, chunk_idx, page_num, chunk_text),
        )

    c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
    conn.commit()
    conn.close()

    return {
        "id": doc_id,
        "conversation_id": conv_id,
        "filename": filename,
        "file_size": len(file_bytes),
        "page_count": page_count,
        "char_count": total_text_chars,
        "status": "ready",
        "extraction_status": "success",
        "created_at": now,
    }


@app.get("/api/v1/conversations/{conv_id}/documents")
async def get_conversation_documents(conv_id: str):
    """
    List all documents associated with a conversation.
    GET /api/v1/conversations/{id}/documents
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, conversation_id, filename, file_size, page_count, created_at 
        FROM documents 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    """, (conv_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document and its associated chunks from SQLite.
    DELETE /api/v1/documents/{id}
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, conversation_id FROM documents WHERE id = ?", (doc_id,))
    doc = c.fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    c.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
    c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
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
    Supports document context augmentation when documents are attached to the conversation.
    POST /api/v1/chat
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    target_model = req.model or DEFAULT_MODEL

    # 1. Verify Ollama availability before beginning stream
    ollama_status = await check_ollama_status()
    if not ollama_status["connected"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama service is unreachable at {OLLAMA_HOST}. Please start Ollama.",
        )

    # 2. Ensure target conversation exists in SQLite
    conn = get_db()
    c = conn.cursor()

    conv_id = req.conversation_id
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if conv_id:
        c.execute("SELECT id, title FROM conversations WHERE id = ?", (conv_id,))
        conv_row = c.fetchone()
        if not conv_row:
            c.execute(
                "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, "New Conversation", target_model, now, now),
            )
            conn.commit()
    else:
        conv_id = f"conv_{uuid.uuid4()}"
        c.execute(
            "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, "New Conversation", target_model, now, now),
        )
        conn.commit()

    # 3. SAVE LATEST USER MESSAGE TO SQLITE BEFORE GENERATION STARTS
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

        # Auto-update conversation title if still default
        c.execute("SELECT title FROM conversations WHERE id = ?", (conv_id,))
        current_title = c.fetchone()["title"]
        if current_title in ("New Conversation", "Untitled Conversation"):
            first_words = latest_user_msg.content.strip().split("\n")[0][:36]
            new_title = first_words + ("..." if len(latest_user_msg.content.strip()) > 36 else "")
            c.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conv_id))

        c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        conn.commit()

    conn.close()

    # 4. Check for attached documents and retrieve relevant chunks
    user_query = latest_user_msg.content if latest_user_msg else ""
    relevant_chunks = retrieve_relevant_chunks(conv_id, user_query, max_words=1200)

    # 5. SSE Streaming Generator
    async def event_generator():
        ollama_url = f"{OLLAMA_HOST}/api/chat"

        # Prepare base messages array
        base_messages = [{"role": m.role, "content": m.content} for m in req.messages]

        # If documents are attached, inject document context instruction
        if relevant_chunks:
            chunk_excerpts = []
            for chk in relevant_chunks:
                chunk_excerpts.append(
                    f"[Document: {chk['filename']}, Page {chk['page_number']}]:\n{chk['content']}"
                )
            context_block = "\n\n---\n\n".join(chunk_excerpts)

            doc_system_prompt = f"""You have access to the following excerpts from document(s) uploaded to this conversation:

---
{context_block}
---

DOCUMENT-BASED ANSWERING INSTRUCTIONS:
1. Answer the user's question directly and factually using ONLY the provided document excerpts above.
2. If the excerpts do not contain the answer or the topic is not mentioned in the document, you MUST explicitly state: "The attached document does not contain this information."
3. Cite the relevant page number(s) when answering.
4. Do not speculate or invent facts not stated in the document excerpts."""

            # Inject as high-priority system instruction
            ollama_messages = [{"role": "system", "content": doc_system_prompt}] + base_messages
        else:
            ollama_messages = base_messages

        ollama_payload = {
            "model": target_model,
            "messages": ollama_messages,
            "stream": True,
            "think": False,  # Disables unnecessary internal thinking tokens for Qwen 3.5 2B
            "options": {
                "num_predict": req.max_tokens or DEFAULT_MAX_TOKENS,
                "temperature": req.temperature if req.temperature is not None else 0.7,
            },
        }

        full_content = ""
        client_cancelled = False
        error_occurred = False
        assistant_msg_id = f"msg_{uuid.uuid4()}"

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

                        if not line:
                            continue

                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_content += token
                            yield f"data: {json.dumps({'token': token})}\n\n"

                        if chunk.get("done", False):
                            yield f"event: done\ndata: {json.dumps({'done': True, 'content': full_content, 'message_id': assistant_msg_id})}\n\n"
                            yield "data: [DONE]\n\n"
                            break

        except (asyncio.CancelledError, GeneratorExit):
            client_cancelled = True
        except Exception as e:
            error_occurred = True
            yield f"event: error\ndata: {json.dumps({'error': f'Inference stream failure: {str(e)}', 'code': 'STREAM_EXCEPTION'})}\n\n"

        # 6. PERSIST ASSISTANT MESSAGE ON COMPLETION OR PARTIAL STOP
        if not error_occurred and full_content.strip():
            try:
                save_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
                save_conn = get_db()
                save_c = save_conn.cursor()
                save_c.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (assistant_msg_id, conv_id, "assistant", full_content, save_time),
                )
                save_c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (save_time, conv_id))
                save_conn.commit()
                save_conn.close()
            except Exception as save_err:
                print(f"[ERROR] Failed to save assistant message to SQLite: {save_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
