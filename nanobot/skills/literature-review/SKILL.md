---
name: literature-review
description: Systematic literature review methodology and best practices.
metadata: '{"nanobot": {"always": false}}'
---

# Literature Review Skill

This skill guides you through conducting a systematic literature review on a given topic.

## When to Use This Skill

Activate when the user asks for:
- "帮我做一个 XXX 的综述"
- "梳理一下 XXX 方向的发展"
- "总结一下 XXX 领域的关键工作"
- "对比这几篇论文"
- "这个方向的研究脉络是什么"

## The SLR Workflow

### Phase 1: Scope Definition (与用户确认)

**Research Question Formulation**
Use PICO framework for clinical/empirical topics:
- **P**opulation: What domain/system?
- **I**ntervention: What method/approach?
- **C**omparison: Compared to what baseline?
- **O**utcome: What metrics/results?

Or use simpler framework for methods/topics:
- What is the core problem?
- What are the main approaches?
- What are the evaluation benchmarks?
- What are the open challenges?

**Inclusion/Exclusion Criteria**
Define BEFORE searching:
- Date range (e.g., 2020-2025)
- Publication venues (e.g., top conferences only)
- Paper types (empirical vs. theoretical vs. survey)
- Language (English)

### Phase 2: Systematic Search

**Multi-Source Search Strategy**
1. **Keyword-based search** on arXiv (use `academic_search`)
2. **Seed paper snowballing**: Start with 2-3 known key papers, use `citation_graph` to find ancestors and descendants
3. **Author tracking**: Identify prolific authors in the area, search their recent work
4. **Venue filtering**: Check recent proceedings of relevant conferences

**Search Iteration**
- Round 1: Broad search → collect candidate papers
- Round 2: Read abstracts → apply inclusion criteria → keep relevant papers
- Round 3: Full-text reading → extract key information

### Phase 3: Information Extraction

For each included paper, extract:

```markdown
### Paper N
- **Citation**: [Author et al., Year]
- **Problem**: [What problem does it solve?]
- **Approach**: [Method in 1-2 sentences]
- **Key Result**: [Main finding with numbers]
- **Relation to others**: [How it compares to prior work]
```

### Phase 4: Synthesis & Taxonomy

**Build a Taxonomy**
Organize papers by:
- **Method type**: e.g., "基于微调的方法", "基于提示的方法", "基于检索的方法"
- **Problem dimension**: e.g., "效率优化", "效果提升", "可解释性"
- **Timeline**: Chronological evolution

**Identify Patterns**
- **Convergence**: Are different approaches converging on similar solutions?
- **Divergence**: Are there competing paradigms?
- **Gaps**: What important problems are understudied?

**Generate Insights**
Use `insight_generator` tool if available, or manually synthesize:
- What is the state-of-the-art?
- What are the trade-offs between approaches?
- What are the most promising future directions?

### Phase 5: Output Format

```markdown
# Literature Review: [Topic]

## 1. 研究背景与问题定义
[Why this topic matters, formal problem statement]

## 2. 方法分类与演进
### 2.1 [Category A]
- [Paper 1]: [One-line summary]
- [Paper 2]: [One-line summary]
### 2.2 [Category B]
...

## 3. 关键对比
| Method | Key Idea | Strength | Weakness | Best Result |
|--------|----------|----------|----------|-------------|
| ...    | ...      | ...      | ...      | ...         |

## 4. 开放问题与未来方向
1. [Open problem 1]
2. [Open problem 2]

## 5. 推荐阅读清单
[Top 5-10 papers, ordered by importance for newcomers]
```

## Quality Control

- **Coverage check**: Did you find the seminal/foundational papers?
- **Balance check**: Are you over-representing one approach?
- **Recency check**: Are recent important papers included (last 1-2 years)?
- **Bias check**: Did you only search one source? Did you miss non-English work?

## Common Mistakes

- ❌ Starting with a narrow search → missing foundational work
- ❌ Including too many papers → shallow analysis
- ❌ Being descriptive only → missing critical analysis
- ❌ Ignoring negative results → over-optimistic view of the field
