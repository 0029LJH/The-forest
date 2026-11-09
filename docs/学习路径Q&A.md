# forest 项目 — AI 应用工程师学习路径 Q&A

以 forest（RAG 知识库平台）为实际项目背景，按五个阶段梳理必须掌握的核心知识点。

---

## 阶段一：工程化基础（单体架构）

### 1. FastAPI 异步编程
**Q: `async def` 和 `def` 在路由处理中有什么区别？为什么这里用 async？**

A: FastAPI 基于 Starlette，内部是 asyncio 事件循环。`async def` 路由不会阻塞事件循环，可同时处理并发请求；`def` 路由会阻塞整个事件循环，高并发下性能差。本项目中所有数据库操作（SQLAlchemy async）、外部 HTTP 调用（httpx）都必须是 async。

参考：[app/main.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\main.py) 所有路由都是 `async`。

---

**Q: FastAPI 的 `Depends()` 依赖注入是如何工作的？**

A: FastAPI 会在调用路由前自动实例化依赖函数，并将其返回值注入到路由参数。本项目用 `Depends(get_db)` 自动管理数据库会话生命周期（请求开始创建，成功提交，异常回滚）。也用于 `Depends(get_current_user)` 做认证，`Depends(require_admin)` 做权限校验。

参考：[app/auth/dependencies.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\auth\dependencies.py)

---

### 2. Pydantic v2 配置管理
**Q: 为什么用 Pydantic Settings 而不用直接读 .env 文件？**

A: Pydantic Settings 提供类型校验、默认值、嵌套结构，比手动解析 .env 更健壮。本项目用 `BaseSettings` 自动从 `.env` 文件读取配置，并按前缀分组（如 `CHAT_`、`EMBEDDING_`、`MINIO_`）。

参考：[app/config.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\config.py)

---

**Q: `model_config = SettingsConfigDict(env_prefix="CHAT_")` 的作用是什么？**

A: 告诉 Pydantic 只读取以 `CHAT_` 为前缀的环境变量，映射到 `ChatModelSettings` 类字段。例如 `CHAT_API_KEY` → `api_key` 字段。避免所有环境变量混在一起，实现模块化配置。

---

### 3. SQLAlchemy 2.0 async ORM
**Q: `async_session_factory` 和手动 `async with async_session_factory() as session:` 有什么区别？**

A: `Depends(get_db)` 是 FastAPI 的依赖注入方式，自动管理 session 的生命周期（请求开始创建，请求结束释放）。手动 `async with` 用在后台任务、周期清理等场景，需要显式管理 commit/rollback。

参考：[app/dependencies.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\dependencies.py) 和 [app/qa/service.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\qa\service.py) 中的 `_persist_session`。

---

**Q: SQLAlchemy 2.0 的 `select()` 和 1.x 的 `session.query()` 有什么区别？**

A: 2.0 使用标准 SQL 表达式风格：`select(Model).where(Model.id == 1)`，返回结果需要用 `.scalars()` 或 `.fetchone()` 获取。1.x 的 `query()` 风格已废弃。本项目全部使用 2.0 风格，并且是 async 版本。

---

### 4. JWT 认证与授权
**Q: Access Token 和 Refresh Token 分别存在哪里？为什么这样设计？**

A: Access Token 存在前端 `localStorage`（`forest_access_token`），每次 API 请求通过 `Authorization: Bearer <token>` 发送，有效期短（30分钟）。Refresh Token 存在 httpOnly Cookie 中，有效期长（14天），用于换取新的 Access Token。这样设计是为了防止 XSS 窃取 Refresh Token（httpOnly 不可被 JS 读取）。

参考：[app/auth/dependencies.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\auth\dependencies.py) 中 `parse_access_token` 和 cookie 设置逻辑。

---

**Q: `require_group_access` 是如何实现多租户数据隔离的？**

A: 每个接口请求都携带 `group_id`，后端在查询时强制加上 `WHERE group_id = :gid` 过滤条件。管理员可以跨组操作，普通成员只能访问所在组的文档和问答数据。查询时通过 SQLAlchemy 的 `.where(Document.group_id == group_id)` 实现隔离。

---

### 5. Docker Compose 基础设施
**Q: 为什么用 Docker Compose 而不是直接在本地安装 PostgreSQL/ES？**

A: Docker Compose 提供一致的运行环境，避免本地安装的版本差异问题。本项目通过 `docker-compose.yml` 一键启动 PostgreSQL（含 pgvector 扩展）、MinIO、Elasticsearch 三个服务，所有依赖都在容器内，本地只需有 Docker 即可。

参考：[docker-compose.yml](D:\Ai应用工程师\RAG_agent\docker-compose.yml)

---

**Q: `healthcheck` 的作用是什么？为什么 ES 的 `start_period` 是 60s？**

