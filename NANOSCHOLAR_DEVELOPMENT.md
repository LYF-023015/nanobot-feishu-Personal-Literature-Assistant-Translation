# NanoScholar 二次开发完整文档

> **项目名称**：NanoScholar —— 基于 nanobot-feishu-specilized 的 AI 科研文献智能助手
>
> **开发目标**：将通用 AI 助手进化为"懂你的科研副手"，实现主动追踪研究方向、自动推送前沿论文、深度解析文献并长期积累研究洞察。

---

## 一、项目定位与创新点

### 1.1 为什么要做这个项目？

现有科研工具（如 Zotero、ChatPDF、Elicit）存在以下痛点：
- **被动**：需要用户手动导入、搜索、阅读
- **无记忆**：每次对话从零开始，不了解用户的研究偏好
- **单线程**：只能单篇阅读，无法并行分析多篇论文并生成综述
- **孤岛**：与日常通讯工具（飞书）割裂，论文发现和使用不在同一工作流

### 1.2 NanoScholar 的核心创新

| 创新点 | 说明 |
|--------|------|
| **主动性** | 基于 Cron + Heartbeat 每天早上推送 arXiv 最新相关论文到飞书 |
| **长期记忆** | Personal Memory System 记录研究方向、阅读偏好、关键结论，越用越懂你 |
| **Agent 协作** | Spawn 子代理并行分析多篇论文，主代理汇总生成综述 |
| **飞书原生工作流** | PDF 直接发送到飞书 → 自动解析 → 生成结构化摘要卡片 → 笔记一键归档 |
| **引用网络分析** | 不只是单篇阅读，能追踪研究脉络（谁引用了这篇、被谁引用、方法演进） |
| **9 种飞书卡片** | 从纯文本升级为结构化卡片，包含按钮、进度条、标签、对比视图 |

---

## 二、技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NanoScholar 架构                              │
├─────────────────────────────────────────────────────────────────────┤
│  现有层（复用 nanobot 原生能力）                                      │
│  ├── Feishu Channel ← 接收论文PDF/链接/指令，推送摘要卡片             │
│  ├── Agent Loop ← 核心推理循环（LLM ↔ 工具执行）                     │
│  ├── LiteLLM Provider ← 调用大模型（支持多 Provider 切换）           │
│  ├── Session Manager ← 多用户/多论文会话隔离                         │
│  ├── Context Compression ← 长对话压缩                                │
│  ├── Personal Memory System ← 研究方向、偏好、关键结论长期记忆         │
│  ├── Cron + Heartbeat ← 定时抓取新论文、主动推送                     │
│  └── Subagent Spawn ← 子代理并行分析                                 │
├─────────────────────────────────────────────────────────────────────┤
│  新增层（本次二次开发）                                               │
│  ├── 📚 Paper Store（SQLite）← 论文元数据、阅读状态、笔记            │
│  ├── 🔍 Academic Search Engine ← arXiv / Semantic Scholar API        │
│  ├── 📄 PDF Pipeline ← MinerU解析 + LLM结构化提取                     │
│  ├── 🕸️ Citation Graph ← 引用关系网络分析                            │
│  ├── 📝 Reading Workspace ← 阅读批注、高亮、笔记管理                  │
│  ├── 📊 Insight Generator ← 综述生成、趋势分析、研究Gap识别           │
│  ├── 🎴 Card Renderer ← 9种飞书交互卡片渲染引擎                       │
│  └── 📡 Feed Service ← 定时论文抓取与推送服务                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、新增模块详解

### 3.1 数据层：Paper Store（`nanobot/research/paper_store.py`）

**数据库**：SQLite，路径默认 `~/.nanobot/workspace/research/papers.db`

**数据模型**：

