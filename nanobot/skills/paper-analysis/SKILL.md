---
name: paper-analysis
description: Deep reading and structured analysis framework for academic papers.
metadata: '{"nanobot": {"always": true}}'
---

# Paper Analysis Skill

This skill provides a systematic framework for reading and analyzing academic papers.

## The 3-Pass Method

### Pass 1: The 5-Minute Scan (Category & Context)
**Goal**: Categorize the paper and understand its context.

Read in this order:
1. **Title** — What problem? What approach?
2. **Abstract** — Claimed contribution in one paragraph
3. **Introduction** — Motivation, problem definition, contribution list
4. **Section & Subsection headings** — Structure of the paper
5. **Conclusion** — Summary of results and future work

**After Pass 1, you should answer**:
- What type of paper is this? (Theory / Empirical / Survey / System)
- Which field/subfield does it belong to?
- What is the core claim?
- Is it relevant to the user's question?

**Decision**: If not relevant, stop and inform user. If relevant, proceed to Pass 2.

### Pass 2: The 30-Minute Grasp (Main Ideas)
**Goal**: Understand the core contribution without getting lost in details.

Read carefully:
1. **Related Work** — What gap does this paper fill?
2. **Method/Model section** — High-level architecture and key equations
3. **Experimental Setup** — Datasets, metrics, baselines
4. **Main Results** — Key tables/figures, not all ablations

**After Pass 2, you should be able to explain**:
- What problem does it solve?
- What is the key idea/insight?
- How does it compare to baselines?
- What are the main results?

### Pass 3: The Deep Dive (Details & Reproduction)
**Goal**: Full understanding for potential building upon or criticism.

Read everything, focusing on:
- **Proofs** — Are they correct? Do assumptions hold?
- **Implementation details** — Hyperparameters, training setup
- **Ablation studies** — Which component matters most?
- **Error analysis** — What cases fail and why?

## Structured Analysis Output

When analyzing a paper, produce output in this structure:

```markdown
## 📄 Paper Overview
- **Title**: [Full title]
- **Authors**: [Author list]
- **Year/Venue**: [Year, Conference/Journal]
- **arXiv ID**: [ID or link]

## 🎯 Core Contribution
[1-2 sentences on the main contribution]

## 🔍 Problem & Motivation
- What problem does it solve?
- Why is this problem important?
- What are the limitations of prior work?

## 🧠 Method
[High-level description of the approach]
- **Key Insight**: [The "aha" moment of the paper]
- **Architecture**: [Model/algorithm structure]
- **Key Equations**: [Most important formula, in LaTeX if possible]

## 📊 Experiments
- **Datasets**: [List of datasets used]
- **Metrics**: [Evaluation metrics]
- **Baselines**: [What methods compared against]
- **Main Results**: [Key numbers, with relative improvements]

## ⚠️ Limitations
[What the authors admit + what you observe]

## 🔮 Future Directions
[Based on limitations, what could be done next?]

## 💡 Relevance to User
[How does this connect to the user's research interests?]
```

## Critical Reading Checklist

Before accepting a paper's claims, check:

- [ ] **Baselines are fair**: Same data, same evaluation, same compute budget?
- [ ] **Metrics are appropriate**: Not cherry-picked? Include failure cases?
- [ ] **Significance is real**: Is 1% improvement on a saturated benchmark meaningful?
- [ ] **Ablation is thorough**: Did they ablate the key components?
- [ ] **Reproducibility**: Code available? Hyperparameters specified?
- [ ] **Generalization**: Does it work on diverse datasets/settings?

## Special Paper Types

### Survey / Review Papers
- Focus on: taxonomy, trends, open problems
- Don't deep-dive into individual methods
- Extract the "landscape map" for the user

### Theory Papers
- Focus on: assumptions, proof sketch, implications
- Check if assumptions hold in practice
- Identify potential counterexamples

### System Papers
- Focus on: architecture, engineering decisions, scalability
- Look for deployment insights and real-world constraints
