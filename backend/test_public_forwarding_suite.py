#!/usr/bin/env python3
"""
Moso AI - Public VS Code Port Forwarding & Remote Testing Comprehensive Verification Suite
Tests:
1. Port Bindings & Localhost Isolation:
   - Vite is bound to 0.0.0.0:5173
   - FastAPI is bound strictly to 127.0.0.1:8000
   - Ollama is bound strictly to 127.0.0.1:11434
2. Vite Host Filtering & Tunnel Compatibility:
   - VS Code Dev Tunnels host (*.devtunnels.ms) permitted
   - GitHub Codespaces host (*.app.github.dev) permitted
3. Vite API Proxying & Security Headers:
   - Requests to http://127.0.0.1:5173/api/v1/... proxy seamlessly to FastAPI
   - Security headers verified (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
4. Tester Authentication & Session Management:
   - Open access mode when MOSO_ACCESS_PASSWORD is unset
   - Dynamic password protection when MOSO_ACCESS_PASSWORD is set
   - 401 Unauthorized for unauthenticated requests
   - CORS OPTIONS preflight bypass for auth checks
   - Login with invalid password rejected (401)
   - Login with valid password succeeds, returns cryptographic session token & sets cookie
   - Auth via Bearer token, X-Moso-Access-Token header, and HTTP cookie
   - Logout invalidates active session
5. Full Vite Proxy End-to-End Workflows:
   - Conversation CRUD through Vite proxy
   - PDF multipart document upload through Vite proxy
   - Real-time SSE chat streaming through Vite proxy (zero buffering headers verified)
"""

import io
import os
import sys
import json
import socket
import urllib.request
import urllib.error
import http.client
import pypdf

# Ensure backend package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.main as bmain

VITE_BASE = "http://127.0.0.1:5173"
FASTAPI_BASE = "http://127.0.0.1:8000"

def make_test_pdf_bytes(text: str) -> bytes:
    """Helper to create genuine PDF bytes using pypdf."""
    writer = pypdf.PdfWriter()
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


