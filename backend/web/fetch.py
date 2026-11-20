"""
Moso AI — Web Fetch Module
Fetches external web pages safely and extracts clean readable text,
metadata (title, canonical URL, author, publish date), and key links.
Supports HTML and PDF extraction.
"""

import io
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import pypdf

from .security import safe_fetch_http, validate_safe_url


@dataclass
class FetchedPage:
    url: str
    canonical_url: Optional[str] = None
    domain: str = ""
    title: str = ""
    content_text: str = ""
    summary: str = ""
    published_date: Optional[str] = None
    author: Optional[str] = None
    links: List[Dict[str, str]] = field(default_factory=list)
    word_count: int = 0
    content_type: str = ""
    status: str = "ok"
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "title": self.title,
            "content_text": self.content_text,
            "summary": self.summary,
            "published_date": self.published_date,
            "author": self.author,
            "links": self.links,
            "word_count": self.word_count,
            "status": self.status,
            "error_message": self.error_message,
        }


class WebFetcher:
    """
    Safely retrieves external web pages and parses readable content.
    """

    MAX_WORDS = 1000  # ~1,300 tokens. 2000 words (~2,700 tokens) plus prompt and answer overflowed a 4096 window.

    async def fetch(self, url: str) -> FetchedPage:
        # 1. SSRF and URL validation
        is_safe, reason, normalized_url = validate_safe_url(url)
        if not is_safe or not normalized_url:
            return FetchedPage(
                url=url,
                status="error_ssrf_blocked",
                error_message=f"Access blocked by security policy: {reason}",
            )

        parsed_url = urllib.parse.urlparse(normalized_url)
        domain = parsed_url.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # 2. Safe HTTP fetch
        try:
            status_code, content_bytes, content_type, headers = await safe_fetch_http(normalized_url)
        except ValueError as ve:
            return FetchedPage(
                url=normalized_url,
                domain=domain,
                status="error_security",
                error_message=str(ve),
            )
        except Exception as e:
            err_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            return FetchedPage(
                url=normalized_url,
                domain=domain,
                status="error_network",
                error_message=f"Failed to fetch page: {err_detail}",
            )

        if status_code >= 400:
            return FetchedPage(
                url=normalized_url,
                domain=domain,
                status=f"http_error_{status_code}",
                error_message=f"Web server returned HTTP error {status_code}",
            )

        # 3. Check for PDF document
        is_pdf = "application/pdf" in content_type or normalized_url.lower().endswith(".pdf")
        if is_pdf:
            return self._extract_pdf_content(normalized_url, domain, content_bytes)

        # 4. Extract HTML document
        return self._extract_html_content(normalized_url, domain, content_bytes, headers)

    def _extract_pdf_content(self, url: str, domain: str, pdf_bytes: bytes) -> FetchedPage:
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            if reader.is_encrypted:
                return FetchedPage(
                    url=url,
                    domain=domain,
                    status="error_pdf_encrypted",
                    error_message="The remote PDF file is password protected or encrypted.",
                )

            extracted_text = []
            for page in reader.pages[:15]:  # Limit to first 15 pages for web fetch
                t = page.extract_text() or ""
                if t.strip():
                    extracted_text.append(t.strip())

            full_text = "\n\n".join(extracted_text)
            if not full_text.strip():
                return FetchedPage(
                    url=url,
                    domain=domain,
                    status="error_pdf_scanned",
                    error_message="The PDF appears to be scanned or contains no extractable text layer.",
                )

            words = full_text.split()
            word_count = len(words)
            if word_count > self.MAX_WORDS:
                full_text = " ".join(words[:self.MAX_WORDS]) + f"\n\n[... PDF content truncated: displayed {self.MAX_WORDS} of {word_count} words ...]"

            title = reader.metadata.title if reader.metadata and reader.metadata.title else f"PDF Document from {domain}"
            author = reader.metadata.author if reader.metadata and reader.metadata.author else None

            return FetchedPage(
                url=url,
                domain=domain,
                title=title,
                content_text=full_text,
                summary=full_text[:300].strip(),
                author=author,
                word_count=word_count,
                content_type="application/pdf",
                status="ok",
            )
        except Exception as e:
            return FetchedPage(
                url=url,
                domain=domain,
                status="error_pdf_parse",
                error_message=f"Failed to parse remote PDF: {e}",
            )

    def _extract_html_content(self, url: str, domain: str, html_bytes: bytes, headers: dict) -> FetchedPage:
        try:
            # Decode HTML with fallback
            html_text = ""
            for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
                try:
                    html_text = html_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not html_text:
                html_text = html_bytes.decode("utf-8", errors="replace")

            soup = BeautifulSoup(html_text, "html.parser")

            # Extract Title
            title = ""
            og_title = soup.find("meta", property="og:title")
            twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
            title_tag = soup.find("title")

            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif twitter_title and twitter_title.get("content"):
                title = twitter_title["content"].strip()
            elif title_tag and title_tag.string:
                title = title_tag.string.strip()
            else:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
                else:
                    title = f"Web Page from {domain}"

            # Extract Canonical URL
            canonical_url = None
            canonical_tag = soup.find("link", rel="canonical")
            if canonical_tag and canonical_tag.get("href"):
                canonical_url = urllib.parse.urljoin(url, canonical_tag["href"].strip())

            # Extract Publication Date
            published_date = None
            for meta_name in ("article:published_time", "datePublished", "pubdate", "publishdate", "dc.date"):
                tag = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
                if tag and tag.get("content"):
                    published_date = tag["content"].strip()[:20]
                    break

            if not published_date:
                time_tag = soup.find("time")
                if time_tag and (time_tag.get("datetime") or time_tag.string):
                    published_date = (time_tag.get("datetime") or time_tag.string).strip()[:20]

            # Extract Author
            author = None
            author_tag = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", attrs={"property": "author"})
            if author_tag and author_tag.get("content"):
                author = author_tag["content"].strip()

            # Extract Useful Outbound Links (top 10 relevant references)
            links = []
            seen_hrefs = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                link_text = a.get_text(strip=True)
                if not link_text or len(link_text) < 3 or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                abs_href = urllib.parse.urljoin(url, href)
                if abs_href in seen_hrefs or abs_href == url:
                    continue
                seen_hrefs.add(abs_href)
                links.append({"text": link_text[:60], "url": abs_href})
                if len(links) >= 10:
                    break

            # Strip intrusive non-content elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "svg", "noscript", "form", "button"]):
                tag.decompose()

            # Find main article container if available
            main_container = soup.find("article") or soup.find("main") or soup.find(role="main") or soup.find(id="content") or soup.find(class_=re.compile(r'(post-content|entry-content|article-body|main-content)'))
            target_element = main_container if main_container else (soup.body if soup.body else soup)

            # Extract structured text paragraphs and headings
            content_blocks = []
            for el in target_element.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre", "table"]):
                text = el.get_text(strip=True)
                if not text or len(text) < 10:
                    continue

                if el.name in ("h1", "h2", "h3", "h4"):
                    content_blocks.append(f"\n### {text}\n")
                elif el.name == "blockquote":
                    content_blocks.append(f"> {text}")
                elif el.name == "li":
                    content_blocks.append(f"- {text}")
                elif el.name == "pre":
                    content_blocks.append(f"```\n{text}\n```")
                else:
                    content_blocks.append(text)

            clean_text = "\n\n".join(content_blocks).strip()
            if not clean_text:
                clean_text = target_element.get_text(separator="\n", strip=True)

            words = clean_text.split()
            word_count = len(words)
            if word_count > self.MAX_WORDS:
                clean_text = " ".join(words[:self.MAX_WORDS]) + f"\n\n[... Content truncated: showing {self.MAX_WORDS} of {word_count} words ...]"

            summary = clean_text[:350].strip()

            return FetchedPage(
                url=url,
                canonical_url=canonical_url,
                domain=domain,
                title=title,
                content_text=clean_text,
                summary=summary,
                published_date=published_date,
                author=author,
                links=links,
                word_count=word_count,
                content_type="text/html",
                status="ok",
            )
        except Exception as e:
            return FetchedPage(
                url=url,
                domain=domain,
                status="error_html_parse",
                error_message=f"Failed to parse HTML content: {e}",
            )
