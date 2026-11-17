"""
Moso AI Backend Automated Verification Test Suite
Tests all endpoints, SQLite persistence, SSE streaming, Ollama integration, and error handling.
"""

import sys
import os
import asyncio
import json
import sqlite3
import httpx

# Ensure backend module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app, DB_FILE, get_db

async def run_tests():
    print("=" * 60)
    print("RUNNING MOSO AI BACKEND VERIFICATION TEST SUITE")
    print("=" * 60)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # --------------------------------------------------
        # 1. Test Health Endpoint
        # --------------------------------------------------
        print("\n[TEST 1] GET /api/v1/health")
        resp = await client.get("/api/v1/health")
        print(f"Status: {resp.status_code}")
        health_data = resp.json()
        print(f"Payload: {json.dumps(health_data, indent=2)}")
        assert resp.status_code == 200, "Health check failed"
        assert health_data["database"] == "sqlite", "Database should be sqlite"
        assert health_data["database_connected"] is True, "Database should be connected"
        assert health_data["active_model"] == "qwen3.5:2b", "Active model should be qwen3.5:2b"
        print("✓ Health endpoint verified")

        # --------------------------------------------------
        # 2. Test Models Endpoint
        # --------------------------------------------------
        print("\n[TEST 2] GET /api/v1/models")
        resp = await client.get("/api/v1/models")
        assert resp.status_code == 200, "Models check failed"
        models = resp.json()
        print(f"Retrieved {len(models)} model(s): {[m['id'] for m in models]}")
        default_model = next((m for m in models if m.get("is_default")), None)
        assert default_model is not None, "A default model must be returned"
        assert default_model["id"] == "qwen3.5:2b", f"Default model must be qwen3.5:2b, got {default_model['id']}"
        print("✓ Models endpoint verified (qwen3.5:2b is default)")

        # --------------------------------------------------
        # 3. Test Conversation Lifecycle (CRUD)
        # --------------------------------------------------
        print("\n[TEST 3] Conversation Lifecycle (Create -> List -> Rename -> Get -> Delete)")
        
        # 3a. Create
        create_resp = await client.post("/api/v1/conversations", json={
            "title": "Initial Test Conversation",
            "model": "qwen3.5:2b"
        })
        assert create_resp.status_code == 201, "Create conversation failed"
        conv = create_resp.json()
        conv_id = conv["id"]
        assert conv_id.startswith("conv_"), "Conversation ID must use UUID format"
        assert conv["title"] == "Initial Test Conversation"
        print(f"✓ Created conversation with ID: {conv_id}")

        # 3b. List
        list_resp = await client.get("/api/v1/conversations")
        assert list_resp.status_code == 200
        all_convs = list_resp.json()
        assert any(c["id"] == conv_id for c in all_convs), "Created conversation must be in list"
        print(f"✓ Listed {len(all_convs)} conversation(s) from SQLite")

        # 3c. Rename via PATCH
        patch_resp = await client.patch(f"/api/v1/conversations/{conv_id}", json={
            "title": "Renamed Architecture Plan"
        })
        assert patch_resp.status_code == 200, "Rename conversation failed"
        renamed = patch_resp.json()
        assert renamed["title"] == "Renamed Architecture Plan", "Title was not updated"
        print(f"✓ Renamed conversation title via PATCH: '{renamed['title']}'")

        # 3d. Get single
        get_resp = await client.get(f"/api/v1/conversations/{conv_id}")
        assert get_resp.status_code == 200
        conv_data = get_resp.json()
        assert conv_data["title"] == "Renamed Architecture Plan"
        print("✓ Retrieved single conversation")

        # --------------------------------------------------
        # 4. Test Chat Generation, Persistence & Ordering
        # --------------------------------------------------
        print("\n[TEST 4] POST /api/v1/chat with SSE Streaming and SQLite Persistence")
        prompt_text = "What is 2+2? Answer in one word."
        chat_req = {
            "conversation_id": conv_id,
            "model": "qwen3.5:2b",
            "messages": [
                {"role": "user", "content": prompt_text}
            ],
            "stream": True,
            "max_tokens": 64,
            "temperature": 0.0
        }

        tokens_received = []
        full_sse_text = ""
        completion_received = False

        async with client.stream("POST", "/api/v1/chat", json=chat_req, timeout=60.0) as chat_resp:
            assert chat_resp.status_code == 200, f"Chat endpoint returned {chat_resp.status_code}"
            assert "text/event-stream" in chat_resp.headers["content-type"]

            async for line in chat_resp.aiter_lines():
                full_sse_text += line + "\n"
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        completion_received = True
                        break
                    try:
                        parsed = json.loads(data_str)
                        if "token" in parsed:
                            tokens_received.append(parsed["token"])
                    except json.JSONDecodeError:
                        pass

        streamed_output = "".join(tokens_received).strip()
        print(f"✓ SSE Stream completed. Streamed output: '{streamed_output}'")
        assert len(tokens_received) > 0, "Expected incremental tokens in SSE stream"
        assert completion_received, "Expected [DONE] termination signal"

        # --------------------------------------------------
        # 5. Verify SQLite Messages Persistence & Recovery
        # --------------------------------------------------
        print("\n[TEST 5] Verify Message Persistence and Chronological Ordering in SQLite")
        get_conv_after_chat = await client.get(f"/api/v1/conversations/{conv_id}")
        assert get_conv_after_chat.status_code == 200
        conv_with_msgs = get_conv_after_chat.json()
        msgs = conv_with_msgs["messages"]
        print(f"Total messages stored in SQLite for {conv_id}: {len(msgs)}")
        assert len(msgs) == 2, f"Expected 2 messages (1 user, 1 assistant), got {len(msgs)}"

        # Verify User Message
        user_msg = msgs[0]
        assert user_msg["role"] == "user", "First message must be user role"
        assert user_msg["content"] == prompt_text, "User message content must match prompt"
        assert user_msg["id"].startswith("msg_"), "User message ID must be a UUID"
        print(f"✓ User message verified: id={user_msg['id']}, role={user_msg['role']}")

        # Verify Assistant Message
        asst_msg = msgs[1]
        assert asst_msg["role"] == "assistant", "Second message must be assistant role"
        assert len(asst_msg["content"].strip()) > 0, "Assistant response cannot be empty"
        assert asst_msg["id"].startswith("msg_"), "Assistant message ID must be a UUID"
        print(f"✓ Assistant message verified: id={asst_msg['id']}, role={asst_msg['role']}")

        # --------------------------------------------------
        # 6. Test Backend Restart Simulation (Direct SQLite query)
        # --------------------------------------------------
        print("\n[TEST 6] Simulated Backend Restart: Direct SQLite Recovery")
        db_conn = sqlite3.connect(DB_FILE)
        db_conn.row_factory = sqlite3.Row
        cur = db_conn.cursor()
        cur.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        recovered_conv = cur.fetchone()
        assert recovered_conv is not None, "Conversation must persist in database file"

        cur.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC", (conv_id,))
        recovered_msgs = cur.fetchall()
        assert len(recovered_msgs) == 2, "All messages must persist across connections"
        print(f"✓ Direct SQLite check: Conversation and {len(recovered_msgs)} messages verified on disk ({DB_FILE})")
        db_conn.close()

        # --------------------------------------------------
        # 7. Test Error Handling for Invalid/Missing Model
        # --------------------------------------------------
        print("\n[TEST 7] Error Handling for Invalid Model")
        bad_chat_req = {
            "conversation_id": conv_id,
            "model": "model_that_does_not_exist_xyz123",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True
        }
        async with client.stream("POST", "/api/v1/chat", json=bad_chat_req) as bad_resp:
            lines = [l async for l in bad_resp.aiter_lines() if l.strip()]
            error_event_found = any("event: error" in l or "Ollama error" in l or "STREAM_EXCEPTION" in l for l in lines)
            print(f"✓ Error response received properly as SSE error event: {lines}")
            assert error_event_found, "Invalid model must yield an error event, not ordinary text"

        # --------------------------------------------------
        # 8. Test Delete Conversation Cleanup
        # --------------------------------------------------
        print("\n[TEST 8] DELETE /api/v1/conversations/{conv_id}")
        del_resp = await client.delete(f"/api/v1/conversations/{conv_id}")
        assert del_resp.status_code == 200
        print("✓ Deleted conversation")

        # Verify deletion in SQLite
        get_deleted = await client.get(f"/api/v1/conversations/{conv_id}")
        assert get_deleted.status_code == 404, "Deleted conversation must return 404"
        print("✓ Verified deleted conversation returns 404")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
