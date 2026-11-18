"""
Moso AI — Bible Reference & Scripture Verification Engine
Provides verified scripture retrieval for public domain texts and enforces
anti-fabrication safeguards when proprietary/copyrighted translations are requested.
"""

import sqlite3
from typing import Optional, Dict, Any, List
from .classifier import (
    BOOK_LOOKUP,
    KNOWN_TRANSLATIONS,
    COPYRIGHTED_TRANSLATIONS,
    PUBLIC_DOMAIN_TRANSLATIONS,
)

PUBLIC_DOMAIN_SCRIPTURE_SEED: List[Dict[str, Any]] = [
    # Luke 24:25
    {
        "translation": "kjv",
        "book": "Luke",
        "chapter": 24,
        "verse": 25,
        "text": "Then he said unto them, O fools, and slow of heart to believe all that the prophets have spoken:",
    },
    {
        "translation": "web",
        "book": "Luke",
        "chapter": 24,
        "verse": 25,
        "text": "He said to them, \"Foolish men, and slow of heart to believe in all that the prophets have spoken!\"",
    },
    # Luke 24:45
    {
        "translation": "kjv",
        "book": "Luke",
        "chapter": 24,
        "verse": 45,
        "text": "Then opened he their understanding, that they might understand the scriptures,",
    },
    {
        "translation": "web",
        "book": "Luke",
        "chapter": 24,
        "verse": 45,
        "text": "Then he opened their minds, that they might understand the Scriptures.",
    },
    # Luke 24:46
    {
        "translation": "kjv",
        "book": "Luke",
        "chapter": 24,
        "verse": 46,
        "text": "And said unto them, Thus it is written, and thus it behoved Christ to suffer, and to rise from the dead the third day:",
    },
    {
        "translation": "web",
        "book": "Luke",
        "chapter": 24,
        "verse": 46,
        "text": "He said to them, \"Thus it is written, and thus it was necessary for the Christ to suffer and to rise from the dead the third day,\"",
    },
    # Luke 24:47
    {
        "translation": "kjv",
        "book": "Luke",
        "chapter": 24,
        "verse": 47,
        "text": "And that repentance and remission of sins should be preached in his name among all nations, beginning at Jerusalem.",
    },
    {
        "translation": "web",
        "book": "Luke",
        "chapter": 24,
        "verse": 47,
        "text": "and that repentance and remission of sins should be preached in his name to all the nations, beginning at Jerusalem.",
    },
    # Isaiah 53:5
    {
        "translation": "kjv",
        "book": "Isaiah",
        "chapter": 53,
        "verse": 5,
        "text": "But he was wounded for our transgressions, he was bruised for our iniquities: the chastisement of our peace was upon him; and with his stripes we are healed.",
    },
    {
        "translation": "web",
        "book": "Isaiah",
        "chapter": 53,
        "verse": 5,
        "text": "But he was pierced for our transgressions. He was crushed for our iniquities. The punishment that brought our peace was on him; and by his wounds we are healed.",
    },
    # John 3:16
    {
        "translation": "kjv",
        "book": "John",
        "chapter": 3,
        "verse": 16,
        "text": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
    },
    {
        "translation": "web",
        "book": "John",
        "chapter": 3,
        "verse": 16,
        "text": "For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.",
    },
    # Genesis 1:1
    {
        "translation": "kjv",
        "book": "Genesis",
        "chapter": 1,
        "verse": 1,
        "text": "In the beginning God created the heaven and the earth.",
    },
    {
        "translation": "web",
        "book": "Genesis",
        "chapter": 1,
        "verse": 1,
        "text": "In the beginning, God created the heavens and the earth.",
    },
]

class BibleEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the local trusted scripture table and seed public domain verses if empty."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS trusted_bible_verses (
                id TEXT PRIMARY KEY,
                translation TEXT NOT NULL,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                is_public_domain INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bible_lookup ON trusted_bible_verses(translation, book, chapter, verse)")
        conn.commit()

        c.execute("SELECT COUNT(*) FROM trusted_bible_verses")
        count = c.fetchone()[0]
        conn.close()

        if count == 0:
            self.seed_reference_passages(PUBLIC_DOMAIN_SCRIPTURE_SEED)

    def get_verse(
        self,
        book: str,
        chapter: int,
        verse: int,
        translation: str = "web",
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve scripture reference.
        If a copyrighted translation (e.g. NIV, ESV) is requested and not licensed in local storage,
        this method returns a structured refusal to prevent fabricating copyrighted wording.
        """
        canonical_book = BOOK_LOOKUP.get(book.lower().strip(), book.strip())
        trans_key = translation.lower().strip()

        # Check licensing status of translation
        if trans_key in COPYRIGHTED_TRANSLATIONS:
            trans_name = KNOWN_TRANSLATIONS.get(trans_key, trans_key.upper())
            return {
                "verified": False,
                "status": "unverified",
                "reference": f"{canonical_book} {chapter}:{verse}",
                "requested_translation": trans_name,
                "is_copyrighted": True,
                "text": None,
                "error": "COPYRIGHTED_TRANSLATION_UNLICENSED",
                "disclaimer": (
                    f"The requested translation ({trans_name}) is proprietary and copyrighted. "
                    "Moso AI does not store or redistribute copyrighted modern translations without permission. "
                    "To avoid fabricating unverified wording, exact text for this translation cannot be generated."
                ),
                "public_domain_alternative": self._get_fallback_text(canonical_book, chapter, verse),
            }

        # Query local database for public domain translation
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("""
            SELECT text, translation, is_public_domain
            FROM trusted_bible_verses
            WHERE book = ? AND chapter = ? AND verse = ? AND translation = ?
        """, (canonical_book, chapter, verse, trans_key))
        row = c.fetchone()

        context_verses: List[Dict[str, Any]] = []
        if include_context and row:
            c.execute("""
                SELECT verse, text
                FROM trusted_bible_verses
                WHERE book = ? AND chapter = ? AND verse IN (?, ?) AND translation = ?
                ORDER BY verse ASC
            """, (canonical_book, chapter, max(1, verse - 1), verse + 1, trans_key))
            context_verses = [{"verse": r["verse"], "text": r["text"]} for r in c.fetchall()]

        conn.close()

        if row:
            return {
                "verified": True,
                "status": "verified",
                "reference": f"{canonical_book} {chapter}:{verse}",
                "requested_translation": KNOWN_TRANSLATIONS.get(trans_key, trans_key.upper()),
                "is_copyrighted": False,
                "text": row["text"],
                "context": context_verses,
                "source": f"Trusted Scripture Collection: {KNOWN_TRANSLATIONS.get(trans_key, trans_key.upper())} (Public Domain)",
            }

        # If not present in database
        return {
            "verified": False,
            "status": "unverified",
            "reference": f"{canonical_book} {chapter}:{verse}",
            "requested_translation": KNOWN_TRANSLATIONS.get(trans_key, trans_key.upper()),
            "is_copyrighted": False,
            "text": None,
            "error": "VERSE_NOT_FOUND_IN_LOCAL_STORAGE",
            "disclaimer": f"The exact wording for {canonical_book} {chapter}:{verse} could not be verified from available local sources.",
        }

    def _get_fallback_text(self, book: str, chapter: int, verse: int) -> Optional[Dict[str, Any]]:
        """Attempt to load a public-domain alternative (e.g. WEB or KJV)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT translation, text
            FROM trusted_bible_verses
            WHERE book = ? AND chapter = ? AND verse = ? AND translation IN ('web', 'kjv')
            ORDER BY translation = 'web' DESC
            LIMIT 1
        """, (book, chapter, verse))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "translation": KNOWN_TRANSLATIONS.get(row["translation"], row["translation"].upper()),
                "text": row["text"],
            }
        return None

    def seed_reference_passages(self, passages: List[Dict[str, Any]]):
        """Seed verified public domain passages into local storage."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for p in passages:
            v_id = f"{p['translation']}_{p['book']}_{p['chapter']}_{p['verse']}".lower().replace(" ", "_")
            c.execute("""
                INSERT OR REPLACE INTO trusted_bible_verses (id, translation, book, chapter, verse, text, is_public_domain)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                v_id,
                p["translation"].lower().strip(),
                BOOK_LOOKUP.get(p["book"].lower().strip(), p["book"].strip()),
                int(p["chapter"]),
                int(p["verse"]),
                p["text"].strip(),
                1 if p.get("is_public_domain", True) else 0
            ))
        conn.commit()
        conn.close()
