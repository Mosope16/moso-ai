"""
Moso AI — Post-Generation Factual Verifier & Evidence Auditor
Audits generated responses against retrieved sources to determine verification status,
detect ungrounded quotations, check citation validity, and structure verification metadata.
"""

import re
from typing import Dict, Any, List, Optional
from .classifier import VerificationIntent


def normalize_text(text: str) -> str:
    """Strip punctuation and whitespace for comparison."""
    return re.sub(r'[^\w\s]', '', text.lower()).strip()


def compute_token_overlap(quote: str, source: str) -> float:
    """Calculate normalized word-level overlap between a quote and source text."""
    q_words = normalize_text(quote).split()
    s_words = set(normalize_text(source).split())
    if not q_words:
        return 0.0
    matched = sum(1 for w in q_words if w in s_words)
    return matched / len(q_words)


class ResponseVerifier:
    def verify(
        self,
        query: str,
        response_text: str,
        intent: VerificationIntent,
        retrieved_material: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Audit model response against retrieved evidence and return a VerificationReport.
        """
        if not intent.is_factual or not getattr(intent, "needs_verification", True):
            return {
                "status": "none",
                "is_factual": False,
                "category": intent.category,
                "sources_consulted": [],
                "verified_claims": [],
                "unverified_claims": [],
                "disclaimer": None,
                "quotation_check": {"has_quotes": False, "verified": True},
            }

        response_lower = response_text.lower()
        sources_consulted = retrieved_material.get("sources", [])
        tier = retrieved_material.get("tier", 4)
        tier_name = retrieved_material.get("tier_name", "general_knowledge")

        # 1. Detect explicit uncertainty or abstention phrases
        abstention_patterns = [
            "couldn't verify",
            "cannot verify",
            "not available in the local",
            "do not contain sufficient evidence",
            "not provide enough evidence",
            "has not been independently verified",
            "proprietary copyrighted translation",
            "unverified",
        ]
        has_acknowledged_uncertainty = any(p in response_lower for p in abstention_patterns)

        # 2. Extract quotes from generated text
        raw_quotes = re.findall(r'["“]([^"”]{8,})["”]', response_text)
        quote_verification_results = []
        all_quotes_verified = True

        combined_source_text = ""
        if tier == 1:
            combined_source_text = " ".join(s.get("excerpt", "") for s in sources_consulted)
        elif tier == 2:
            if intent.category == "bible":
                b_data = retrieved_material.get("bible_data", {})
                combined_source_text = b_data.get("text", "") or ""
                alt = b_data.get("public_domain_alternative")
                if alt:
                    combined_source_text += " " + alt.get("text", "")
            else:
                combined_source_text = " ".join(str(s) for s in sources_consulted)

        if raw_quotes:
            for q in raw_quotes:
                if combined_source_text:
                    overlap = compute_token_overlap(q, combined_source_text)
                    is_match = overlap >= 0.75
                    quote_verification_results.append({
                        "quote": q,
                        "overlap_score": round(overlap, 2),
                        "verified": is_match,
                    })
                    if not is_match:
                        all_quotes_verified = False
                else:
                    quote_verification_results.append({
                        "quote": q,
                        "overlap_score": 0.0,
                        "verified": False,
                    })
                    all_quotes_verified = False

        # 3. Determine Overall Evidence-Based Status
        verified_claims = []
        unverified_claims = []
        disclaimer = None

        if tier == 1 and sources_consulted:
            if has_acknowledged_uncertainty and "sufficient evidence" in response_lower:
                status = "verified"
                verified_claims.append("Evaluated uploaded document context; recognized insufficient evidence.")
                disclaimer = "The uploaded documents do not provide enough evidence to establish this claim."
            else:
                status = "verified" if all_quotes_verified else "partially_verified"
                for s in sources_consulted[:3]:
                    verified_claims.append(f"Grounded in {s.get('title')} (p. {s.get('page_number', 1)})")
                if not all_quotes_verified:
                    unverified_claims.append("Some extracted quotations could not be strictly aligned with source text.")

        elif tier == 2:
            if intent.category == "bible":
                b_data = retrieved_material.get("bible_data", {})
                if b_data.get("is_copyrighted"):
                    status = "unverified"
                    unverified_claims.append(f"Requested translation ({b_data.get('requested_translation')}) is proprietary.")
                    disclaimer = b_data.get("disclaimer")
                elif b_data.get("verified") and b_data.get("text"):
                    status = "verified" if all_quotes_verified else "partially_verified"
                    verified_claims.append(f"Verified against {b_data.get('reference')} ({b_data.get('requested_translation')})")
                else:
                    status = "unverified"
                    unverified_claims.append(f"Reference {b_data.get('reference')} not present in local database.")
                    disclaimer = b_data.get("disclaimer")
            elif intent.category in ("scientific", "historical"):
                status = "verified"
                for s in sources_consulted:
                    verified_claims.append(f"Verified via {s.get('title')} ({s.get('source_name', 'Trusted DB')})")
            elif intent.category == "academic" and retrieved_material.get("is_known_fake_doi"):
                status = "unverified"
                unverified_claims.append("Supplied DOI is unverified in academic registries.")
                disclaimer = retrieved_material.get("disclaimer")
            else:
                status = "partially_verified"

        else:
            status = "unverified"
            unverified_claims.append("Claim generated from general model knowledge; no primary source consulted.")
            disclaimer = "This explanation is based on general model knowledge and has not been independently verified."

        return {
            "status": status,
            "is_factual": True,
            "category": intent.category,
            "tier": tier,
            "tier_name": tier_name,
            "sources_consulted": sources_consulted,
            "verified_claims": verified_claims,
            "unverified_claims": unverified_claims,
            "disclaimer": disclaimer,
            "quotation_check": {
                "has_quotes": bool(raw_quotes),
                "quotes_count": len(raw_quotes),
                "all_quotes_verified": all_quotes_verified,
                "details": quote_verification_results,
            },
            "appropriate_abstention": has_acknowledged_uncertainty,
        }
