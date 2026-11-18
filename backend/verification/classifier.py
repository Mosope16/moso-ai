"""
Moso AI — Lightweight Factual Question Classifier
Fast, deterministic (< 1ms) classification of user queries to identify whether factual
verification, scripture retrieval, academic check, or quotation verification is required.
Distinguishes factual queries from conversational, brainstorming, and creative tasks.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# Standard 66 Protestant Canonical Bible Books and common aliases
BIBLE_BOOKS = {
    # Old Testament
    "genesis": ["gen", "ge", "gn"],
    "exodus": ["exo", "ex", "exod"],
    "leviticus": ["lev", "le", "lv"],
    "numbers": ["num", "nu", "nm", "nb"],
    "deuteronomy": ["deut", "dt", "de"],
    "joshua": ["josh", "jos", "jsh"],
    "judges": ["judg", "jdg", "jg", "jdgs"],
    "ruth": ["rth", "ru"],
    "1 samuel": ["1 sam", "1sam", "1 sa", "1 s", "i samuel", "i sam"],
    "2 samuel": ["2 sam", "2sam", "2 sa", "2 s", "ii samuel", "ii sam"],
    "1 kings": ["1 kgs", "1kgs", "1 ki", "1 k", "i kings", "i kgs"],
    "2 kings": ["2 kgs", "2kgs", "2 ki", "2 k", "ii kings", "ii kgs"],
    "1 chronicles": ["1 chron", "1chron", "1 ch", "i chronicles", "i chron"],
    "2 chronicles": ["2 chron", "2chron", "2 ch", "ii chronicles", "ii chron"],
    "ezra": ["ezr", "ez"],
    "nehemiah": ["neh", "ne"],
    "esther": ["esth", "es"],
    "job": ["jb"],
    "psalms": ["psalm", "psa", "psm", "pss", "ps"],
    "proverbs": ["prov", "pro", "prv", "pr"],
    "ecclesiastes": ["eccles", "eccle", "ecc", "ec"],
    "song of solomon": ["song of songs", "song", "sos", "canticles"],
    "isaiah": ["isa", "is"],
    "jeremiah": ["jer", "je", "jr"],
    "lamentations": ["lam", "la"],
    "ezekiel": ["ezek", "eze", "ezk"],
    "daniel": ["dan", "da", "dn"],
    "hosea": ["hos", "ho"],
    "joel": ["joe", "jl"],
    "amos": ["amo", "am"],
    "obadiah": ["obad", "ob"],
    "jonah": ["jnh", "jon"],
    "micah": ["mic", "mc"],
    "nahum": ["nah", "na"],
    "habakkuk": ["hab", "hb"],
    "zephaniah": ["zeph", "zep", "zp"],
    "haggai": ["hag", "hg"],
    "zechariah": ["zech", "zec", "zc"],
    "malachi": ["mal", "ml"],
    # New Testament
    "matthew": ["matt", "mat", "mt"],
    "mark": ["mrk", "mar", "mk", "mr"],
    "luke": ["luk", "lu", "lk"],
    "john": ["jhn", "joh", "jn"],
    "acts": ["act", "ac"],
    "romans": ["rom", "ro", "rm"],
    "1 corinthians": ["1 cor", "1cor", "1 co", "i corinthians", "i cor"],
    "2 corinthians": ["2 cor", "2cor", "2 co", "ii corinthians", "ii cor"],
    "galatians": ["gal", "ga"],
    "ephesians": ["eph", "ep"],
    "philippians": ["phil", "php", "pp"],
    "colossians": ["col", "co"],
    "1 thessalonians": ["1 thess", "1thess", "1 th", "i thessalonians", "i thess"],
    "2 thessalonians": ["2 thess", "2thess", "2 th", "ii thessalonians", "ii thess"],
    "1 timothy": ["1 tim", "1tim", "1 ti", "i timothy", "i tim"],
    "2 timothy": ["2 tim", "2tim", "2 ti", "ii timothy", "ii tim"],
    "titus": ["tit", "ti"],
    "philemon": ["philem", "phm", "pm"],
    "hebrews": ["heb", "he"],
    "james": ["jas", "jm", "jam"],
    "1 peter": ["1 pet", "1pet", "1 pe", "1 pt", "i peter", "i pet"],
    "2 peter": ["2 pet", "2pet", "2 pe", "2 pt", "ii peter", "ii pet"],
    "1 john": ["1 jn", "1jn", "1 jo", "i john", "i jn"],
    "2 john": ["2 jn", "2jn", "2 jo", "ii john", "ii jn"],
    "3 john": ["3 jn", "3jn", "3 jo", "iii john", "iii jn"],
    "jude": ["jud", "jd"],
    "revelation": ["rev", "re", "apocalypse"],
}

# Inverted mapping for quick canonical lookup
BOOK_LOOKUP: Dict[str, str] = {}
for canonical, aliases in BIBLE_BOOKS.items():
    BOOK_LOOKUP[canonical.lower()] = canonical
    for a in aliases:
        BOOK_LOOKUP[a.lower()] = canonical

KNOWN_TRANSLATIONS = {
    "niv": "New International Version (NIV)",
    "esv": "English Standard Version (ESV)",
    "kjv": "King James Version (KJV)",
    "web": "World English Bible (WEB)",
    "nasb": "New American Standard Bible (NASB)",
    "nlt": "New Living Translation (NLT)",
    "asv": "American Standard Version (ASV)",
    "bsb": "Berean Standard Bible (BSB)",
    "nab": "New American Bible (NAB)",
    "csb": "Christian Standard Bible (CSB)",
    "rsv": "Revised Standard Version (RSV)",
}

COPYRIGHTED_TRANSLATIONS = {"niv", "esv", "nasb", "nlt", "nab", "csb", "rsv"}
PUBLIC_DOMAIN_TRANSLATIONS = {"kjv", "web", "asv", "bsb"}

# Regex for chapter:verse references e.g. "Luke 24:46", "Lk. 24:25-26", "Isaiah 53:5"
VERSE_REGEX = re.compile(
    r'\b(?P<book>(?:[123iI]{1,3}\s+)?[a-zA-Z]+(?:\s+of\s+[a-zA-Z]+)?)\.?\s+(?P<chapter>\d{1,3}):(?P<verse>\d{1,3})(?:-(?P<end_verse>\d{1,3}))?\b',
    re.IGNORECASE
)

# Regex for DOIs: e.g. 10.1000/182, 10.1038/s41586-020-2649-2
DOI_REGEX = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b')

# Conversational greetings & pleasantries that require zero factual verification
CONVERSATIONAL_PATTERNS = [
    r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings|howdy)\b',
    r'^(how\s+are\s+you|what\'?s\s+up|thank\s+you|thanks|cheers|bye|goodbye)\b',
    r'^(tell\s+me\s+a\s+joke|write\s+a\s+poem|write\s+a\s+story|brainstorm|let\'?s\s+chat)\b',
]

EXACT_QUOTE_TRIGGERS = [
    "quote", "exact words", "verbatim", "word for word", "exact quotation",
    "directly quote", "what does it say word for word", "cite textually"
]

ACADEMIC_TRIGGERS = [
    "doi", "citation", "academic reference", "journal paper", "published in",
    "peer-reviewed", "bibliography", "arxiv", "pubmed", "crossref", "author list"
]

SCIENTIFIC_TRIGGERS = [
    "formula", "speed of light", "gravitational constant", "planck", "planck constant",
    "planck's constant", "avogadro", "equation", "equation for", "constant value",
    "scientific law", "metric tensor", "schrodinger", "einstein", "mass-energy",
    "equivalence", "si units", "si value", "quantum"
]

HISTORICAL_TRIGGERS = [
    "what year did", "what date did", "when was the", "who was the president in",
    "fall of the berlin wall", "apollo 11", "declaration of independence", "battle of",
    "timeline of"
]


@dataclass
class VerificationIntent:
    is_factual: bool
    category: str  # 'bible', 'academic', 'quote', 'scientific', 'historical', 'document_qa', 'conversational', 'general_factual'
    requires_exact_quotation: bool = False
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


def classify_query(query: str, has_workspace_documents: bool = False) -> VerificationIntent:
    """
    Lightweight, deterministic classification to decide if factual grounding or
    verification layers should activate.
    Takes < 1 millisecond.
    """
    cleaned = query.strip()
    lower = cleaned.lower()

    if not cleaned:
        return VerificationIntent(is_factual=False, category="conversational")

    # 1. Pure conversational check
    for pat in CONVERSATIONAL_PATTERNS:
        if re.search(pat, lower):
            # Only mark non-factual if not also containing a specific factual request
            if not any(k in lower for k in ["quote", "luke", "verse", "doi", "formula", "10."]):
                return VerificationIntent(is_factual=False, category="conversational")

    # 2. Bible verse detection
    verse_match = VERSE_REGEX.search(cleaned)
    if verse_match:
        raw_book = verse_match.group("book").strip().lower()
        # Check if matched token is a legitimate Bible book
        canonical_book = BOOK_LOOKUP.get(raw_book)
        if canonical_book:
            chapter = int(verse_match.group("chapter"))
            verse = int(verse_match.group("verse"))
            end_verse = int(verse_match.group("end_verse")) if verse_match.group("end_verse") else None

            # Detect requested translation
            detected_trans = "web"  # default to modern public domain WEB
            for trans_code in KNOWN_TRANSLATIONS:
                if re.search(rf'\b{trans_code}\b', lower):
                    detected_trans = trans_code
                    break

            is_exact_quote = any(trig in lower for trig in EXACT_QUOTE_TRIGGERS) or "quote" in lower

            return VerificationIntent(
                is_factual=True,
                category="bible",
                requires_exact_quotation=is_exact_quote,
                entities={
                    "book": canonical_book,
                    "chapter": chapter,
                    "verse": verse,
                    "end_verse": end_verse,
                    "translation": detected_trans,
                    "is_copyrighted": detected_trans in COPYRIGHTED_TRANSLATIONS,
                    "reference_str": f"{canonical_book} {chapter}:{verse}",
                }
            )

    # Secondary Bible check (e.g., "what does the Bible say in Isaiah", "Luke 24")
    if "bible" in lower or "scripture" in lower or "gospel" in lower:
        for book_name in BOOK_LOOKUP:
            if re.search(rf'\b{re.escape(book_name)}\b', lower):
                canonical_book = BOOK_LOOKUP[book_name]
                return VerificationIntent(
                    is_factual=True,
                    category="bible",
                    requires_exact_quotation="quote" in lower,
                    entities={"book": canonical_book, "translation": "web", "is_copyrighted": False}
                )

    # 3. DOI & Academic reference requests
    doi_match = DOI_REGEX.search(cleaned)
    is_academic = any(trig in lower for trig in ACADEMIC_TRIGGERS)
    if doi_match or is_academic:
        doi = doi_match.group(0) if doi_match else None
        return VerificationIntent(
            is_factual=True,
            category="academic",
            requires_exact_quotation=False,
            entities={"doi": doi, "raw_query": cleaned}
        )

    # 4. Exact quotation request
    if any(trig in lower for trig in EXACT_QUOTE_TRIGGERS):
        return VerificationIntent(
            is_factual=True,
            category="quote",
            requires_exact_quotation=True,
            entities={"query": cleaned}
        )

    # 5. Scientific facts / formulas
    if any(trig in lower for trig in SCIENTIFIC_TRIGGERS):
        return VerificationIntent(
            is_factual=True,
            category="scientific",
            requires_exact_quotation=False,
            entities={"query": cleaned}
        )

    # 6. Historical dates & events
    if any(trig in lower for trig in HISTORICAL_TRIGGERS):
        return VerificationIntent(
            is_factual=True,
            category="historical",
            requires_exact_quotation=False,
            entities={"query": cleaned}
        )

    # 7. Document context question
    if has_workspace_documents:
        # If user has uploaded documents attached, default to document QA verification
        return VerificationIntent(
            is_factual=True,
            category="document_qa",
            requires_exact_quotation=False,
            entities={"query": cleaned}
        )

    # 8. Check for general factual questions (who was, when did, what is the population, etc.)
    if re.search(r'^(what\s+is|who\s+was|who\s+is|when\s+did|where\s+is|how\s+many|how\s+much)\b', lower):
        return VerificationIntent(
            is_factual=True,
            category="general_factual",
            requires_exact_quotation=False,
            entities={"query": cleaned}
        )

    # Default fallback: general conversational / open-ended
    return VerificationIntent(is_factual=False, category="conversational")
