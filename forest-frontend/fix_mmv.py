import re

filePath = r'D:\Ai应用工程师\RAG_agent\forest-frontend\src\views\admin\ModelManagementView.vue'
with open(filePath, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. ModelType union
c = c.replace(
    "type ModelType = 'chat' | 'embedding' | 'mineru'",
    "type ModelType = 'chat' | 'embedding' | 'reranker' | 'mineru'"
)

# 2. TYPE_LABELS
c = c.replace(
    "  mineru: 'MinerU 文档解析',",
    "  reranker: '重排模型',\n  mineru: 'MinerU 文档解析',"
)

# 3. TYPES array
c = c.replace(
    "const TYPES: ModelType[] = ['chat', 'embedding', 'mineru']",
    "const TYPES: ModelType[] = ['chat', 'embedding', 'reranker', 'mineru']"
)

# 4. configs initial value
c = c.replace(
    "const configs = reactive<Record<ModelType, ModelConfigItem[]>>({ chat: [], embedding: [], mineru: [] })",
    "const configs = reactive<Record<ModelType, ModelConfigItem[]>>({ chat: [], embedding: [], reranker: [], mineru: [] })"
)

# 5. allConfigs computed
c = c.replace(
    "const allConfigs = computed(() => [...configs.chat, ...configs.embedding, ...configs.mineru])",
    "const allConfigs = computed(() => [...configs.chat, ...configs.embedding, ...configs.reranker, ...configs.mineru])"
)

# 6. loadAll - add reranker fetch
c = c.replace(
    "      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'mineru' } }),",
    "      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'reranker' } }),\n      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'mineru' } }),"
)
c = c.replace(
    "    configs.mineru = mineru.data.data ?? []",
    "    configs.reranker = reranker.data.data ?? []\n    configs.mineru = mineru.data.data ?? []"
)
c = c.replace(
    "    const [chat, emb, mineru, cardRes] = await Promise.all([",
    "    const [chat, emb, reranker, mineru, cardRes] = await Promise.all(["
)

# 7. modelTab type
c = c.replace(
    "const modelTab = ref<'chat' | 'embedding'>('chat')",
    "const modelTab = ref<'chat' | 'embedding' | 'reranker'>('chat')"
)

with open(filePath, 'w', encoding='utf-8') as f:
    f.write(c)

print('ModelManagementView.vue updated successfully')