```sql
-- 论文主表
papers:
  id, title, authors, abstract, pdf_path, doi, arxiv_id,
  published_date, added_date, source, citation_count,
  reading_status (unread/reading/read), priority,
  extracted_summary, methodology, key_findings,
  limitations, future_work, user_rating

-- 标签表（支持自动提取 + 手动标注）
paper_tags:
  paper_id, tag, auto_extracted

-- 阅读笔记表
reading_notes:
  id, paper_id, note_type (highlight/summary/question/insight),
  content, page_ref, created_at

-- 研究主题表
research_topics:
  topic_id, name, description, keywords, created_at, is_active

-- 主题-论文关联表（带相关度评分）
topic_papers:
  topic_id, paper_id, relevance_score
```

**核心能力**：
- 去重导入（按 DOI / arXiv ID）
- 阅读状态流转：`unread` → `reading` → `read`
- 按研究方向/主题聚类
- 与 Memory System 联动（自动将论文关键结论写入长期记忆）
- **阅读统计**（新增）：总论文数、各状态分布、近7天新增、主要来源、热门标签

---

### 3.2 搜索层：学术搜索引擎（`nanobot/agent/tools/academic_search.py`）

**支持的数据源**：

| 数据源 | API | 返回字段 |
|--------|-----|---------|
| **arXiv** | `https://export.arxiv.org/api/query` | 标题、作者、摘要、PDF链接、发表日期、类别 |
| **Semantic Scholar** | `https://api.semanticscholar.org/graph/v1` | 引用数、影响力、相关论文、DOI |

**提供的工具**：

| 工具名 | 功能 |
|--------|------|
| `academic_search` | 按关键词/作者/类别搜索，支持多源联合搜索 |
| `get_paper_by_arxiv` | 通过 arXiv ID 获取单篇论文完整元数据 |
| `get_related_papers` | 通过 Semantic Scholar 获取相关论文 |

**重要设计决策**：
- arXiv API 使用 `https` + `follow_redirects=True`（国内网络环境兼容）
- 超时设置为 10 秒（快速失败，不阻塞 Agent）
- 默认返回 5 篇结果（减少 Token 消耗和 LLM 处理时间）

---

### 3.3 分析层：PDF 深度解析管道

#### 3.3.1 PDF 下载（`nanobot/agent/tools/download_paper.py`）

- 支持通过 arXiv ID 或直链下载 PDF
- 自动保存到 `workspace/research/pdfs/`
- 下载后自动关联到 Paper Store

#### 3.3.2 PDF 解析（复用现有 `parse_pdf_mineru`）

- 调用 MinerU API 将 PDF 转为结构化 Markdown
- 提取图片到本地目录

#### 3.3.3 结构化分析（`nanobot/agent/tools/paper_analyzer.py`）

**核心流程**：
```
PDF Markdown → LLM 提取 → 结构化 JSON → 存入 Paper Store
```

**提取字段**：
```json
{
  "summary": "一句话核心贡献",
  "problem": "研究背景与问题定义",
  "methodology": "核心方法与技术路线",
  "experiments": "实验设置与数据集",
  "key_findings": ["发现1", "发现2"],
  "limitations": "论文自承的局限",
  "future_work": "未来方向",
  "tags": ["tag1", "tag2"]
}
```

**性能优化**：
- 文本截断策略：保留**前 4000 + 后 4000 字符**，截断中间部分（保留引言和结论，丢弃冗余方法细节）
- 最大 8000 字符（控制 Token 消耗，减少 LLM 响应时间）
- Temperature = 0.2（保证提取结果稳定、可复现）

---

### 3.4 管理层：论文图书馆（`nanobot/agent/tools/paper_library.py`）

**支持的 Action**：

| Action | 功能 |
|--------|------|
| `list` | 按状态/主题/标签列出论文 |
| `get` | 获取单篇论文完整信息 |
| `update_status` | 更新阅读状态（unread/reading/read） |
| `add_note` | 添加阅读笔记（highlight/summary/question/insight） |
| `get_notes` | 查看某篇论文的所有笔记 |
| `search` | 在图书馆内搜索 |
| `add_topic` | 创建研究主题 |
| `list_topics` | 列出所有主题 |
| `link_topic` | 将论文关联到主题 |
| **statistics** ⭐ | 获取阅读统计仪表盘数据 |
| **compare** ⭐ | 传入两个 paper_id，返回并排对比数据 |

