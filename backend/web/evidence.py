"""
Moso AI — Retrieval Evidence Contract
Defines the strict data contract for all external retrieval operations (web fetch,
web search, GitHub repository inspection, and local document RAG).
Ensures evidence gating, identity verification, error categorization, and provenance.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import datetime
import json


# Standardized error types required by the evidence contract
ERROR_TYPE_NOT_FOUND = "not_found"
ERROR_TYPE_FORBIDDEN = "forbidden"
ERROR_TYPE_RATE_LIMITED = "rate_limited"
ERROR_TYPE_TIMEOUT = "timeout"
ERROR_TYPE_CONNECTION_FAILURE = "connection_failure"
ERROR_TYPE_UNSUPPORTED_URL = "unsupported_url"
ERROR_TYPE_EXTRACTION_FAILURE = "extraction_failure"
ERROR_TYPE_EMPTY_CONTENT = "empty_content"
ERROR_TYPE_IDENTITY_MISMATCH = "identity_mismatch"
ERROR_TYPE_SSRF_BLOCKED = "ssrf_blocked"


@dataclass
class EvidenceContract:
    """
    Structured result produced by every retrieval operation.
    Guarantees that failed retrievals are never silently converted into guesses.
    """
    success: bool
    tool: str                          # "github_inspect", "web_fetch", "web_search", "document_rag"
    requested_url: str
    resolved_url: str
    http_status: Optional[int]
    content_type: str                  # "text/markdown", "application/json", "text/html", etc.
    title: str
    source_name: str                   # e.g., "GitHub: Mosope16/pulse_watch", "Wikipedia", "Docs"
    retrieved_content: str             # Verified content extracted from the source
    retrieved_at: str                  # ISO-8601 UTC timestamp
    error: Optional[str] = None
    error_type: Optional[str] = None   # Standardized error category
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_groundable(self) -> bool:
        """Return True only when content has sufficient provenance for its tool type."""
        if not (self.success and self.retrieved_content and len(self.retrieved_content.strip()) >= 20):
            return False
        if self.tool == "github_inspect":
            # A 200 response or non-empty body is not enough: the API response
            # must prove that it belongs to the exact requested owner/repo.
            if self.metadata.get("identity_verified") is not True:
                return False
            if not self.metadata.get("owner") or not self.metadata.get("repo"):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceContract":
        return cls(**data)

    def format_diagnostic_summary(self) -> Dict[str, Any]:
        """Provides a safe developer-facing diagnostic representation without sensitive data."""
        return {
            "tool": self.tool,
            "requested_url": self.requested_url,
            "resolved_url": self.resolved_url,
            "http_status": self.http_status,
            "success": self.success,
            "content_length": len(self.retrieved_content) if self.retrieved_content else 0,
            "error": self.error,
            "error_type": self.error_type,
            "identity_verified": self.metadata.get("identity_verified", None),
            "files_retrieved": self.metadata.get("files_retrieved", []),
            "retrieved_at": self.retrieved_at,
        }

    def format_for_model(self) -> str:
        """
        Formats the evidence for injection into the model context or tool response.
        Enforces clear separation between verified facts and failed operations.
        """
        if self.is_groundable():
            meta_lines = []
            if self.metadata.get("owner") and self.metadata.get("repo"):
                meta_lines.append(f"Repository: {self.metadata['owner']}/{self.metadata['repo']}")
            if self.metadata.get("language"):
                meta_lines.append(f"Primary Language: {self.metadata['language']}")
            if self.metadata.get("files_retrieved"):
                meta_lines.append(f"Inspected Files: {', '.join(self.metadata['files_retrieved'])}")

            meta_block = ("\n" + "\n".join(meta_lines)) if meta_lines else ""
            return (
                f"### VERIFIED RETRIEVED EVIDENCE from [{self.source_name}]({self.resolved_url}):\n"
                f"Source Title: {self.title}\n"
                f"Status: Successfully Retrieved (HTTP {self.http_status or 200}){meta_block}\n\n"
                f"```\n{self.retrieved_content}\n```\n\n"
                f"STRICT GROUNDING INSTRUCTIONS:\n"
                f"- Ground your response strictly in the verified text above.\n"
                f"- Do not assume, extrapolate, or invent features not explicitly present.\n"
                f"- If the requested question is not answered by the text above, explicitly state: 'The retrieved source does not contain information on this topic.'"
            )
        else:
            # Deterministic failure statement
            return (
                f"### RETRIEVAL FAILED for [{self.source_name}]({self.requested_url}):\n"
                f"Reason: {self.error or 'Unable to retrieve evidence'}\n"
                f"Error Classification: {self.error_type or 'unknown_error'} (HTTP Status: {self.http_status or 'N/A'})\n\n"
                f"STRICT ABSTENTION INSTRUCTIONS:\n"
                f"- You MUST report that this source could not be retrieved.\n"
                f"- You MUST NOT invent, guess, or imagine what this repository or page contains.\n"
                f"- You MUST NOT use the URL name or repository name to deduce its functionality.\n"
                f"- Explain the exact failure reason to the user honestly."
            )
