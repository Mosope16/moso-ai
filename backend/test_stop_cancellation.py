"""
Test SSE stream interruption and cancellation handling when client stops early.
"""

import sys
import os
import asyncio
import json
import sqlite3
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.main import app, DB_FILE

async def test_cancellation():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create conversation
        conv_resp = await client.post("/api/v1/conversations", json={"title": "Cancellation Test", "model": "qwen3.5:2b"})
        conv_id = conv_resp.json()["id"]

        print(f"Created conversation {conv_id} for cancellation test")

        tokens_before_abort = []
        try:
            async with client.stream(
                "POST",
                "/api/v1/chat",
                json={
                    "conversation_id": conv_id,
                    "model": "qwen3.5:2b",
                    "messages": [{"role": "user", "content": "Write a long essay explaining quantum physics."}],
                    "stream": True,
                    "max_tokens": 128
                },
                timeout=30.0
            ) as chat_resp:
                async for line in chat_resp.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            parsed = json.loads(data_str)
                            if "token" in parsed:
                                tokens_before_abort.append(parsed["token"])
                                # Simulate pressing Stop after 3 tokens
                                if len(tokens_before_abort) >= 3:
                                    print(f"User clicked STOP after {len(tokens_before_abort)} tokens!")
                                    break
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"Stream abort handled: {e}")

        # Check database: user message must be present, conversation must not be corrupted
        db_conn = sqlite3.connect(DB_FILE)
        cur = db_conn.cursor()
        cur.execute("SELECT id, role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC", (conv_id,))
        msgs = cur.fetchall()
        print(f"Messages in database after abort: {len(msgs)}")
        for m in msgs:
            print(f" - [{m[1]}] {m[0]}: {m[2][:40]}...")
        assert len(msgs) >= 1, "User message must be preserved in SQLite even after client abort"
        assert msgs[0][1] == "user", "First message must be user"

        # Cleanup
        await client.delete(f"/api/v1/conversations/{conv_id}")
        db_conn.close()
        print("✓ Cancellation test passed cleanly without database corruption")

if __name__ == "__main__":
    asyncio.run(test_cancellation())