---

### 3.5 洞察层：高级分析（`nanobot/research/insight_generator.py`）

**基于多篇论文的 LLM 驱动的洞察生成**：

| 功能 | Prompt 策略 |
|------|------------|
| **文献综述** | 按主题聚类、对比方法论、提炼核心贡献、识别研究空白 |
| **研究空白识别** | 基于论文集合找出未被探索的方向，给出具体可行的研究建议 |
| **趋势追踪** | 按时间排序论文，分析方法论演进、性能提升趋势、新兴主题 |
| **推荐阅读** | 基于当前论文的标签和主题，推荐下一步阅读的论文 |

---

### 3.6 网络层：引用分析（`nanobot/agent/tools/citation_graph.py`）

**数据源**：Semantic Scholar API

| Action | 功能 |
|--------|------|
| `citations` | 获取**引用此论文**的文献列表（支持 2 级深度） |
| `references` | 获取**此论文引用**的文献列表 |
| `lineage` | 追溯方法演进脉络（核心论文 → 直接参考文献） |
| `key_papers` | 某领域的高被引核心论文排序 |

---

### 3.7 推送层：主动发现（`nanobot/research/feed_service.py`）

**工作流程**：
```
Cron 触发（每天 8:00）
  → 抓取 arXiv 更新（按类别 + 关键词过滤）
  → 与 Paper Store 去重
  → 生成飞书推送卡片
  → 用户收到通知
```

**配置示例**：
```json
{
  "feeds": [{
    "source": "arxiv",
    "categories": ["cs.AI", "cs.CL", "cs.LG"],
    "keywords": ["large language model", "agent", "reasoning"],
    "schedule": "0 8 * * *",
    "max_results": 5,
    "auto_download_pdf": false
  }]
}
```

---

### 3.8 展示层：飞书卡片渲染引擎（`nanobot/research/card_renderer.py`）

**核心机制**：
- 工具返回或 Agent 回复中，以 `🎴CARD:` 开头的内容会被 `feishu.py` 识别为**自建卡片 JSON**
- `feishu.py` 自动解析并渲染为飞书 interactive 卡片
- 非 `🎴CARD:` 内容保持原有模板卡片渲染

**9 种卡片类型**：

| 卡片 | 场景 | 功能亮点 |
|------|------|---------|
| **论文详情** | 展示单篇论文 | 标题/作者/摘要/核心贡献/方法/关键发现/标签/阅读状态色标/直达 arXiv & PDF 按钮 |
| **搜索结果** | 返回多篇论文 | 编号列表/作者/年份/引用数/直达链接/操作提示 |
| **主动推送** | 新论文推送 | 相关性标识（🔥高度/⭐较为/📌可能）/摘要预览/一键分析提示 |
| **综述结果** | 文献综述输出 | 研究主题分类/核心贡献列表/研究空白与机会 |
| **引用网络** | 引用关系分析 | 参考文献列表/被引用列表/Mermaid 关系图支持 |
| **阅读统计** ⭐ | 个人数据看板 | 总论文数/已读/阅读中/未读/**阅读进度百分比**/主要来源/热门标签 |
| **论文对比** ⭐ | 两篇论文对比 | 并排展示标题/作者/核心贡献/方法/关键发现 |
| **研究主题** ⭐ | 主题概览 | 主题描述/关键词/关联论文列表（带阅读状态 emoji） |
| **每日推送聚合** ⭐ | 多篇论文汇总 | 一天内多篇新论文的汇总/编号列表/直达链接 |

**自动卡片增强**（`AgentLoop` 内置逻辑）：
- 当检测到科研工具被调用后，如果 Agent 的最终回复中**没有**包含 `🎴CARD:`，系统会**自动根据工具结果生成对应卡片**并附加到回复中
- 这意味着即使用户没有明确请求卡片，系统也会自动提供更友好的展示形式

---

## 四、架构改造详解

### 4.1 配置层扩展（`nanobot/config/schema.py`）

