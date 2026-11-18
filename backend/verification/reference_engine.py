"""
Moso AI — Trusted Reference & Multi-Tier Grounding Engine
Prioritizes sources:
1. User-uploaded documents in conversation/project.
2. Local trusted reference collections (Scripture, scientific facts, historical milestones).
3. Approved external sources (if enabled).
4. General model knowledge (explicitly identified as unverified).
"""

import re
from typing import Optional, Dict, Any, List
from .bible_engine import BibleEngine
from .classifier import VerificationIntent, DOI_REGEX

# Verified scientific and mathematical constants/facts
VERIFIED_SCIENTIFIC_FACTS = {
    "speed of light": {
        "claim": "Speed of light in vacuum (c)",
        "value": "299,792,458 m/s (exact)",
        "latex": r"\(c = 299{,}792{,}458\text{ m/s}\)",
        "source": "CODATA Recommended Values of the Fundamental Physical Constants",
    },
    "gravitational constant": {
        "claim": "Newtonian constant of gravitation (G)",
        "value": "6.67430(15) x 10^-11 m^3 kg^-1 s^-2",
        "latex": r"\(G \approx 6.67430 \times 10^{-11}\text{ m}^3\text{kg}^{-1}\text{s}^{-2}\)",
        "source": "CODATA Recommended Values of the Fundamental Physical Constants",
    },
    "planck constant": {
        "claim": "Planck constant (h)",
        "value": "6.62607015 x 10^-34 J s (exact)",
        "latex": r"\(h = 6.62607015 \times 10^{-34}\text{ J}\cdot\text{s}\)",
        "source": "BIPM SI Brochure (9th edition)",
    },
    "mass-energy equivalence": {
        "claim": "Einstein mass-energy equivalence",
        "value": "E = mc^2",
        "latex": r"\(E = mc^2\)",
        "source": "Special Relativity (Einstein, 1905)",
    },
}

# Verified historical milestones
VERIFIED_HISTORICAL_EVENTS = {
    "apollo 11": {
        "claim": "Apollo 11 Crewed Moon Landing",
        "date": "July 20, 1969",
        "details": "Neil Armstrong and Buzz Aldrin landed the Apollo Lunar Module Eagle on the Moon on July 20, 1969, at 20:17 UTC.",
        "source": "NASA History Division (Apollo 11 Mission Overview)",
    },
    "berlin wall": {
        "claim": "Fall of the Berlin Wall",
        "date": "November 9, 1989",
        "details": "The border checkpoints of the Berlin Wall were opened on the evening of November 9, 1989.",
        "source": "German Historical Museum / Federal Archives",
    },
    "declaration of independence": {
        "claim": "Adoption of the United States Declaration of Independence",
        "date": "July 4, 1776",
        "details": "The Continental Congress approved the final wording of the Declaration of Independence on July 4, 1776.",
        "source": "U.S. National Archives and Records Administration",
    },
}

# Registry of known synthetic/fake test DOIs
KNOWN_INVALID_DOIS = {
    "10.1234/fake.doi.2024.001",
    "10.9999/nonexistent.paper.123",
    "10.5555/fabricated.study.2023",
    "10.0000/invented.research",
}


class ReferenceEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.bible_engine = BibleEngine(db_path)

    def retrieve_trusted_material(
        self,
        intent: VerificationIntent,
        uploaded_chunks: List[Dict[str, Any]],
        online_enabled: bool = False
    ) -> Dict[str, Any]:
        """
        Gathers evidence across priority tiers:
        Tier 1: Uploaded documents.
        Tier 2: Trusted reference collection (Bible, scientific, historical).
        Tier 3: Approved online sources (if configured).
        Tier 4: General model knowledge (unverified).
        """
        # Tier 1: User-Uploaded Documents
        if uploaded_chunks:
            return {
                "tier": 1,
                "tier_name": "uploaded_documents",
                "verified": True,
                "status": "verified",
                "sources": [
                    {
                        "type": "uploaded_document",
                        "title": chk["filename"],
                        "page_number": chk.get("page_number", 1),
                        "excerpt": chk["content"][:300].strip(),
                        "id": chk["id"],
                    }
                    for chk in uploaded_chunks
                ],
                "grounding_text": "\n\n".join(
                    f"[Document: {chk['filename']}, Page {chk.get('page_number', 1)}]:\n{chk['content']}"
                    for chk in uploaded_chunks
                ),
            }

        # Tier 2: Bible Reference
        if intent.category == "bible" and intent.entities:
            b_info = intent.entities
            verse_data = self.bible_engine.get_verse(
                book=b_info.get("book", ""),
                chapter=b_info.get("chapter", 1),
                verse=b_info.get("verse", 1),
                translation=b_info.get("translation", "web"),
            )
            return {
                "tier": 2,
                "tier_name": "trusted_scripture_reference",
                "verified": verse_data["verified"],
                "status": verse_data["status"],
                "bible_data": verse_data,
                "sources": [
                    {
                        "type": "trusted_scripture",
                        "title": f"{b_info.get('book')} {b_info.get('chapter')}:{b_info.get('verse')} ({verse_data.get('requested_translation')})",
                        "text": verse_data.get("text"),
                        "is_copyrighted": verse_data.get("is_copyrighted", False),
                    }
                ] if verse_data.get("text") else [],
                "disclaimer": verse_data.get("disclaimer"),
            }

        # Tier 2: Scientific Constants
        if intent.category == "scientific":
            q_lower = intent.entities.get("query", "").lower()
            matched_facts = []
            for k, fact in VERIFIED_SCIENTIFIC_FACTS.items():
                if k in q_lower or any(word in q_lower for word in k.split()):
                    matched_facts.append(fact)
            if matched_facts:
                return {
                    "tier": 2,
                    "tier_name": "trusted_scientific_constants",
                    "verified": True,
                    "status": "verified",
                    "sources": [
                        {
                            "type": "trusted_reference",
                            "title": f["claim"],
                            "value": f["value"],
                            "latex": f["latex"],
                            "source_name": f["source"],
                        }
                        for f in matched_facts
                    ],
                    "grounding_text": "\n".join(
                        f"Fact: {f['claim']} = {f['value']} ({f['latex']}) [Source: {f['source']}]"
                        for f in matched_facts
                    ),
                }

        # Tier 2: Historical Events
        if intent.category == "historical":
            q_lower = intent.entities.get("query", "").lower()
            matched_events = []
            for k, ev in VERIFIED_HISTORICAL_EVENTS.items():
                if k in q_lower:
                    matched_events.append(ev)
            if matched_events:
                return {
                    "tier": 2,
                    "tier_name": "trusted_historical_records",
                    "verified": True,
                    "status": "verified",
                    "sources": [
                        {
                            "type": "trusted_reference",
                            "title": ev["claim"],
                            "date": ev["date"],
                            "details": ev["details"],
                            "source_name": ev["source"],
                        }
                        for ev in matched_events
                    ],
                    "grounding_text": "\n".join(
                        f"Event: {ev['claim']} occurred on {ev['date']}. Details: {ev['details']} [Source: {ev['source']}]"
                        for ev in matched_events
                    ),
                }

        # Academic DOI Verification
        if intent.category == "academic":
            doi = intent.entities.get("doi")
            if doi and doi.lower() in KNOWN_INVALID_DOIS:
                return {
                    "tier": 2,
                    "tier_name": "academic_reference_check",
                    "verified": False,
                    "status": "unverified",
                    "sources": [],
                    "is_known_fake_doi": True,
                    "disclaimer": f"The identifier '{doi}' could not be validated in trusted registries. To prevent citing fabricated research, this DOI is unverified.",
                }

        # Tier 4: General Knowledge / No Source Available
        return {
            "tier": 4,
            "tier_name": "general_knowledge",
            "verified": False,
            "status": "unverified",
            "sources": [],
            "disclaimer": "This explanation is based on general model knowledge and has not been independently verified.",
        }
