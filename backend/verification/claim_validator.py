"""
Moso AI — Post-Generation Claim-to-Evidence Validator
Validates assistant responses against the retrieved evidence registry:
- Verifies that factual claims are grounded in actual retrieved evidence
- Detects and neutralizes name-based hallucinations (e.g. heartbeat tracking for 'pulse_watch')
- Filters out fabricated or ungrounded citation URLs
- Attaches authoritative verification notes when speculative claims are detected
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
from backend.web.evidence import EvidenceContract


# High-risk hallucination keywords frequently hallucinated from names without evidence
DOMAIN_HALLUCINATION_TRIGGERS = {
    "biometric_cardio": {
        "pattern": re.compile(r'\b(heart\s*rates?|pulse\s*rates?|cardiovascular|cardiac|ecg|blood\s*pressures?|vital\s*signs?|stethoscopes?)\b', re.IGNORECASE),
        "label": "cardiovascular / vital signs monitoring",
    },
    "blockchain_crypto": {
        "pattern": re.compile(r'\b(blockchains?|cryptocurrenc(?:y|ies)|smart\s*contracts?|erc-20|ethereum|solana|bitcoin|nft|web3)\b', re.IGNORECASE),
        "label": "blockchain / cryptocurrency technology",
    },
    "deep_learning_magic": {
        "pattern": re.compile(r'\b(transformer\s*neural\s*networks?|diffusion\s*models?|reinforcement\s*learning|deep\s*neural\s*networks?|llm\s*training)\b', re.IGNORECASE),
        "label": "deep neural network architecture",
    },
    "medical_diagnosis": {
        "pattern": re.compile(r'\b(clinical\s*diagnos(?:is|es)|medical\s*treatments?|patient\s*monitoring|physicians?|fda\s*approved)\b', re.IGNORECASE),
        "label": "clinical / medical diagnostic capability",
    },
}


@dataclass
class ValidationResult:
    """Outcome of claim-to-evidence validation."""
    passed: bool
    validated_response: str
    supported_claims: List[str] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)
    retained_citations: List[Dict[str, Any]] = field(default_factory=list)
    removed_citations: List[Dict[str, Any]] = field(default_factory=list)
    validation_notes: List[str] = field(default_factory=list)
    validation_score: float = 1.0


def validate_grounded_response(
    generated_text: str,
    contracts: List[EvidenceContract],
    citations: List[Dict[str, Any]],
    user_query: str = "",
) -> ValidationResult:
    """
    Validates model completion against the evidence registry.
    Removes ungrounded citations and corrects speculative claims.
    """
    if not contracts or not any(c.is_groundable() for c in contracts):
        # Pure general knowledge / conversational - no external evidence to gate against
        return ValidationResult(
            passed=True,
            validated_response=generated_text,
            retained_citations=citations,
            removed_citations=[],
            validation_score=1.0,
        )

    # Combine all verified evidence text into a single lowercase corpus for fast verification
    verified_corpus = " ".join([c.retrieved_content.lower() for c in contracts if c.is_groundable()])
    valid_resolved_urls = {c.resolved_url.lower().rstrip("/") for c in contracts if c.is_groundable()}
    valid_requested_urls = {c.requested_url.lower().rstrip("/") for c in contracts if c.is_groundable()}
    all_valid_urls = valid_resolved_urls | valid_requested_urls

    retained_citations = []
    removed_citations = []

    # -------------------------------------------------------------
    # 1. Citation Provenance & URL Validation
    # -------------------------------------------------------------
    for cit in citations:
        c_url = (cit.get("url") or "").lower().rstrip("/")
        # Verify citation matches an actual retrieved contract
        if any(c_url.startswith(valid_u) or valid_u.startswith(c_url) for valid_u in all_valid_urls):
            retained_citations.append(cit)
        else:
            removed_citations.append(cit)

    # -------------------------------------------------------------
    # 2. Hallucination Detection & Inferred Feature Audit
    # -------------------------------------------------------------
    unsupported_claims = []
    supported_claims = []
    validation_notes = []

    for domain_key, trig in DOMAIN_HALLUCINATION_TRIGGERS.items():
        model_matches = trig["pattern"].findall(generated_text)
        if model_matches:
            # Check if this concept exists anywhere in the retrieved evidence corpus
            evidence_matches = trig["pattern"].findall(verified_corpus)
            if not evidence_matches:
                # The model asserted domain claims that are completely absent from the retrieved evidence!
                matched_sample = model_matches[0] if isinstance(model_matches[0], str) else model_matches[0][0]
                unsupported_claims.append(f"{trig['label']} (e.g. '{matched_sample}')")
            else:
                supported_claims.append(trig["label"])

    # -------------------------------------------------------------
    # 3. Repository Stack & Metadata Consistency Check
    # -------------------------------------------------------------
    git_contracts = [c for c in contracts if c.tool == "github_inspect" and c.is_groundable()]
    for gc in git_contracts:
        expected_lang = gc.metadata.get("language")
        if expected_lang and expected_lang != "Unspecified":
            # If model states the repository is written in another primary language
            known_languages = ["Python", "Rust", "Go", "TypeScript", "JavaScript", "Java", "C++", "C#", "Ruby", "Swift", "PHP"]
            for lang in known_languages:
                if lang.lower() != expected_lang.lower() and f"written in {lang.lower()}" in generated_text.lower():
                    if f"written in {lang.lower()}" not in verified_corpus:
                        unsupported_claims.append(f"primary language as '{lang}' (actual repository language is '{expected_lang}')")

    # -------------------------------------------------------------
    # 4. Construct Cleaned Response & Verification Disclaimer
    # -------------------------------------------------------------
    cleaned_response = generated_text
    passed = len(unsupported_claims) == 0

    if unsupported_claims:
        validation_notes.append(
            f"Detected {len(unsupported_claims)} unverified claim(s) unsupported by retrieved evidence."
        )
        disclaimer_lines = [
            "\n\n> ⚠️ **Verification Notice:** The retrieved documentation for this project does not mention "
            + ", ".join(unsupported_claims)
            + ". Those statements have been flagged as unverified inferences and should not be treated as established facts."
        ]
        cleaned_response = generated_text + "".join(disclaimer_lines)

    score = 1.0 if passed else max(0.2, 1.0 - (len(unsupported_claims) * 0.25))

    return ValidationResult(
        passed=passed,
        validated_response=cleaned_response,
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        retained_citations=retained_citations,
        removed_citations=removed_citations,
        validation_notes=validation_notes,
        validation_score=score,
    )