新增以下 Pydantic 配置模型：

```python
class AcademicSearchConfig(BaseModel):
    enabled: bool = True
    default_sources: list[str] = ["arxiv"]
    arxiv_categories: list[str] = []
    semantic_scholar_api_key: str = ""
    max_results: int = 10

class ResearchFeedConfig(BaseModel):
    enabled: bool = False
    feeds: list[ResearchFeedItemConfig] = []

class PaperStoreConfig(BaseModel):
    db_path: str = "~/.nanobot/workspace/research/papers.db"
    auto_extract_tags: bool = True
    auto_sync_memory: bool = True

class ResearchConfig(BaseModel):
    enabled: bool = False
    academic_search: AcademicSearchConfig
    research_feed: ResearchFeedConfig
    paper_store: PaperStoreConfig
    auto_analyze_pdf: bool = True
    default_reading_topic: str = ""
```

并扩展 `ToolsConfig`：
```python
class ToolsConfig(BaseModel):
    ...
    research: ResearchConfig = Field(default_factory=ResearchConfig)
```

### 4.2 Agent 上下文增强（`nanobot/agent/context.py`）

- `ContextBuilder` 新增 `research_mode: bool` 参数
- 当 `research_mode=True` 时，在系统提示中自动注入 **NanoScholar 科研助手身份**
- 包含：能力清单、论文处理工作流、图书馆管理指南、研究动态推送说明

### 4.3 Agent Loop 集成（`nanobot/agent/loop.py`）

**新增内容**：
1. `__init__` 接收 `research_config` 参数
2. `_register_default_tools()` 注册全部 8 个科研工具：
   - `AcademicSearchTool`
   - `GetPaperByArxivTool`
   - `GetRelatedPapersTool`
   - `CitationGraphTool`
   - `DownloadPaperPdfTool`
   - `PaperAnalyzerTool`
   - `PaperLibraryTool`
   - `InsightGeneratorTool`
3. `_auto_render_research_card()` — 根据最后一次科研工具调用结果，自动渲染对应卡片

### 4.4 飞书通道改造（`nanobot/channels/feishu.py`）

在 `_send_template_message()` 中增加 `🎴CARD:` 检测逻辑：

```python
if msg.content and msg.content.startswith("🎴CARD:"):
    card_json = json.loads(msg.content[7:])
    content = json.dumps(card_json, ensure_ascii=False)
else:
    # 原有模板卡片逻辑
```

### 4.5 CLI 配置传递（`nanobot/cli/commands.py`）

三个 `AgentLoop` 实例化位置全部添加：
```python
research_config=config.tools.research,
```

### 4.6 Provider 修复（`nanobot/providers/litellm_provider.py`）

**问题**：Moonshot 的 `api_base` 与 LiteLLM provider 路由冲突，导致模型名前缀 `moonshot/` 没有被正确剥离，API 收到 `moonshot/moonshot-v1-32k` 而非 `moonshot-v1-32k`。

**修复**：
1. 对于 Moonshot 模型，不再直接设置 `litellm.api_base`（靠 `MOONSHOT_API_BASE` 环境变量即可）
2. 在 `chat()` 中增加安全剥离逻辑：如果 `api_base` 已设置且模型名以 `moonshot/` 开头，自动去掉前缀

---

## 五、Provider 切换说明

### 5.1 为什么从 Moonshot 切换到 DeepSeek？

开发过程中遇到以下问题：

| 问题 | 现象 | 原因 |
|------|------|------|
| `engine_overloaded_error` | 上传图片时模型超载 | `kimi-k2.5` 负载高 |
| `resource_not_found_error` | 模型名不被识别 | LiteLLM 前缀传递问题 |
| `LLM transient error` | 重试间隔 3565 秒（59分钟） | 账户限流/余额不足/Tier 太低 |

**结论**：Moonshot 对该 API Key 的限制极为严格，无法支撑需要频繁工具调用的 Agent 场景。

### 5.2 最终配置

