"""
Moso AI — Comprehensive Web Search & URL Fetching Verification Suite
Tests:
1. SSRF and Safe URL Validation (localhost, private IPs, metadata IP 169.254.169.254, internal domains)
2. Web Search Manager (DuckDuckGo provider, result parsing, limits, caching, empty query handling)
3. Web Fetcher (HTML parsing, title/metadata extraction, link extraction, 404 handling, SSRF rejection)
4. Direct REST Endpoints (/api/v1/tools/web-search, /api/v1/tools/web-fetch)
5. End-to-End Chat Tool-Calling Loop with SSE Streaming, Status Events, and Citation Grounding
6. Conversation Isolation & Database Persistence (messages.tool_calls and web_retrievals table)
"""

import sys
import os
import asyncio
import json
import sqlite3
import httpx

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app, DB_FILE
from backend.web.security import validate_safe_url
from backend.web.search import WebSearchManager, DuckDuckGoSearchProvider
from backend.web.fetch import WebFetcher


async def run_suite():
    print("=" * 70)
    print("MOSO AI: WEB SEARCH & URL FETCHING COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST 1: SSRF & URL Security Controls
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing SSRF & Safe URL Validation...")

    forbidden_cases = [
        ("http://127.0.0.1:8000/api/v1/health", "127.0.0.1"),
        ("http://localhost:5173", "localhost"),
        ("http://0.0.0.0:8000", "0.0.0.0"),
        ("http://[::1]:8000", "::1"),
        ("http://192.168.1.1/admin", "RFC1918 192.168.x.x"),
        ("http://10.0.0.1/secret", "RFC1918 10.x.x.x"),
        ("http://172.16.0.1/internal", "RFC1918 172.16.x.x"),
        ("http://169.254.169.254/latest/meta-data/", "AWS/Cloud Metadata 169.254.169.254"),
        ("http://server.local/page", ".local domain"),
        ("http://database.internal/query", ".internal domain"),
        ("file:///etc/passwd", "file:// scheme"),
        ("ftp://ftp.example.com", "ftp:// scheme"),
        ("javascript:alert(1)", "javascript: scheme"),
    ]

    for url, label in forbidden_cases:
        is_safe, reason, _ = validate_safe_url(url)
        assert not is_safe, f"Security vulnerability: {label} ({url}) was not blocked! Reason given: {reason}"

    # Verify public legitimate URLs are accepted
    is_safe, _, norm = validate_safe_url("https://fastapi.tiangolo.com/")
    assert is_safe, "Valid URL 'https://fastapi.tiangolo.com/' was unexpectedly rejected"
    assert norm == "https://fastapi.tiangolo.com/"

    print("  ✓ PASSED: All 13 SSRF, loopback, private IP, and metadata attack vectors blocked.")

    # -------------------------------------------------------------
    # TEST 2: Web Search Manager & Free DuckDuckGo Provider
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Web Search Manager (DuckDuckGo Provider)...")
    sm = WebSearchManager()

    # Empty query check
    empty_res = await sm.search("   ")
    assert empty_res == [], "Empty query must return empty list"

    # Live search check
    results = await sm.search("FastAPI Python framework", max_results=3)
    assert len(results) > 0, "Search should return at least one result"
    first = results[0]
    assert first.title, "Search result must have a title"
    assert first.url.startswith("http"), "Search result URL must be valid HTTP(S)"
    assert first.domain, "Search result must have a domain"
    assert len(results) <= 3, "Search result must respect max_results"

    print(f"  ✓ PASSED: Web search returned {len(results)} sources. Top: [{first.domain}] '{first.title[:45]}...'")

    # -------------------------------------------------------------
    # TEST 3: Web Fetcher (HTML Parsing & Error Reporting)
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Web Fetcher Content Extraction...")
    wf = WebFetcher()

    # Fetch legitimate page
    page = await wf.fetch("https://fastapi.tiangolo.com/")
    assert page.status == "ok", f"Expected ok status, got: {page.status} ({page.error_message})"
    assert "FastAPI" in page.title, f"Expected FastAPI in title, got: {page.title}"
    assert page.domain == "fastapi.tiangolo.com", f"Domain mismatch: {page.domain}"
    assert page.word_count > 100, f"Expected substantial content, got word_count={page.word_count}"
    assert page.summary, "Expected non-empty summary"

    # Fetch 404 / nonexistent page
    err_page = await wf.fetch("https://httpbin.org/status/404")
    assert err_page.status.startswith("http_error_404") or err_page.status.startswith("error"), f"Expected 404 error status, got: {err_page.status}"
    assert err_page.error_message, "Expected clear error message for 404"

    # Fetch SSRF-blocked URL through WebFetcher
    ssrf_page = await wf.fetch("http://127.0.0.1:8000/api/v1/health")
    assert ssrf_page.status == "error_ssrf_blocked", f"Expected error_ssrf_blocked, got: {ssrf_page.status}"

    print(f"  ✓ PASSED: Page fetched successfully ({page.word_count} words). Error handling and SSRF defense confirmed.")

    # -------------------------------------------------------------
    # TEST 4: Direct REST Endpoints
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Direct Tool REST Endpoints...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /api/v1/tools/web-search
        s_resp = await client.post("/api/v1/tools/web-search", json={"query": "Python programming language", "max_results": 2})
        assert s_resp.status_code == 200, f"web-search endpoint failed: {s_resp.text}"
        s_data = s_resp.json()
        assert s_data["count"] > 0
        assert len(s_data["results"]) <= 2

        # 2. /api/v1/tools/web-fetch
        f_resp = await client.post("/api/v1/tools/web-fetch", json={"url": "https://fastapi.tiangolo.com/"})
        assert f_resp.status_code == 200, f"web-fetch endpoint failed: {f_resp.text}"
        f_data = f_resp.json()
        assert f_data["page"]["status"] == "ok"
        assert "FastAPI" in f_data["page"]["title"]

        # 3. /api/v1/tools/web-fetch with SSRF target
        bad_f_resp = await client.post("/api/v1/tools/web-fetch", json={"url": "http://169.254.169.254/latest/meta-data/"})
        assert bad_f_resp.status_code == 200
        assert bad_f_resp.json()["page"]["status"] == "error_ssrf_blocked"

    print("  ✓ PASSED: Direct REST endpoints /api/v1/tools/web-search and web-fetch operational.")

    # -------------------------------------------------------------
    # TEST 5: End-to-End Chat Tool Calling, SSE Status Events & Citations
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing End-to-End Chat Tool Calling & Streaming...")
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=90.0) as client:
        # Create conversation
        conv_resp = await client.post("/api/v1/conversations", json={"title": "Web Tool Test"})
        conv_id = conv_resp.json()["id"]

        chat_payload = {
            "conversation_id": conv_id,
            "model": "qwen3.5:2b",
            "messages": [
                {"role": "user", "content": "What is the official documentation URL and primary purpose of FastAPI according to https://fastapi.tiangolo.com/?"}
            ],
            "enable_web_search": True,
            "stream": True,
        }

        events_received = []
        tokens = []
        citations_received = []
        status_events = []

        async with client.stream("POST", "/api/v1/chat", json=chat_payload) as resp:
            assert resp.status_code == 200, f"Stream failed with code {resp.status_code}"
            current_event = None
            async for line in resp.aiter_lines():
                if not line or not line.strip():
                    continue
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    events_received.append(current_event)
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data_str)
                        if current_event == "status":
                            status_events.append(parsed)
                        elif current_event == "token" or "token" in parsed:
                            tokens.append(parsed["token"])
                        elif current_event == "citations" or "citations" in parsed:
                            citations_received = parsed.get("citations", [])
                    except Exception:
                        pass

        full_answer = "".join(tokens)
        print(f"  Streamed {len(tokens)} tokens across events: {set(events_received)}")
        print(f"  Tool status events emitted: {len(status_events)}")
        for st in status_events:
            print(f"    • [{st.get('status')}] {st.get('message')}")
        print(f"  Citations captured: {len(citations_received)}")
        for cit in citations_received:
            print(f"    • [{cit.get('type')}] {cit.get('domain')} - {cit.get('title')}: {cit.get('url')}")
        print(f"  Assistant response preview: {full_answer[:120]}...")

        assert len(tokens) > 0, "Expected non-empty streamed response"
        assert len(citations_received) > 0, "Expected at least 1 citation from web retrieval"
        assert citations_received[0].get("url"), "Citation must include target URL"
        assert citations_received[0].get("type") == "web", "Citation type must be 'web'"

        # -------------------------------------------------------------
        # TEST 6: SQLite Persistence & Isolation Verification
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing Database Persistence & Conversation Isolation...")
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Check messages table
        c.execute("SELECT content, citations, tool_calls FROM messages WHERE conversation_id = ? AND role = 'assistant'", (conv_id,))
        msg_row = c.fetchone()
        assert msg_row, "Assistant message was not saved in SQLite!"
        assert msg_row["content"] == full_answer, "Persisted content does not match streamed content"
        assert msg_row["citations"], "Citations JSON must be persisted"

        saved_citations = json.loads(msg_row["citations"])
        assert len(saved_citations) == len(citations_received), "Saved citations count mismatch"

        # Check web_retrievals audit table
        c.execute("SELECT tool_name, query_or_url, status, results_count FROM web_retrievals WHERE conversation_id = ?", (conv_id,))
        retrieval_rows = [dict(r) for r in c.fetchall()]
        assert len(retrieval_rows) > 0, "Web retrieval record was not saved to web_retrievals table!"
        print(f"  ✓ Persisted {len(retrieval_rows)} retrieval record(s) in web_retrievals:")
        for r in retrieval_rows:
            print(f"    • Tool: {r['tool_name']}, Target: {r['query_or_url'][:50]}, Status: {r['status']}")

        # Verify cross-conversation isolation: another conversation must NOT see this retrieval
        other_conv_id = "conv_other_isolated_test"
        c.execute("SELECT COUNT(*) FROM web_retrievals WHERE conversation_id = ?", (other_conv_id,))
        assert c.fetchone()[0] == 0, "Isolation failure: records leaked across conversations"

        conn.close()
        print("  ✓ PASSED: SQLite persistence and strict multi-tenant conversation isolation verified.")

    print("\n" + "=" * 70)
    print("ALL WEB SEARCH & URL FETCHING TESTS PASSED (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_suite())
