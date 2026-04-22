"""Insight generator tool for research literature analysis."""

import json
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.providers.base import LLMProvider
from nanobot.research.insight_generator import InsightGenerator as InsightGeneratorCore
from nanobot.research.paper_store import PaperStore


class InsightGeneratorTool(Tool):
    """Generate literature reviews, identify research gaps, and track trends."""

    name = "insight_generator"
    description = (
        "Generate high-level research insights from collections of papers. "
        "Capabilities: literature review generation, research gap identification, trend tracking, "
        "and next-reading suggestions. "
        "Use this when the user wants to synthesize knowledge from multiple papers, "
        "find what's missing in a research area, or understand how a field is evolving."
    )

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["literature_review", "research_gaps", "track_trends", "suggest_next"],
                "description": "Type of insight to generate.",
            },
            "topic": {
                "type": "string",
                "description": "Research topic or keywords. Used to select papers from the library.",
            },
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Specific paper IDs to analyze. Alternative to topic.",
            },
            "max_papers": {
                "type": "integer",
                "description": "Maximum papers to include in analysis.",
                "default": 10,
                "minimum": 2,
                "maximum": 20,
            },
            "base_paper_id": {
                "type": "integer",
                "description": "For suggest_next: the paper ID to base recommendations on.",
            },
        },
        "required": ["action"],
    }

    def __init__(
        self,
        provider: LLMProvider,
        paper_store: PaperStore,
        model: str | None = None,
    ):
        self.generator = InsightGeneratorCore(
            provider=provider,
            paper_store=paper_store,
            model=model,
        )

    async def execute(
        self,
        action: str,
        topic: str = "",
        paper_ids: list[int] | None = None,
        max_papers: int = 10,
        base_paper_id: int = 0,
    ) -> str:
        if action == "literature_review":
            result = await self.generator.generate_literature_review(
                topic=topic, paper_ids=paper_ids, max_papers=max_papers
            )
        elif action == "research_gaps":
            result = await self.generator.identify_research_gaps(
                topic=topic, paper_ids=paper_ids, max_papers=max_papers
            )
        elif action == "track_trends":
            result = await self.generator.track_trends(
                topic=topic, paper_ids=paper_ids, max_papers=max_papers
            )
        elif action == "suggest_next":
            if not base_paper_id:
                return "Error: base_paper_id is required for suggest_next action."
            result = await self.generator.suggest_next_reading(base_paper_id)
        else:
            return f"Error: Unknown action '{action}'"

        if "error" in result:
            return f"Error: {result['error']}"

        return json.dumps(result, ensure_ascii=False, indent=2)
