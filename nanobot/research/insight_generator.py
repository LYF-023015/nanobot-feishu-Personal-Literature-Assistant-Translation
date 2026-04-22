"""Insight generator for research literature analysis."""

import json
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider
from nanobot.research.paper_store import PaperStore


LITERATURE_REVIEW_PROMPT = """You are an expert research analyst. Generate a structured literature review based on the following papers.

Output strictly as a JSON object with this structure:
{
  "title": "Literature Review: [Topic]",
  "summary": "2-3 sentence overview of the field based on these papers",
  "themes": [
    {
      "theme": "Theme name",
      "description": "What this theme covers",
      "papers": ["paper_id_or_title_1", "paper_id_or_title_2"]
    }
  ],
  "comparative_analysis": [
    {
      "aspect": "Methodology / Dataset / Metric / etc.",
      "comparison": "How different papers approach this aspect"
    }
  ],
  "key_contributions": ["contribution 1", "contribution 2", ...],
  "gaps_and_opportunities": ["gap 1", "gap 2", ...],
  "future_directions": ["direction 1", "direction 2", ...]
}

Rules:
- Be specific and cite paper titles or IDs when making claims
- Identify 2-4 distinct research themes
- Comparative analysis should highlight methodological differences
- Gaps should be genuine research opportunities, not generic statements
- Output JSON only, no markdown formatting

Papers:
{papers_text}
"""

RESEARCH_GAP_PROMPT = """You are a critical research analyst. Based on the following papers, identify research gaps and unexplored opportunities.

Output strictly as a JSON object:
{
  "analyzed_papers_count": N,
  "identified_gaps": [
    {
      "gap": "Clear description of the gap",
      "evidence": "Why this is a gap based on the papers",
      "potential_approach": "How one might address this gap",
      "impact": "High/Medium/Low"
    }
  ],
  "underexplored_areas": ["area 1", "area 2", ...],
  "methodological_limitations": ["limitation 1", ...],
  "recommended_next_steps": ["step 1", "step 2", ...]
}

Rules:
- Gaps must be specific and actionable, not vague "more research is needed"
- Reference specific papers to justify why something is a gap
- Consider: methodology gaps, dataset gaps, evaluation gaps, application gaps
- Output JSON only

Papers:
{papers_text}
"""

TREND_TRACKING_PROMPT = """Analyze the research trends in the following papers, organized by time.

Output strictly as a JSON object:
{
  "time_range": "analyzed period",
  "evolution_summary": "How the field has evolved",
  "emerging_themes": ["theme 1", ...],
  "declining_themes": ["theme 1", ...],
  "methodology_shifts": ["shift 1", ...],
  "performance_trends": "How results have improved over time",
  "predictions": ["prediction 1", ...]
}

Rules:
- Identify clear temporal patterns
- Note when key methodologies were introduced
- Track performance improvements if metrics are available
- Output JSON only

Papers:
{papers_text}
"""


