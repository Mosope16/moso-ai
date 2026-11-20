"""
Moso AI — Dedicated GitHub Repository Inspector & Identity Verifier
Provides authoritative, SSRF-safe inspection of GitHub repositories:
- Strict owner/repo identity verification (prevents cross-owner substitution)
- Explicit HTTP status discrimination (404 not found vs 403 forbidden vs 429 rate limit vs timeout)
- README and manifest inspection (package.json, pyproject.toml, requirements.txt, Cargo.toml)
- Rejection of name-based hallucinations
"""

import os
import re
import json
import base64
import urllib.parse
import datetime
from typing import Optional, Tuple, Dict, Any, List
import httpx

from .security import validate_safe_url, safe_fetch_http
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


GITHUB_URL_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?github\.com/(?P<owner>[a-zA-Z0-9_\-\.]+)/(?P<repo>[a-zA-Z0-9_\-\.]+)(?:/(?:tree|blob)/(?P<branch>[^/]+)(?:/(?P<path>.+))?)?',
    re.IGNORECASE
)

GITHUB_IDENTIFIER_REGEX = re.compile(
    r'^(?P<owner>[a-zA-Z0-9_\-\.]+)/(?P<repo>[a-zA-Z0-9_\-\.]+)$'
)


def parse_github_target(raw: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """
    Parses a GitHub URL or 'owner/repo' identifier into (owner, repo, subpath).
    Strips trailing '.git' or slashes.
    """
    cleaned = raw.strip().strip('"\'<>')
    # URL extraction commonly includes sentence punctuation (e.g. a trailing
    # question mark or period). Remove only terminal punctuation before parsing.
    cleaned = cleaned.rstrip(".,;:!?)]}")
    # Match full URL
    m = GITHUB_URL_REGEX.search(cleaned)
    if m:
        owner = m.group("owner")
        repo = m.group("repo")
        if repo.endswith(".git"):
            repo = repo[:-4]
        subpath = m.group("path")
        return owner, repo, subpath

    # Match simple 'owner/repo'
    m_id = GITHUB_IDENTIFIER_REGEX.match(cleaned)
    if m_id:
        owner = m_id.group("owner")
        repo = m_id.group("repo")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo, None

    return None


class GitHubInspector:
    """
    Authoritative GitHub inspection engine with strict identity verification.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "").strip()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "MosoAI-ResearchAssistant/1.0 (Linux; x86_64)",
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def inspect_repository(
        self,
        url_or_identifier: str,
        timeout_sec: float = 10.0,
    ) -> EvidenceContract:
        """
        Inspects an exact GitHub repository with strict identity validation.
        Guarantees that:
        1. Owner and Repo match the requested URL.
        2. Exact HTTP error statuses are preserved (404 != 403 != 429).
        3. Failed retrievals are returned as structured failed contracts.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        parsed = parse_github_target(url_or_identifier)

        canonical_url = url_or_identifier.strip()
        if not canonical_url.startswith("http"):
            if parsed:
                canonical_url = f"https://github.com/{parsed[0]}/{parsed[1]}"
            else:
                canonical_url = f"https://{canonical_url}"

        if not parsed:
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=url_or_identifier,
                resolved_url=canonical_url,
                http_status=None,
                content_type="text/plain",
                title="Invalid GitHub Repository Target",
                source_name="GitHub",
                retrieved_content="",
                retrieved_at=now,
                error=f"'{url_or_identifier}' is not a valid GitHub repository URL or 'owner/repo' identifier.",
                error_type=ERROR_TYPE_UNSUPPORTED_URL,
                metadata={"url_or_identifier": url_or_identifier},
            )

        expected_owner, expected_repo, subpath = parsed

        # Security check on canonical URL
        is_safe, sec_reason, norm_url = validate_safe_url(canonical_url)
        if not is_safe:
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=canonical_url,
                resolved_url=canonical_url,
                http_status=None,
                content_type="text/plain",
                title=f"GitHub: {expected_owner}/{expected_repo}",
                source_name="GitHub",
                retrieved_content="",
                retrieved_at=now,
                error=f"Blocked by security policy: {sec_reason}",
                error_type=ERROR_TYPE_SSRF_BLOCKED,
                metadata={"owner": expected_owner, "repo": expected_repo},
            )

        api_url = f"https://api.github.com/repos/{expected_owner}/{expected_repo}"
        headers = self._get_headers()

        timeout = httpx.Timeout(connect=5.0, read=timeout_sec, write=5.0, pool=5.0)

        # 1. Fetch Repository Metadata from GitHub API
        repo_data: Optional[Dict[str, Any]] = None
        http_status: Optional[int] = None
        resolved_url = canonical_url
        resp_history: List[Any] = []

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                resp = await client.get(api_url)
                http_status = resp.status_code
                resolved_url = str(resp.url).replace("api.github.com/repos", "github.com")
                resp_history = list(resp.history)

                if resp.status_code == 200:
                    repo_data = resp.json()
                elif resp.status_code == 404:
                    return EvidenceContract(
                        success=False,
                        tool="github_inspect",
                        requested_url=canonical_url,
                        resolved_url=resolved_url,
                        http_status=404,
                        content_type="application/json",
                        title=f"GitHub: {expected_owner}/{expected_repo} (Not Found)",
                        source_name=f"GitHub ({expected_owner}/{expected_repo})",
                        retrieved_content="",
                        retrieved_at=now,
                        error=f"Repository '{expected_owner}/{expected_repo}' was not found on GitHub (HTTP 404). It does not exist or may be inaccessible.",
                        error_type=ERROR_TYPE_NOT_FOUND,
                        metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
                    )
                elif resp.status_code == 403:
                    rate_remaining = resp.headers.get("x-ratelimit-remaining", "")
                    if rate_remaining == "0":
                        err_type = ERROR_TYPE_RATE_LIMITED
                        err_msg = "GitHub API rate limit exceeded. Unauthenticated requests are limited to 60/hr."
                    else:
                        err_type = ERROR_TYPE_FORBIDDEN
                        err_msg = f"Access to repository '{expected_owner}/{expected_repo}' is forbidden (HTTP 403)."
                    return EvidenceContract(
                        success=False,
                        tool="github_inspect",
                        requested_url=canonical_url,
                        resolved_url=resolved_url,
                        http_status=403,
                        content_type="application/json",
                        title=f"GitHub: {expected_owner}/{expected_repo} (Forbidden / Rate Limited)",
                        source_name=f"GitHub ({expected_owner}/{expected_repo})",
                        retrieved_content="",
                        retrieved_at=now,
                        error=err_msg,
                        error_type=err_type,
                        metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
                    )
                elif resp.status_code == 429:
                    return EvidenceContract(
                        success=False,
                        tool="github_inspect",
                        requested_url=canonical_url,
                        resolved_url=resolved_url,
                        http_status=429,
                        content_type="application/json",
                        title=f"GitHub: {expected_owner}/{expected_repo} (Rate Limited)",
                        source_name=f"GitHub ({expected_owner}/{expected_repo})",
                        retrieved_content="",
                        retrieved_at=now,
                        error=f"GitHub returned HTTP 429 Rate Limit for '{expected_owner}/{expected_repo}'.",
                        error_type=ERROR_TYPE_RATE_LIMITED,
                        metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
                    )
                else:
                    return EvidenceContract(
                        success=False,
                        tool="github_inspect",
                        requested_url=canonical_url,
                        resolved_url=resolved_url,
                        http_status=resp.status_code,
                        content_type="application/json",
                        title=f"GitHub: {expected_owner}/{expected_repo} (HTTP Error {resp.status_code})",
                        source_name=f"GitHub ({expected_owner}/{expected_repo})",
                        retrieved_content="",
                        retrieved_at=now,
                        error=f"GitHub API returned HTTP {resp.status_code} for '{expected_owner}/{expected_repo}'.",
                        error_type=ERROR_TYPE_EXTRACTION_FAILURE,
                        metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
                    )
        except httpx.TimeoutException:
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=canonical_url,
                resolved_url=canonical_url,
                http_status=None,
                content_type="text/plain",
                title=f"GitHub: {expected_owner}/{expected_repo} (Timeout)",
                source_name=f"GitHub ({expected_owner}/{expected_repo})",
                retrieved_content="",
                retrieved_at=now,
                error=f"Connection to GitHub timed out after {timeout_sec}s while fetching '{expected_owner}/{expected_repo}'.",
                error_type=ERROR_TYPE_TIMEOUT,
                metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
            )
        except Exception as e:
            # Fallback to direct raw README if API had a network/SSL error
            raw_res = await self._fallback_raw_inspection(expected_owner, expected_repo, canonical_url, now)
            if raw_res:
                return raw_res
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=canonical_url,
                resolved_url=canonical_url,
                http_status=None,
                content_type="text/plain",
                title=f"GitHub: {expected_owner}/{expected_repo} (Network Failure)",
                source_name=f"GitHub ({expected_owner}/{expected_repo})",
                retrieved_content="",
                retrieved_at=now,
                error=f"Network error connecting to GitHub: {type(e).__name__}: {e}",
                error_type=ERROR_TYPE_CONNECTION_FAILURE,
                metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
            )

        if not repo_data:
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=canonical_url,
                resolved_url=resolved_url,
                http_status=http_status,
                content_type="text/plain",
                title=f"GitHub: {expected_owner}/{expected_repo}",
                source_name="GitHub",
                retrieved_content="",
                retrieved_at=now,
                error=f"No repository metadata returned for '{expected_owner}/{expected_repo}'.",
                error_type=ERROR_TYPE_EXTRACTION_FAILURE,
                metadata={"owner": expected_owner, "repo": expected_repo, "identity_verified": False},
            )

        # -------------------------------------------------------------
        # 2. Strict Repository Identity Verification
        # -------------------------------------------------------------
        actual_owner = repo_data.get("owner", {}).get("login", "")
        actual_repo = repo_data.get("name", "")

        is_exact_match = (actual_owner.lower() == expected_owner.lower() and actual_repo.lower() == expected_repo.lower())
        is_legitimate_redirect = bool(resp_history) and (actual_repo.lower() == expected_repo.lower())

        if not is_exact_match and not is_legitimate_redirect:
            # Identity mismatch! (e.g. cross-owner substitution or unrelated project)
            return EvidenceContract(
                success=False,
                tool="github_inspect",
                requested_url=canonical_url,
                resolved_url=repo_data.get("html_url", canonical_url),
                http_status=200,
                content_type="application/json",
                title="GitHub Identity Mismatch",
                source_name="GitHub",
                retrieved_content="",
                retrieved_at=now,
                error=(
                    f"Repository identity mismatch: requested '{expected_owner}/{expected_repo}', "
                    f"but GitHub resolved to '{actual_owner}/{actual_repo}'. Cross-owner substitution rejected."
                ),
                error_type=ERROR_TYPE_IDENTITY_MISMATCH,
                metadata={
                    "requested_owner": expected_owner,
                    "requested_repo": expected_repo,
                    "actual_owner": actual_owner,
                    "actual_repo": actual_repo,
                    "identity_verified": False,
                },
            )

        default_branch = repo_data.get("default_branch", "main")
        description = repo_data.get("description") or "(No description provided)"
        primary_lang = repo_data.get("language") or "Unspecified"
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        open_issues = repo_data.get("open_issues_count", 0)
        license_name = (repo_data.get("license") or {}).get("name", "Unspecified")

        files_retrieved = []
        readme_content = ""
        manifest_content = ""

        # -------------------------------------------------------------
        # 3. Retrieve README Content
        # -------------------------------------------------------------
        readme_url = f"https://api.github.com/repos/{actual_owner}/{actual_repo}/readme"
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                r_resp = await client.get(readme_url)
                if r_resp.status_code == 200:
                    r_json = r_resp.json()
                    raw_b64 = r_json.get("content", "")
                    encoding = r_json.get("encoding", "base64")
                    readme_filename = r_json.get("name", "README.md")
                    if encoding == "base64" and raw_b64:
                        try:
                            readme_content = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
                            files_retrieved.append(readme_filename)
                        except Exception:
                            pass
        except Exception:
            pass

        # Fallback to raw.githubusercontent.com for README if API did not return it
        if not readme_content:
            raw_readme = await self._fetch_raw_file(actual_owner, actual_repo, default_branch, "README.md")
            if raw_readme:
                readme_content = raw_readme
                files_retrieved.append("README.md")

        # -------------------------------------------------------------
        # 4. Retrieve Root Directory Contents / Key Project Manifests
        # -------------------------------------------------------------
        contents_url = f"https://api.github.com/repos/{actual_owner}/{actual_repo}/contents"
        root_filenames: List[str] = []
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                c_resp = await client.get(contents_url)
                if c_resp.status_code == 200:
                    c_json = c_resp.json()
                    if isinstance(c_json, list):
                        root_filenames = [item.get("name", "") for item in c_json if item.get("name")]
        except Exception:
            pass

        # Fetch primary manifest if present (e.g. package.json, pyproject.toml, Cargo.toml)
        candidate_manifests = [
            "package.json", "pyproject.toml", "requirements.txt", "Cargo.toml",
            "go.mod", "pom.xml", "build.gradle", "setup.py"
        ]
        manifest_found = None
        for mf in candidate_manifests:
            if mf in root_filenames:
                manifest_found = mf
                break

        if manifest_found:
            mf_text = await self._fetch_raw_file(actual_owner, actual_repo, default_branch, manifest_found)
            if mf_text:
                files_retrieved.append(manifest_found)
                # Cap manifest at 2000 chars for prompt efficiency
                truncated_mf = mf_text[:2000] + ("\n... [truncated]" if len(mf_text) > 2000 else "")
                manifest_content = f"### File: {manifest_found}\n```\n{truncated_mf}\n```"

        # -------------------------------------------------------------
        # 5. Assemble Evidence Contract
        # -------------------------------------------------------------
        content_sections = [
            f"# Repository: {actual_owner}/{actual_repo}",
            f"- Description: {description}",
            f"- Primary Language: {primary_lang}",
            f"- Default Branch: {default_branch}",
            f"- License: {license_name}",
            f"- Stars: {stars} | Forks: {forks} | Open Issues: {open_issues}",
        ]

        if root_filenames:
            file_preview = ", ".join(root_filenames[:25])
            if len(root_filenames) > 25:
                file_preview += f" ... ({len(root_filenames) - 25} more files)"
            content_sections.append(f"- Root Files Detected: {file_preview}")

        if readme_content:
            # Cap README at 4000 words / 16KB to prevent context bloat
            words = readme_content.split()
            if len(words) > 3000:
                readme_trimmed = " ".join(words[:3000]) + "\n... [README truncated for length]"
            else:
                readme_trimmed = readme_content
            content_sections.append(f"\n## README:\n{readme_trimmed}")
        else:
            content_sections.append("\n## README:\n(No README file was found or accessible in this repository.)")

        if manifest_content:
            content_sections.append(f"\n## Manifest Details:\n{manifest_content}")

        assembled_content = "\n".join(content_sections)

        metadata = {
            "owner": actual_owner,
            "repo": actual_repo,
            "default_branch": default_branch,
            "language": primary_lang,
            "description": description,
            "stars": stars,
            "forks": forks,
            "open_issues": open_issues,
            "license": license_name,
            "identity_verified": True,
            "readme_available": bool(readme_content),
            "files_retrieved": files_retrieved,
            "root_file_count": len(root_filenames),
        }

        return EvidenceContract(
            success=True,
            tool="github_inspect",
            requested_url=canonical_url,
            resolved_url=repo_data.get("html_url", canonical_url),
            http_status=200,
            content_type="text/markdown",
            title=f"GitHub: {actual_owner}/{actual_repo}",
            source_name=f"GitHub ({actual_owner}/{actual_repo})",
            retrieved_content=assembled_content,
            retrieved_at=now,
            error=None,
            error_type=None,
            metadata=metadata,
        )

    async def _fetch_raw_file(self, owner: str, repo: str, branch: str, path: str) -> Optional[str]:
        """Fetches raw file directly from raw.githubusercontent.com."""
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        try:
            status_code, content_bytes, content_type, headers = await safe_fetch_http(raw_url, max_size=512 * 1024, timeout_sec=6.0)
            if status_code == 200:
                return content_bytes.decode("utf-8", errors="replace")
        except Exception:
            pass
        return None

    async def _fallback_raw_inspection(self, owner: str, repo: str, canonical_url: str, now: str) -> Optional[EvidenceContract]:
        """Fallback direct inspection via raw.githubusercontent.com when GitHub REST API fails or is unavailable."""
        for branch in ("main", "master"):
            readme = await self._fetch_raw_file(owner, repo, branch, "README.md")
            if readme:
                content = (
                    f"# Repository: {owner}/{repo}\n"
                    f"- Source: raw.githubusercontent.com ({branch})\n"
                    f"\n## README:\n{readme[:10000]}"
                )
                return EvidenceContract(
                    success=True,
                    tool="github_inspect",
                    requested_url=canonical_url,
                    resolved_url=canonical_url,
                    http_status=200,
                    content_type="text/markdown",
                    title=f"GitHub: {owner}/{repo}",
                    source_name=f"GitHub ({owner}/{repo})",
                    retrieved_content=content,
                    retrieved_at=now,
                    error=None,
                    error_type=None,
                    metadata={
                        "owner": owner,
                        "repo": repo,
                        "default_branch": branch,
                        "identity_verified": True,
                        "readme_available": True,
                        "files_retrieved": ["README.md"],
                        "fallback_raw": True,
                    },
                )
        return None
