"""Citation graph analysis tool for research papers."""

import json
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1"


class CitationGraphTool(Tool):
    """Analyze citation networks using Semantic Scholar."""

    name = "citation_graph"
    description = (
        "Analyze citation relationships for research papers. "
        "Get papers that cite a given paper, papers that the given paper cites, "
        "or identify key papers in a research area. "
        "Use this when the user wants to understand the research lineage, impact, or related work of a paper."
    )

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["citations", "references", "lineage", "key_papers"],
                "description": "Type of citation analysis to perform.",
            },
            "arxiv_id": {
                "type": "string",
                "description": "arXiv ID of the paper.",
            },
            "doi": {
                "type": "string",
                "description": "DOI of the paper (alternative to arxiv_id).",
            },
            "topic": {
                "type": "string",
                "description": "For key_papers action: research topic/keywords to search.",
            },
            "depth": {
                "type": "integer",
                "description": "Depth of citation traversal (1 = direct only, 2 = includes citations of citations).",
                "minimum": 1,
                "maximum": 2,
                "default": 1,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results per level.",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
            },
        },
        "required": ["action"],
    }

    def __init__(self, semantic_scholar_api_key: str = ""):
        self.api_key = semantic_scholar_api_key

    async def execute(
        self,
        action: str,
        arxiv_id: str = "",
        doi: str = "",
        topic: str = "",
        depth: int = 1,
        max_results: int = 10,
    ) -> str:
        headers = {"x-api-key": self.api_key} if self.api_key else {}

        if action == "key_papers":
            if not topic:
                return "Error: topic is required for key_papers action."
            return await self._find_key_papers(topic, max_results, headers)

        if not arxiv_id and not doi:
            return "Error: Please provide arxiv_id or doi."

        paper_id = f"ARXIV:{arxiv_id}" if arxiv_id else f"DOI:{doi}"

        if action == "citations":
            return await self._get_citations(paper_id, depth, max_results, headers)
        elif action == "references":
            return await self._get_references(paper_id, depth, max_results, headers)
        elif action == "lineage":
            return await self._get_lineage(paper_id, max_results, headers)

        return f"Error: Unknown action '{action}'"

    async def _get_citations(
        self, paper_id: str, depth: int, max_results: int, headers: dict[str, str]
    ) -> str:
        """Get papers that cite the given paper."""
        fields = "title,authors,year,citationCount,abstract,url"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/{paper_id}/citations",
                params={"fields": fields, "limit": max_results},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        citations = []
        for item in data.get("data", []):
            citing_paper = item.get("citingPaper", {})
            citations.append(self._format_paper(citing_paper))

        result = {
            "paper_id": paper_id,
            "analysis_type": "citations",
            "total_found": data.get("total", 0),
            "citations": citations,
        }

        if depth >= 2 and citations:
            # Get citations of top 3 citations
            top_ids = []
            for c in citations[:3]:
                if c.get("paperId"):
                    top_ids.append(c["paperId"])

            second_level = []
            for pid in top_ids:
                try:
                    r2 = await client.get(
                        f"{SEMANTIC_SCHOLAR_API_URL}/paper/{pid}/citations",
                        params={"fields": fields, "limit": 5},
                        headers=headers,
                    )
                    if r2.status_code == 200:
                        d2 = r2.json()
                        for item in d2.get("data", [])[:3]:
                            second_level.append(self._format_paper(item.get("citingPaper", {})))
                except Exception as e:
                    logger.debug(f"Second-level citation fetch failed for {pid}: {e}")

            if second_level:
                result["second_level_citations"] = second_level

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _get_references(
        self, paper_id: str, depth: int, max_results: int, headers: dict[str, str]
    ) -> str:
        """Get papers that the given paper cites."""
        fields = "title,authors,year,citationCount,abstract,url"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/{paper_id}/references",
                params={"fields": fields, "limit": max_results},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        references = []
        for item in data.get("data", []):
            cited_paper = item.get("citedPaper", {})
            references.append(self._format_paper(cited_paper))

        result = {
            "paper_id": paper_id,
            "analysis_type": "references",
            "total_found": data.get("total", 0),
            "references": references,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _get_lineage(
        self, paper_id: str, max_results: int, headers: dict[str, str]
    ) -> str:
        """Trace the method lineage by following references."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # Get the paper itself
            r1 = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/{paper_id}",
                params={"fields": "title,authors,year,abstract,references,citations"},
                headers=headers,
            )
            r1.raise_for_status()
            paper = r1.json()

            # Get direct references (what this paper builds on)
            refs = []
            ref_ids = [r.get("paperId") for r in paper.get("references", [])[:max_results] if r.get("paperId")]
            for rid in ref_ids[:5]:
                try:
                    r2 = await client.get(
                        f"{SEMANTIC_SCHOLAR_API_URL}/paper/{rid}",
                        params={"fields": "title,authors,year,abstract,citationCount"},
                        headers=headers,
                    )
                    if r2.status_code == 200:
                        refs.append(self._format_paper(r2.json()))
                except Exception:
                    pass

        lineage = {
            "paper": self._format_paper(paper),
            "direct_references": refs,
            "lineage_summary": (
                f"'{paper.get('title', 'This paper')}' builds on {len(refs)} key prior works. "
                f"Tracing the reference chain reveals the methodological foundation."
            ),
        }
        return json.dumps(lineage, ensure_ascii=False, indent=2)

    async def _find_key_papers(
        self, topic: str, max_results: int, headers: dict[str, str]
    ) -> str:
        """Find highly-cited papers on a topic."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/search",
                params={
                    "query": topic,
                    "fields": "title,authors,year,abstract,citationCount,url",
                    "limit": max_results,
                },
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        papers = []
        for p in data.get("data", []):
            papers.append(self._format_paper(p))

        # Sort by citation count
        papers.sort(key=lambda x: x.get("citation_count", 0), reverse=True)

        result = {
            "topic": topic,
            "analysis_type": "key_papers",
            "papers": papers,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    @staticmethod
    def _format_paper(paper: dict[str, Any]) -> dict[str, Any]:
        """Normalize paper format from Semantic Scholar."""
        return {
            "title": paper.get("title", ""),
            "authors": [a.get("name", "") for a in paper.get("authors", [])],
            "year": paper.get("year"),
            "abstract": paper.get("abstract", ""),
            "citation_count": paper.get("citationCount", 0),
            "url": paper.get("url", ""),
            "paper_id": paper.get("paperId", ""),
        }