```json
{
  "agents": {
    "defaults": {
      "model": "deepseek/deepseek-chat",
      "maxTokens": 4096,
      "maxToolIterations": 15,
      "temperature": 0.3
    }
  },
  "providers": {
    "deepseek": {
      "apiKey": "sk-9ef22141a06443db853d4fce97854e9f",
      "apiBase": "https://api.deepseek.com/v1"
    }
  },
  "tools": {
    "research": {
      "enabled": true,
      "academicSearch": {
        "maxResults": 5
      }
    },
    "web": {
      "search": {
        "provider": "serper"
      }
    }
  }
}
```

### 5.3 优化措施

| 优化项 | 前值 | 后值 | 目的 |
|--------|------|------|------|
| 模型 | `kimi-k2.5` | `deepseek-chat` | 稳定、支持工具调用 |
| Max Tokens | `8192` | `4096` | 减少单轮生成时间 |
| Max Tool Iterations | `200` | `15` | 防止无限循环 |
| Temperature | `0.1` | `0.3` | 决策更果断 |
| 搜索返回数 | `10` | `5` | 减少处理量 |
| arXiv 超时 | `30s` | `10s` | 快速失败 |
| PDF 分析截断 | `12000` 字符 | `8000` 字符（头4000+尾4000） | 保留引言和结论，减少 Token |
| Web 搜索 | DuckDuckGo | Serper (Google) | 国内网络稳定 |

---

## 六、文件变更清单

### 6.1 新增文件（12个）

```
nanobot/
├── research/
│   ├── __init__.py
│   ├── paper_store.py          # SQLite 论文库 ORM
│   ├── feed_service.py         # 定时论文抓取与推送
│   ├── insight_generator.py    # 综述/空白/趋势分析核心
│   └── card_renderer.py        # 9种飞书卡片渲染引擎
└── agent/tools/
    ├── academic_search.py      # 学术搜索工具
    ├── paper_analyzer.py       # 论文结构化分析
    ├── paper_library.py        # 图书馆管理工具
    ├── download_paper.py       # PDF 下载工具
    ├── citation_graph.py       # 引用网络分析工具
    └── insight_generator.py    # 洞察生成器工具
```

### 6.2 修改文件（7个）

```
nanobot/
├── channels/feishu.py          # 支持 🎴CARD: 自建卡片
├── agent/loop.py               # 注册科研工具 + 自动卡片增强
├── agent/context.py            # 科研助手身份注入系统提示
├── config/schema.py            # 扩展 ResearchConfig 等配置模型
├── cli/commands.py             # 传递科研配置到 AgentLoop
├── providers/litellm_provider.py  # 修复 Moonshot 模型名前缀问题
└── research/paper_store.py     # 新增统计查询方法
```

---

## 七、使用指南

### 7.1 启动

```bash
# 确保在项目根目录
nanobot gateway
```

### 7.2 飞书可用指令

| 指令 | 效果 |
|------|------|
| `搜索 transformer 论文` | 返回 arXiv 搜索结果卡片 |
| `获取论文 1706.03762` | 返回论文详情卡片（含元数据、摘要、按钮） |
| `分析论文 1` | MinerU 解析 + LLM 结构化分析 + 详情卡片 |
| `论文 1 引用了哪些工作？` | 引用网络卡片（参考文献 + 被引用） |
| `生成 Transformer 综述` | 调用 insight_generator，返回综述卡片 |
| `这个方向还有什么空白？` | 研究 Gap 识别 |
| `我的论文库` | 图书馆列表卡片 |
| `阅读统计` | 阅读统计仪表盘卡片 |
| `对比论文 1 和 2` | 论文对比卡片（A/B 并排） |
| `列出主题` | 研究主题卡片 |
| `标记论文 1 为已读` | 更新阅读状态 |
| `笔记 1 这个方法有问题` | 添加阅读笔记 |

### 7.3 配置调整

```bash
# 编辑配置
nano ~/.nanobot/config.json
```

