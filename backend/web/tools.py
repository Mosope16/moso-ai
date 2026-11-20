"""
Moso AI — Web Retrieval Tools for Ollama
Defines JSON tool schemas for Ollama `/api/chat` and executes tool calls safely.
Integrates strict EvidenceContract generation, GitHub identity verification,
and error classification.
"""

import json
import uuid
import datetime
from typing import List, Dict, Any, Tuple, Optional
from .search import WebSearchManager, SearchResult
from .fetch import WebFetcher, FetchedPage
from .github import GitHubInspector, parse_github_target
from .evidence import (
    EvidenceContract,
    ERROR_TYPE_NOT_FOUND,
    ERROR_TYPE_FORBIDDEN,
    ERROR_TYPE_RATE_LIMITED,
    ERROR_TYPE_TIMEOUT,
    ERROR_TYPE_CONNECTION_FAILURE,
    ERROR_TYPE_UNSUPPORTED_URL,
    ERROR_TYPE_EXTRACTION_FAILURE,
    ERROR_TYPE_EMPTY_CONTENT,
    ERROR_TYPE_IDENTITY_MISMATCH,
    ERROR_TYPE_SSRF_BLOCKED,
)


# Global singleton instances
search_manager = WebSearchManager()
page_fetcher = WebFetcher()
github_inspector = GitHubInspector()


WEB_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "github_inspect",
            "description": "Inspect and verify an exact GitHub repository by owner and repo name (e.g. 'owner/repo') or GitHub URL. Retrieves verified metadata, README, and project structure with strict identity verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url_or_repo": {
                        "type": "string",
                        "description": "The exact GitHub repository URL (e.g. 'https://github.com/owner/repo') or 'owner/repo' identifier."
                    }
                },
                "required": ["url_or_repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for up-to-date facts, current news, recent documentation, real-time prices, releases, or topics requiring external evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search keywords or natural-language query."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of search results to return (1 to 8, default 5)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch, extract, and read the full readable text content, title, and key links from a specific external web page or PDF URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The complete HTTP or HTTPS URL of the web page to fetch."
                    }
                },
                "required": ["url"]
            }
        }
    }
]