class InsightGenerator:
    """Generate insights from collections of papers using LLM."""

    def __init__(
        self,
        provider: LLMProvider,
        paper_store: PaperStore,
        model: str | None = None,
    ):
        self.provider = provider
        self.paper_store = paper_store
        self.model = model

    async def generate_literature_review(
        self,
        topic: str = "",
        paper_ids: list[int] | None = None,
        max_papers: int = 10,
    ) -> dict[str, Any]:
        """Generate a literature review from papers."""
        papers = await self._get_papers(topic, paper_ids, max_papers)
        if not papers:
            return {"error": "No papers found for review generation."}

        papers_text = self._format_papers_for_prompt(papers)
        prompt = LITERATURE_REVIEW_PROMPT.format(papers_text=papers_text)

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are an expert literature review writer. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Literature review generation failed: {e}")
            return {"error": str(e)}

        return self._parse_json_response(response.content or "")

    async def identify_research_gaps(
        self,
        topic: str = "",
        paper_ids: list[int] | None = None,
        max_papers: int = 10,
    ) -> dict[str, Any]:
        """Identify research gaps from papers."""
        papers = await self._get_papers(topic, paper_ids, max_papers)
        if not papers:
            return {"error": "No papers found for gap analysis."}

        papers_text = self._format_papers_for_prompt(papers)
        prompt = RESEARCH_GAP_PROMPT.format(papers_text=papers_text)

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a critical research analyst. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Gap analysis failed: {e}")
            return {"error": str(e)}

        return self._parse_json_response(response.content or "")

    async def track_trends(
        self,
        topic: str = "",
        paper_ids: list[int] | None = None,
        time_range: str = "6m",
        max_papers: int = 15,
    ) -> dict[str, Any]:
        """Track research trends over time."""
        papers = await self._get_papers(topic, paper_ids, max_papers)
        if not papers:
            return {"error": "No papers found for trend analysis."}

        # Sort by published date
        papers.sort(key=lambda p: p.published_date or "", reverse=True)

        papers_text = self._format_papers_for_prompt(papers)
        prompt = TREND_TRACKING_PROMPT.format(papers_text=papers_text)

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a research trends analyst. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Trend tracking failed: {e}")
            return {"error": str(e)}

        return self._parse_json_response(response.content or "")

    async def suggest_next_reading(self, paper_id: int) -> dict[str, Any]:
        """Suggest next papers to read based on a given paper."""
        paper = self.paper_store.get_paper(paper_id)
        if not paper:
            return {"error": f"Paper {paper_id} not found."}

        # Find papers with similar tags or in the same topic
        tags = self.paper_store.get_tags(paper_id)
        related = []

        # Search by tags
        for tag in tags[:3]:
            related.extend(self.paper_store.list_papers(tag=tag, limit=5))

        # Deduplicate and remove self
        seen = {paper_id}
        unique_related = []
        for p in related:
            if p.id not in seen:
                seen.add(p.id)
                unique_related.append(p)

        # If no related papers found by tags, get recent unread papers
        if not unique_related:
            unique_related = self.paper_store.list_papers(status="unread", limit=5)

        suggestions = []
        for p in unique_related[:5]:
            suggestions.append({
                "id": p.id,
                "title": p.title,
                "reason": f"Related to '{paper.title}' through shared research area",
            })

        return {
            "based_on": {"id": paper.id, "title": paper.title},
            "suggestions": suggestions,
        }

    async def _get_papers(
        self,
        topic: str = "",
        paper_ids: list[int] | None = None,
        max_papers: int = 10,
    ) -> list[Any]:
        """Get papers by topic or IDs."""
        if paper_ids:
            papers = []
            for pid in paper_ids:
                p = self.paper_store.get_paper(pid)
                if p:
                    papers.append(p)
            return papers

        if topic:
            # Try topic name match first
            topics = self.paper_store.list_topics()
            matching_topic = None
            for t in topics:
                if topic.lower() in t.name.lower():
                    matching_topic = t
                    break

            if matching_topic:
                return self.paper_store.get_papers_by_topic(matching_topic.topic_id, limit=max_papers)

            # Fallback to text search
            return self.paper_store.list_papers(search=topic, limit=max_papers)

        # Default: return recent papers
        return self.paper_store.list_papers(limit=max_papers)

    @staticmethod
    def _format_papers_for_prompt(papers: list[Any]) -> str:
        """Format papers for LLM prompt."""
        sections = []
        for idx, p in enumerate(papers, 1):
            authors = []
            try:
                authors = json.loads(p.authors) if p.authors else []
            except json.JSONDecodeError:
                authors = [p.authors]

            findings = []
            try:
                findings = json.loads(p.key_findings) if p.key_findings else []
            except json.JSONDecodeError:
                findings = [p.key_findings]

            section = f"""--- Paper {idx}: {p.title} ---
ID: {p.id}
arXiv: {p.arxiv_id}
Authors: {', '.join(authors[:5])}
Published: {p.published_date}
Status: {p.reading_status}

Abstract:
{p.abstract[:800]}

Summary: {p.extracted_summary}
Methodology: {p.methodology}
Key Findings: {', '.join(findings[:5])}
Limitations: {p.limitations}
Future Work: {p.future_work}
"""
            sections.append(section)

        return "\n\n".join(sections)

    @staticmethod
    def _parse_json_response(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {"error": "Failed to parse LLM response", "raw": text[:500]}