A: healthcheck 让 Docker 监测服务是否真正可用（不仅仅是进程在运行）。ES 启动较慢（Java 堆内存初始化），需要 `start_period: 60s` 给 ES 足够时间完成启动，期间健康检查不计入重试次数。

---

---

## 阶段二：中间件使用

### 6. PostgreSQL + pgvector
**Q: pgvector 是什么？为什么用它而不用专门的向量数据库？**

A: pgvector 是 PostgreSQL 的扩展，将向量作为 `vector` 数据类型存储，支持 HNSW 近似最近邻索引。好处是与业务数据共用同一数据库，事务一致性有保障，不需要额外运维一个向量数据库服务。本项目用 `vector_cosine_ops` 做余弦距离检索。

参考：[app/engine/vector_store.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\engine\vector_store.py) 中的 HNSW 索引创建和相似度查询 SQL。

---

**Q: HNSW 索引相比暴力搜索（全表扫描）有什么优势？有什么代价？**

A: HNSW（Hierarchical Navigable Small World）将 O(n) 全表扫描降到近似 O(log n)，检索速度快几个数量级。代价是建索引慢、占用更多内存、插入时索引需要维护。对于知识库平台（读多写少、向量数量万级），HNSW 是最佳选择。

---

**Q: `cmetadata->>'group_id' = :gid` 这个 GIN 索引的作用是什么？**

A: `cmetadata` 是 JSONB 类型，存储了 `document_id`、`group_id`、`chunk_index` 等元数据。GIN 索引加速 `WHERE cmetadata->>'group_id' = 'xxx'` 这类 JSONB 字段过滤查询。没有这个索引，每次检索都要全表扫描所有元数据。

---

### 7. Elasticsearch
**Q: 为什么有了 pgvector 还要用 Elasticsearch？**

A: pgvector 擅长语义检索（向量相似度），但关键词精确匹配、全文检索、中文分词是 ES 的强项。两者互补：pgvector 找"意思相近的"，ES 找"包含精确关键词的"。本项目用 RRF 融合两种结果，兼顾语义和关键词。

---

**Q: IK 中文分词器是什么？为什么要单独构建带 IK 的 ES 镜像？**

A: IK 是 ES 的中文分词插件，将中文文本切分成有意义的词语（如"人工智能"→"人工"+"智能"）。官方 ES 镜像不带 IK，需要手动构建：在 Dockerfile 中安装 `analysis-ik` 插件。本项目通过自定义 Docker 镜像 `./elasticsearch-ik` 实现。

参考：[docker-compose.yml](D:\Ai应用工程师\RAG_agent\docker-compose.yml) 中 `elasticsearch` 服务的 `build: ./elasticsearch-ik`。

---

**Q: ES 检索时 BM25 算法和向量检索的结果如何融合？**

A: 本项目使用 RRF（Reciprocal Rank Fusion）算法。对每条候选 chunk，分别计算其在向量检索和 ES 检索中的排名贡献：`rrf_score = 1/(k + rank)`，k 通常取 60。两条通道都命中的 chunk 得分翻倍（同时获得向量分数和关键词分数），单通道命中的只有一份贡献。最后按总 RRF 分数排序取 Top-K。

参考：[app/qa/retrieval.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\qa\retrieval.py) 中 `_merge_vector_hits` 和 `_merge_keyword_hits` 方法。

---

### 8. MinIO 对象存储
**Q: 为什么用 MinIO 而不是直接存文件系统？**

A: MinIO 是 S3 兼容的对象存储，提供高可靠的文件存储、分片上传、断点续传能力。与文件系统相比：支持水平扩展、有 REST API 接口便于分布式部署、支持生命周期管理。本项目用它存储用户上传的原始文档（PDF/DOCX/TXT）。

参考：[app/engine/storage.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\engine\storage.py)

---

---

## 阶段三：RAG 核心

### 9. 文档解析（ETL 流水线）
**Q: 文档从上传到可检索，经历了哪几个步骤？**

A: 完整链路：上传到 MinIO → 解析（按格式选择 Parser：PDF 用 Docling/MinerU，DOCX 用 python-docx，MD/TXT 直接读）→ 清洗（去除空白字符、特殊符号）→ 切块（StructureAwareChunkTransformer，按语义结构分块，重叠 32 token）→ 向量嵌入（调用 Embedding API）→ 存入 pgvector → 存入 ES 索引。

参考：[app/ingestion/pipeline.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\ingestion\pipeline.py)

---

**Q: 为什么需要"重叠切块"（overlap）？重叠 32 token 有什么考虑？**

A: 文档边界处的语义可能不完整。重叠确保相邻 chunk 之间有语义衔接，避免关键信息正好在边界上被切断。32 token（约 64 个中文字符）是经验值：足够衔接上下文，又不会导致检索时重复太多内容浪费 token。