async def execute_web_tool(
    name: str,
    args: Dict[str, Any],
    db_conn=None,
    conversation_id: str = "",
    message_id: str = "",
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any], EvidenceContract]:
    """
    Executes a web tool requested by the model.
    Returns:
        (tool_output_content: str, citations: List[dict], metadata: dict, contract: EvidenceContract)
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    citations: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {"tool": name, "args": args}

    # -------------------------------------------------------------
    # Tool 1: github_inspect (Dedicated GitHub Inspection)
    # -------------------------------------------------------------
    if name == "github_inspect":
        target = str(args.get("url_or_repo", "")).strip()
        contract = await github_inspector.inspect_repository(target)
        metadata.update(contract.metadata)
        metadata["status"] = "ok" if contract.success else contract.error_type
        metadata["contract"] = contract.to_dict()

        if contract.success:
            cit_id = f"git_{uuid.uuid4()}"
            citations.append({
                "id": cit_id,
                "document_id": "github_inspect",
                "filename": contract.title,
                "document_name": contract.title,
                "page_number": 1,
                "excerpt": contract.retrieved_content[:400] + ("..." if len(contract.retrieved_content) > 400 else ""),
                "url": contract.resolved_url,
                "title": contract.title,
                "domain": "github.com",
                "type": "web",
            })
            tool_text = contract.format_for_model()
            _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", target, "ok", 1, metadata, now)
            return tool_text, citations, metadata, contract
        else:
            tool_text = contract.format_for_model()
            _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", target, contract.error_type or "failed", 0, metadata, now)
            return tool_text, [], metadata, contract

    # -------------------------------------------------------------
    # Tool 2: web_search
    # -------------------------------------------------------------
    elif name == "web_search":
        raw_query = args.get("query", "")
        max_res = min(max(int(args.get("max_results", 5)), 1), 8)
        query = str(raw_query).strip()

        if not query:
            contract = EvidenceContract(
                success=False,
                tool="web_search",
                requested_url="",
                resolved_url="",
                http_status=None,
                content_type="text/plain",
                title="Empty Search Query",
                source_name="Web Search",
                retrieved_content="",
                retrieved_at=now,
                error="Search query cannot be empty.",
                error_type=ERROR_TYPE_EMPTY_CONTENT,
                metadata={"query": ""},
            )
            metadata["contract"] = contract.to_dict()
            return "Error: Search query cannot be empty.", [], {"status": "error", "error": "Empty query", "contract": contract.to_dict()}, contract

        # Check if the query is attempting to locate a specific GitHub repo
        github_target = parse_github_target(query)
        if github_target:
            # Delegate directly to GitHub inspector for precision and zero-hallucination
            g_owner, g_repo, _ = github_target
            contract = await github_inspector.inspect_repository(f"{g_owner}/{g_repo}")
            metadata.update(contract.metadata)
            metadata["contract"] = contract.to_dict()
            if contract.success:
                cit_id = f"git_{uuid.uuid4()}"
                citations.append({
                    "id": cit_id,
                    "document_id": "github_inspect",
                    "filename": contract.title,
                    "document_name": contract.title,
                    "page_number": 1,
                    "excerpt": contract.retrieved_content[:400] + ("..." if len(contract.retrieved_content) > 400 else ""),
                    "url": contract.resolved_url,
                    "title": contract.title,
                    "domain": "github.com",
                    "type": "web",
                })
                tool_text = contract.format_for_model()
                _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", query, "ok", 1, metadata, now)
                return tool_text, citations, metadata, contract
            else:
                tool_text = contract.format_for_model()
                _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", query, contract.error_type or "failed", 0, metadata, now)
                return tool_text, [], metadata, contract

        results = await search_manager.search(query, max_results=max_res)
        metadata["results_count"] = len(results)
        metadata["query"] = query

        if not results:
            contract = EvidenceContract(
                success=False,
                tool="web_search",
                requested_url=query,
                resolved_url=query,
                http_status=200,
                content_type="text/plain",
                title=f"Web Search: {query}",
                source_name="Web Search",
                retrieved_content="",
                retrieved_at=now,
                error=f"No web search results found for query: '{query}'.",
                error_type=ERROR_TYPE_NOT_FOUND,
                metadata={"query": query, "results_count": 0},
            )
            metadata["contract"] = contract.to_dict()
            tool_text = contract.format_for_model()
            _persist_web_retrieval(db_conn, conversation_id, message_id, "web_search", query, "no_results", 0, metadata, now)
            return tool_text, [], metadata, contract

        formatted_lines = [f"Web search results for: '{query}' (Found {len(results)} sources):\n"]
        for idx, res in enumerate(results, 1):
            date_str = f" [Date: {res.published_date}]" if res.published_date else ""
            formatted_lines.append(
                f"[{idx}] Title: {res.title}\n"
                f"    Domain: {res.domain}{date_str}\n"
                f"    URL: {res.url}\n"
                f"    Snippet: {res.snippet}\n"
            )
            cit_id = f"web_{uuid.uuid4()}"
            citations.append({
                "id": cit_id,
                "document_id": "web_search",
                "filename": res.title,
                "document_name": res.title,
                "page_number": idx,
                "excerpt": res.snippet,
                "url": res.url,
                "title": res.title,
                "domain": res.domain,
                "published_date": res.published_date,
                "type": "web",
            })

        formatted_lines.append(
            "\nINSTRUCTIONS FOR RESPONSE:\n"
            "- Ground your response strictly in the retrieved web search evidence above.\n"
            "- Mention source domains or titles when stating facts.\n"
            "- If the search snippets do not contain sufficient detail, state that clearly."
        )
        tool_text = "\n".join(formatted_lines)

        contract = EvidenceContract(
            success=True,
            tool="web_search",
            requested_url=query,
            resolved_url=results[0].url if results else query,
            http_status=200,
            content_type="text/plain",
            title=f"Web Search: {query}",
            source_name="Web Search",
            retrieved_content=tool_text,
            retrieved_at=now,
            error=None,
            error_type=None,
            metadata={"query": query, "results_count": len(results)},
        )
        metadata["contract"] = contract.to_dict()
        _persist_web_retrieval(db_conn, conversation_id, message_id, "web_search", query, "ok", len(results), metadata, now)
        return tool_text, citations, metadata, contract

    # -------------------------------------------------------------
    # Tool 3: web_fetch
    # -------------------------------------------------------------
    elif name == "web_fetch":
        url = str(args.get("url", "")).strip()
        if not url:
            contract = EvidenceContract(
                success=False,
                tool="web_fetch",
                requested_url="",
                resolved_url="",
                http_status=None,
                content_type="text/plain",
                title="Empty URL",
                source_name="Web Fetch",
                retrieved_content="",
                retrieved_at=now,
                error="URL cannot be empty.",
                error_type=ERROR_TYPE_EMPTY_CONTENT,
                metadata={},
            )
            metadata["contract"] = contract.to_dict()
            return "Error: URL cannot be empty.", [], {"status": "error", "error": "Empty URL", "contract": contract.to_dict()}, contract

        # Check if URL is a GitHub repository target
        if parse_github_target(url):
            contract = await github_inspector.inspect_repository(url)
            metadata.update(contract.metadata)
            metadata["contract"] = contract.to_dict()
            if contract.success:
                cit_id = f"git_{uuid.uuid4()}"
                citations.append({
                    "id": cit_id,
                    "document_id": "github_inspect",
                    "filename": contract.title,
                    "document_name": contract.title,
                    "page_number": 1,
                    "excerpt": contract.retrieved_content[:400] + ("..." if len(contract.retrieved_content) > 400 else ""),
                    "url": contract.resolved_url,
                    "title": contract.title,
                    "domain": "github.com",
                    "type": "web",
                })
                tool_text = contract.format_for_model()
                _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", url, "ok", 1, metadata, now)
                return tool_text, citations, metadata, contract
            else:
                tool_text = contract.format_for_model()
                _persist_web_retrieval(db_conn, conversation_id, message_id, "github_inspect", url, contract.error_type or "failed", 0, metadata, now)
                return tool_text, [], metadata, contract

        metadata["url"] = url
        page: FetchedPage = await page_fetcher.fetch(url)
        metadata["status"] = page.status
        metadata["domain"] = page.domain
        metadata["word_count"] = page.word_count

        if page.status != "ok":
            # Map page.status to standard error_type
            if "ssrf" in page.status:
                err_type = ERROR_TYPE_SSRF_BLOCKED
            elif "404" in page.status:
                err_type = ERROR_TYPE_NOT_FOUND
            elif "403" in page.status:
                err_type = ERROR_TYPE_FORBIDDEN
            elif "429" in page.status:
                err_type = ERROR_TYPE_RATE_LIMITED
            elif "timeout" in page.status:
                err_type = ERROR_TYPE_TIMEOUT
            elif "network" in page.status:
                err_type = ERROR_TYPE_CONNECTION_FAILURE
            else:
                err_type = ERROR_TYPE_EXTRACTION_FAILURE

            contract = EvidenceContract(
                success=False,
                tool="web_fetch",
                requested_url=url,
                resolved_url=page.url or url,
                http_status=int(page.status.split("_")[-1]) if page.status.startswith("http_error_") and page.status.split("_")[-1].isdigit() else None,
                content_type="text/html",
                title=f"Web Fetch: {page.domain or url}",
                source_name=page.domain or "Web",
                retrieved_content="",
                retrieved_at=now,
                error=page.error_message or f"Failed to retrieve web page from '{url}'.",
                error_type=err_type,
                metadata=metadata,
            )
            metadata["contract"] = contract.to_dict()
            tool_text = contract.format_for_model()
            _persist_web_retrieval(db_conn, conversation_id, message_id, "web_fetch", url, page.status, 0, metadata, now)
            return tool_text, [], metadata, contract

        cit_id = f"web_{uuid.uuid4()}"
        citations.append({
            "id": cit_id,
            "document_id": "web_fetch",
            "filename": page.title,
            "document_name": page.title,
            "page_number": 1,
            "excerpt": page.summary,
            "url": page.url,
            "title": page.title,
            "domain": page.domain,
            "published_date": page.published_date,
            "author": page.author,
            "type": "web",
        })

        date_line = f"Publication Date: {page.published_date}\n" if page.published_date else ""
        author_line = f"Author: {page.author}\n" if page.author else ""

        links_summary = ""
        if page.links:
            links_summary = "\nKey Reference Links on Page:\n" + "\n".join(f"- [{l['text']}]({l['url']})" for l in page.links[:6])

        tool_text = (
            f"Successfully fetched content from: {page.url}\n"
            f"Page Title: {page.title}\n"
            f"Domain: {page.domain}\n"
            f"{date_line}{author_line}\n"
            f"Extracted Content:\n{page.content_text}\n"
            f"{links_summary}\n\n"
            f"INSTRUCTIONS FOR RESPONSE:\n"
            f"- Ground your response strictly in the content retrieved from this web page.\n"
            f"- Distinguish between the author's statements and your own synthesis.\n"
            f"- Cite the source URL ({page.url}) in your response."
        )

        contract = EvidenceContract(
            success=True,
            tool="web_fetch",
            requested_url=url,
            resolved_url=page.url,
            http_status=200,
            content_type="text/html",
            title=page.title,
            source_name=page.domain or "Web",
            retrieved_content=page.content_text,
            retrieved_at=now,
            error=None,
            error_type=None,
            metadata=metadata,
        )
        metadata["contract"] = contract.to_dict()
        _persist_web_retrieval(db_conn, conversation_id, message_id, "web_fetch", url, "ok", 1, metadata, now)
        return tool_text, citations, metadata, contract

    else:
        contract = EvidenceContract(
            success=False,
            tool=name,
            requested_url="",
            resolved_url="",
            http_status=None,
            content_type="text/plain",
            title=f"Unknown Tool: {name}",
            source_name="System",
            retrieved_content="",
            retrieved_at=now,
            error=f"Unknown tool '{name}'. Available tools are github_inspect, web_search, and web_fetch.",
            error_type=ERROR_TYPE_UNSUPPORTED_URL,
            metadata={},
        )
        return f"Unknown tool '{name}'. Available tools are github_inspect, web_search and web_fetch.", [], {"status": "error_unknown_tool", "contract": contract.to_dict()}, contract


def _persist_web_retrieval(
    db_conn,
    conversation_id: str,
    message_id: str,
    tool_name: str,
    query_or_url: str,
    status: str,
    results_count: int,
    metadata: dict,
    created_at: str,
):
    if not db_conn or not conversation_id:
        return
    try:
        c = db_conn.cursor()
        retrieval_id = f"ret_{uuid.uuid4()}"
        c.execute("""
            INSERT INTO web_retrievals (id, conversation_id, message_id, tool_name, query_or_url, status, results_count, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            retrieval_id,
            conversation_id,
            message_id,
            tool_name,
            query_or_url,
            status,
            results_count,
            json.dumps(metadata),
            created_at,
        ))
        db_conn.commit()
    except Exception:
        pass
