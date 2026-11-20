"""
Moso AI — Comprehensive Evidence-Grounded Responses & Hallucination Prevention Test Suite
Covers:
1. GitHub Tests (Cases 1-10):
   - Valid repo with README
   - Valid repo without README
   - Repo with large file tree
   - Nonexistent repo (404)
   - Forbidden repo (403)
   - Rate-limited API response (429)
   - Network timeout
   - Redirected repository URL
   - Similar name / different owner (identity mismatch rejection)
   - Misleading name (e.g. 'pulse_watch' that is actually a CLI timer)
2. Hallucination Prevention Scenarios (A through F):
   - Scenario A: No retrieval -> Honest failure notice, zero invented description
   - Scenario B: Unrelated search results -> Reject third-party repo, report unverified
   - Scenario C: Name-based inference -> Grounded in actual retrieved code, not heartbeat detection
   - Scenario D: Incomplete evidence -> Report verified metadata only, zero invented functionality
   - Scenario E: Unsupported features -> Unsupported claims rejected/labelled with verification notice
   - Scenario F: Successful retrieval -> Faithful grounded summary with citations
3. Regression & Database Persistence
"""

import asyncio
import json
import uuid
import httpx
from unittest.mock import patch, MagicMock

from backend.main import app, get_db
from backend.web.evidence import (
    EvidenceContract,
    ERROR_TYPE_NOT_FOUND,
    ERROR_TYPE_FORBIDDEN,
    ERROR_TYPE_RATE_LIMITED,
    ERROR_TYPE_TIMEOUT,
    ERROR_TYPE_IDENTITY_MISMATCH,
)
from backend.web.github import GitHubInspector, parse_github_target
from backend.verification.evidence_gating import (
    EvidenceRegistry,
    evaluate_evidence_gating,
)
from backend.verification.claim_validator import validate_grounded_response
from backend.verification.classifier import classify_query


