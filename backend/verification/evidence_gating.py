"""
Moso AI — Deterministic Evidence Gating & Evidence Registry
Enforces application-level verification gating before prompting the language model:
- Rejects ungrounded guesses when external retrieval fails or is incomplete
- Enforces strict repository identity checks
- Distinguishes 404 Not Found vs 403 Forbidden vs 429 Rate Limit vs Timeout
- Blocks name-based inferences (e.g. guessing that 'pulse_watch' is a heartbeat app)
- Maintains request-scoped evidence provenance and diagnostics
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re

from backend.web.evidence import (
    EvidenceContract,
    ERROR_TYPE_NOT_FOUND,
    ERROR_TYPE_FORBIDDEN,
    ERROR_TYPE_RATE_LIMITED,
    ERROR_TYPE_TIMEOUT,
    ERROR_TYPE_CONNECTION_FAILURE,
    ERROR_TYPE_IDENTITY_MISMATCH,
    ERROR_TYPE_EMPTY_CONTENT,
    ERROR_TYPE_SSRF_BLOCKED,
)
from backend.web.github import parse_github_target
from .classifier import VerificationIntent, _bare_token_is_repo


@dataclass
class GatingDecision:
    """Outcome of the deterministic evidence evaluation."""
    can_proceed_to_model: bool
    requires_abstention: bool
    abstention_response: Optional[str] = None
    grounding_directives: str = ""
    evidence_contracts: List[EvidenceContract] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


class EvidenceRegistry:
    """Request-scoped registry tracking all retrieval operations, evidence, and provenance."""

    def __init__(self):
        self.contracts: List[EvidenceContract] = []

    def add_contract(self, contract: EvidenceContract):
        self.contracts.append(contract)

    def get_verified_contracts(self) -> List[EvidenceContract]:
        return [c for c in self.contracts if c.is_groundable()]

    def get_failed_contracts(self) -> List[EvidenceContract]:
        return [c for c in self.contracts if not c.success]

    def has_verified_content(self) -> bool:
        return any(c.is_groundable() for c in self.contracts)

    def to_diagnostics(self) -> List[Dict[str, Any]]:
        return [c.format_diagnostic_summary() for c in self.contracts]


def evaluate_evidence_gating(
    intent: VerificationIntent,
    user_query: str,
    registry: EvidenceRegistry,
) -> GatingDecision:
    """
    Evaluates whether retrieval succeeded and whether evidence is sufficient
    before allowing the model to generate responses for external queries.
    """
    diagnostics = registry.to_diagnostics()
    github_target = None
    if intent and getattr(intent, "entities", None) and "github_target" in intent.entities:
        github_target = intent.entities["github_target"]
    # Same rule as the classifier: a bare "word/word" is only a repo when the message
    # really points at GitHub. Real github.com URLs always count.
    if not github_target:
        pq = parse_github_target(user_query)
        if pq and ("github.com" in user_query.lower() or _bare_token_is_repo(user_query.strip(), user_query, pq)):
            github_target = pq
    if not github_target:
        for token in user_query.split():
            pt = parse_github_target(token)
            if pt and ("github.com" in token.lower() or _bare_token_is_repo(token, user_query, pt)):
                github_target = pt
                break
    if not github_target:
        for c in registry.contracts:
            if c.tool == "github_inspect" or "github.com" in c.requested_url.lower():
                pt = parse_github_target(c.requested_url)
                if pt:
                    github_target = pt
                    break
                if c.metadata and "requested_owner" in c.metadata and "requested_repo" in c.metadata:
                    github_target = (c.metadata["requested_owner"], c.metadata["requested_repo"], None)
                    break
                if c.metadata and "owner" in c.metadata and "repo" in c.metadata:
                    github_target = (c.metadata["owner"], c.metadata["repo"], None)
                    break

    # -------------------------------------------------------------
    # 1. Dedicated GitHub Repository Evaluation
    # -------------------------------------------------------------
    if github_target:
        owner, repo, _ = github_target
        repo_contracts = [
            c for c in registry.contracts
            if c.tool == "github_inspect" or "github.com" in c.requested_url.lower() or "github.com" in c.resolved_url.lower()
        ]

        # Case A: GitHub repository requested, but retrieval FAILED completely
        failed_repo = next((c for c in repo_contracts if not c.success), None)
        if failed_repo or not repo_contracts:
            err_type = failed_repo.error_type if failed_repo else ERROR_TYPE_NOT_FOUND
            http_status = failed_repo.http_status if failed_repo else 404

            if err_type == ERROR_TYPE_NOT_FOUND or http_status == 404:
                msg = (
                    f"### Repository Inaccessible: {owner}/{repo}\n\n"
                    f"I could not inspect the repository **`{owner}/{repo}`** because it was not found on GitHub (HTTP 404).\n\n"
                    f"- **Status:** The repository does not exist at this address, or may be inaccessible.\n"
                    f"- **Identity Check:** No source code or documentation could be retrieved.\n\n"
                    f"> **Note:** Moso AI does not infer application features, tech stacks, or architectures from a repository name alone. "
                    f"To inspect this project, please verify that the repository URL is public and spelled correctly."
                )
            elif err_type == ERROR_TYPE_FORBIDDEN or http_status == 403:
                msg = (
                    f"### Repository Access Forbidden: {owner}/{repo}\n\n"
                    f"Access to the repository **`{owner}/{repo}`** was rejected with HTTP 403 Forbidden.\n\n"
                    f"- **Status:** Access is restricted or authorization is required.\n"
                    f"- **Identity Check:** No verified files or README could be inspected.\n\n"
                    f"> **Note:** Moso AI will not invent project details without verified access to the repository code."
                )
            elif err_type == ERROR_TYPE_RATE_LIMITED or http_status == 429:
                msg = (
                    f"### GitHub Rate Limit Encountered: {owner}/{repo}\n\n"
                    f"Unable to inspect **`{owner}/{repo}`** because the GitHub API rate limit was reached.\n\n"
                    f"- **Status:** HTTP 429 / Rate Limited.\n"
                    f"- **Identity Check:** Retrieval paused to comply with upstream provider quotas.\n\n"
                    f"Please try again shortly or configure a `GITHUB_TOKEN` in your environment."
                )
            elif err_type == ERROR_TYPE_IDENTITY_MISMATCH:
                msg = (
                    f"### Repository Identity Mismatch: {owner}/{repo}\n\n"
                    f"A search result or redirect pointed to a different repository, which was rejected.\n\n"
                    f"- **Requested Target:** `{owner}/{repo}`\n"
                    f"- **Rejection Reason:** Moso AI enforces strict owner and repository matching to prevent substituting unrelated projects.\n\n"
                    f"No verified evidence was found for the requested repository."
                )
            elif err_type == ERROR_TYPE_TIMEOUT:
                msg = (
                    f"### Connection Timeout: {owner}/{repo}\n\n"
                    f"Retrieval timed out while connecting to GitHub for **`{owner}/{repo}`**.\n\n"
                    f"No code or documentation could be fetched within the time limit."
                )
            else:
                msg = (
                    f"### Repository Inspection Failed: {owner}/{repo}\n\n"
                    f"Unable to retrieve repository content for **`{owner}/{repo}`**.\n\n"
                    f"- **Error:** {failed_repo.error if failed_repo else 'No response from repository service'}.\n\n"
                    f"Moso AI cannot verify the contents or purpose of this project."
                )

            return GatingDecision(
                can_proceed_to_model=False,
                requires_abstention=True,
                abstention_response=msg,
                evidence_contracts=registry.contracts,
                diagnostics=diagnostics,
            )

        # Case B: Repository metadata retrieved, but README and files are absent
        verified_repo = next((c for c in repo_contracts if c.is_groundable()), None)
        if not verified_repo:
            # A nominally successful response without verified owner/repo
            # identity or usable content must never authorize generation.
            msg = (
                f"### Repository Evidence Unverified: {owner}/{repo}\n\n"
                "GitHub returned a response, but Moso AI could not establish verified repository identity and usable content.\n\n"
                "No project description will be generated from the repository name alone."
            )
            return GatingDecision(
                can_proceed_to_model=False,
                requires_abstention=True,
                abstention_response=msg,
                evidence_contracts=registry.contracts,
                diagnostics=diagnostics,
            )
        if verified_repo:
            actual_owner = str(verified_repo.metadata.get("owner", ""))
            actual_repo = str(verified_repo.metadata.get("repo", ""))
            if (actual_owner.casefold(), actual_repo.casefold()) != (owner.casefold(), repo.casefold()):
                msg = (
                    f"### Repository Identity Mismatch: {owner}/{repo}\n\n"
                    f"Retrieved evidence identifies `{actual_owner}/{actual_repo}`, not the requested repository.\n\n"
                    "The response is blocked to prevent substituting another project."
                )
                return GatingDecision(
                    can_proceed_to_model=False,
                    requires_abstention=True,
                    abstention_response=msg,
                    evidence_contracts=registry.contracts,
                    diagnostics=diagnostics,
                )
            has_readme = verified_repo.metadata.get("readme_available", False)
            files = verified_repo.metadata.get("files_retrieved", [])

            if not has_readme and not files:
                desc = verified_repo.metadata.get("description")
                lang = verified_repo.metadata.get("language")
                abstention = (
                    f"### Repository Metadata: {owner}/{repo}\n\n"
                    f"The repository **`{owner}/{repo}`** exists on GitHub, but contains no README or accessible source files:\n\n"
                    f"- Primary Language: {lang or 'Unspecified'}\n"
                    f"- Description: {desc or '(No description provided on GitHub)'}\n"
                    f"- Default Branch: {verified_repo.metadata.get('default_branch', 'main')}\n"
                    f"- Stars: {verified_repo.metadata.get('stars', 0)} | Forks: {verified_repo.metadata.get('forks', 0)}\n\n"
                    f"> **Limitation:** Because this repository does not include documentation or source code, "
                    f"further application features or internal mechanisms cannot be verified and will not be inferred."
                )
                return GatingDecision(
                    can_proceed_to_model=False,
                    requires_abstention=True,
                    abstention_response=abstention,
                    evidence_contracts=registry.contracts,
                    diagnostics=diagnostics,
                )

    # -------------------------------------------------------------
    # 2. Direct Web URL Evaluation (Non-GitHub)
    # -------------------------------------------------------------
    if intent.task_type == "web_fetch" and intent.detected_urls:
        url_contracts = [c for c in registry.contracts if c.tool in ("web_fetch", "github_inspect")]
        failed_fetch = next((c for c in url_contracts if not c.success), None)

        if failed_fetch and not any(c.is_groundable() for c in url_contracts):
            req_url = failed_fetch.requested_url or intent.detected_urls[0]
            err_reason = failed_fetch.error or "The target web page could not be accessed."
            err_code = failed_fetch.http_status or failed_fetch.error_type or "inaccessible"

            abstention = (
                f"### Web Page Inaccessible: {req_url}\n\n"
                f"I could not retrieve content from the requested URL:\n\n"
                f"- **Target URL:** `{req_url}`\n"
                f"- **Failure Detail:** {err_reason} (Status: {err_code})\n\n"
                f"> **Integrity Notice:** Moso AI does not generate or extrapolate website content when retrieval fails. "
                f"Please verify the URL or ensure the target site is publicly reachable."
            )
            return GatingDecision(
                can_proceed_to_model=False,
                requires_abstention=True,
                abstention_response=abstention,
                evidence_contracts=registry.contracts,
                diagnostics=diagnostics,
            )

    # -------------------------------------------------------------
    # 3. Verified Evidence Grounding Directives for Qwen
    # -------------------------------------------------------------
    grounding_rules = (
        "\nCRITICAL EVIDENCE-GROUNDING INSTRUCTIONS:\n"
        "1. Every factual statement about the retrieved source MUST be supported by the retrieved evidence.\n"
        "2. Do NOT infer or invent project functionality, medical uses, AI algorithms, or features from a repository or product name.\n"
        "3. Do NOT invent technologies, libraries, authors, or affiliations that are not stated in the evidence.\n"
        "4. If the user asks about an aspect not covered in the evidence, say: 'This is not mentioned in the retrieved material.'\n"
        "5. If you provide general engineering context, clearly distinguish it as general knowledge, not a verified fact about this source.\n"
    )

    return GatingDecision(
        can_proceed_to_model=True,
        requires_abstention=False,
        abstention_response=None,
        grounding_directives=grounding_rules,
        evidence_contracts=registry.contracts,
        diagnostics=diagnostics,
    )
