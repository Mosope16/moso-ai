"""
Moso AI — Intelligent Task Classifier & Generation Profiler
Identifies broad task types and selects optimal generation profiles for Qwen 3.5 2B:
- Conversational
- General Knowledge
- Explanation
- Mathematical
- Programming
- Creative Writing
- Academic Research
- Document Question Answering
- Exact Quotation
- Current Information
- Multi-step Reasoning

Enforces:
- Selective retrieval (allows model to answer directly for general knowledge without DB lookup)
- Selective verification (only triggers verification for exact quotes, citations, and documents)
- Task-aware generation parameters (temperature, top_p, num_predict)
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from .tools import run_deterministic_tools

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
    "philemon": ["phlm", "phm"],
    "hebrews": ["heb", "he"],
    "james": ["jas", "jm"],
    "1 peter": ["1 pet", "1pet", "1 pe", "1 pt", "i peter", "i pet"],
    "2 peter": ["2 pet", "2pet", "2 pe", "2 pt", "ii peter", "ii pet"],
    "1 john": ["1 jn", "1jn", "1 jo", "i john", "i jn"],
    "2 john": ["2 jn", "2jn", "2 jo", "ii john", "ii jn"],
    "3 john": ["3 jn", "3jn", "3 jo", "iii john", "iii jn"],
    "jude": ["jud", "jd"],
    "revelation": ["rev", "re", "apocalypse"],
}

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

VERSE_REGEX = re.compile(
    r'\b(?P<book>(?:[123iI]{1,3}\s+)?[a-zA-Z]+(?:\s+of\s+[a-zA-Z]+)?)\.?\s+(?P<chapter>\d{1,3}):(?P<verse>\d{1,3})(?:-(?P<end_verse>\d{1,3}))?\b',
    re.IGNORECASE
)

DOI_REGEX = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b')

# Task-Aware Generation Profiles (Section 2)
GENERATION_PROFILES = {
    "factual": {"temperature": 0.2, "top_p": 0.8, "num_predict": 512, "num_ctx": 4096},
    "general_knowledge": {"temperature": 0.3, "top_p": 0.85, "num_predict": 512, "num_ctx": 4096},
    "explanation": {"temperature": 0.3, "top_p": 0.85, "num_predict": 512, "num_ctx": 4096},
    "conversational": {"temperature": 0.6, "top_p": 0.9, "num_predict": 512, "num_ctx": 4096},
    "creative_writing": {"temperature": 0.8, "top_p": 0.95, "num_predict": 768, "num_ctx": 4096},
    "mathematical": {"temperature": 0.1, "top_p": 0.8, "num_predict": 384, "num_ctx": 4096},
    "programming": {"temperature": 0.2, "top_p": 0.8, "num_predict": 512, "num_ctx": 4096},
    "academic_research": {"temperature": 0.2, "top_p": 0.85, "num_predict": 768, "num_ctx": 4096},
    "multi_step_reasoning": {"temperature": 0.2, "top_p": 0.85, "num_predict": 768, "num_ctx": 4096},
    "document_qa": {"temperature": 0.2, "top_p": 0.8, "num_predict": 512, "num_ctx": 4096},
    "exact_quotation": {"temperature": 0.1, "top_p": 0.7, "num_predict": 256, "num_ctx": 4096},
    "web_retrieval": {"temperature": 0.2, "top_p": 0.8, "num_predict": 768, "num_ctx": 4096},
}

URL_REGEX = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+', re.IGNORECASE)


@dataclass
class VerificationIntent:
    """Task classification and processing instructions for Moso AI pipeline."""
    task_type: str  # conversational, general_knowledge, explanation, mathematical, programming, creative_writing, academic_research, document_qa, exact_quotation, current_information, multi_step_reasoning, web_fetch, web_search
    is_factual: bool
    category: str   # legacy category: bible, academic, quote, scientific, historical, document_qa, conversational, general_factual, web
    requires_exact_quotation: bool = False
    needs_local_rag: bool = False
    needs_verification: bool = False
    needs_task_decomposition: bool = False
    needs_web: bool = False
    detected_urls: List[str] = field(default_factory=list)
    web_search_query: Optional[str] = None
    deterministic_tool_result: Optional[Dict[str, Any]] = None
    generation_profile: Dict[str, Any] = field(default_factory=lambda: GENERATION_PROFILES["conversational"])
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


# A bare "word/word" token is only treated as a GitHub repo when the message gives a
# real signal. Without this, "System/Instruction", "and/or", "I/O", "3/4" and
# "src/utils" all got sent to the GitHub inspector and abstained with a 404.
_GITHUB_HINT_REGEX = re.compile(r"\b(github|git\s*hub|repo|repos|repository|repositories)\b", re.IGNORECASE)

_COMMON_SLASH_PAIRS = {
    "and/or", "he/she", "his/her", "him/her", "s/he", "i/o", "w/o", "n/a", "a/b", "ci/cd",
    "tcp/ip", "udp/ip", "input/output", "read/write", "true/false", "yes/no", "on/off",
    "up/down", "km/h", "m/s", "either/or", "pros/cons", "client/server", "system/instruction",
}

_COMMON_DIR_NAMES = {
    "src", "lib", "bin", "usr", "etc", "var", "home", "tmp", "docs", "app", "dist", "build",
    "test", "tests", "backend", "frontend", "public", "assets", "components", "node_modules",
}


def _bare_token_is_repo(token: str, query: str, parsed) -> bool:
    """Decide whether a bare owner/repo token (no URL) really means a GitHub repository."""
    owner, repo, _ = parsed
    if "github.com" in token.lower():
        return True  # an explicit github.com URL, with or without https://
    if not (re.search(r"[A-Za-z]", owner) and re.search(r"[A-Za-z]", repo)):
        return False  # fractions and dates like 3/4 or 12/05
    if f"{owner}/{repo}".lower() in _COMMON_SLASH_PAIRS or owner.lower() in _COMMON_DIR_NAMES:
        return False
    words = query.split()
    if len(words) == 1:
        return True  # the whole message is just the identifier
    if _GITHUB_HINT_REGEX.search(query):
        return True  # the user said github / repo / repository
    # Short question with a repo-looking name such as "what does Mosope16/pulse_watch do?"
    return len(words) <= 12 and ("_" in repo or "-" in repo)


def classify_query(query: str, has_workspace_documents: bool = False) -> VerificationIntent:
    """
    Intelligent, deterministic (< 1ms) classification of user queries.
    Identifies broad task type, execution steps, tool needs, and generation profile.
    """
    cleaned = query.strip()
    lower = cleaned.lower()

    if not cleaned:
        return VerificationIntent(
            task_type="conversational",
            is_factual=False,
            category="conversational",
            generation_profile=GENERATION_PROFILES["conversational"]
        )

    # 1. Deterministic Tool Check (Math, Calendar, Unit Conversion)
    tool_result = run_deterministic_tools(cleaned)
    if tool_result:
        return VerificationIntent(
            task_type="mathematical",
            is_factual=True,
            category="scientific",
            needs_verification=True,
            deterministic_tool_result=tool_result,
            generation_profile=GENERATION_PROFILES["mathematical"],
            entities={"tool": tool_result["type"]}
        )

    # 2. Conversational greetings & pleasantries
    conversational_patterns = [
        r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings|howdy)\b',
        r'^(how\s+are\s+you|what\'?s\s+up|thank\s+you|thanks|cheers|bye|goodbye)\b',
    ]
    for pat in conversational_patterns:
        if re.search(pat, lower) and len(cleaned.split()) <= 6:
            return VerificationIntent(
                task_type="conversational",
                is_factual=False,
                category="conversational",
                generation_profile=GENERATION_PROFILES["conversational"]
            )

    # 3. Direct GitHub Repository Target Detection
    from backend.web.github import parse_github_target
    detected_urls = URL_REGEX.findall(cleaned)
    github_target = None
    for u in detected_urls:
        parsed_g = parse_github_target(u)
        if parsed_g:
            github_target = parsed_g
            break
    if not github_target:
        # Check if the query itself is or contains a GitHub target (e.g. "what does Mosope16/pulse_watch do?")
        for token in cleaned.split():
            parsed_token = parse_github_target(token)
            if parsed_token and _bare_token_is_repo(token, cleaned, parsed_token):
                github_target = parsed_token
                break

    if github_target:
        return VerificationIntent(
            task_type="github_inspect",
            is_factual=True,
            category="programming",
            needs_web=True,
            detected_urls=detected_urls or [f"https://github.com/{github_target[0]}/{github_target[1]}"],
            needs_verification=True,
            generation_profile=GENERATION_PROFILES["web_retrieval"],
            entities={"github_target": github_target}
        )

    # 4. Direct Generic URL Detection (Extract & Fetch Web Pages / Remote PDFs)
    if detected_urls:
        return VerificationIntent(
            task_type="web_fetch",
            is_factual=True,
            category="web",
            needs_web=True,
            detected_urls=detected_urls,
            needs_verification=False,
            generation_profile=GENERATION_PROFILES["web_retrieval"],
            entities={"urls": detected_urls}
        )

    # 4. Explicit Web Search & Real-Time Query Triggers
    web_triggers = [
        "search the web", "search online", "look up online", "browse the web", "search for",
        "latest news", "current weather", "weather in", "today's weather",
        "stock price of", "current price of", "recent release", "latest release",
        "what is the latest", "who is the current", "recent developments",
        "latest documentation", "documentation for", "documentation of",
        "who won the 2024", "who won the 2025", "who won the 2026",
        "cite sources", "provide sources", "with sources", "find online"
    ]
    if any(trig in lower for trig in web_triggers):
        return VerificationIntent(
            task_type="web_search",
            is_factual=True,
            category="web",
            needs_web=True,
            web_search_query=cleaned,
            needs_verification=False,
            generation_profile=GENERATION_PROFILES["web_retrieval"]
        )

    # 3. Creative Writing (poems, haikus, stories, metaphors)
    creative_triggers = [
        "write a poem", "write a story", "compose a haiku", "haiku about",
        "mystery opening", "poetic metaphor", "write a fictional", "creative story",
        "write a song", "write lyrics"
    ]
    if any(trig in lower for trig in creative_triggers):
        return VerificationIntent(
            task_type="creative_writing",
            is_factual=False,
            category="conversational",
            needs_verification=False,
            generation_profile=GENERATION_PROFILES["creative_writing"]
        )

    # 4. Programming & Code Generation
    programming_triggers = [
        "write a python", "write a function", "write code", "implement in python",
        "time complexity of", "difference between mutable and immutable", "concurrency vs parallelism",
        "binary search", "algorithm to", "sql query", "fix this error", "typescript"
    ]
    if any(trig in lower for trig in programming_triggers) or re.search(r'\b(def|class|function|import|const|let)\s+[a-zA-Z_]', cleaned):
        return VerificationIntent(
            task_type="programming",
            is_factual=True,
            category="general_factual",
            needs_verification=False,
            generation_profile=GENERATION_PROFILES["programming"]
        )

    # 5. Bible Verse & Scripture
    verse_match = VERSE_REGEX.search(cleaned)
    if verse_match:
        raw_book = verse_match.group("book").strip().lower()
        canonical_book = BOOK_LOOKUP.get(raw_book)
        if canonical_book:
            chapter = int(verse_match.group("chapter"))
            verse = int(verse_match.group("verse"))
            end_verse = int(verse_match.group("end_verse")) if verse_match.group("end_verse") else None

            detected_trans = "web"
            for trans_code in KNOWN_TRANSLATIONS:
                if re.search(rf'\b{trans_code}\b', lower):
                    detected_trans = trans_code
                    break

            is_exact = any(k in lower for k in ["quote", "verbatim", "exact text", "exact words"]) or "quote" in lower

            return VerificationIntent(
                task_type="exact_quotation" if is_exact else "explanation",
                is_factual=True,
                category="bible",
                requires_exact_quotation=is_exact,
                needs_verification=True,
                generation_profile=GENERATION_PROFILES["exact_quotation"] if is_exact else GENERATION_PROFILES["factual"],
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

    # Secondary Bible check (e.g. "what does the Bible say in John 3:16")
    if "bible" in lower or "scripture" in lower or "gospel" in lower:
        for book_name in BOOK_LOOKUP:
            if re.search(rf'\b{re.escape(book_name)}\b', lower):
                canonical_book = BOOK_LOOKUP[book_name]
                return VerificationIntent(
                    task_type="explanation",
                    is_factual=True,
                    category="bible",
                    requires_exact_quotation="quote" in lower,
                    needs_verification=True,
                    generation_profile=GENERATION_PROFILES["factual"],
                    entities={"book": canonical_book, "translation": "web", "is_copyrighted": False}
                )

    # 6. Exact Quotations (Literature, Speeches, Historical)
    if any(trig in lower for trig in ["quote the opening", "quote the famous", "exact quote", "quote verbatim"]):
        return VerificationIntent(
            task_type="exact_quotation",
            is_factual=True,
            category="quote",
            requires_exact_quotation=True,
            needs_verification=True,
            generation_profile=GENERATION_PROFILES["exact_quotation"]
        )

    # 7. Document Q&A (Explicitly references uploaded PDFs, documents, or context)
    doc_ref_triggers = ["uploaded document", "attached document", "in the pdf", "in my notes", "from the document", "in the report"]
    if has_workspace_documents and any(trig in lower for trig in doc_ref_triggers):
        return VerificationIntent(
            task_type="document_qa",
            is_factual=True,
            category="document_qa",
            needs_local_rag=True,
            needs_verification=True,
            generation_profile=GENERATION_PROFILES["document_qa"]
        )

    # 8. Multi-Step Reasoning & Word Problems
    reasoning_triggers = [
        "if a car travels", "average speed", "probability of", "water tank", "if all bloops",
        "calculate the probability", "step by step reasoning", "how many days between"
    ]
    if any(trig in lower for trig in reasoning_triggers):
        return VerificationIntent(
            task_type="multi_step_reasoning",
            is_factual=True,
            category="general_factual",
            needs_task_decomposition=True,
            generation_profile=GENERATION_PROFILES["multi_step_reasoning"]
        )

    # 9. Academic Research & Neurology (Alzheimer's, Machine Learning, Transformers)
    academic_triggers = [
        "alzheimer", "amyloid-beta", "tau tangles", "mri", "cholinesterase", "apoe",
        "convolutional neural network", "vision transformer", "confusion matrix", "roc-auc",
        "ablation stud", "peer-reviewed", "doi", "arxiv", "crossref", "pubmed"
    ]
    doi_match = DOI_REGEX.search(cleaned)
    if doi_match or any(trig in lower for trig in academic_triggers):
        return VerificationIntent(
            task_type="academic_research",
            is_factual=True,
            category="academic",
            needs_task_decomposition=len(cleaned.split()) > 8,
            needs_verification=bool(doi_match),
            generation_profile=GENERATION_PROFILES["academic_research"],
            entities={"doi": doi_match.group(0) if doi_match else None}
        )

    # 10. Science & Physical Laws
    scientific_triggers = [
        "newton's", "nuclear fission", "nuclear fusion", "absolute zero",
        "fundamental forces", "mitochondria", "central dogma", "mrna vaccine",
        "speed of light", "planck", "gravitational constant", "mass-energy equivalence",
        "e = mc", "quantum"
    ]
    if any(trig in lower for trig in scientific_triggers):
        return VerificationIntent(
            task_type="explanation",
            is_factual=True,
            category="scientific",
            needs_verification=False,  # Answer directly using learned science knowledge!
            generation_profile=GENERATION_PROFILES["factual"]
        )

    # 11. Historical Dates & Events
    historical_triggers = [
        "world war", "magna carta", "president of the united states", "united nations",
        "apollo 11", "berlin wall", "declaration of independence", "french revolution"
    ]
    if any(trig in lower for trig in historical_triggers):
        return VerificationIntent(
            task_type="general_knowledge",
            is_factual=True,
            category="historical",
            needs_verification=False,  # Answer directly using model knowledge!
            generation_profile=GENERATION_PROFILES["factual"]
        )

    # 12. General Knowledge / Explanation fallback
    if re.search(r'^(what\s+is|what\s+are|how\s+does|how\s+do|why\s+is|why\s+do|who\s+was|who\s+is|explain|describe)\b', lower):
        return VerificationIntent(
            task_type="general_knowledge",
            is_factual=True,
            category="general_factual",
            needs_verification=False,  # Answer directly without blocking on DB!
            generation_profile=GENERATION_PROFILES["general_knowledge"]
        )

    # Default fallback
    return VerificationIntent(
        task_type="conversational",
        is_factual=False,
        category="conversational",
        needs_verification=False,
        generation_profile=GENERATION_PROFILES["conversational"]
    )
