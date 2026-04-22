"""Paper analyzer tool for structured extraction from research papers."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.providers.base import LLMProvider
from nanobot.research.paper_store import PaperStore


ANALYSIS_PROMPT = """You are an expert research assistant. Analyze the following research paper text and extract structured information.

Output strictly as a JSON object with this structure:
{
  "summary": "One-sentence core contribution (max 150 chars)",
  "problem": "Research background and problem definition",
  "methodology": "Core methodology and technical approach",
  "experiments": "Experimental setup, datasets, and metrics",
  "key_findings": ["finding 1", "finding 2", ...],
  "limitations": "Acknowledged limitations from the paper",
  "future_work": "Suggested future directions",
  "tags": ["tag1", "tag2", ...]
}

Rules:
- Be concise but technically accurate
- Key findings should be specific, not generic
- Tags should be lowercase, domain-specific keywords (3-8 tags)
- If the text is truncated or incomplete, note this in your analysis
- Output JSON only, no markdown formatting

Paper text:
---
{text}
---
"""

COMPARE_PROMPT = """Compare the following research papers and identify their relationships, differences, and complementary aspects.

Output strictly as a JSON object:
{
  "comparison_summary": "Overall comparison (2-3 sentences)",
  "commonalities": ["shared aspect 1", ...],
  "differences": [
    {"aspect": "methodology", "paper_a": "...", "paper_b": "..."},
    ...
  ],
  "complementary": "How these papers could complement each other",
  "recommendation": "Which paper to read first and why"
}

Papers:
{papers_text}

Output JSON only, no markdown formatting.
"""


class PaperAnalyzerTool(Tool):
    """Analyze research papers using LLM to extract structured insights."""

    name = "paper_analyzer"
    description = (
        "Analyze a research paper and extract structured information: summary, methodology, "
        "key findings, limitations, and future work. Also supports comparing multiple papers. "
        "Use this after parsing a PDF to generate a structured analysis that gets stored in the paper library."
    )

    parameters = {
        "type": "object",
        "properties": {
            "paper_id": {
                "type": "integer",
                "description": "ID of the paper in the paper store. Required for storing results.",
            },
            "text": {
                "type": "string",
                "description": "The paper text content (e.g. from MinerU parsing). If omitted, will use stored paper text.",
            },
            "analysis_type": {
                "type": "string",
                "enum": ["full", "methodology_only", "compare"],
                "description": "Type of analysis. 'full' = complete structured extraction. 'methodology_only' = extract just methods. 'compare' = compare multiple papers.",
                "default": "full",
            },
            "compare_paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "For compare mode: list of paper IDs to compare.",
            },
        },
        "required": ["paper_id"],
    }

    def __init__(
        self,
        provider: LLMProvider,
        paper_store: PaperStore,
        model: str | None = None,
    ):
        self.provider = provider
        self.paper_store = paper_store
        self.model = model

    async def execute(
        self,
        paper_id: int,
        text: str = "",
        analysis_type: str = "full",
        compare_paper_ids: list[int] | None = None,
    ) -> str:
        if analysis_type == "compare":
            return await self._compare_papers(paper_id, compare_paper_ids or [])

        paper = self.paper_store.get_paper(paper_id)
        if not paper:
            return f"Error: Paper {paper_id} not found in library."

        # Use provided text or fall back to trying to read stored content
        content = text
        if not content and paper.pdf_path:
            pdf_path = Path(paper.pdf_path)
            # Try to find MinerU output
            if pdf_path.exists() and pdf_path.is_dir():
                md_file = pdf_path / "full.md"
                if md_file.exists():
                    content = md_file.read_text(encoding="utf-8", errors="replace")
            elif pdf_path.exists() and pdf_path.suffix == ".md":
                content = pdf_path.read_text(encoding="utf-8", errors="replace")

        if not content or len(content.strip()) < 200:
            return (
                f"Error: No analyzable text found for paper {paper_id}. "
                "Please parse the PDF first using parse_pdf_mineru and provide the text."
            )

        # Truncate if too long (save tokens & reduce latency)
        max_chars = 8000
        if len(content) > max_chars:
            # Keep first 4000 + last 4000 to preserve intro and conclusion
            content = content[:4000] + "\n\n[... middle section truncated ...]\n\n" + content[-4000:]

        prompt = ANALYSIS_PROMPT.format(text=content)
        if analysis_type == "methodology_only":
            prompt = prompt.replace(
                "extract structured information",
                "extract ONLY the methodology and technical approach",
            )

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a precise research paper analyst. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=2048,
                temperature=0.2,
            )
        except Exception as e:
            logger.error(f"LLM analysis failed for paper {paper_id}: {e}")
            return f"Error: LLM analysis failed: {str(e)}"

        raw = response.content or ""
        analysis = self._parse_json_response(raw)
        if not isinstance(analysis, dict):
            return f"Error: Failed to parse LLM response. Raw output:\n{raw[:500]}"

        # Store results
        key_findings = analysis.get("key_findings", [])
        findings_json = json.dumps(key_findings, ensure_ascii=False) if isinstance(key_findings, list) else str(key_findings)

        self.paper_store.update_analysis(
            paper_id=paper_id,
            summary=analysis.get("summary", ""),
            methodology=analysis.get("methodology", ""),
            key_findings=findings_json,
            limitations=analysis.get("limitations", ""),
            future_work=analysis.get("future_work", ""),
        )

        # Auto-extract tags
        tags = analysis.get("tags", [])
        if tags:
            self.paper_store.add_tags(paper_id, tags, auto=True)

        # Update reading status to 'read'
        self.paper_store.update_reading_status(paper_id, "read")

        result = {
            "paper_id": paper_id,
            "title": paper.title,
            "analysis": analysis,
            "stored": True,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _compare_papers(self, base_paper_id: int, other_ids: list[int]) -> str:
        papers = []
        for pid in [base_paper_id] + other_ids:
            p = self.paper_store.get_paper(pid)
            if not p:
                return f"Error: Paper {pid} not found."
            papers.append(p)

        papers_text = ""
        for idx, p in enumerate(papers, 1):
            papers_text += f"\n--- Paper {idx}: {p.title} ---\n"
            papers_text += f"Summary: {p.extracted_summary}\n"
            papers_text += f"Methodology: {p.methodology}\n"
            papers_text += f"Key findings: {p.key_findings}\n"

        prompt = COMPARE_PROMPT.format(papers_text=papers_text)

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a research comparison expert. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=2048,
                temperature=0.2,
            )
        except Exception as e:
            return f"Error: Comparison failed: {str(e)}"

        raw = response.content or ""
        result = self._parse_json_response(raw)
        if not isinstance(result, dict):
            return f"Error: Failed to parse comparison. Raw:\n{raw[:500]}"

        return json.dumps(result, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_json_response(text: str) -> Any:
        """Extract JSON from LLM response, handling markdown fences."""
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
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return None
