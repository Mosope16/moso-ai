"""
Moso AI — Web Search Module & Provider Abstraction
Supports:
- DuckDuckGo (Free, zero-credential default provider)
- Optional Ollama-hosted search via OLLAMA_API_KEY / OLLAMA_SEARCH_ENDPOINT
- Optional Tavily search via TAVILY_API_KEY
- Result deduplication, query cleaning, timeouts, and rate-limit resilience
"""

import os
import re
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup

from .security import validate_safe_url


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    domain: str
    published_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "published_date": self.published_date,
        }


class SearchProvider(ABC):
    """Abstract base class for search engine providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        pass


class DuckDuckGoSearchProvider(SearchProvider):
    """
    DuckDuckGo search provider.
    Free, no API key or subscription required.
    Uses public HTML/Lite endpoints with resilient parsing and result normalization.
    """

    @property
    def name(self) -> str:
        return "DuckDuckGo"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        results: List[SearchResult] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Attempt 1: HTML endpoint
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                resp = await client.post("https://html.duckduckgo.com/html/", data={"q": cleaned_query})
                if resp.status_code == 200:
                    results = self._parse_html_results(resp.text, max_results)
        except Exception as e:
            # Silently fall through to Lite endpoint
            pass

        # Attempt 2: Lite endpoint if HTML yielded 0 results
        if not results:
            try:
                async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.post("https://lite.duckduckgo.com/lite/", data={"q": cleaned_query})
                    if resp.status_code == 200:
                        results = self._parse_lite_results(resp.text, max_results)
            except Exception:
                pass

        return results[:max_results]

    def _extract_target_url(self, raw_url: str) -> str:
        """Extracts the actual destination URL from DuckDuckGo redirect paths (/l/?uddg=...)."""
        if not raw_url:
            return ""
        if "uddg=" in raw_url:
            try:
                parsed = urllib.parse.urlparse(raw_url)
                params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in params and params["uddg"]:
                    return params["uddg"][0]
            except Exception:
                pass
        if raw_url.startswith("//"):
            return "https:" + raw_url
        return raw_url

    def _parse_html_results(self, html_text: str, max_results: int) -> List[SearchResult]:
        soup = BeautifulSoup(html_text, "html.parser")
        results: List[SearchResult] = []
        seen_domains: set = set()

        for item in soup.select(".result"):
            title_node = item.select_one(".result__title a")
            snippet_node = item.select_one(".result__snippet")
            if not title_node:
                continue

            raw_href = title_node.get("href", "")
            target_url = self._extract_target_url(raw_href)

            # Validate destination URL is safe and valid
            is_safe, _, norm_url = validate_safe_url(target_url)
            if not is_safe or not norm_url:
                continue

            parsed_url = urllib.parse.urlparse(norm_url)
            domain = parsed_url.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Avoid spamming duplicates from same domain if multiple results exist
            if domain in seen_domains and len(results) >= 2:
                continue
            seen_domains.add(domain)

            title = title_node.get_text(strip=True)
            snippet = snippet_node.get_text(strip=True) if snippet_node else ""

            # Attempt to extract publication date from snippet if present (e.g. "Oct 14, 2024 ...")
            pub_date = None
            date_match = re.match(r"^([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})", snippet)
            if date_match:
                pub_date = date_match.group(1)
                snippet = snippet[date_match.end():].lstrip(" -—.")

            results.append(SearchResult(
                title=title,
                url=norm_url,
                snippet=snippet,
                domain=domain,
                published_date=pub_date,
            ))

            if len(results) >= max_results:
                break

        return results

    def _parse_lite_results(self, html_text: str, max_results: int) -> List[SearchResult]:
        soup = BeautifulSoup(html_text, "html.parser")
        results: List[SearchResult] = []

        # In lite DuckDuckGo, results are formatted as tables with class 'result-link' and 'result-snippet'
        links = soup.select("a.result-link")
        snippets = soup.select("td.result-snippet")

        for idx, link_tag in enumerate(links):
            raw_href = link_tag.get("href", "")
            target_url = self._extract_target_url(raw_href)
            is_safe, _, norm_url = validate_safe_url(target_url)
            if not is_safe or not norm_url:
                continue

            title = link_tag.get_text(strip=True)
            snippet = ""
            if idx < len(snippets):
                snippet = snippets[idx].get_text(strip=True)

            domain = urllib.parse.urlparse(norm_url).netloc.lower()
            results.append(SearchResult(
                title=title,
                url=norm_url,
                snippet=snippet,
                domain=domain,
            ))
            if len(results) >= max_results:
                break

        return results


class OllamaSearchProvider(SearchProvider):
    """
    Optional search provider connecting to an Ollama-hosted or Ollama-compatible search endpoint
    if OLLAMA_API_KEY and/or OLLAMA_SEARCH_ENDPOINT are configured.
    """

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.endpoint = endpoint or os.getenv("OLLAMA_SEARCH_ENDPOINT", "").strip()
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY", "").strip()

    @property
    def name(self) -> str:
        return "Ollama Hosted Search"

    @property
    def is_available(self) -> bool:
        return bool(self.endpoint and self.api_key)

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.is_available:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "max_results": max_results}

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(self.endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("results", [])
                    results = []
                    for it in items:
                        url = it.get("url", "")
                        is_safe, _, norm_url = validate_safe_url(url)
                        if not is_safe or not norm_url:
                            continue
                        domain = urllib.parse.urlparse(norm_url).netloc.lower()
                        results.append(SearchResult(
                            title=it.get("title", ""),
                            url=norm_url,
                            snippet=it.get("snippet", ""),
                            domain=domain,
                            published_date=it.get("published_date"),
                        ))
                    return results[:max_results]
        except Exception:
            pass
        return []


class TavilySearchProvider(SearchProvider):
    """
    Optional Tavily search provider if TAVILY_API_KEY is configured in environment.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "").strip()

    @property
    def name(self) -> str:
        return "Tavily"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.is_available:
            return []

        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post("https://api.tavily.com/search", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("results", [])
                    results = []
                    for it in items:
                        url = it.get("url", "")
                        is_safe, _, norm_url = validate_safe_url(url)
                        if not is_safe or not norm_url:
                            continue
                        domain = urllib.parse.urlparse(norm_url).netloc.lower()
                        results.append(SearchResult(
                            title=it.get("title", ""),
                            url=norm_url,
                            snippet=it.get("content", ""),
                            domain=domain,
                            published_date=it.get("published_date"),
                        ))
                    return results[:max_results]
        except Exception:
            pass
        return []


class WikipediaSearchProvider(SearchProvider):
    """
    Open knowledge and encyclopedic search provider.
    Always free, globally reliable, zero credentials required.
    """

    @property
    def name(self) -> str:
        return "Wikipedia"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        cleaned = query.strip()
        if not cleaned:
            return []

        headers = {
            "User-Agent": "MosoAI/1.0 (academic research assistant; mailto:contact@moso.local)",
            "Accept": "application/json",
        }
        params = {
            "action": "query",
            "list": "search",
            "srsearch": cleaned,
            "utf8": "1",
            "format": "json",
            "srlimit": max_results,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.get("https://en.wikipedia.org/w/api.php", params=params)
                if resp.status_code == 200:
                    data = resp.json().get("query", {}).get("search", [])
                    results = []
                    for it in data:
                        title = it.get("title", "")
                        raw_snippet = it.get("snippet", "")
                        clean_snippet = re.sub(r'<[^>]+>', '', raw_snippet).strip()
                        wiki_path = urllib.parse.quote(title.replace(" ", "_"))
                        url = f"https://en.wikipedia.org/wiki/{wiki_path}"
                        pub_date = it.get("timestamp", "")[:10] if it.get("timestamp") else None
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=clean_snippet,
                            domain="en.wikipedia.org",
                            published_date=pub_date,
                        ))
                    return results[:max_results]
        except Exception:
            pass
        return []


