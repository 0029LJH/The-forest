# forest 项目面试指南

> 基于实际代码整理的面试问答库
> 版本：1.0 ｜ 日期：2026-09-16

---

## 一、项目概述（1分钟自我介绍）

**forest** 是一款企业级 RAG 知识库平台，核心能力：
- **混合检索**：PGvector 语义 + Elasticsearch 关键词，RRF 融合 + Cross-Encoder 重排序
- **证据评估**：四级评估（SUFFICIENT/PARTIAL/WEAK/NONE），证据不足主动拒答
- **AI 助手**：LangGraph ReactAgent + 短期记忆 + 会话归档
- **多租户**：群组级数据隔离，双重防护（应用层 + 检索层）

技术栈：Python 3.12 / FastAPI / Vue3 / PostgreSQL 16 + pgvector / Elasticsearch 8.x / LangGraph

---

## 二、高频面试题

### 1. RAG 检索链路

**Q: 你的 RAG 检索流程是怎样的？**

A: 四步走：
```
1. 查询规划：LLM 判断 DIRECT/REWRITE/DECOMPOSE，生成 1-3 条检索问句
2. 混合检索：PGvector 语义检索（top50）+ ES 关键词检索（top50）并行执行
3. RRF 融合：1/(K + rank)，K=60，同 chunk 双通道命中得分翻倍
4. 重排序：Cross-Encoder 对 top20 重新打分，阈值过滤后取 top8
```

代码位置：`forest-python/app/qa/retrieval.py`

---

**Q: 为什么用 RRF 而不是简单拼接？**

A: RRF（Reciprocal Rank Fusion）的优势：
- 不受绝对分数影响，只看排名
- 天然惩罚单通道的高分 hit（避免向量检索一家独大）
- 双通道都命中的 chunk 得分翻倍（协同效应）
- 公式简单：score = Σ 1/(K + rank)，K 是平滑系数

---

**Q: 证据评估怎么做的？**

A: 四级评估逻辑：
```python
# 优先级：向量相似度 < 0.65 → NONE
#          重排序分数 < 0.05 → NONE
#          双通道命中 → SUFFICIENT
#          单通道命中 >=2 篇 → PARTIAL
#          其他 → WEAK
```

NONE 级别直接返回"未检索到相关文档"，不调用 LLM，节省成本约 70%。

代码位置：`forest-python/app/qa/retrieval.py:240-260`

---

### 2. Agent 系统

**Q: 你的 Agent 架构是怎么设计的？**

A: 基于 LangGraph 的状态机：
```
用户提问
    ↓
[planner] 查询规划（LLM 决策）
    ↓
[retriever] 混合检索
    ↓
[answerer] LLM 生成回答
    ↓
[checker] 证据评估（是否拒答）
    ↓
流式输出（SSE）
```

工具调用可视化：tool_start → tool_end → 前端展示卡片。

代码位置：`forest-python/app/assistant/agent/facade.py`

---

**Q: 如何处理 Agent 的工具调用？**

A: 两层设计：
1. 工具描述：在 Agent prompt 中定义工具签名和用途
2. 参数截断：参数超过 200 字符截断，结果超过 500 字符截断
3. 中断确认：写操作（停用/删除）通过 interrupt() 暂停，前端展示确认卡片

---

**Q: LangGraph 相比 LangChain Agent 有什么优势？**

A: LangGraph 是显式状态机：
- 状态转移清晰可见，容易调试
- 支持中断（interrupt）实现 human-in-the-loop
- 可以可视化执行图
- 更适合复杂工作流（多步决策、条件分支）

---

### 3. 记忆系统

**Q: 短期记忆是怎么实现的？**

A: 三层记忆架构：
```
短期记忆：最近 20 条消息 / 8000 字符
    ↓ 触发压缩
LLM 语义摘要（失败回退：拼接最近 30 条）
    ↓ 存储
AssistantSessionContext 表（summary_text, context_version）
```

可视化："AI 记住了什么"卡片展示摘要 + 更新时间。

代码位置：`forest-python/app/assistant/memory/manager.py`

---

**Q: 记忆压缩的触发条件是什么？**

A: 两个条件满足其一即触发：
- 消息数 > 20 条
- 字符数 > 8000（约 2000 tokens）

压缩方式：
1. 优先：LLM 生成语义摘要（保留关键信息）
2. 回退：拼接最近 30 条消息的前 200 字符

---

### 4. 文档处理

**Q: 文档上传后的处理流水线是怎样的？**

A: 10 步 ETL 流水线：
```
1. 读取 MinIO 文件
2. 解析（PDF/DOCX/MD/TXT）
3. 清洗（保留代码块）
4. 保存预览文本（前 200 字符）
5. 结构化切块（标题/段落/句子，目标 240 token）
6. 清理旧索引（防残留）
7. 保存 chunks 到 DB
8. 向量化 + 存入 PGvector
9. 索引到 Elasticsearch
10. 标记 READY 状态
```

