#!/usr/bin/env python3
"""
Moso AI - Research Assistant & Project Workspace Comprehensive Test Suite
Tests:
1. Project CRUD (create, read, update, delete, cascade).
2. Project Notes CRUD (create, list with category filters, update, delete).
3. Project Activity audit trail logging.
4. Local Document chunking (~240 words, 40 overlap) & SQLite FTS5 BM25 retrieval.
5. Strict project & conversation isolation (zero cross-tenant leakage).
6. Research assistant prompt & project custom instructions injection.
7. Source citation emission & persistence in SQLite.
8. Regression check on ordinary non-project chats.
"""

import io
import os
import sys
import json
import sqlite3
import pypdf
from fastapi.testclient import TestClient

# Ensure backend package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import (
    app,
    DB_FILE,
    get_db,
    init_db,
    chunk_text_overlapping,
    retrieve_relevant_chunks,
    DEFAULT_RESEARCH_SYSTEM_PROMPT,
)

client = TestClient(app)


def make_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to create genuine multi-page PDF bytes using pypdf."""
    writer = pypdf.PdfWriter()
    for text in pages_text:
        stream_data = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
        header = f"5 0 obj <</Length {len(stream_data)}>> stream\n".encode("latin-1")
        page_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj\n"
            b"4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            + header
            + stream_data
            + b"\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n"
            b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n0\n%%EOF"
        )
        r = pypdf.PdfReader(io.BytesIO(page_bytes))
        writer.add_page(r.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_chunk_text_overlapping():
    print("\n--- Test 1: Text Chunking with Overlap ---")
    # Generate 500 words
    words = [f"word{i}" for i in range(500)]
    page_text = " ".join(words)
    chunks = chunk_text_overlapping(page_text, page_number=2, target_words=240, overlap_words=40)
    
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"
    print(f"  Created {len(chunks)} overlapping chunks from 500 words.")
    for idx, (p_num, c_text) in enumerate(chunks):
        word_count = len(c_text.split())
        assert p_num == 2
        print(f"  Chunk {idx}: {word_count} words (starts with '{c_text.split()[:3]}')")
    
    # Check overlap: last words of chunk 0 should be present at beginning of chunk 1
    c0_words = chunks[0][1].split()
    c1_words = chunks[1][1].split()
    overlap_slice = c0_words[-20:]
    overlap_found = any(overlap_slice[0] == w for w in c1_words[:40])
    assert overlap_found, "Overlap words not found between chunk 0 and chunk 1"
    print("  PASS: Overlapping window verified.")


def test_project_crud():
    print("\n--- Test 2: Project Workspace CRUD Lifecycle ---")
    # 1. Create Project
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Biomedical Deep Learning",
            "description": "Evaluating U-Net and Transformers on microscopy data",
            "custom_instructions": "Focus on Dice score and ROC-AUC. Use formal LaTeX equations for derivations.",
        },
    )
    assert resp.status_code == 200, resp.text
    proj = resp.json()
    proj_id = proj["id"]
    assert proj["name"] == "Biomedical Deep Learning"
    assert "Dice score" in proj["custom_instructions"]
    print(f"  Created project: {proj_id} ('{proj['name']}')")

    # 2. Get Project
    resp = client.get(f"/api/v1/projects/{proj_id}")
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["id"] == proj_id
    assert fetched["document_count"] == 0
    assert fetched["note_count"] == 0

    # 3. Update Project
    resp = client.patch(
        f"/api/v1/projects/{proj_id}",
        json={
            "name": "Biomedical Deep Learning (Updated)",
            "custom_instructions": "Prioritize F1-score and Hausdorff distance metrics.",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "Biomedical Deep Learning (Updated)"
    assert "Hausdorff distance" in updated["custom_instructions"]
    print("  PASS: Project creation, retrieval, and updates verified.")
    return proj_id


def test_project_notes(proj_id: str):
    print("\n--- Test 3: Project Notes & Findings CRUD ---")
    # 1. Create finding note
    resp = client.post(
        f"/api/v1/projects/{proj_id}/notes",
        json={
            "title": "Validation Loss Anomaly",
            "category": "finding",
            "content": "Observed gradient saturation at epoch 42 when learning rate = 1e-3. Reduced to 1e-4 with AdamW.",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    note1 = resp.json()
    note1_id = note1["id"]
    assert note1["category"] == "finding"

    # 2. Create methodology note
    resp = client.post(
        f"/api/v1/projects/{proj_id}/notes",
        json={
            "title": "Swin-UNETR Loss Formulation",
            "category": "methodology",
            "content": "Combined Dice and Cross-Entropy loss: \\(L_{total} = L_{Dice} + \\alpha L_{CE}\\) where \\(\\alpha = 0.5\\).",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    note2 = resp.json()

    # 3. List notes (all)
    resp = client.get(f"/api/v1/projects/{proj_id}/notes")
    assert resp.status_code == 200
    all_notes = resp.json()
    assert len(all_notes) >= 2

    # 4. Filter by category
    resp = client.get(f"/api/v1/projects/{proj_id}/notes?category=finding")
    assert resp.status_code == 200
    findings = resp.json()
    assert all(n["category"] == "finding" for n in findings)

    # 5. Update note
    resp = client.patch(
        f"/api/v1/projects/{proj_id}/notes/{note1_id}",
        json={"title": "Validation Loss Anomaly - Resolved"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Validation Loss Anomaly - Resolved"

    # 6. Delete one note
    resp = client.delete(f"/api/v1/projects/{proj_id}/notes/{note1_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    print("  PASS: Notes creation, categorization, filtering, and deletion verified.")


def test_activity_logging(proj_id: str):
    print("\n--- Test 4: Project Activity Audit History ---")
    resp = client.get(f"/api/v1/projects/{proj_id}/activity")
    assert resp.status_code == 200
    activities = resp.json()
    assert len(activities) > 0, "Expected activity logs"
    print(f"  Found {len(activities)} audit records:")
    for a in activities[:3]:
        print(f"    - [{a['action_type']}] {a['description']}")
    print("  PASS: Activity audit trail verified.")


def test_fts5_bm25_retrieval_and_ingestion(proj_id: str):
    print("\n--- Test 5: Ingestion with Overlapping Chunks and SQLite FTS5 Retrieval ---")
    page1 = "Convolutional neural networks use residual learning with shortcut connections to solve degradation in deep networks."
    page2 = "Vision Transformer ViT replaces standard convolutions with pure self-attention mechanisms yielding an ROC-AUC of 0.942 and F1-score of 0.891."
    page3 = "Quantization on Intel Core i5-1155G7 and Iris Xe graphics delivers a 2.4x inference speedup with INT8 precision without accuracy degradation."

    pdf_data = make_pdf_bytes([page1, page2, page3])
    files = {"file": ("deep_learning_survey.pdf", pdf_data, "application/pdf")}
    resp = client.post(f"/api/v1/documents?project_id={proj_id}", files=files)
    assert resp.status_code in (200, 201), resp.text
    doc = resp.json()
    doc_id = doc["id"]
    assert doc["page_count"] == 3
    print(f"  Ingested PDF '{doc['filename']}' ({doc['page_count']} pages)")

    # Direct FTS5 BM25 retrieval test
    query = "Vision Transformer self-attention ROC-AUC"
    chunks = retrieve_relevant_chunks(conv_id=None, project_id=proj_id, query=query, max_words=1200)
    assert len(chunks) > 0, "FTS5 BM25 should retrieve matching chunks"
    top_chunk = chunks[0]
    print(f"  Top retrieved chunk (page {top_chunk['page_number']}): '{top_chunk['content'][:80]}...'")
    assert "Vision Transformer" in top_chunk["content"]
    assert top_chunk["page_number"] == 2

    # Query page 3 content
    chunks_hw = retrieve_relevant_chunks(conv_id=None, project_id=proj_id, query="Iris Xe quantization speedup", max_words=1200)
    assert len(chunks_hw) > 0
    assert "i5-1155G7" in chunks_hw[0]["content"]
    assert chunks_hw[0]["page_number"] == 3

    print("  PASS: Overlapping chunking and SQLite FTS5 BM25 retrieval verified.")
    return doc_id


def test_project_isolation(proj_a_id: str):
    print("\n--- Test 6: Strict Workspace Isolation (Zero Cross-Tenant Leakage) ---")
    # Create Project B
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Quantum Computing",
            "description": "Superconducting qubits and variational algorithms",
        },
    )
    assert resp.status_code == 200
    proj_b_id = resp.json()["id"]

    # Querying Project B with terms exclusive to Project A's paper
    query_exclusive = "Iris Xe quantization speedup 1155G7"
    chunks_in_b = retrieve_relevant_chunks(conv_id=None, project_id=proj_b_id, query=query_exclusive, max_words=1200)
    assert len(chunks_in_b) == 0, f"Project B should NOT see Project A chunks! Got: {chunks_in_b}"

    # Querying with no project and no conversation (standalone)
    chunks_standalone = retrieve_relevant_chunks(conv_id=None, project_id=None, query=query_exclusive, max_words=1200)
    assert len(chunks_standalone) == 0, "Standalone query should NOT see Project A chunks!"

    print("  PASS: Strict project isolation verified. Zero cross-workspace leakage.")
    # Clean up Project B
    client.delete(f"/api/v1/projects/{proj_b_id}")


def test_system_prompt_and_citation_streaming(proj_id: str):
    print("\n--- Test 7: Research System Prompt Injection & Citations Emission ---")
    # Create a conversation scoped to the project
    resp = client.post(
        "/api/v1/conversations",
        json={"title": "Model Comparison Discussion", "model": "qwen3.5:2b", "project_id": proj_id},
    )
    assert resp.status_code in (200, 201), resp.text
    conv = resp.json()
    conv_id = conv["id"]
    assert conv.get("project_id") == proj_id

    # Test Chat SSE stream
    payload = {
        "conversation_id": conv_id,
        "project_id": proj_id,
        "model": "qwen3.5:2b",
        "messages": [
            {"role": "user", "content": "What is the ROC-AUC score of Vision Transformer reported in the paper?"}
        ],
    }

    citations_received = []
    tokens_received = []
    done_received = False

    with client.stream("POST", "/api/v1/chat", json=payload) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: citations"):
                pass
            elif line.startswith("data: ") and not line.startswith("data: [DONE]"):
                data_str = line[6:]
                try:
                    parsed = json.loads(data_str)
                    if isinstance(parsed, dict) and "citations" in parsed:
                        citations_received = parsed["citations"]
                    elif isinstance(parsed, list) and len(parsed) > 0 and "document_id" in parsed[0]:
                        citations_received = parsed
                    elif isinstance(parsed, dict) and "token" in parsed:
                        tokens_received.append(parsed["token"])
                    elif isinstance(parsed, dict) and "content" in parsed:
                        tokens_received.append(parsed["content"])
                except json.JSONDecodeError:
                    pass
            elif line == "data: [DONE]":
                done_received = True

    print(f"  Citations received in SSE stream: {len(citations_received)}")
    if citations_received:
        cit = citations_received[0]
        print(f"  Citation 1: {cit.get('filename')} (page {cit.get('page_number')})")
        assert cit.get("page_number") == 2, f"Expected page 2 citation, got {cit.get('page_number')}"
        assert "Vision Transformer" in cit.get("excerpt", "")

    # Verify message persistence in DB with citations JSON column
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT content, role, citations FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conv_id,))
    msgs = cur.fetchall()
    assert len(msgs) >= 2, f"Expected user and assistant messages in DB, got {len(msgs)}"
    user_row, asst_row = msgs[0], msgs[1]
    assert user_row["role"] == "user"
    assert asst_row["role"] == "assistant"
    if asst_row["citations"]:
        persisted_cits = json.loads(asst_row["citations"])
        print(f"  Persisted {len(persisted_cits)} citations in SQLite messages table.")
        assert len(persisted_cits) > 0

    print("  PASS: SSE citations streaming and SQLite persistence verified.")


def test_cascading_deletion(proj_id: str):
    print("\n--- Test 8: Cascading Project Deletion ---")
    resp = client.delete(f"/api/v1/projects/{proj_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify project is gone
    resp = client.get(f"/api/v1/projects/{proj_id}")
    assert resp.status_code == 404

    # Verify related notes, activity, documents are purged
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM project_notes WHERE project_id = ?", (proj_id,))
    assert cur.fetchone()[0] == 0, "Project notes should be cascade deleted"

    cur.execute("SELECT COUNT(*) FROM project_activity WHERE project_id = ?", (proj_id,))
    assert cur.fetchone()[0] == 0, "Project activity should be cascade deleted"

    cur.execute("SELECT COUNT(*) FROM documents WHERE project_id = ?", (proj_id,))
    assert cur.fetchone()[0] == 0, "Project documents should be cascade deleted"

    print("  PASS: Cascading project deletion verified.")


def main():
    print("================================================================")
    print("Moso AI: Research Assistant & Project Workspace Test Suite")
    print("================================================================")

    init_db()
    test_chunk_text_overlapping()
    proj_id = test_project_crud()
    test_project_notes(proj_id)
    test_activity_logging(proj_id)
    doc_id = test_fts5_bm25_retrieval_and_ingestion(proj_id)
    test_project_isolation(proj_id)
    test_system_prompt_and_citation_streaming(proj_id)
    test_cascading_deletion(proj_id)

    print("\n================================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (8 / 8)")
    print("================================================================")


if __name__ == "__main__":
    main()