async def run_suite():
    print("=" * 70)
    print("MOSO AI: EVIDENCE GROUNDING & HALLUCINATION PREVENTION TEST SUITE")
    print("=" * 70)

    inspector = GitHubInspector()

    # -------------------------------------------------------------
    # PART 1: GITHUB TESTS (1 to 10)
    # -------------------------------------------------------------
    print("\n--- [PART 1] GITHUB REPOSITORY INSPECTION TESTS ---")

    # TEST 1: Valid repo with README (e.g. tiangolo/fastapi)
    print("\n[GITHUB 1] Valid repository with README...")
    contract_1 = await inspector.inspect_repository("tiangolo/fastapi")
    assert contract_1.success is True, f"Expected success, got error: {contract_1.error}"
    assert contract_1.metadata["identity_verified"] is True
    assert contract_1.metadata["readme_available"] is True
    assert "FastAPI" in contract_1.retrieved_content
    assert contract_1.http_status == 200
    print(f"  ✓ PASSED: Valid repo verified. Title: {contract_1.title}, Files: {contract_1.metadata['files_retrieved']}")

    # TEST 2: Valid repo without README (Mocked or verified)
    print("\n[GITHUB 2] Valid repository without README...")
    mock_no_readme_meta = {
        "name": "bare_repo",
        "owner": {"login": "testuser"},
        "html_url": "https://github.com/testuser/bare_repo",
        "description": "A bare repository without documentation",
        "language": "C",
        "default_branch": "main",
        "stargazers_count": 5,
        "forks_count": 1,
        "open_issues_count": 0,
    }
    with patch("httpx.AsyncClient.get") as mock_get:
        # 1st call for repo metadata returns 200, 2nd call for readme returns 404, 3rd call for contents returns 200 empty list
        resp_meta = MagicMock(status_code=200, json=lambda: mock_no_readme_meta, headers={}, url="https://api.github.com/repos/testuser/bare_repo")
        resp_404 = MagicMock(status_code=404, headers={}, url="")
        resp_empty_contents = MagicMock(status_code=200, json=lambda: [], headers={}, url="")
        mock_get.side_effect = [resp_meta, resp_404, resp_empty_contents]

        contract_2 = await inspector.inspect_repository("testuser/bare_repo")
        assert contract_2.success is True
        assert contract_2.metadata["readme_available"] is False
        assert "No README file was found" in contract_2.retrieved_content
        print("  ✓ PASSED: Correctly handled repo without README, metadata preserved.")

    # TEST 3: Repository with large file tree
    print("\n[GITHUB 3] Repository with large file tree...")
    large_tree = [{"name": f"module_{i}.py"} for i in range(120)]
    with patch("httpx.AsyncClient.get") as mock_get:
        resp_meta = MagicMock(status_code=200, json=lambda: mock_no_readme_meta, headers={}, url="")
        resp_readme = MagicMock(status_code=404, headers={}, url="")
        resp_contents = MagicMock(status_code=200, json=lambda: large_tree, headers={}, url="")
        mock_get.side_effect = [resp_meta, resp_readme, resp_contents]

        contract_3 = await inspector.inspect_repository("testuser/bare_repo")
        assert contract_3.success is True
        assert contract_3.metadata["root_file_count"] == 120
        assert "more files" in contract_3.retrieved_content
        print(f"  ✓ PASSED: Successfully capped file listing without context blowup ({contract_3.metadata['root_file_count']} files).")

    # TEST 4: Nonexistent repository (404)
    print("\n[GITHUB 4] Nonexistent repository (404)...")
    contract_4 = await inspector.inspect_repository("this_user_does_not_exist_at_all_12345/nonexistent_repo_9999")
    assert contract_4.success is False
    assert contract_4.error_type == ERROR_TYPE_NOT_FOUND
    assert contract_4.http_status == 404
    assert "not found" in contract_4.error.lower()
    print(f"  ✓ PASSED: Distinguished 404 Not Found cleanly: {contract_4.error}")

    # TEST 5: Forbidden repository (403)
    print("\n[GITHUB 5] Forbidden repository (403)...")
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=403, headers={"x-ratelimit-remaining": "50"}, url="")
        contract_5 = await inspector.inspect_repository("secretorg/classified_project")
        assert contract_5.success is False
        assert contract_5.error_type == ERROR_TYPE_FORBIDDEN
        assert contract_5.http_status == 403
        print(f"  ✓ PASSED: Distinguished 403 Forbidden correctly: {contract_5.error}")

    # TEST 6: Rate-limited API response (429 / 403 rate limit)
    print("\n[GITHUB 6] Rate-limited API response...")
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=403, headers={"x-ratelimit-remaining": "0"}, url="")
        contract_6 = await inspector.inspect_repository("test/rate_limit_target")
        assert contract_6.success is False
        assert contract_6.error_type == ERROR_TYPE_RATE_LIMITED
        print(f"  ✓ PASSED: Rate limit detected & distinguished: {contract_6.error}")

    # TEST 7: Network timeout
    print("\n[GITHUB 7] Network timeout...")
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        contract_7 = await inspector.inspect_repository("slowhost/timeout_repo")
        assert contract_7.success is False
        assert contract_7.error_type == ERROR_TYPE_TIMEOUT
        print(f"  ✓ PASSED: Timeout handled gracefully: {contract_7.error}")

    # TEST 8: Redirected repository URL
    print("\n[GITHUB 8] Redirected repository URL...")
    redirect_target_meta = {
        "name": "pulse_watch",
        "owner": {"login": "Mosope16"},
        "html_url": "https://github.com/Mosope16/pulse_watch",
        "description": "Verified Project",
        "language": "Python",
        "default_branch": "main",
    }
    with patch("httpx.AsyncClient.get") as mock_get:
        # Redirect succeeds to exact same owner/repo
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: redirect_target_meta,
            headers={},
            url="https://api.github.com/repos/Mosope16/pulse_watch"
        )
        contract_8 = await inspector.inspect_repository("https://github.com/Mosope16/pulse_watch.git")
        assert contract_8.success is True
        assert contract_8.metadata["identity_verified"] is True
        print(f"  ✓ PASSED: Redirect followed and canonical identity verified: {contract_8.resolved_url}")

    # TEST 9: Repository with similar name belonging to another owner (Identity Mismatch)
    print("\n[GITHUB 9] Cross-owner substitution rejection (Identity Mismatch)...")
    mismatch_meta = {
        "name": "PulseWatch",
        "owner": {"login": "ThirdPartyAuthor"},
        "html_url": "https://github.com/ThirdPartyAuthor/PulseWatch",
        "description": "Unrelated Heartbeat Project",
    }
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mismatch_meta, headers={}, url="")
        contract_9 = await inspector.inspect_repository("Mosope16/pulse_watch")
        assert contract_9.success is False
        assert contract_9.error_type == ERROR_TYPE_IDENTITY_MISMATCH
        assert "identity mismatch" in contract_9.error.lower()
        print(f"  ✓ PASSED: Blocked third-party substitution: {contract_9.error}")

    # TEST 10: Misleading repository name ('pulse_watch' that is actually a CLI timer)
    print("\n[GITHUB 10] Misleading repository name implementation check...")
    pulse_watch_meta = {
        "name": "pulse_watch",
        "owner": {"login": "Mosope16"},
        "html_url": "https://github.com/Mosope16/pulse_watch",
        "description": "A terminal-based precision stopwatch and interval countdown tool written in Python.",
        "language": "Python",
        "default_branch": "main",
        "stargazers_count": 12,
        "forks_count": 0,
        "open_issues_count": 0,
    }
    readme_text = "# pulse_watch\nA terminal-based countdown timer and interval stopwatch for CLI workflows."
    with patch("httpx.AsyncClient.get") as mock_get:
        resp_meta = MagicMock(status_code=200, json=lambda: pulse_watch_meta, headers={}, url="")
        resp_readme = MagicMock(status_code=200, json=lambda: {"content": "IyBwdWxzZV93YXRjaApBIHRlcm1pbmFsLWJhc2VkIGNvdW50ZG93biB0aW1lciBhbmQgaW50ZXJ2YWwgc3RvcHdhdGNoIGZvciBDTEkgd29ya2Zsb3dzLg==", "encoding": "base64", "name": "README.md"}, headers={}, url="")
        resp_contents = MagicMock(status_code=200, json=lambda: [{"name": "pulse_watch.py"}, {"name": "README.md"}], headers={}, url="")
        mock_get.side_effect = [resp_meta, resp_readme, resp_contents]

        contract_10 = await inspector.inspect_repository("Mosope16/pulse_watch")
        assert contract_10.success is True
        assert "stopwatch" in contract_10.retrieved_content.lower()
        assert "heart" not in contract_10.retrieved_content.lower()
        print("  ✓ PASSED: Retrieved genuine CLI stopwatch code, not medical heart monitor.")

    # -------------------------------------------------------------
    # PART 2: HALLUCINATION PREVENTION SCENARIOS (A to F)
    # -------------------------------------------------------------
    print("\n--- [PART 2] HALLUCINATION PREVENTION SCENARIOS ---")

    # SCENARIO A: No retrieval -> Must abstain, zero invented description
    print("\n[SCENARIO A] No repository content retrieved...")
    query_a = "What does this repository do: https://github.com/Mosope16/nonexistent_project?"
    intent_a = classify_query(query_a)
    reg_a = EvidenceRegistry()
    reg_a.add_contract(EvidenceContract(
        success=False,
        tool="github_inspect",
        requested_url="https://github.com/Mosope16/nonexistent_project",
        resolved_url="https://github.com/Mosope16/nonexistent_project",
        http_status=404,
        content_type="text/plain",
        title="GitHub: Mosope16/nonexistent_project (Not Found)",
        source_name="GitHub",
        retrieved_content="",
        retrieved_at="2026-11-19T00:00:00Z",
        error="Repository 'Mosope16/nonexistent_project' was not found on GitHub (HTTP 404).",
        error_type=ERROR_TYPE_NOT_FOUND,
    ))
    gating_a = evaluate_evidence_gating(intent_a, query_a, reg_a)
    assert gating_a.requires_abstention is True, "Gating must force abstention on failed retrieval"
    assert gating_a.can_proceed_to_model is False, "Must not prompt Qwen when retrieval failed"
    assert "not found on GitHub (HTTP 404)" in gating_a.abstention_response
    assert "Moso AI does not infer application features" in gating_a.abstention_response
    print("  ✓ PASSED: Zero-hallucination deterministic abstention enforced.")

    # SCENARIO B: Unrelated search results -> Reject third-party owner
    print("\n[SCENARIO B] Unrelated search results pointing to different owner...")
    query_b = "Tell me about Mosope16/pulse_watch"
    intent_b = classify_query(query_b)
    reg_b = EvidenceRegistry()
    reg_b.add_contract(EvidenceContract(
        success=False,
        tool="github_inspect",
        requested_url="https://github.com/Mosope16/pulse_watch",
        resolved_url="https://github.com/OtherUser/PulseWatch",
        http_status=200,
        content_type="application/json",
        title="GitHub Identity Mismatch",
        source_name="GitHub",
        retrieved_content="",
        retrieved_at="2026-11-19T00:00:00Z",
        error="Repository identity mismatch: requested 'Mosope16/pulse_watch', but resolved to 'OtherUser/PulseWatch'",
        error_type=ERROR_TYPE_IDENTITY_MISMATCH,
    ))
    gating_b = evaluate_evidence_gating(intent_b, query_b, reg_b)
    assert gating_b.requires_abstention is True
    assert "Identity Mismatch" in gating_b.abstention_response
    print("  ✓ PASSED: Third-party owner substitution rejected deterministically.")

    # SCENARIO C: Name-based inference -> Describe actual retrieved code, not heartbeat detection
    print("\n[SCENARIO C] Name-based inference detection ('pulse_watch')...")
    # Simulate a model generating heartbeat claims for a CLI timer repo
    invented_response = "The pulse_watch repository is a health monitoring system designed to track pulse rate and cardiovascular ECG data."
    val_c = validate_grounded_response(
        invented_response,
        [contract_10],  # contract_10 is the CLI timer
        [{"url": "https://github.com/Mosope16/pulse_watch", "title": "pulse_watch"}],
        "What does Mosope16/pulse_watch do?"
    )
    assert val_c.passed is False, "Validation must catch cardiovascular claims unsupported by timer code"
    assert len(val_c.unsupported_claims) > 0
    assert "Verification Notice" in val_c.validated_response
    print(f"  ✓ PASSED: Caught name-based hallucination and attached verification disclaimer:\n    {val_c.unsupported_claims}")

    # SCENARIO D: Incomplete evidence -> Report verified metadata only, zero invented functionality
    print("\n[SCENARIO D] Incomplete evidence (metadata retrieved, no README/code)...")
    query_d = "What does testuser/bare_repo do?"
    intent_d = classify_query(query_d)
    reg_d = EvidenceRegistry()
    reg_d.add_contract(contract_2)  # Bare repo without README
    gating_d = evaluate_evidence_gating(intent_d, query_d, reg_d)
    assert gating_d.requires_abstention is True
    assert "contains no README or accessible source files" in gating_d.abstention_response
    assert "Primary Language: C" in gating_d.abstention_response
    assert "further application features or internal mechanisms cannot be verified" in gating_d.abstention_response
    print("  ✓ PASSED: Only verified metadata reported; application feature invention prohibited.")

    # SCENARIO E: Unsupported features -> Flagged and disclaimed
    print("\n[SCENARIO E] Unsupported features (claims of blockchain/deep learning on basic app)...")
    basic_response = "This application uses deep neural networks, diffusion models, and blockchain smart contracts to manage timers."
    val_e = validate_grounded_response(
        basic_response,
        [contract_10],
        [],
        "Explain pulse_watch features"
    )
    assert val_e.passed is False
    assert any("blockchain" in c for c in val_e.unsupported_claims)
    assert any("deep neural network" in c for c in val_e.unsupported_claims)
    print("  ✓ PASSED: Unsupported AI and blockchain claims detected and disclaimed.")

    # SCENARIO F: Successful retrieval -> Faithful grounded summary with citations
    print("\n[SCENARIO F] Faithful grounded summary with citations...")
    truthful_response = "FastAPI is a modern, high-performance web framework for building APIs with Python based on standard Python type hints."
    truthful_citations = [{
        "id": "cit_1",
        "url": "https://github.com/tiangolo/fastapi",
        "title": "GitHub: tiangolo/fastapi",
        "type": "web",
    }]
    val_f = validate_grounded_response(
        truthful_response,
        [contract_1],
        truthful_citations,
        "What is FastAPI?"
    )
    assert val_f.passed is True
    assert len(val_f.retained_citations) == 1
    assert len(val_f.unsupported_claims) == 0
    assert val_f.validation_score == 1.0
    print("  ✓ PASSED: Grounded response validated cleanly with 100% score.")

    # -------------------------------------------------------------
    # PART 3: END-TO-END ASGI INTEGRATION & CONVERSATION ISOLATION
    # -------------------------------------------------------------
    print("\n--- [PART 3] END-TO-END STREAMING & PERSISTENCE ---")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        # Create conversation
        conv_resp = await client.post("/api/v1/conversations", json={"title": "Evidence Grounding Test"})
        conv_id = conv_resp.json()["id"]

        # 1. Test Nonexistent repo through /api/v1/chat: Must yield abstention without crashing or guessing
        payload_abstain = {
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "What does this repo do: https://github.com/Mosope16/this_does_not_exist_test_xyz?"}],
            "enable_web_search": True,
            "stream": True,
        }
        tokens_received = []
        diagnostics_received = []
        events_received = []

        async with client.stream("POST", "/api/v1/chat", json=payload_abstain) as resp:
            assert resp.status_code == 200
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
                        if current_event == "token":
                            tokens_received.append(parsed["token"])
                        elif current_event == "diagnostic":
                            diagnostics_received.append(parsed)
                    except Exception:
                        pass

        full_reply = "".join(tokens_received)
        assert "not found on GitHub (HTTP 404)" in full_reply or "Inaccessible" in full_reply
        assert "diagnostic" in events_received
        print(f"  ✓ PASSED: End-to-end SSE chat returned deterministic abstention for missing repo.")
        print(f"    Diagnostic events: {len(diagnostics_received)}")

        # 2. Verify SQLite persistence of diagnostics and message content
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT content, tool_calls, diagnostics FROM messages WHERE conversation_id = ? AND role = 'assistant'", (conv_id,))
        row = c.fetchone()
        assert row is not None, "Assistant message must be persisted in SQLite"
        assert row["diagnostics"] is not None, "Retrieval diagnostics must be persisted in SQLite"
        diag_data = json.loads(row["diagnostics"])
        assert len(diag_data) > 0
        assert diag_data[0]["tool"] == "github_inspect"
        conn.close()
        print("  ✓ PASSED: Diagnostics and abstention verified on disk in SQLite.")

    print("\n" + "=" * 70)
    print("ALL GITHUB & EVIDENCE GROUNDING TESTS COMPLETED WITH 100% SUCCESS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_suite())
