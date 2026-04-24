"""Research feed service for automatic paper discovery and push."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from nanobot.research.paper_store import PaperStore

ARXIV_API_URL = "https://export.arxiv.org/api/query"


class ResearchFeedService:
    """Service that periodically fetches new papers and pushes them to users."""

    def __init__(
        self,
        paper_store: PaperStore,
        feeds: list[dict[str, Any]],
        feishu_bus: Any | None = None,
    ):
        self.paper_store = paper_store
        self.feeds = feeds
        self.feishu_bus = feishu_bus

    async def check_feeds(self) -> list[dict[str, Any]]:
        """Check all feeds and return new papers to push."""
        all_new_papers: list[dict[str, Any]] = []

        for feed in self.feeds:
            if not feed.get("enabled", True):
                continue

            source = feed.get("source", "arxiv")
            if source != "arxiv":
                logger.warning(f"Feed source '{source}' not yet supported, skipping")
                continue

            try:
                papers = await self._fetch_arxiv(feed)
                for paper in papers:
                    # Deduplicate against paper store
                    existing = None
                    if paper.get("arxiv_id"):
                        existing = self.paper_store.get_paper_by_arxiv(paper["arxiv_id"])
                    if not existing and paper.get("doi"):
                        # Could check by DOI too
                        pass

                    if not existing:
                        all_new_papers.append({
                            "paper": paper,
                            "feed": feed,
                        })
            except Exception as e:
                logger.error(f"Feed check failed for {feed}: {e}")

        return all_new_papers

    async def _fetch_arxiv(self, feed: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch papers from arXiv for a feed configuration."""
        categories = feed.get("categories", [])
        keywords = feed.get("keywords", [])
        max_results = feed.get("max_results", 5)

        # Build query
        cat_query = " OR ".join(f"cat:{c}" for c in categories) if categories else ""
        kw_query = " OR ".join(f'"{k}"' for k in keywords) if keywords else ""

        if cat_query and kw_query:
            search_query = f"({cat_query}) AND ({kw_query})"
        elif cat_query:
            search_query = cat_query
        elif kw_query:
            search_query = kw_query
        else:
            search_query = "all"

        # Sort by submitted date to get newest first
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        import urllib.parse
        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return self._parse_arxiv_xml(response.text)

    @staticmethod
    def _parse_arxiv_xml(xml_text: str) -> list[dict[str, Any]]:
        """Parse arXiv Atom XML."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError:
            return []

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

            id_elem = entry.findtext("atom:id", "", ns)
            if not arxiv_id and "arxiv.org/abs/" in id_elem:
                arxiv_id = id_elem.split("/")[-1]

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.findtext("atom:name", "", ns)
                if name:
                    authors.append(name)

            categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]

            results.append({
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
            })

        return results

    async def push_paper(
        self,
        paper: dict[str, Any],
        feed: dict[str, Any],
        relevance_score: float = 0.0,
    ) -> None:
        """Push a paper notification to the user via Feishu."""
        if not self.feishu_bus:
            logger.warning("No Feishu bus configured, cannot push paper")
            return

        # Store in paper library first
        from nanobot.research.paper_store import Paper
        p = Paper(
            title=paper["title"],
            authors=json.dumps(paper.get("authors", []), ensure_ascii=False),
            abstract=paper.get("abstract", ""),
            arxiv_id=paper.get("arxiv_id", ""),
            doi=paper.get("doi", ""),
            pdf_path=paper.get("pdf_url", ""),
            published_date=paper.get("published", ""),
            source=paper.get("source", "arxiv"),
            reading_status="unread",
        )
        paper_id = self.paper_store.add_paper(p)

        # Build push message as Feishu interactive card
        title = paper["title"]
        authors = ", ".join(paper.get("authors", [])[:3])
        if len(paper.get("authors", [])) > 3:
            authors += " et al."
        abstract_preview = paper.get("abstract", "")[:280]
        if len(paper.get("abstract", "")) > 280:
            abstract_preview += "..."
        
        arxiv_url = paper.get("url", "")
        pdf_url = paper.get("pdf_url", "")
        published = paper.get("published", "")
        categories = ", ".join(paper.get("categories", [])[:3])

        card_json = {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{title}**"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"*{authors}* ｜ {published} ｜ {categories}"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🔑 **摘要：**\n{abstract_preview}"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📄 arXiv 页面"
                            },
                            "type": "primary",
                            "url": arxiv_url
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📥 PDF 下载"
                            },
                            "type": "default",
                            "url": pdf_url
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"Library ID: {paper_id} ｜ 回复 '分析 {paper_id}' 让 NanoScholar 深度解析这篇论文"
                        }
                    ]
                }
            ],
            "header": {
                "template": "blue",
                "title": {
                    "tag": "plain_text",
                    "content": "📄 每日论文推送"
                }
            }
        }

        message = f"🎴CARD:{json.dumps(card_json, ensure_ascii=False)}"

        # Publish via bus
        from nanobot.bus.events import OutboundMessage
        await self.feishu_bus.publish_outbound(
            OutboundMessage(
                channel="feishu",
                chat_id="",  # Will be resolved by channel
                content=message,
            )
        )

        logger.info(f"Pushed paper {paper_id}: {title}")

    def generate_mermaid_graph(
        self,
        central_paper: dict[str, Any],
        references: list[dict[str, Any]],
        citations: list[dict[str, Any]],
    ) -> str:
        """Generate a Mermaid flowchart for citation visualization."""
        lines = ["graph TD"]
        central_id = f"P{hash(central_paper.get('title', '')) % 10000}"
        central_label = central_paper.get("title", "Paper")[:40].replace('"', "'")
        lines.append(f'    {central_id}["{central_label}"]')

        for ref in references[:8]:
            rid = f"R{hash(ref.get('title', '')) % 10000}"
            rlabel = ref.get("title", "")[:40].replace('"', "'")
            lines.append(f'    {rid}["{rlabel}"]')
            lines.append(f"    {rid} --> {central_id}")

        for cit in citations[:8]:
            cid = f"C{hash(cit.get('title', '')) % 10000}"
            clabel = cit.get("title", "")[:40].replace('"', "'")
            lines.append(f'    {cid}["{clabel}"]')
            lines.append(f"    {central_id} --> {cid}")

        return "\n".join(lines)
