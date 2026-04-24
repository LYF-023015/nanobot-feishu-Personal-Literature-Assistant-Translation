# NanoScholar 项目 —— 简历描述参考

## 推荐版本（标准技术岗）

### 项目介绍
**NanoScholar** — 基于开源 nanobot 框架二次开发的 AI 科研文献智能助手，深度集成飞书生态，实现"搜索-解析-分析-归档"全流程自动化。支持 arXiv/Semantic Scholar 多源学术搜索、MinerU PDF 结构化解析、LLM 驱动的文献综述生成，并通过 9 种飞书交互卡片实现富媒体论文展示。

### 主要工作
• 独立设计并实现 12 个核心模块（学术搜索、PDF 解析管道、论文库管理、引用网络分析、卡片渲染引擎等），基于 Pydantic 配置模型 + SQLite 构建异步数据持久化层，支持论文去重、阅读状态流转与主题关联管理
• 封装 arXiv Atom API 与 Semantic Scholar REST API 实现多源论文抓取与引用网络遍历，基于 LiteLLM 构建多 Provider 路由（Moonshot/DeepSeek），设计结构化 Prompt 实现论文核心贡献自动抽取与综述生成
• 基于 lark-oapi SDK 开发飞书 CardKit 卡片渲染引擎，设计 `🎴CARD:` 标记协议实现 Agent 回复的零侵入卡片增强；优化 Agent 工具迭代上限（200→15）与搜索超时（30s→10s），完成 Provider 限流迁移

---

## 精简版（1页简历适用）

### 项目介绍
基于开源 nanobot 框架二次开发的 AI 科研文献助手，深度集成飞书，支持 arXiv/语义学者搜索、PDF 结构化解析、LLM 综述生成，通过 9 种飞书卡片实现论文全流程管理。

### 主要工作
- 独立开发学术搜索、PDF 解析、引用网络、文献综述等 12 个核心模块，基于 SQLite 构建论文库
- 封装 arXiv/Semantic Scholar API，实现多源论文抓取、去重、引用关系分析
- 设计 LLM 结构化提取 Prompt，实现论文核心贡献自动抽取、研究空白识别
- 开发飞书卡片渲染引擎，支持 9 种交互卡片类型，设计 `🎴CARD:` 零侵入发送协议
- 优化 Agent 性能（工具迭代 200→15、超时 30s→10s），完成 Moonshot→DeepSeek Provider 迁移

---

## 学术/科研导向版

### 项目介绍
**NanoScholar** — 面向科研工作者的智能文献管理 Agent。基于开源框架二次开发，通过大语言模型实现论文的自动发现、深度解析、知识提取与长期积累，打通"文献发现→阅读理解→知识沉淀"的完整科研工作流。

### 主要工作
- **智能文献发现**：集成 arXiv 和 Semantic Scholar API，支持关键词/作者/类别多维度搜索；开发定时推送服务，每日自动抓取目标领域新论文并推送到飞书
- **深度内容解析**：基于 MinerU PDF 解析 API 提取结构化文本，设计 LLM Prompt 实现论文核心贡献、方法论、实验结果、局限性的自动抽取
- **知识网络构建**：开发引用网络分析工具，支持参考文献追踪、被引用分析、方法演进脉络梳理；基于 SQLite 构建个人论文库，支持阅读状态管理和主题聚类
- **智能综述生成**：实现 LLM 驱动的文献综述自动生成、研究空白识别、领域趋势追踪；支持 Spawn 子代理并行分析多篇论文
- **交互体验设计**：为飞书平台开发 9 种科研专用卡片（论文详情、搜索结果、引用网络、阅读统计等），实现结构化知识的可视化呈现

---

## 全栈/工程师导向版

### 项目介绍
基于 Python asyncio + LiteLLM 构建的 AI Agent 系统，深度集成飞书开放平台和多个第三方学术 API，实现科研文献的自动化发现、解析、分析与可视化。

### 主要工作
- **后端架构**：基于 Pydantic 配置模型、SQLite 数据层、异步 httpx 客户端构建模块化 Agent 系统；开发 8 个 Tool 类并通过 Registry 模式动态注册
- **API 集成**：封装 arXiv Atom API、Semantic Scholar Graph API、MinerU Batch API，处理 XML 解析、异步轮询、错误降级
- **LLM 工程**：基于 LiteLLM 实现多 Provider 路由（Moonshot/DeepSeek）；设计结构化 JSON 输出 Prompt，处理 LLM 响应解析和容错
- **前端卡片**：基于飞书 CardKit 规范开发 9 种卡片模板，实现 Markdown → 卡片 JSON 的自动转换；设计 `🎴CARD:` 协议实现与现有消息系统的兼容
- **系统优化**：修复 LiteLLM 与 Moonshot 的 api_base 冲突导致的模型名传递 Bug；将 DuckDuckGo 切换为 Serper 解决国内网络不稳定问题

---

## 一句话描述（用于项目列表）

> 基于开源框架二次开发的 AI 科研文献助手，集成 arXiv/Semantic Scholar 搜索、MinerU PDF 解析、LLM 综述生成，通过 9 种飞书卡片实现论文全流程管理。

---

## 关键词建议（用于简历搜索优化）

Python, asyncio, SQLite, Pydantic, LiteLLM, LLM, Agent, Function Calling, API Integration, arXiv, Semantic Scholar, Feishu/Lark, CardKit, PDF Parsing, NLP, Prompt Engineering, Research Tools

---

## 技术栈标签

**语言/框架**：Python 3.11, asyncio, Pydantic, Typer  
**LLM/AI**：LiteLLM, OpenAI-compatible API, Function Calling, Prompt Engineering  
**数据**：SQLite, JSON, XML (arXiv Atom)  
**API/集成**：arXiv API, Semantic Scholar API, MinerU API, Feishu Open Platform (lark-oapi)  
**工具**：httpx, loguru, croniter  

---

## 注意事项

1. **如果用于课程/毕业设计**：建议强调"独立完成架构设计、模块开发、测试验证全流程"
2. **如果用于求职**：建议强调"解决实际问题（科研人员文献管理痛点）"和"可量化的技术决策（性能优化数据）"
3. **GitHub 展示**：建议将项目 push 到个人 GitHub，简历中附上链接，展示代码组织和文档完整性
4. **演示准备**：如果面试需要演示，建议准备一个 2 分钟的飞书录屏，展示"搜索论文 → 自动分析 → 收到卡片"的完整流程