参考：[app/config.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\config.py) 中 `ChunkingSettings` 的 `target_tokens=240, overlap_tokens=32`。

---

### 10. Embedding 模型调用
**Q: Embedding API 调用失败时，系统如何降级？**

A: 系统先尝试使用管理员在控制台中配置的激活模型，失败时回退到 `.env` 中预设的模型。Embedding 配置通过 `get_embedding_config(user_id)` 解析，支持多模型卡片（卡片中声明了 API 格式、维度、batch 限制等）。

参考：[app/engine/vector_store.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\engine\vector_store.py) 中 `_resolve_embedding()` 函数。

---

**Q: 为什么 embedding 需要分批调用（batch_size=9）而不是一次全部发送？**

A: 大部分 Embedding API 对单次请求的文本数量有上限。例如阿里 text-embedding-v4 限制每批最多 10 条。本项目根据模型卡片的 `batch_limit` 动态调整批次大小，超过限制则分批发送。

---

### 11. 查询规划（Query Planning）
**Q: 为什么需要查询规划？直接用用户原问题检索不行吗？**

A: 用户问题往往表述模糊或包含多个子问题。查询规划用 LLM 分析意图，决定三种策略之一：
- **DIRECT**：问题清晰，直接检索
- **REWRITE**：需要改写以提高检索效果
- **DECOMPOSE**：复杂问题拆成多个子查询并行检索

这样可以显著提高检索召回率，尤其是多轮对话中上下文相关的追问。

参考：[app/qa/query_planning.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\qa\query_planning.py)

---

### 12. 证据等级评估
**Q: 四级证据评估（SUFFICIENT/PARTIAL/WEAK/NONE）的逻辑是什么？**

A:
- **NONE**：无任何文档命中，或最大余弦相似度 < 0.65（向量完全不相关）→ 直接拒答
- **WEAK**：仅单通道命中一条文档 → 谨慎回答，明确说明依据有限
- **PARTIAL**：双通道各命中一条（或单通道多条）→ 只回答证据覆盖的部分
- **SUFFICIENT**：双通道都命中且 ≥ 2 条文档 → 正常回答

参考：[app/qa/retrieval.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\qa\retrieval.py) 中 `_assess_evidence` 方法。

---

**Q: 证据等级如何影响 LLM 的回答？**

A: 证据等级和控制指令一起传入 System Prompt。LLM 收到后必须遵守对应规则：WEAK 时必须说明依据有限，PARTIAL 时必须标注未覆盖部分，NONE 时直接拒答。这是减少幻觉的关键机制——不是让 LLM 自由发挥，而是用严格的证据约束生成内容。

---

### 13. 流式输出（SSE）
**Q: SSE 流式输出和非流式输出有什么区别？为什么 QA 要用流式？**

A: 非流式（`ask`）：等 LLM 全部生成完再一次性返回。流式（`stream-ask`）：LLM 每生成一个 token 就推送给前端，用户即时看到打字机效果。RAG 场景下检索+生成可能有 3-5 秒延迟，流式让用户感知更快，体验更好。

参考：[app/qa/service.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\qa\service.py) 中 `ask_stream` 方法和 `StreamingAnswerParser` 类。

---

**Q: `StreamingAnswerParser` 为什么要用 `<<<ANSWER>>>` / `<<<END>>>` 分隔符？**

A: LLM 输出了四种标记：ANSWER（答案）、THINKING（推理过程）、CITATIONS（引用来源）。前端只需要展示 ANSWER，THINKING 和 CITATIONS 用于后端统计和展示引用。分隔符解析器在流式接收过程中，只输出 ANSWER 段的 token，其他段丢弃。尾部保留 9 个字符（`<<<END>>>` 的长度）是为了确保能检测到完整的结束标记。

---

---

## 阶段四：AI Agent

### 14. LangGraph + ReactAgent
**Q: ReactAgent 的工作原理是什么？**

A: React（Reasoning + Acting）模式：Agent 每轮做两件事——先推理（thinking），再决定调用哪个工具。具体流程：用户输入 → LLM 生成思考 + 工具调用 → 执行工具获取结果 → LLM 根据结果继续推理 → 直到生成最终答案。本项目用 LangGraph 的 `create_react_agent` 实现。

参考：[app/assistant/agent/factory.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\assistant\agent\factory.py)

---

**Q: `recursion_limit` 为什么不同工具有不同的限制？**

A: 限制 Agent 最多执行多少轮工具调用，防止陷入无限循环。KB_SEARCH 模式只需要检索知识库（10 轮足够），ADMIN 模式可能涉及多步骤管理操作（15 轮），普通聊天模式不需要太多工具调用（12 轮）。

---