class WebSearchManager:
    """
    Master Web Search Manager.
    Orchestrates search providers with fallback:
    1. If configured: Tavily or Ollama Search
    2. Primary web provider: DuckDuckGo
    3. Resilient fallback: Wikipedia Open Search (zero API key, zero rate limit)
    Caches queries in-memory to prevent repeated network queries.
    """

    def __init__(self):
        self.ddg_provider = DuckDuckGoSearchProvider()
        self.wiki_provider = WikipediaSearchProvider()
        self.ollama_provider = OllamaSearchProvider()
        self.tavily_provider = TavilySearchProvider()
        self._cache: Dict[str, List[SearchResult]] = {}
        self._cache_order: List[str] = []
        self._max_cache = 50

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        cleaned = re.sub(r'\s+', ' ', query).strip()
        if not cleaned:
            return []

        cache_key = f"{cleaned.lower()}::{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        results: List[SearchResult] = []

        # 1. Try Ollama hosted search if configured
        if self.ollama_provider.is_available:
            results = await self.ollama_provider.search(cleaned, max_results)

        # 2. Try Tavily if configured and no results yet
        if not results and self.tavily_provider.is_available:
            results = await self.tavily_provider.search(cleaned, max_results)

        # 3. Default Provider: DuckDuckGo
        if not results:
            results = await self.ddg_provider.search(cleaned, max_results)

        # 4. Reliable Open Knowledge Fallback if DDG was challenge-blocked or empty
        if not results:
            results = await self.wiki_provider.search(cleaned, max_results)

        # Cache results
        if results:
            if len(self._cache_order) >= self._max_cache:
                oldest = self._cache_order.pop(0)
                self._cache.pop(oldest, None)
            self._cache[cache_key] = results
            self._cache_order.append(cache_key)

        return results
