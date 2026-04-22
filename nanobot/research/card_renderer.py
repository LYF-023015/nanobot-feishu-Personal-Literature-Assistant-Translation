"""Research card renderer for Feishu interactive messages.

Generates Feishu card JSON (self-built card format) for rich research paper display.
Usage: tools return markdown with a 🎴CARD: prefix, feishu.py detects and renders it.
"""

import json
from typing import Any


def render_paper_card(
    title: str,
    authors: list[str],
    abstract: str,
    arxiv_id: str = "",
    doi: str = "",
    published: str = "",
    citation_count: int = 0,
    reading_status: str = "unread",
    tags: list[str] | None = None,
    summary: str = "",
    methodology: str = "",
    key_findings: list[str] | None = None,
    paper_id: int = 0,
) -> str:
    """Render a rich paper detail card.

    Returns a string starting with 🎴CARD: followed by JSON.
    """
    tags = tags or []
    key_findings = key_findings or []

    # Header color based on reading status
    status_colors = {
        "unread": "blue",
        "reading": "orange",
        "read": "green",
    }
    header_color = status_colors.get(reading_status, "blue")
    status_labels = {"unread": "未读", "reading": "阅读中", "read": "已读"}

    # Build authors text
    authors_text = ", ".join(authors[:4])
    if len(authors) > 4:
        authors_text += f" 等 {len(authors)} 位作者"

    # Abstract preview
    abstract_preview = abstract[:400]
    if len(abstract) > 400:
        abstract_preview += "..."

    # Tags as markdown badges
    tags_md = " ".join(f"`{t}`" for t in tags[:8]) if tags else ""

    # Key findings
    findings_md = ""
    if key_findings:
        findings_md = "\n".join(f"• {f}" for f in key_findings[:5])

    # Actions as text hints (since WebSocket mode can't easily handle callbacks)
    actions_md = ""
    if paper_id:
        actions_md = (
            f"💡 **操作提示**：回复 `分析 {paper_id}` 解析论文，"
            f"`笔记 {paper_id} <内容>` 添加笔记，"
            f"`状态 {paper_id} 已读` 标记阅读状态"
        )

    elements: list[dict[str, Any]] = []

    # Meta info
    meta_parts = []
    if published:
        meta_parts.append(f"📅 {published}")
    if arxiv_id:
        meta_parts.append(f"🆔 arXiv:{arxiv_id}")
    if doi:
        meta_parts.append(f"🔬 DOI:{doi}")
    if citation_count:
        meta_parts.append(f"📊 引用 {citation_count}")
    meta_parts.append(f"🏷️ {status_labels.get(reading_status, reading_status)}")

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": " | ".join(meta_parts)},
    })

    # Divider
    elements.append({"tag": "hr"})

    # Abstract
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**摘要**\n{abstract_preview}"},
    })

    # Summary / Methodology
    if summary:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**核心贡献**\n{summary}"},
        })

    if methodology:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**方法**\n{methodology[:300]}"},
        })

    # Key findings
    if findings_md:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**关键发现**\n{findings_md}"},
        })

    # Tags
    if tags_md:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**标签** {tags_md}"},
        })

    # Divider
    elements.append({"tag": "hr"})

    # Action hints
    if actions_md:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": actions_md},
            "padding": "8px 0 0 0",
        })

    # Buttons for external links
    button_actions: list[dict[str, Any]] = []
    if arxiv_id:
        button_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "查看 arXiv"},
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "type": "default",
        })
        button_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "下载 PDF"},
            "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "type": "default",
        })
    if doi:
        button_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "查看 DOI"},
            "url": f"https://doi.org/{doi}",
            "type": "default",
        })

    if button_actions:
        elements.append({
            "tag": "action",
            "actions": button_actions,
            "padding": "12px 0 0 0",
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title[:100],
            },
            "subtitle": {
                "tag": "plain_text",
                "content": authors_text[:100],
            },
            "template": header_color,
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_search_results_card(
    query: str,
    papers: list[dict[str, Any]],
) -> str:
    """Render a search results list card."""
    elements: list[dict[str, Any]] = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"🔍 **搜索**: `{query}` — 找到 {len(papers)} 篇论文"},
    })
    elements.append({"tag": "hr"})

    for idx, p in enumerate(papers[:10], 1):
        title = p.get("title", "Unknown")
        authors = p.get("authors", [])
        authors_text = ", ".join(authors[:2]) if authors else "Unknown"
        if len(authors) > 2:
            authors_text += " 等"
        arxiv_id = p.get("arxiv_id", "")
        year = p.get("published", "")[:4] if p.get("published") else ""
        citation_count = p.get("citation_count", 0)

        meta = []
        if year:
            meta.append(year)
        if citation_count:
            meta.append(f"引用 {citation_count}")
        if arxiv_id:
            meta.append(f"arXiv:{arxiv_id}")
        meta_text = " | ".join(meta)

        content = f"**{idx}. {title}**\n*{authors_text}*\n{meta_text}"
        if arxiv_id:
            content += f"\n[查看 arXiv](https://arxiv.org/abs/{arxiv_id}) | [PDF](https://arxiv.org/pdf/{arxiv_id}.pdf)"

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": content},
            "padding": "8px 0",
        })
        elements.append({"tag": "hr"})

    if len(papers) > 10:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"... 还有 {len(papers) - 10} 篇结果"},
        })

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "💡 回复 `获取论文 <arXiv ID>` 下载并分析特定论文"},
        "padding": "8px 0 0 0",
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "论文搜索结果"},
            "template": "blue",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_push_card(
    paper: dict[str, Any],
    relevance_score: float = 0.0,
) -> str:
    """Render a daily paper push notification card."""
    title = paper.get("title", "New Paper")
    authors = paper.get("authors", [])
    authors_text = ", ".join(authors[:3]) if authors else "Unknown"
    abstract_preview = paper.get("abstract", "")[:350]
    if len(paper.get("abstract", "")) > 350:
        abstract_preview += "..."
    arxiv_id = paper.get("arxiv_id", "")
    published = paper.get("published", "")
    paper_id = paper.get("paper_id", 0)

    relevance_text = ""
    if relevance_score > 0:
        if relevance_score >= 0.8:
            relevance_text = "🔥 高度相关"
        elif relevance_score >= 0.5:
            relevance_text = "⭐ 较为相关"
        else:
            relevance_text = "📌 可能相关"

    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"📅 {published} {relevance_text}"},
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**摘要**\n{abstract_preview}"},
        },
    ]

    if paper_id:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"💡 回复 `分析 {paper_id}` 自动下载并解析此论文"},
            "padding": "8px 0 0 0",
        })

    button_actions = []
    if arxiv_id:
        button_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "查看 arXiv"},
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "type": "default",
        })
        button_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "下载 PDF"},
            "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "type": "default",
        })

    if button_actions:
        elements.append({
            "tag": "action",
            "actions": button_actions,
            "padding": "12px 0 0 0",
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title[:100]},
            "subtitle": {"tag": "plain_text", "content": authors_text[:100]},
            "template": "orange",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_review_card(
    topic: str,
    review_data: dict[str, Any],
) -> str:
    """Render a literature review result card."""
    elements: list[dict[str, Any]] = []

    summary = review_data.get("summary", "")
    themes = review_data.get("themes", [])
    gaps = review_data.get("gaps_and_opportunities", [])
    contributions = review_data.get("key_contributions", [])

    if summary:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**概述**\n{summary}"},
        })

    if themes:
        elements.append({"tag": "hr"})
        theme_lines = ["**研究主题**"]
        for t in themes:
            theme_lines.append(f"• **{t.get('theme', '')}**: {t.get('description', '')}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(theme_lines)},
        })

    if contributions:
        elements.append({"tag": "hr"})
        contrib_lines = ["**核心贡献**"] + [f"• {c}" for c in contributions[:8]]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(contrib_lines)},
        })

    if gaps:
        elements.append({"tag": "hr"})
        gap_lines = ["**研究空白与机会**"] + [f"• {g}" for g in gaps[:6]]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(gap_lines)},
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"文献综述: {topic[:60]}"},
            "template": "purple",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_citation_graph_card(
    paper_title: str,
    references: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    mermaid_graph: str = "",
) -> str:
    """Render a citation graph visualization card."""
    elements: list[dict[str, Any]] = []

    if references:
        ref_lines = [f"**参考文献 ({len(references)} 篇)**"]
        for r in references[:8]:
            year = r.get("year", "")
            cc = r.get("citation_count", 0)
            meta = " | ".join(filter(None, [str(year), f"引用 {cc}" if cc else ""]))
            ref_lines.append(f"• {r.get('title', '')} ({meta})")
        if len(references) > 8:
            ref_lines.append(f"... 还有 {len(references) - 8} 篇")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(ref_lines)},
        })

    if citations:
        elements.append({"tag": "hr"})
        cit_lines = [f"**被引用 ({len(citations)} 篇)**"]
        for c in citations[:8]:
            year = c.get("year", "")
            cc = c.get("citation_count", 0)
            meta = " | ".join(filter(None, [str(year), f"引用 {cc}" if cc else ""]))
            cit_lines.append(f"• {c.get('title', '')} ({meta})")
        if len(citations) > 8:
            cit_lines.append(f"... 还有 {len(citations) - 8} 篇")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(cit_lines)},
        })

    if mermaid_graph:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**引用关系图**\n```mermaid\n{mermaid_graph}\n```"},
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"引用网络: {paper_title[:60]}"},
            "template": "wathet",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_statistics_card(stats: dict[str, Any]) -> str:
    """Render a reading statistics dashboard card."""
    elements: list[dict[str, Any]] = []

    total = stats.get("total", 0)
    unread = stats.get("unread", 0)
    reading = stats.get("reading", 0)
    read = stats.get("read", 0)
    recent = stats.get("recent_7d", 0)

    # Summary stats
    stats_md = (
        f"📚 **总论文数**: {total}\n"
        f"📖 **已读**: {read} | 🔄 **阅读中**: {reading} | 📑 **未读**: {unread}\n"
        f"📈 **最近 7 天新增**: {recent}"
    )
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": stats_md},
    })

    # Reading progress bar visualization
    if total > 0:
        read_pct = round(read / total * 100, 1)
        reading_pct = round(reading / total * 100, 1)
        unread_pct = round(unread / total * 100, 1)
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**阅读进度**: ✅ {read_pct}% | 🔄 {reading_pct}% | 📑 {unread_pct}%"},
        })

    elements.append({"tag": "hr"})

    # Top sources
    sources = stats.get("top_sources", [])
    if sources:
        source_lines = ["**主要来源**"]
        for s in sources:
            source_lines.append(f"• {s['source']}: {s['count']} 篇")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(source_lines)},
        })

    # Top tags
    tags = stats.get("top_tags", [])
    if tags:
        if sources:
            elements.append({"tag": "hr"})
        tag_lines = ["**热门标签**"] + [f"`{t['tag']}` ({t['count']})" for t in tags]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": " ".join(tag_lines)},
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 阅读统计"},
            "template": "green",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_compare_card(
    paper_a: dict[str, Any],
    paper_b: dict[str, Any],
) -> str:
    """Render a side-by-side paper comparison card."""
    elements: list[dict[str, Any]] = []

    def _fmt_paper(p: dict[str, Any]) -> str:
        authors = p.get("authors", [])
        authors_text = ", ".join(authors[:3]) if authors else "Unknown"
        year = p.get("published", "")[:4] if p.get("published") else ""
        cc = p.get("citation_count", 0)
        meta = " | ".join(filter(None, [authors_text, str(year), f"引用 {cc}" if cc else ""]))
        summary = p.get("extracted_summary", p.get("summary", ""))
        method = p.get("methodology", "")
        findings = p.get("key_findings", [])
        findings_text = "\n".join(f"• {f}" for f in findings[:3]) if findings else ""

        parts = [f"**{p.get('title', 'Unknown')}**", f"*{meta}*"]
        if summary:
            parts.append(f"**核心贡献**: {summary}")
        if method:
            parts.append(f"**方法**: {method[:150]}")
        if findings_text:
            parts.append(f"**关键发现**:\n{findings_text}")
        return "\n".join(parts)

    # Use a 2-column layout with div blocks
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**📄 论文 A**"},
        "padding": "8px 0",
    })
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": _fmt_paper(paper_a)},
        "padding": "8px",
        "border": {"color": "#E0E0E0", "width": "1px", "style": "solid"},
    })

    elements.append({"tag": "hr"})

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**📄 论文 B**"},
        "padding": "8px 0",
    })
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": _fmt_paper(paper_b)},
        "padding": "8px",
        "border": {"color": "#E0E0E0", "width": "1px", "style": "solid"},
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "论文对比"},
            "template": "indigo",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_topic_card(
    topic: dict[str, Any],
    papers: list[dict[str, Any]],
) -> str:
    """Render a research topic overview card."""
    elements: list[dict[str, Any]] = []

    name = topic.get("name", "Research Topic")
    desc = topic.get("description", "")
    keywords = topic.get("keywords", "")

    header_md = f"**{name}**"
    if desc:
        header_md += f"\n{desc}"
    if keywords:
        header_md += f"\n🏷️ {keywords}"

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": header_md},
    })
    elements.append({"tag": "hr"})

    if papers:
        paper_lines = [f"**关联论文 ({len(papers)} 篇)**"]
        for p in papers[:8]:
            status_emoji = {"unread": "📑", "reading": "🔄", "read": "✅"}.get(p.get("status", ""), "📑")
            paper_lines.append(f"{status_emoji} {p.get('title', '')}")
        if len(papers) > 8:
            paper_lines.append(f"... 还有 {len(papers) - 8} 篇")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(paper_lines)},
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": name[:60]},
            "template": "blue",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"


