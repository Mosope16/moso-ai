"""
Moso AI — Web Access & Retrieval Package
"""

from .security import validate_safe_url, safe_fetch_http
from .search import WebSearchManager, SearchResult, DuckDuckGoSearchProvider
from .fetch import WebFetcher, FetchedPage
from .github import GitHubInspector, parse_github_target
from .evidence import EvidenceContract
from .tools import WEB_TOOLS_SCHEMA, execute_web_tool

__all__ = [
    "validate_safe_url",
    "safe_fetch_http",
    "WebSearchManager",
    "SearchResult",
    "DuckDuckGoSearchProvider",
    "WebFetcher",
    "FetchedPage",
    "GitHubInspector",
    "parse_github_target",
    "EvidenceContract",
    "WEB_TOOLS_SCHEMA",
    "execute_web_tool",
]
