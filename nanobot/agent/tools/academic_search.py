"""Academic search tool for finding research papers."""

import json
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool


ARXIV_API_URL = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1"


class AcademicSearchTool(Tool):
    """Search academic papers from arXiv and Semantic Scholar."""

    name = "academic_search"
    description = (
        "Search for academic papers from arXiv and Semantic Scholar. "
        "Returns paper metadata including title, authors, abstract, PDF link, and citation count. "
        "Use this when the user wants to find papers on a specific topic, author, or keyword."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string. Can include keywords, phrases, or author names.",
            },
            "source": {
                "type": "string",
                "enum": ["arxiv", "semantic_scholar", "all"],
                "description": "Which source to search. Defaults to arxiv.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1-20).",
                "minimum": 1,
                "maximum": 20,
                "default": 5,
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                "description": "Sort order. relevance is default.",
                "default": "relevance",
            },
            "arxiv_category": {
                "type": "string",
                "description": "Optional arXiv category filter, e.g. cs.AI, cs.CL, cs.LG.",
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        default_sources: list[str] | None = None,
        arxiv_categories: list[str] | None = None,
        semantic_scholar_api_key: str = "",
        max_results: int = 10,
    ):
        self.default_sources = default_sources or ["arxiv"]
        self.arxiv_categories = arxiv_categories or []
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.default_max_results = max_results

    async def execute(
        self,
        query: str,
        source: str = "arxiv",
        max_results: int = 5,
        sort_by: str = "relevance",
        arxiv_category: str = "",
    ) -> str:
        max_results = min(max_results, 20)
        results: list[dict[str, Any]] = []

        if source in ("arxiv", "all"):
            try:
                arxiv_results = await self._search_arxiv(
                    query, max_results, sort_by, arxiv_category
                )
                results.extend(arxiv_results)
            except Exception as e:
                logger.warning(f"arXiv search failed: {e}")

        if source in ("semantic_scholar", "all") and len(results) < max_results:
            try:
                ss_results = await self._search_semantic_scholar(
                    query, max_results - len(results)
                )
                results.extend(ss_results)
            except Exception as e:
                logger.warning(f"Semantic Scholar search failed: {e}")

        if not results:
            return "No papers found for this query. Try broadening your search terms."

        # Deduplicate by title similarity (simple exact match for now)
        seen_titles = set()
        unique_results = []
        for r in results:
            key = r.get("title", "").lower().strip()
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique_results.append(r)

        return json.dumps(unique_results[:max_results], ensure_ascii=False, indent=2)

    async def _search_arxiv(
        self,
        query: str,
        max_results: int,
        sort_by: str,
        arxiv_category: str = "",
    ) -> list[dict[str, Any]]:
        """Search arXiv using the public API."""
        search_query = query
        if arxiv_category:
            search_query = f"cat:{arxiv_category} AND ({query})"
        elif self.arxiv_categories:
            cats = " OR ".join(f"cat:{c}" for c in self.arxiv_categories)
            search_query = f"({cats}) AND ({query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }

        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return self._parse_arxiv_xml(response.text)

    def _parse_arxiv_xml(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse arXiv Atom XML response."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError:
            return []

        # arXiv uses Atom namespace
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        results = []

        for entry in entries:
            title = entry.findtext("atom:title", "", ns).replace("\n", " ").strip()
            summary = entry.findtext("atom:summary", "", ns).strip()
            published = entry.findtext("atom:published", "", ns)
            arxiv_id = ""
            pdf_url = ""

            for link in entry.findall("atom:link", ns):
                href = link.get("href", "")
                rel = link.get("rel", "")
                if "title" in link.attrib and link.attrib["title"] == "pdf":
                    pdf_url = href
                elif rel == "alternate" and "arxiv.org/abs/" in href:
                    arxiv_id = href.split("/")[-1]

            # Extract arxiv ID from id element if not found
            id_elem = entry.findtext("atom:id", "", ns)
            if not arxiv_id and "arxiv.org/abs/" in id_elem:
                arxiv_id = id_elem.split("/")[-1]

            # Authors
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.findtext("atom:name", "", ns)
                if name:
                    authors.append(name)

            # Categories
            categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]

            results.append(
                {
                    "title": title,
                    "authors": authors,
                    "abstract": summary,
                    "arxiv_id": arxiv_id,
                    "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    "published": published[:10] if published else "",
                    "source": "arxiv",
                    "categories": categories,
                    "doi": "",
                    "citation_count": 0,
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                }
            )

        return results

    async def _search_semantic_scholar(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Search Semantic Scholar."""
        headers = {}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key

        params = {
            "query": query,
            "fields": "title,authors,year,abstract,openAccessPdf,citationCount,externalIds,url",
            "limit": max_results,
        }

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/search",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for paper in data.get("data", []):
            authors = [a.get("name", "") for a in paper.get("authors", [])]
            pdf_url = ""
            oa = paper.get("openAccessPdf")
            if oa:
                pdf_url = oa.get("url", "")

            ext_ids = paper.get("externalIds", {})
            arxiv_id = ext_ids.get("ArXiv", "")
            doi = ext_ids.get("DOI", "")

            results.append(
                {
                    "title": paper.get("title", ""),
                    "authors": authors,
                    "abstract": paper.get("abstract", ""),
                    "arxiv_id": arxiv_id,
                    "doi": doi,
                    "pdf_url": pdf_url,
                    "published": str(paper.get("year", "")),
                    "source": "semantic_scholar",
                    "categories": [],
                    "citation_count": paper.get("citationCount", 0),
                    "url": paper.get("url", ""),
                }
            )

        return results


class GetPaperByArxivTool(Tool):
    """Fetch paper metadata by arXiv ID."""

    name = "get_paper_by_arxiv"
    description = (
        "Fetch detailed paper metadata from arXiv by its ID. "
        "Use this when the user provides an arXiv link or ID like 2401.12345."
    )

    parameters = {
        "type": "object",
        "properties": {
            "arxiv_id": {
                "type": "string",
                "description": "The arXiv ID, e.g. '2401.12345' or 'hep-th/9901001'.",
            },
        },
        "required": ["arxiv_id"],
    }

    async def execute(self, arxiv_id: str) -> str:
        # Clean the ID
        arxiv_id = arxiv_id.strip()
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.split("/")[-1]
        if "arxiv.org/abs/" in arxiv_id:
            arxiv_id = arxiv_id.split("/")[-1]

        url = f"{ARXIV_API_URL}?id_list={arxiv_id}"

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        tool = AcademicSearchTool()
        results = tool._parse_arxiv_xml(response.text)

        if not results:
            return f"Paper with arXiv ID '{arxiv_id}' not found."

        return json.dumps(results[0], ensure_ascii=False, indent=2)


class GetRelatedPapersTool(Tool):
    """Find related papers using Semantic Scholar."""

    name = "get_related_papers"
    description = (
        "Find papers related to a given paper using Semantic Scholar. "
        "Requires either arxiv_id or doi."
    )

    parameters = {
        "type": "object",
        "properties": {
            "arxiv_id": {
                "type": "string",
                "description": "arXiv ID of the paper.",
            },
            "doi": {
                "type": "string",
                "description": "DOI of the paper.",
            },
            "max_results": {
                "type": "integer",
                "description": "Max related papers to return.",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": [],
    }

    def __init__(self, semantic_scholar_api_key: str = ""):
        self.api_key = semantic_scholar_api_key

    async def execute(
        self,
        arxiv_id: str = "",
        doi: str = "",
        max_results: int = 5,
    ) -> str:
        if not arxiv_id and not doi:
            return "Error: Please provide either arxiv_id or doi."

        paper_id = f"ARXIV:{arxiv_id}" if arxiv_id else f"DOI:{doi}"
        headers = {"x-api-key": self.api_key} if self.api_key else {}

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(
                f"{SEMANTIC_SCHOLAR_API_URL}/paper/{paper_id}/related",
                params={"fields": "title,authors,year,abstract,url", "limit": max_results},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        papers = []
        for p in data.get("data", []):
            papers.append(
                {
                    "title": p.get("title", ""),
                    "authors": [a.get("name", "") for a in p.get("authors", [])],
                    "year": p.get("year"),
                    "abstract": p.get("abstract", ""),
                    "url": p.get("url", ""),
                }
            )

        return json.dumps(papers, ensure_ascii=False, indent=2)