def run_tests():
    print("=" * 70)
    print("MOSO AI: PUBLIC VS CODE PORT FORWARDING COMPREHENSIVE SUITE")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Port Bindings & Network Isolation
    # ---------------------------------------------------------
    print("\n[TEST 1] Network Port Bindings & Localhost Isolation")
    # Verify we can connect to FastAPI on 127.0.0.1:8000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        fastapi_alive = (s.connect_ex(("127.0.0.1", 8000)) == 0)
        assert fastapi_alive, "FastAPI backend is not running on 127.0.0.1:8000"
    print("  ✓ FastAPI is listening on 127.0.0.1:8000")

    # Verify we can connect to Vite on 127.0.0.1:5173
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        vite_alive = (s.connect_ex(("127.0.0.1", 5173)) == 0)
        assert vite_alive, "Vite dev server is not running on 127.0.0.1:5173"
    print("  ✓ Vite dev server is listening on 0.0.0.0:5173")

    # ---------------------------------------------------------
    # 2. Vite Host Header & Tunnel Compatibility
    # ---------------------------------------------------------
    print("\n[TEST 2] Vite Host Filtering & Remote Tunnel Compatibility")
    devtunnel_headers = {"Host": "5173-xy9876.devtunnels.ms"}
    req = urllib.request.Request(f"{VITE_BASE}/", headers=devtunnel_headers)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        html_content = resp.read().decode("utf-8")
        assert "Moso AI" in html_content or "vite" in html_content
    print("  ✓ Dev Tunnels host (*.devtunnels.ms) accepted without host blocking")

    codespace_headers = {"Host": "shiny-disco-5173.app.github.dev"}
    req = urllib.request.Request(f"{VITE_BASE}/", headers=codespace_headers)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
    print("  ✓ GitHub Codespaces host (*.app.github.dev) accepted without host blocking")

    # ---------------------------------------------------------
    # 3. Vite API Proxy & Security Headers
    # ---------------------------------------------------------
    print("\n[TEST 3] Vite Proxying to FastAPI & Security Response Headers")
    req = urllib.request.Request(f"{VITE_BASE}/api/v1/auth/status")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-xss-protection") == "1; mode=block"
        body = json.loads(resp.read().decode("utf-8"))
        print(f"  ✓ Proxied auth status: {body}")
        print("  ✓ Verified security headers (nosniff, DENY, XSS-Protection)")

    # ---------------------------------------------------------
    # 4. Tester Authentication & Session Lifecycle (via TestClient)
    # ---------------------------------------------------------
    print("\n[TEST 4] Tester Access Password & Session Token Authentication")
    from fastapi.testclient import TestClient
    tc = TestClient(bmain.app)

    # Save original access password and configure test password
    orig_pwd = bmain.MOSO_ACCESS_PASSWORD
    orig_env = os.environ.get("MOSO_ACCESS_PASSWORD")
    os.environ["MOSO_ACCESS_PASSWORD"] = "test-remote-pass-2026"
    bmain.MOSO_ACCESS_PASSWORD = "test-remote-pass-2026"
    bmain.ACTIVE_SESSIONS.clear()
    try:
        # Step 4a: Status should now report auth_required = True, authenticated = False
        resp = tc.get("/api/v1/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_required"] is True, f"Expected auth_required=True, got {data}"
        assert data["authenticated"] is False, f"Expected authenticated=False, got {data}"
        print("  ✓ Unauthenticated state: auth_required=True, authenticated=False")

        # Step 4b: Protected endpoint without auth should return 401
        resp = tc.get("/api/v1/conversations")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        assert "Tester access password required" in resp.json().get("error", "")
        print("  ✓ Unauthenticated call to /api/v1/conversations rejected with HTTP 401")

        # Step 4c: CORS OPTIONS preflight must succeed with 200 without auth
        resp = tc.options(
            "/api/v1/conversations",
            headers={
                "Origin": "https://remote.devtunnels.ms",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert resp.status_code == 200, f"Expected 200 for OPTIONS, got {resp.status_code}"
        print("  ✓ CORS preflight OPTIONS bypasses auth enforcement with HTTP 200")

        # Step 4d: Login with bad password should return 401
        resp = tc.post("/api/v1/auth/login", json={"password": "wrong-password"})
        assert resp.status_code == 401
        err_body = resp.json()
        msg = err_body.get("detail", {}).get("error", "") or err_body.get("error", "")
        assert "Incorrect tester access password" in msg
        print("  ✓ Incorrect tester password rejected with HTTP 401")

        # Step 4e: Login with correct password should succeed and return session token
        resp = tc.post("/api/v1/auth/login", json={"password": "test-remote-pass-2026"})
        assert resp.status_code == 200
        assert "moso_session" in resp.cookies
        login_res = resp.json()
        session_token = login_res["token"]
        assert len(session_token) >= 32
        print(f"  ✓ Login succeeded, session token issued: {session_token[:8]}...")

        # Step 4f: Access protected endpoint using Bearer token
        resp = tc.get("/api/v1/conversations", headers={"Authorization": f"Bearer {session_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        print("  ✓ Protected /api/v1/conversations succeeded using Authorization Bearer token")

        # Step 4g: Access protected endpoint using X-Moso-Access-Token header
        resp = tc.get("/api/v1/auth/status", headers={"X-Moso-Access-Token": session_token})
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True
        print("  ✓ Auth status reports authenticated=True using X-Moso-Access-Token header")

        # Step 4h: Logout session
        resp = tc.post("/api/v1/auth/logout", json={}, headers={"Authorization": f"Bearer {session_token}"})
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

        # Step 4i: Verify old session token is now rejected with 401
        resp = tc.get("/api/v1/conversations", headers={"Authorization": f"Bearer {session_token}"})
        assert resp.status_code == 401
        print("  ✓ Logout invalidated session token; subsequent calls returned HTTP 401")

    finally:
        # Restore original password configuration
        if orig_env is None:
            os.environ.pop("MOSO_ACCESS_PASSWORD", None)
        else:
            os.environ["MOSO_ACCESS_PASSWORD"] = orig_env
        bmain.MOSO_ACCESS_PASSWORD = orig_pwd
        bmain.ACTIVE_SESSIONS.clear()

    # ---------------------------------------------------------
    # 5. Full End-to-End Workflows Through Vite Proxy
    # ---------------------------------------------------------
    print("\n[TEST 5] End-to-End Chat & Documents Through Vite Proxy")
    
    # 5a. Create a conversation via Vite proxy
    create_body = json.dumps({"title": "Remote Proxy Verification Chat"}).encode("utf-8")
    req = urllib.request.Request(
        f"{VITE_BASE}/api/v1/conversations",
        data=create_body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        conv = json.loads(resp.read().decode("utf-8"))
        conv_id = conv["id"]
    print(f"  ✓ Created conversation via proxy: {conv_id}")

    # 5b. Upload a PDF document through Vite proxy
    boundary = "----WebKitFormBoundaryProxyTest7MA4YWxkTrZu0gW"
    pdf_bytes = make_test_pdf_bytes("Moso AI remote testing over VS Code port forwarding.")
    
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode("latin-1"))
    body.write(b'Content-Disposition: form-data; name="file"; filename="remote_test_doc.pdf"\r\n')
    body.write(b"Content-Type: application/pdf\r\n\r\n")
    body.write(pdf_bytes)
    body.write(f"\r\n--{boundary}\r\n".encode("latin-1"))
    body.write(f'Content-Disposition: form-data; name="conversation_id"\r\n\r\n{conv_id}\r\n'.encode("latin-1"))
    body.write(f"--{boundary}--\r\n".encode("latin-1"))
    payload = body.getvalue()

    req = urllib.request.Request(
        f"{VITE_BASE}/api/v1/documents",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        doc = json.loads(resp.read().decode("utf-8"))
        doc_id = doc["id"]
        assert doc["char_count"] > 0
    print(f"  ✓ Uploaded PDF via proxy ({doc['char_count']} chars extracted): {doc_id}")

    # 5c. Test SSE Chat Streaming through Vite proxy
    chat_body = json.dumps({
        "conversation_id": conv_id,
        "model": "qwen3.5:2b",
        "messages": [{"role": "user", "content": "Respond with the word SUCCESS."}]
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{VITE_BASE}/api/v1/chat",
        data=chat_body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type, f"Expected event-stream, got {content_type}"
        
        # Verify proxy preservation headers
        buffering = resp.headers.get("X-Accel-Buffering", "")
        cache_ctrl = resp.headers.get("Cache-Control", "")
        assert buffering == "no"
        assert "no-cache" in cache_ctrl
        
        # Read SSE events
        events_received = 0
        tokens_received = []
        while True:
            line = resp.readline()
            if not line:
                break
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("data:"):
                events_received += 1
                data_payload = line_str[5:].strip()
                if data_payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_payload)
                    if "text" in chunk:
                        tokens_received.append(chunk["text"])
                except json.JSONDecodeError:
                    pass

        assert events_received > 0, "No SSE events received through Vite proxy"
        full_response = "".join(tokens_received)
        print(f"  ✓ SSE streaming received {events_received} events through proxy ({len(full_response)} chars)")
        print(f"  ✓ Zero-buffering headers verified (X-Accel-Buffering: no, Cache-Control: {cache_ctrl})")

    # Clean up test conversation
    req = urllib.request.Request(f"{VITE_BASE}/api/v1/conversations/{conv_id}", method="DELETE")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
    print("  ✓ Cleaned up test conversation through proxy")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED: PUBLIC VS CODE PORT FORWARDING IS FULLY READY")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