失败重试：指数退避，最多 3 次。

代码位置：`forest-python/app/ingestion/pipeline.py`

---

**Q: 切块策略是怎么设计的？**

A: 结构感知切块（StructureAwareChunkTransformer）：
- 按标题层级切分（H1/H2/H3）
- 段落内按句子切分
- 目标 240 token，重叠 40 token
- 代码块整体保留，不切断

---

### 5. 多租户隔离

**Q: 如何保证多租户数据安全？**

A: 双层防护：
```
第一层（应用层）：
  - 所有接口强制校验 group_id
  - 群组成员关系校验（require_group_access）
  - 停用/解散群组拒绝访问

第二层（检索层）：
  - 向量检索：metadata 过滤 group_id
  - ES 检索：filter query 加 group_id
```

群组解散时级联清理：文档 → chunks → 向量 → ES 索引 → MinIO 文件。

---

### 6. 性能优化

**Q: 检索性能如何优化？**

A: 多项优化：
| 优化点 | 效果 |
|--------|------|
| 双通道并行 | 检索时间从串行变并行，节省 50%+ |
| 证据不足拒答 | 不调用 LLM，从 ~10s 降至 ~3s |
| HNSW 索引 | 向量检索 <100ms |
| Rerank 阈值过滤 | 减少 LLM 输入长度 |
| 邻居扩展 | 提升上下文连贯性 |

---

**Q: 大文件上传怎么处理？**

A: 分片上传 + 断点续传：
- 分片大小：5MB
- 会话过期：24h（后台定时清理）
- 合并：MinIO 服务端 Merge
- 去重：同群组 SHA-256 计算，相同则秒传

---

### 7. 模型配置

**Q: 如何实现模型动态切换？**

A: 模型配置表（model_configs）：
- 每个用户可配置 chat/embedding 模型
- 激活模型全局生效（含查询规划、记忆摘要）
- 连接测试：启动时验证 API 连通性
- 降级策略：主模型失败自动切换到备用模型

已支持 45+ 模型卡（DeepSeek、Claude、GPT、Gemini、Qwen 等）。

---

## 三、系统设计题

### Q: 如果让你设计一个学习助手，你会怎么做？

A: （参考之前聊的内容，结合项目经验）

架构：
```
Vue3 + SSE 对话界面
    ↓
FastAPI + LangGraph
  ├── 查询规划（意图识别）
  ├── 知识检索（RAG）
  ├── 作业批改（OCR + 评分）
  ├── 错题诊断（薄弱点分析）
  └── 学习规划（进度追踪）
    ↓
PostgreSQL（用户/错题）+ Milvus（知识点）+ MinIO（上传文件）
```

核心模块：
1. 查询规划：识别学生意图（解题/复习/测验）
2. 知识检索：RAG 检索知识点
3. 作业批改：OCR 识别 + LLM 评分（给提示不给答案）
4. 学习诊断：错题本 + 薄弱点分析 + 推荐练习

---

## 四、踩过的坑

### 1. 向量删除残留
**问题**：文档删除后向量未清理，检索时仍出现
**解决**：删除时级联清理向量 + ES + MinIO，清理失败告警

---

### 2. RRF 单通道主导
**问题**：纯向量检索一个高分 hit 淹没其他结果
**解决**：RRF K=60 平滑 + 双通道命中翻倍

---

### 3. 长对话 Token 溢出
**问题**：对话过长导致超出模型上下文限制
**解决**：20 条/8000 字符触发记忆压缩

---

### 4. 异步任务状态丢失
**问题**：worker 崩溃导致 PROCESSING 状态卡住
**解决**：启动时自动恢复卡住的任务，状态机设计

---

## 五、项目亮点总结

| 亮点 | 技术深度 |
|------|---------|
| 混合检索 + RRF 融合 | 算法层面优化 |
| 四级证据评估 + 拒答机制 | 成本控制 + 用户体验 |
| LangGraph 状态机 | 现代 Agent 架构 |
| 短期记忆压缩 | 长对话支持 |
| 双层数据隔离 | 企业级安全 |
| 模型动态切换 | 灵活配置 |

---

## 六、面试反问环节

可以问的问题：
1. 团队目前用什么 Agent 框架？LangChain 还是自研？
2. RAG 检索效果的评估指标是什么？（准确率/召回率/用户满意度）
3. 是否有自己的知识库？还是通用场景？
4. 对 Agent 的安全性和可控性有什么要求？

---

*最后更新：2026-09-16*
*代码版本：与 origin/main 一致*