### 15. 短期记忆管理
**Q: 为什么需要"语义摘要"而不是直接存储所有历史消息？**

A: 对话越长，上下文越多，LLM 调用成本越高，且超出 token 限制会报错。系统设定阈值（>20 条消息 或 >8000 字符）时，用 LLM 将历史消息压缩成 3-6 条要点摘要，替代原始消息存入 `compact_summary`。这样既保留了关键上下文，又控制了 token 消耗。

参考：[app/assistant/memory/manager.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\assistant\memory\manager.py)

---

**Q: 摘要生成失败时有什么降级策略？**

A: 如果 LLM 摘要失败（网络错误、模型不可用），系统回退为拼接最近 30 条消息的前 200 个字符。虽然效果不如语义摘要，但保证了功能不中断。

---

### 16. 会话归档
**Q: 什么是会话归档？为什么需要 30 天不活跃自动归档？**

A: 会话归档是将长时间不活跃的对话标记为 ARCHIVED 状态，不再出现在用户的主列表中，但保留数据可在需要时恢复。30 天阈值平衡了用户体验（活跃对话始终可见）和资源消耗（长期不活跃数据不影响列表性能）。

参考：[CLAUDE.md](D:\Ai应用工程师\RAG_agent\CLAUDE.md) 中 Assistant 模块描述。

---

---

## 阶段五：系统设计与工程化

### 17. 多租户数据隔离
**Q: 项目如何实现组级别的数据隔离？**

A: 三层隔离：① 查询层：所有文档/问答检索都带 `WHERE group_id = :gid` 过滤；② 权限层：`require_group_access` 中间件校验当前用户是否为该组成员；③ 引擎层：pgvector 的 `cmetadata->>'group_id'` 和 ES 查询都携带 group_id 过滤。管理员可跨组操作。

---

### 18. 审计日志
**Q: 哪些操作需要记录审计日志？为什么？**

A: 敏感操作需要留痕：删除文档、解散群组、禁用用户、重置密码、修改模型配置。审计日志记录操作人、操作时间、操作类型、目标对象和详情，用于安全追溯和问题排查。

参考：[app/audit/service.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\audit\service.py) 中 `log_audit` 方法。

---

### 19. LLM 用量统计
**Q: 如何追踪 LLM 的 token 消耗和费用？**

A: 每次 LLM 调用后，从响应中提取真实 usage（input_tokens + output_tokens），记录到 `llm_usage_records` 表，关联用户、群组、模块（qa/assistant）、端点。前端管理台展示用量趋势图和排行榜。估算模式用于无法获取真实 usage 的情况（如某些模型不返回）。

参考：[app/metrics/collector.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\metrics\collector.py)

---

### 20. 模型配置管理
**Q: 管理员如何在不改代码的情况下切换 LLM 模型？**

A: 系统设置中管理员可以添加/修改模型配置（chat_model + embedding_model），配置存储在数据库 `model_configs` 表中。每次请求时通过 `get_chat_config(user_id)` 动态获取当前激活的模型配置，覆盖 `.env` 中的默认值。这样切换模型无需重启服务。

参考：[app/models_config/resolver.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\models_config\resolver.py)

---

### 21. 系统健康检查
**Q: 健康检查检查哪些服务？为什么要检查这些？**

A: 检查 PostgreSQL（连接+pgvector 可用）、Elasticsearch（集群健康+索引可用）、MinIO（S3 连接）、Embedding API（能否正常调用）。这些是 RAG 链路的关键依赖，任何一项故障都会导致功能异常。管理台实时显示各组件状态，方便运维排查。

参考：[app/system/router.py](D:\Ai应用工程师\RAG_agent\forest-backend\app\system\router.py)

---

### 22. 文档去重与失败重试
**Q: 同组内如何避免重复文档？失败文档如何处理？**

A: 上传时用 SHA-256 计算文件哈希，同组内已存在相同哈希的文件跳过入库。处理失败的文档标记为 FAILED 状态并记录失败原因，管理员可在控制台批量重试。失败原因可能是解析失败、Embedding API 报错、数据库写入失败等。

---

## 快速自检清单

| 阶段 | 核心问题 | 能否说清楚 |
|------|---------|-----------|
| 阶段一 | FastAPI 异步原理、Pydantic Settings、SQLAlchemy 2.0 async、JWT 认证流程 | □ |
| 阶段二 | pgvector HNSW、ES BM25+IK、RRF 融合、MinIO 作用 | □ |
| 阶段三 | RAG 完整链路、查询规划三种策略、证据四级评估、SSE 流式解析 | □ |
| 阶段四 | ReactAgent 工作流、短期记忆摘要机制、会话归档 | □ |
| 阶段五 | 多租户隔离、审计日志、用量统计、模型热切换 | □ |
