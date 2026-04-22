"""Paper store for research assistant - SQLite-backed paper library."""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class Paper:
    """A research paper record."""

    id: int | None = None
    title: str = ""
    authors: str = ""  # JSON list
    abstract: str = ""
    pdf_path: str = ""
    doi: str = ""
    arxiv_id: str = ""
    published_date: str = ""
    added_date: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""  # arxiv, semantic_scholar, etc.
    citation_count: int = 0
    reading_status: str = "unread"  # unread, reading, read
    priority: int = 0
    extracted_summary: str = ""
    methodology: str = ""
    key_findings: str = ""  # JSON list
    limitations: str = ""
    future_work: str = ""
    user_rating: int = 0


@dataclass
class ReadingNote:
    """A reading note for a paper."""

    id: int | None = None
    paper_id: int = 0
    note_type: str = "summary"  # highlight, summary, question, insight
    content: str = ""
    page_ref: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ResearchTopic:
    """A research topic/direction."""

    topic_id: int | None = None
    name: str = ""
    description: str = ""
    keywords: str = ""  # comma-separated
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True


class PaperStore:
    """SQLite-backed store for research papers, notes, and topics."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    authors TEXT DEFAULT '[]',
                    abstract TEXT DEFAULT '',
                    pdf_path TEXT DEFAULT '',
                    doi TEXT DEFAULT '',
                    arxiv_id TEXT DEFAULT '',
                    published_date TEXT DEFAULT '',
                    added_date TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    citation_count INTEGER DEFAULT 0,
                    reading_status TEXT DEFAULT 'unread',
                    priority INTEGER DEFAULT 0,
                    extracted_summary TEXT DEFAULT '',
                    methodology TEXT DEFAULT '',
                    key_findings TEXT DEFAULT '[]',
                    limitations TEXT DEFAULT '',
                    future_work TEXT DEFAULT '',
                    user_rating INTEGER DEFAULT 0
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_arxiv
                    ON papers(arxiv_id) WHERE arxiv_id != '';
                CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi
                    ON papers(doi) WHERE doi != '';
                CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(reading_status);
                CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);

                CREATE TABLE IF NOT EXISTS paper_tags (
                    paper_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    auto_extracted INTEGER DEFAULT 0,
                    PRIMARY KEY (paper_id, tag),
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_tags ON paper_tags(tag);

                CREATE TABLE IF NOT EXISTS reading_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    note_type TEXT DEFAULT 'summary',
                    content TEXT DEFAULT '',
                    page_ref TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_notes_paper ON reading_notes(paper_id);

                CREATE TABLE IF NOT EXISTS research_topics (
                    topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    keywords TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS topic_papers (
                    topic_id INTEGER NOT NULL,
                    paper_id INTEGER NOT NULL,
                    relevance_score REAL DEFAULT 0.0,
                    PRIMARY KEY (topic_id, paper_id),
                    FOREIGN KEY (topic_id) REFERENCES research_topics(topic_id) ON DELETE CASCADE,
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()

    def add_paper(self, paper: Paper) -> int:
        """Add or update a paper. Returns paper id."""
        with sqlite3.connect(self.db_path) as conn:
            # Check for duplicate by arxiv_id or doi
            existing = None
            if paper.arxiv_id:
                row = conn.execute(
                    "SELECT id FROM papers WHERE arxiv_id = ?", (paper.arxiv_id,)
                ).fetchone()
                if row:
                    existing = row[0]
            if not existing and paper.doi:
                row = conn.execute(
                    "SELECT id FROM papers WHERE doi = ?", (paper.doi,)
                ).fetchone()
                if row:
                    existing = row[0]

            data = {
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "pdf_path": paper.pdf_path,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "published_date": paper.published_date,
                "added_date": paper.added_date or datetime.now().isoformat(),
                "source": paper.source,
                "citation_count": paper.citation_count,
                "reading_status": paper.reading_status,
                "priority": paper.priority,
                "extracted_summary": paper.extracted_summary,
                "methodology": paper.methodology,
                "key_findings": paper.key_findings,
                "limitations": paper.limitations,
                "future_work": paper.future_work,
                "user_rating": paper.user_rating,
            }

            if existing:
                set_clause = ", ".join(f"{k} = :{k}" for k in data)
                data["id"] = existing
                conn.execute(
                    f"UPDATE papers SET {set_clause} WHERE id = :id", data
                )
                conn.commit()
                logger.info(f"Updated paper {existing}: {paper.title}")
                return existing

            columns = ", ".join(data.keys())
            placeholders = ", ".join(f":{k}" for k in data)
            cursor = conn.execute(
                f"INSERT INTO papers ({columns}) VALUES ({placeholders})", data
            )
            conn.commit()
            logger.info(f"Added paper {cursor.lastrowid}: {paper.title}")
            return cursor.lastrowid

    def get_paper(self, paper_id: int) -> Paper | None:
        """Get a paper by id."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_paper(row, conn)

    def get_paper_by_arxiv(self, arxiv_id: str) -> Paper | None:
        """Get a paper by arXiv ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_paper(row, conn)

    def list_papers(
        self,
        status: str | None = None,
        topic_id: int | None = None,
        tag: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Paper]:
        """List papers with optional filters."""
        query = "SELECT p.* FROM papers p"
        params: list[Any] = []
        conditions: list[str] = []

        if topic_id is not None:
            query += " JOIN topic_papers tp ON p.id = tp.paper_id"
            conditions.append("tp.topic_id = ?")
            params.append(topic_id)

        if tag:
            query += " JOIN paper_tags pt ON p.id = pt.paper_id"
            conditions.append("pt.tag = ?")
            params.append(tag)

        if status:
            conditions.append("p.reading_status = ?")
            params.append(status)

        if search:
            conditions.append(
                "(p.title LIKE ? OR p.abstract LIKE ? OR p.authors LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY p.added_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_paper(row, conn) for row in rows]

    def update_reading_status(self, paper_id: int, status: str) -> bool:
        """Update reading status."""
        valid = {"unread", "reading", "read"}
        if status not in valid:
            return False
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE papers SET reading_status = ? WHERE id = ?",
                (status, paper_id),
            )
            conn.commit()
        return True

    def update_analysis(
        self,
        paper_id: int,
        summary: str = "",
        methodology: str = "",
        key_findings: str = "",
        limitations: str = "",
        future_work: str = "",
    ) -> bool:
        """Update LLM-extracted analysis fields."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE papers SET
                    extracted_summary = ?,
                    methodology = ?,
                    key_findings = ?,
                    limitations = ?,
                    future_work = ?
                WHERE id = ?""",
                (summary, methodology, key_findings, limitations, future_work, paper_id),
            )
            conn.commit()
        return True

    def add_note(self, note: ReadingNote) -> int:
        """Add a reading note. Returns note id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO reading_notes
                    (paper_id, note_type, content, page_ref, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    note.paper_id,
                    note.note_type,
                    note.content,
                    note.page_ref,
                    note.created_at or datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_notes(self, paper_id: int) -> list[ReadingNote]:
        """Get all notes for a paper."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, paper_id, note_type, content, page_ref, created_at
                FROM reading_notes WHERE paper_id = ? ORDER BY created_at DESC""",
                (paper_id,),
            ).fetchall()
            return [
                ReadingNote(
                    id=r[0],
                    paper_id=r[1],
                    note_type=r[2],
                    content=r[3],
                    page_ref=r[4],
                    created_at=r[5],
                )
                for r in rows
            ]

    def add_topic(self, topic: ResearchTopic) -> int:
        """Add a research topic. Returns topic id."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """INSERT INTO research_topics
                        (name, description, keywords, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        topic.name,
                        topic.description,
                        topic.keywords,
                        topic.created_at or datetime.now().isoformat(),
                        int(topic.is_active),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Name already exists
                row = conn.execute(
                    "SELECT topic_id FROM research_topics WHERE name = ?",
                    (topic.name,),
                ).fetchone()
                return row[0] if row else 0

    def list_topics(self, active_only: bool = True) -> list[ResearchTopic]:
        """List research topics."""
        query = "SELECT * FROM research_topics"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query).fetchall()
            return [
                ResearchTopic(
                    topic_id=r[0],
                    name=r[1],
                    description=r[2],
                    keywords=r[3],
                    created_at=r[4],
                    is_active=bool(r[5]),
                )
                for r in rows
            ]

    def link_paper_to_topic(
        self, paper_id: int, topic_id: int, relevance_score: float = 0.0
    ) -> None:
        """Link a paper to a topic."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO topic_papers
                    (topic_id, paper_id, relevance_score)
                VALUES (?, ?, ?)""",
                (topic_id, paper_id, relevance_score),
            )
            conn.commit()

    def add_tags(self, paper_id: int, tags: list[str], auto: bool = False) -> None:
        """Add tags to a paper."""
        with sqlite3.connect(self.db_path) as conn:
            for tag in tags:
                conn.execute(
                    """INSERT OR IGNORE INTO paper_tags
                        (paper_id, tag, auto_extracted)
                    VALUES (?, ?, ?)""",
                    (paper_id, tag.strip().lower(), int(auto)),
                )
            conn.commit()

    def get_tags(self, paper_id: int) -> list[str]:
        """Get tags for a paper."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT tag FROM paper_tags WHERE paper_id = ?", (paper_id,)
            ).fetchall()
            return [r[0] for r in rows]

    def get_papers_by_topic(self, topic_id: int, limit: int = 50) -> list[Paper]:
        """Get papers linked to a topic."""
        return self.list_papers(topic_id=topic_id, limit=limit)

    def delete_paper(self, paper_id: int) -> None:
        """Delete a paper and its related data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
            conn.commit()

    def get_statistics(self) -> dict[str, Any]:
        """Get reading statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            unread = conn.execute("SELECT COUNT(*) FROM papers WHERE reading_status = 'unread'").fetchone()[0]
            reading = conn.execute("SELECT COUNT(*) FROM papers WHERE reading_status = 'reading'").fetchone()[0]
            read = conn.execute("SELECT COUNT(*) FROM papers WHERE reading_status = 'read'").fetchone()[0]

            # Recent additions (last 7 days)
            from datetime import datetime, timedelta
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            recent = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE added_date > ?", (week_ago,)
            ).fetchone()[0]

            # Top sources
            sources = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM papers WHERE source != '' GROUP BY source ORDER BY cnt DESC LIMIT 5"
            ).fetchall()

            # Top tags
            tags = conn.execute(
                "SELECT tag, COUNT(*) as cnt FROM paper_tags GROUP BY tag ORDER BY cnt DESC LIMIT 10"
            ).fetchall()

            return {
                "total": total,
                "unread": unread,
                "reading": reading,
                "read": read,
                "recent_7d": recent,
                "top_sources": [{"source": s[0], "count": s[1]} for s in sources],
                "top_tags": [{"tag": t[0], "count": t[1]} for t in tags],
            }

    def _row_to_paper(self, row: sqlite3.Row, conn: sqlite3.Connection) -> Paper:
        """Convert a DB row to Paper dataclass."""
        paper = Paper(
            id=row[0],
            title=row[1],
            authors=row[2],
            abstract=row[3],
            pdf_path=row[4],
            doi=row[5],
            arxiv_id=row[6],
            published_date=row[7],
            added_date=row[8],
            source=row[9],
            citation_count=row[10],
            reading_status=row[11],
            priority=row[12],
            extracted_summary=row[13],
            methodology=row[14],
            key_findings=row[15],
            limitations=row[16],
            future_work=row[17],
            user_rating=row[18],
        )
        return paper
