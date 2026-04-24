---
name: research-tracking
description: Research direction tracking, trend discovery, and author monitoring.
metadata: '{"nanobot": {"always": false}}'
---

# Research Tracking Skill

This skill helps you monitor research directions, discover emerging trends, and track influential authors.

## When to Use This Skill

Activate when the user asks for:
- "最近 XXX 有什么新进展？"
- "帮我追踪一下 XXX 方向"
- "XXX 领域现在最火的是什么？"
- "XXX 团队最近在做什么？"
- "有没有什么跨学科的机会？"

## Trend Discovery Methods

### Method 1: Keyword Frequency Analysis
Track which keywords are appearing more frequently in recent papers:
1. Search for papers in the last 6 months on arXiv
2. Extract key terms from titles and abstracts
3. Compare with 1-2 years ago to identify rising terms

**Example**: If "speculative decoding" appears in 5% of LLM inference papers in 2024 vs. 0% in 2023, it's an emerging trend.

### Method 2: Citation Velocity
Papers gaining citations rapidly (relative to their age) indicate hot topics:
- Use Semantic Scholar API to get citation counts and velocity
- Compare across subfields

### Method 3: Conference Proceedings Scan
Top conference acceptance patterns reveal trends:
- NeurIPS/ICML/ICLR: What topics have dedicated workshops?
- ACL/EMNLP: What shared tasks are new this year?
- CVPR/ICCV/ECCV: What challenges are being organized?

### Method 4: Cross-Pollination Detection
Breakthroughs often come from borrowing ideas across fields:
- Look for papers combining previously separate areas
- Example: "Transformer + graph neural networks" → Graph Transformers
- Example: "Diffusion models + protein design" → new bio-AI intersection

## Author Tracking Strategy

### Identifying Key Authors
1. **Pioneers**: First paper on the topic, highly cited
2. **Prolific contributors**: 3+ papers on the topic in recent years
3. **Influential critics**: Papers that spark debate or correction

### Tracking Workflow
1. Use `academic_search` with `au:AuthorName` to find their recent papers
2. Use `get_related_papers` on their most influential work
3. Check their collaborators (co-authors) for related work

### Author Alert Setup
Guide the user to set up `research_feed` in config:
```json
{
  "research": {
    "research_feed": {
      "enabled": true,
      "feeds": [
        {
          "source": "arxiv",
          "categories": ["cs.CL", "cs.LG"],
          "keywords": ["your keyword 1", "your keyword 2"],
          "schedule": "0 8 * * *",
          "max_results": 5,
          "notify_channel": "feishu"
        }
      ]
    }
  }
}
```

## Trend Report Format

When reporting trends to the user, use this structure:

```markdown
# 🔥 [Topic] 最新趋势报告

## 热门方向
1. **[Trend Name]** — [Brief description]
   - 代表论文: [Paper 1], [Paper 2]
   - 热度指标: [Citations, frequency, etc.]

2. **[Trend Name]** — ...

## 值得关注的论文
| 论文 | 作者 | 核心创新 | 为什么重要 |
|------|------|---------|-----------|
| ...  | ...  | ...     | ...       |

## 新兴交叉领域
- **[Intersection A + B]** — [Description and potential]

## 建议行动
1. [具体建议：阅读某篇论文、关注某个作者、尝试某个方法]
```

## Research Profile Maintenance

If `memory/research_profile.md` exists:
- Update it with newly discovered keywords and authors
- Mark topics that are becoming less relevant
- Add new research questions that emerge from trend analysis

## Proactive Tracking Tasks

You can suggest adding these to `HEARTBEAT.md`:
- Weekly arXiv scan for top keywords
- Monthly citation velocity check for tracked papers
- Quarterly trend summary report