def render_daily_digest_card(
    papers: list[dict[str, Any]],
    date: str = "",
) -> str:
    """Render a daily paper digest card with multiple papers."""
    elements: list[dict[str, Any]] = []

    header = f"📰 **每日论文推送** {date}"
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": header},
    })
    elements.append({"tag": "hr"})

    for idx, p in enumerate(papers[:5], 1):
        title = p.get("title", "")
        authors = p.get("authors", [])
        authors_text = ", ".join(authors[:2]) if authors else ""
        arxiv_id = p.get("arxiv_id", "")
        abstract = p.get("abstract", "")[:200]
        if len(p.get("abstract", "")) > 200:
            abstract += "..."

        content = f"**{idx}. {title}**\n*{authors_text}*\n{abstract}"
        if arxiv_id:
            content += f"\n[arXiv](https://arxiv.org/abs/{arxiv_id}) | [PDF](https://arxiv.org/pdf/{arxiv_id}.pdf)"

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": content},
            "padding": "8px 0",
        })
        elements.append({"tag": "hr"})

    if len(papers) > 5:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"... 还有 {len(papers) - 5} 篇论文"},
        })

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "💡 回复 `分析 <论文ID>` 解析感兴趣的论文"},
        "padding": "8px 0 0 0",
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"每日论文推送 ({len(papers)} 篇)"},
            "template": "orange",
        },
        "elements": elements,
    }

    return f"🎴CARD:{json.dumps(card, ensure_ascii=False)}"
