"""Paper library management tool for querying and updating the paper store."""

import json
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.research.paper_store import PaperStore


class PaperLibraryTool(Tool):
    """Manage the research paper library: list, query, update status, and add notes."""

    name = "paper_library"
    description = (
        "Query and manage the research paper library. "
        "You can list papers by status or topic, search papers, update reading status, "
        "add notes, or get paper details. "
        "Use this when the user asks about their saved papers, reading list, or wants to manage paper metadata."
    )

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list",
                    "get",
                    "update_status",
                    "add_note",
                    "get_notes",
                    "search",
                    "add_topic",
                    "list_topics",
                    "link_topic",
                    "statistics",
                    "compare",
                ],
                "description": "Action to perform on the paper library.",
            },
            "compare_paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "For compare action: list of exactly 2 paper IDs to compare.",
            },
            "paper_id": {
                "type": "integer",
                "description": "Paper ID for get, update_status, add_note, get_notes actions.",
            },
            "status": {
                "type": "string",
                "enum": ["unread", "reading", "read"],
                "description": "Filter by reading status for list action, or target status for update_status.",
            },
            "topic_id": {
                "type": "integer",
                "description": "Topic ID for list or link_topic action.",
            },
            "search": {
                "type": "string",
                "description": "Search query for search action.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results for list/search.",
                "default": 20,
            },
            "note_type": {
                "type": "string",
                "enum": ["highlight", "summary", "question", "insight"],
                "description": "Type of note for add_note action.",
                "default": "summary",
            },
            "content": {
                "type": "string",
                "description": "Note content for add_note action.",
            },
            "topic_name": {
                "type": "string",
                "description": "Topic name for add_topic action.",
            },
            "topic_description": {
                "type": "string",
                "description": "Topic description for add_topic action.",
            },
            "keywords": {
                "type": "string",
                "description": "Comma-separated keywords for add_topic action.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, paper_store: PaperStore):
        self.paper_store = paper_store

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "list":
            return self._do_list(**kwargs)
        elif action == "get":
            return self._do_get(**kwargs)
        elif action == "update_status":
            return self._do_update_status(**kwargs)
        elif action == "add_note":
            return self._do_add_note(**kwargs)
        elif action == "get_notes":
            return self._do_get_notes(**kwargs)
        elif action == "search":
            return self._do_search(**kwargs)
        elif action == "add_topic":
            return self._do_add_topic(**kwargs)
        elif action == "list_topics":
            return self._do_list_topics(**kwargs)
        elif action == "link_topic":
            return self._do_link_topic(**kwargs)
        elif action == "statistics":
            return self._do_statistics(**kwargs)
        elif action == "compare":
            return self._do_compare(**kwargs)
        return f"Error: Unknown action '{action}'"

    def _do_list(self, status: str = "", topic_id: int = 0, limit: int = 20, **kwargs: Any) -> str:
        papers = self.paper_store.list_papers(
            status=status or None,
            topic_id=topic_id or None,
            limit=limit,
        )
        if not papers:
            return "No papers found."
        results = []
        for p in papers:
            results.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "authors": json.loads(p.authors) if p.authors else [],
                    "status": p.reading_status,
                    "arxiv_id": p.arxiv_id,
                    "published": p.published_date,
                    "source": p.source,
                    "citation_count": p.citation_count,
                }
            )
        return json.dumps(results, ensure_ascii=False, indent=2)

    def _do_get(self, paper_id: int = 0, **kwargs: Any) -> str:
        paper = self.paper_store.get_paper(paper_id)
        if not paper:
            return f"Paper {paper_id} not found."
        tags = self.paper_store.get_tags(paper_id)
        data = {
            "id": paper.id,
            "title": paper.title,
            "authors": json.loads(paper.authors) if paper.authors else [],
            "abstract": paper.abstract,
            "arxiv_id": paper.arxiv_id,
            "doi": paper.doi,
            "published": paper.published_date,
            "source": paper.source,
            "status": paper.reading_status,
            "citation_count": paper.citation_count,
            "summary": paper.extracted_summary,
            "methodology": paper.methodology,
            "key_findings": json.loads(paper.key_findings) if paper.key_findings else [],
            "limitations": paper.limitations,
            "future_work": paper.future_work,
            "tags": tags,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _do_update_status(self, paper_id: int = 0, status: str = "", **kwargs: Any) -> str:
        if not status:
            return "Error: status is required"
        ok = self.paper_store.update_reading_status(paper_id, status)
        if ok:
            return f"Paper {paper_id} status updated to '{status}'."
        return f"Error: Failed to update status for paper {paper_id}."

    def _do_add_note(
        self, paper_id: int = 0, note_type: str = "summary", content: str = "", **kwargs: Any
    ) -> str:
        if not content:
            return "Error: content is required"
        from nanobot.research.paper_store import ReadingNote

        note = ReadingNote(paper_id=paper_id, note_type=note_type, content=content)
        note_id = self.paper_store.add_note(note)
        return f"Note added to paper {paper_id} (note_id: {note_id})."

    def _do_get_notes(self, paper_id: int = 0, **kwargs: Any) -> str:
        notes = self.paper_store.get_notes(paper_id)
        if not notes:
            return f"No notes for paper {paper_id}."
        results = []
        for n in notes:
            results.append(
                {
                    "id": n.id,
                    "type": n.note_type,
                    "content": n.content,
                    "page_ref": n.page_ref,
                    "created_at": n.created_at,
                }
            )
        return json.dumps(results, ensure_ascii=False, indent=2)

    def _do_search(self, search: str = "", limit: int = 20, **kwargs: Any) -> str:
        if not search:
            return "Error: search query is required"
        papers = self.paper_store.list_papers(search=search, limit=limit)
        if not papers:
            return f"No papers matching '{search}'."
        results = []
        for p in papers:
            results.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "status": p.reading_status,
                    "arxiv_id": p.arxiv_id,
                }
            )
        return json.dumps(results, ensure_ascii=False, indent=2)

    def _do_add_topic(
        self, topic_name: str = "", topic_description: str = "", keywords: str = "", **kwargs: Any
    ) -> str:
        if not topic_name:
            return "Error: topic_name is required"
        from nanobot.research.paper_store import ResearchTopic

        topic = ResearchTopic(
            name=topic_name,
            description=topic_description,
            keywords=keywords,
        )
        topic_id = self.paper_store.add_topic(topic)
        return f"Topic '{topic_name}' added (topic_id: {topic_id})."

    def _do_list_topics(self, **kwargs: Any) -> str:
        topics = self.paper_store.list_topics()
        if not topics:
            return "No research topics defined."
        results = []
        for t in topics:
            results.append(
                {
                    "topic_id": t.topic_id,
                    "name": t.name,
                    "description": t.description,
                    "keywords": t.keywords,
                    "is_active": t.is_active,
                }
            )
        return json.dumps(results, ensure_ascii=False, indent=2)

    def _do_link_topic(
        self, paper_id: int = 0, topic_id: int = 0, **kwargs: Any
    ) -> str:
        if not paper_id or not topic_id:
            return "Error: paper_id and topic_id are required"
        self.paper_store.link_paper_to_topic(paper_id, topic_id)
        return f"Paper {paper_id} linked to topic {topic_id}."

    def _do_statistics(self, **kwargs: Any) -> str:
        stats = self.paper_store.get_statistics()
        return json.dumps(stats, ensure_ascii=False, indent=2)

    def _do_compare(self, compare_paper_ids: list[int] | None = None, **kwargs: Any) -> str:
        ids = compare_paper_ids or []
        if len(ids) != 2:
            return "Error: compare action requires exactly 2 paper IDs in compare_paper_ids."
        paper_a = self.paper_store.get_paper(ids[0])
        paper_b = self.paper_store.get_paper(ids[1])
        if not paper_a or not paper_b:
            return "Error: One or both papers not found."

        def _paper_to_dict(p):
            return {
                "id": p.id,
                "title": p.title,
                "authors": json.loads(p.authors) if p.authors else [],
                "abstract": p.abstract,
                "published": p.published_date,
                "summary": p.extracted_summary,
                "methodology": p.methodology,
                "key_findings": json.loads(p.key_findings) if p.key_findings else [],
                "citation_count": p.citation_count,
            }

        return json.dumps({
            "paper_a": _paper_to_dict(paper_a),
            "paper_b": _paper_to_dict(paper_b),
        }, ensure_ascii=False, indent=2)