**常用调整项**：
- `tools.research.enabled` — 开关科研模式
- `tools.research.academicSearch.maxResults` — 搜索结果数量
- `tools.research.researchFeed.enabled` — 开关定时推送
- `agents.defaults.maxToolIterations` — 工具调用上限

---

## 八、已知限制与未来方向

### 8.1 当前限制

| 限制 | 说明 | 缓解方案 |
|------|------|---------|
| arXiv API 限流 | 频繁搜索可能被限流 | 已实现指数退避，支持多源切换 |
| PDF 解析质量 | MinerU 对复杂排版可能不稳定 | 失败后降级为纯文本提取 |
| 长综述超出消息长度 | 飞书消息有长度限制 | 分页发送或生成 Markdown 文件 |
| WebSocket 模式按钮回调 | 无法直接处理卡片按钮点击 | 使用文本指令替代（如"分析 1"） |
| 图片多模态 | DeepSeek V3 暂不支持图片理解 | 使用支持多模态的模型（如 Moonshot V1 Vision） |

### 8.2 建议的后续扩展

1. **多 Agent 协作综述**
   - 利用 `spawn` 子代理并行分析多篇论文的核心方法
   - 主代理汇总各子代理输出，生成高质量综述

2. **Notion 深度集成**
   - 论文笔记一键归档到 Notion 指定数据库
   - 自动同步阅读状态到 Notion

3. **语音/图片交互**
   - 发送论文截图自动 OCR 识别 arXiv ID
   - 语音指令搜索和分析论文

4. **更多学术数据源**
   - IEEE Xplore、PubMed、知网 CNKI、DBLP

5. **研究主题自动发现**
   - 基于用户收藏论文的聚类分析，自动推荐新的研究方向

---

## 九、开发与测试记录

| 阶段 | 完成内容 | 测试结果 |
|------|---------|---------|
| Phase 1 | 核心闭环：搜索→下载→解析→摘要→存储 | ✅ PaperStore CRUD 通过 ✅ arXiv 实时搜索通过 |
| Phase 2 | 引用网络 + 阅读管理 | ✅ CitationGraphTool 语法通过 |
| Phase 3 | 综述生成 + 趋势分析 + 洞察工具 | ✅ InsightGenerator 语法通过 |
| 卡片升级 | 9种卡片 + 自动渲染 + 统计/对比/主题 | ✅ 全部语法通过 ✅ feishu.py 卡片识别通过 |
| Provider 修复 | Moonshot → DeepSeek 切换 | ✅ DeepSeek 配置完成 |

---

## 十、附录：配置参考

### 10.1 完整科研相关配置块

```json
{
  "tools": {
    "research": {
      "enabled": true,
      "academicSearch": {
        "enabled": true,
        "defaultSources": ["arxiv", "semantic_scholar"],
        "arxivCategories": ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.IR"],
        "semanticScholarApiKey": "",
        "maxResults": 5
      },
      "researchFeed": {
        "enabled": true,
        "feeds": [
          {
            "source": "arxiv",
            "categories": ["cs.AI", "cs.CL", "cs.LG"],
            "keywords": ["large language model", "agent", "reasoning"],
            "schedule": "0 8 * * *",
            "maxResults": 5,
            "autoDownloadPdf": false,
            "notifyChannel": "feishu"
          }
        ]
      },
      "paperStore": {
        "dbPath": "~/.nanobot/workspace/research/papers.db",
        "autoExtractTags": true,
        "autoSyncMemory": true
      },
      "autoAnalyzePdf": true,
      "defaultReadingTopic": ""
    },
    "web": {
      "search": {
        "provider": "serper",
        "apiKey": "your-serper-key",
        "maxResults": 5
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "deepseek/deepseek-chat",
      "maxTokens": 4096,
      "maxToolIterations": 15,
      "temperature": 0.3
    }
  },
  "providers": {
    "deepseek": {
      "apiKey": "sk-your-key",
      "apiBase": "https://api.deepseek.com/v1"
    }
  }
}
```

---

*文档版本：v1.0*
*生成时间：2026-04-22*
*基于 nanobot-feishu-specilized 二次开发*
