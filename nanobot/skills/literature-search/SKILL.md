---
name: literature-search
description: Academic literature search best practices and strategies.
metadata: '{"nanobot": {"always": true}}'
---

# Literature Search Skill

This skill guides you on how to effectively search for academic papers.

## Core Principles

1. **Use English keywords** — Academic databases are primarily English-based. Even for Chinese queries, translate to English for searching.
2. **Start broad, then narrow** — Begin with 2-3 core keywords, then add constraints (year, method, dataset).
3. **Exploit multiple sources** — arXiv, Semantic Scholar, Google Scholar, PubMed each have strengths.

## Keyword Construction

### Basic Rules
- Use **specific technical terms** over general words: "transformer efficiency" beats "fast neural network"
- Include **method + task + dataset** when possible: "LoRA fine-tuning LLaMA CommonsenseQA"
- Use **abbreviations AND full names** in OR queries: "(LLM OR large language model)"

### Advanced arXiv Query Syntax
```
cat:cs.CL AND ("chain of thought" OR CoT) AND NOT survey
```
- `cat:cs.CL` — Computational Linguistics category
- `AND` / `OR` / `AND NOT` — Boolean operators
- `"exact phrase"` — Phrase search
- `au:Smith_J` — Author search

### Example Queries by Intent

| User Intent | Search Query |
|------------|--------------|
| "LLM推理加速" | `cat:cs.CL AND ("inference acceleration" OR "speculative decoding" OR "KV cache" OR "quantization") AND "large language model"` |
| "Transformer效率" | `cat:cs.LG AND ("transformer efficiency" OR "linear attention" OR "flash attention" OR "sparse attention")` |
| "多模态融合" | `cat:cs.CV AND ("multimodal fusion" OR "vision language model" OR "cross-modal")` |
| "图神经网络综述" | `cat:cs.LG AND ("graph neural network" OR GNN) AND (survey OR review)` |

## Search Strategy Workflow

### Step 1: Quick Scan (5 minutes)
- Search with 2-3 core keywords, `max_results=10`
- Read titles and abstracts only
- Goal: understand the terminology landscape

### Step 2: Targeted Search (10 minutes)
- Refine keywords based on Step 1 findings
- Add year constraint if needed: `submittedDate:[20240101 TO 20241231]`
- Search with `max_results=20`
- Identify 3-5 most relevant papers

### Step 3: Snowballing
- For each key paper, use `get_related_papers` or `citation_graph`
- Check references (what they built upon) and citations (who built upon them)
- This often finds the most impactful papers missed by keyword search

## Source-Specific Tips

### arXiv
- **Strengths**: Latest preprints, CS/Physics/Math heavy
- **Best for**: Cutting-edge methods, benchmark papers
- **Tip**: Use `export.arxiv.org` API for structured results; check `announce_type` for updates

### Semantic Scholar
- **Strengths**: Citation counts, influential citations, author disambiguation
- **Best for**: Finding highly-cited foundational papers
- **Tip**: Filter by "highly influential" citations rather than raw count

### Google Scholar
- **Strengths**: Broadest coverage, includes books/theses
- **Best for**: Interdisciplinary topics, finding older foundational work
- **Tip**: Use "Cited by" and "Related articles" features

## Common Pitfalls

- ❌ Using too many AND terms → zero results
- ❌ Searching only in Chinese → misses 90% of literature
- ❌ Ignoring publication year → wasting time on outdated methods
- ❌ Not checking citations → missing follow-up improvements
