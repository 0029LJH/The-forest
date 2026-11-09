<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { type ApiResponse } from '@/api/http'
import { extractApiError } from '@/api/http'

// ── 类型 ──

interface ModelConfigItem {
  id: number
  modelType: string
  displayName: string
  baseUrl: string
  apiKey: string
  modelName: string
  apiFormat?: string
  parameters: Record<string, unknown> | null
  isActive: boolean
  fallbackConfigId: number | null
  createdAt: string | null
}

interface ModelParamSchema {
  type?: string
  title?: string
  description?: string
  default?: unknown
  minimum?: number
  maximum?: number
  enum?: unknown[]
}

interface ModelCardItem {
  name: string
  label: string
  provider: string
  kind: string
  status: string
  description: string
  contextSize: number
  outputSize: number
  dimensions: number[] | null
  batchLimit: number | null
  parameters: Record<string, ModelParamSchema>
  apiBaseUrl: string | null
}

type ModelType = 'chat' | 'embedding' | 'reranker' | 'mineru'

const TYPE_LABELS: Record<ModelType, string> = {
  chat: '聊天大模型',
  embedding: '嵌入大模型',
  reranker: '重排模型',
  mineru: 'MinerU 文档解析',
}
const TYPES: ModelType[] = ['chat', 'embedding', 'reranker', 'mineru']

// ── 数据 ──

const configs = reactive<Record<ModelType, ModelConfigItem[]>>({ chat: [], embedding: [], reranker: [], mineru: [] })
const cards = ref<ModelCardItem[]>([])
const loading = ref(false)
const selectedId = ref<number | null>(null)

const allConfigs = computed(() => [...configs.chat, ...configs.embedding, ...configs.reranker, ...configs.mineru])
const selected = computed(() => allConfigs.value.find((c) => c.id === selectedId.value) ?? null)
const selectedCard = computed(() => cards.value.find((c) => c.name === selected.value?.modelName) ?? null)

async function loadAll() {
  loading.value = true
  try {
    const [chat, emb, reranker, mineru, cardRes] = await Promise.all([
      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'chat' } }),
      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'embedding' } }),
      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'reranker' } }),
      http.get<ApiResponse<ModelConfigItem[]>>('/admin/model-configs', { params: { modelType: 'mineru' } }),
      http.get<ApiResponse<ModelCardItem[]>>('/admin/model-cards'),
    ])
    configs.chat = chat.data.data ?? []
    configs.embedding = emb.data.data ?? []
    configs.reranker = reranker.data.data ?? []
    configs.mineru = mineru.data.data ?? []
    cards.value = cardRes.data.data ?? []
    // 保持选中有效；默认选中当前激活的聊天模型
    if (!allConfigs.value.find((c) => c.id === selectedId.value)) {
      selectedId.value =
        allConfigs.value.find((c) => c.isActive)?.id ?? allConfigs.value[0]?.id ?? null
    }
  } catch (err) {
    ElMessage.error(extractApiError(err, '加载模型配置失败'))
  } finally {
    loading.value = false
  }
}

function select(config: ModelConfigItem) {
  selectedId.value = config.id
}

function providerOf(modelName: string): string {
  const card = cards.value.find((c) => c.name === modelName)
  return card ? providerLabel(card.provider) : ''
}

function providerLabel(provider: string): string {
  const map: Record<string, string> = {
    deepseek: 'DeepSeek',
    dashscope: '阿里云 DashScope',
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    gemini: 'Google Gemini',
    moonshot: '月之暗面 Moonshot',
    xai: 'xAI',
    ollama: 'Ollama（本地）',
    zhipu: '智谱 AI',
  }
  return map[provider] ?? provider
}

function paramsText(p: Record<string, unknown> | null | undefined): string {
  if (!p || Object.keys(p).length === 0) return ''
  // null/空值与「未设置」等价，不显示（全空时上层显示「默认」）
  const entries = Object.entries(p).filter(([, v]) => v !== null && v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}=${v}`).join(' · ')
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatNumber(n: number): string {
  return n >= 10000 ? `${(n / 10000).toFixed(0)} 万` : String(n)
}

// ── API Key 掩码显示（仿 web_ui MaskedValue） ──

const keyVisible = ref(false)
const maskedKey = computed(() => {
  const v = selected.value?.apiKey ?? ''
  if (!v) return ''
  return keyVisible.value ? v : v.length > 8 ? `${v.slice(0, 4)}••••••••${v.slice(-4)}` : '••••••••'
})

// ── 备用模型（降级目标） ──

const fallbackDialogVisible = ref(false)
const fallbackPick = ref<number | null>(null)

const selectedFallback = computed(() =>
  selected.value?.fallbackConfigId != null
    ? allConfigs.value.find((c) => c.id === selected.value!.fallbackConfigId) ?? null
    : null,
)

const fallbackOptions = computed(() =>
  allConfigs.value.filter(
    (c) => c.modelType === selected.value?.modelType && c.id !== selected.value?.id,
  ),
)

function openFallbackDialog() {
  fallbackPick.value = selected.value?.fallbackConfigId ?? null
  fallbackDialogVisible.value = true
}

async function saveFallback() {
  if (!selected.value) return
  try {
    await http.patch(`/admin/model-configs/${selected.value.id}/fallback`, {
      fallbackConfigId: fallbackPick.value,
    })
    ElMessage.success('备用模型已更新')
    fallbackDialogVisible.value = false
    await loadAll()
  } catch (err) {
    ElMessage.error(extractApiError(err, '设置失败'))
  }
}

// ── 激活 / 删除 ──

async function activateSelected() {
  if (!selected.value) return
  try {
    await http.patch(`/admin/model-configs/${selected.value.id}/activate`)
    ElMessage.success('已切换为使用中')
    await loadAll()
  } catch (err) {
    ElMessage.error(extractApiError(err, '切换失败'))
  }
}

async function deleteSelected() {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${selected.value.displayName}」？`,
      '删除配置',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.delete(`/admin/model-configs/${selected.value.id}`)
    ElMessage.success('已删除')
    selectedId.value = null
    await loadAll()
  } catch (err) {
    ElMessage.error(extractApiError(err, '删除失败'))
  }
}

// ── 添加配置对话框 ──

const addType = ref<ModelType | null>(null)
const addLoading = ref(false)
const addError = ref('')
const testResult = ref<{ ok: boolean; message: string } | null>(null)
const addForm = reactive({
  displayName: '',
  baseUrl: '',
  apiKey: '',
  modelName: '',
  parameters: {} as Record<string, any>,
})

// 自定义模型（未注册卡片）：下拉中的两类自由选项，选中后模型名改自由输入
const CUSTOM_OPENAI = '__custom_openai__'
const CUSTOM_ANTHROPIC = '__custom_anthropic__'
const pickValue = ref('')
const customMode = ref<'openai' | 'anthropic' | null>(null)

// 添加表单只列在售模型（deprecated 不出现）
const cardsForType = computed(() =>
  cards.value.filter((c) => c.kind === addType.value && c.status !== 'deprecated'),
)
const pickedCard = computed(() => cards.value.find((c) => c.name === addForm.modelName) ?? null)
// 自定义模式下即使手填的模型名与注册卡片重名，也不渲染参数表单
const addParamSchema = computed(() =>
  customMode.value ? {} : (pickedCard.value?.parameters ?? {}),
)
const providerGroups = computed(() => {
  const map = new Map<string, ModelCardItem[]>()
  for (const c of cardsForType.value) {
    if (!map.has(c.provider)) map.set(c.provider, [])
    map.get(c.provider)!.push(c)
  }
  return [...map.entries()].map(([provider, list]) => ({ provider, cards: list }))
})

function openAddForm(type: ModelType) {
  addType.value = type
  addForm.displayName = type === 'mineru' ? 'MinerU 文档解析' : ''
  addForm.baseUrl = type === 'mineru' ? 'https://mineru.net' : ''
  addForm.apiKey = ''
  addForm.modelName = type === 'mineru' ? 'vlm' : ''
  addForm.parameters = {}
  pickValue.value = ''
  customMode.value = null
  addError.value = ''
  testResult.value = null
}

function onCardPick() {
  const card = cards.value.find((c) => c.name === addForm.modelName)
  if (card?.apiBaseUrl) addForm.baseUrl = card.apiBaseUrl
  const next: Record<string, any> = {}
  if (card) {
    for (const [key, prop] of Object.entries(card.parameters ?? {})) {
      if (prop.default !== undefined) next[key] = prop.default
    }
  }
  addForm.parameters = next
}

function onPickChange(val: string) {
  if (val === CUSTOM_OPENAI || val === CUSTOM_ANTHROPIC) {
    customMode.value = val === CUSTOM_OPENAI ? 'openai' : 'anthropic'
    addForm.modelName = ''
    addForm.parameters = {}
    testResult.value = null
    return
  }
  customMode.value = null
  addForm.modelName = val
  onCardPick()
}

function cancelAdd() {
  addType.value = null
  testResult.value = null
}

async function testConnection() {
  testResult.value = null
  try {
    const { data } = await http.post<ApiResponse<{ ok: boolean; message: string; status: number }>>('/admin/model-configs/test', {
      baseUrl: addForm.baseUrl,
      apiKey: addForm.apiKey,
      modelName: addForm.modelName,
      modelType: addType.value,
      apiFormat: customMode.value ?? undefined,
    })
    testResult.value = { ok: data.data?.ok ?? false, message: data.data?.message ?? '未知结果' }
  } catch (err) {
    testResult.value = { ok: false, message: extractApiError(err, '测试失败') }
  }
}

async function saveModel() {
  if (!addForm.displayName.trim() || !addForm.apiKey.trim() || !addForm.modelName.trim()) {
    addError.value = '请填写所有字段'
    return
  }
  if (addType.value !== 'mineru' && !addForm.baseUrl.trim()) {
    addError.value = '请填写 API URL'
    return
  }
  addLoading.value = true
  addError.value = ''
  try {
    await http.post('/admin/model-configs', {
      modelType: addType.value,
      displayName: addForm.displayName,
      baseUrl: addForm.baseUrl,
      apiKey: addForm.apiKey,
      modelName: addForm.modelName,
      apiFormat: customMode.value ?? undefined,
      parameters: addType.value === 'mineru' ? {} : addForm.parameters,
    })
    addType.value = null
    await loadAll()
  } catch (err) {
    addError.value = extractApiError(err, '保存失败')
  } finally {
    addLoading.value = false
  }
}

// ── 可用模型表格 ──
// 只显示「已配置了 key 的厂商」的模型：没配过 key 的厂商不出现

const configuredProviders = computed(() => {
  const set = new Set<string>()
  for (const c of allConfigs.value) {
    const p = cards.value.find((card) => card.name === c.modelName)?.provider
    if (p) set.add(p)
  }
  return set
})

const chatCards = computed(() =>
  cards.value.filter((c) => c.kind === 'chat' && configuredProviders.value.has(c.provider)),
)
const embCards = computed(() =>
  cards.value.filter((c) => c.kind === 'embedding' && configuredProviders.value.has(c.provider)),
)
const modelTab = ref<'chat' | 'embedding' | 'reranker'>('chat')

onMounted(loadAll)
</script>

<template>
  <div class="mm-page">
    <!-- 左侧：已配置 + 添加入口（仿 web_ui 凭证页 Sidebar） -->
    <aside class="mm-side">
      <header class="mm-side__head">
        <h2>模型管理</h2>
        <p>多厂商模型配置与当前使用模型</p>
      </header>

      <div v-if="loading && allConfigs.length === 0" class="mm-side__empty">加载中...</div>

      <template v-else>
        <div class="mm-group">
          <div class="mm-group__label">
            已配置
            <span class="mm-count">{{ allConfigs.length }}</span>
          </div>
          <template v-for="type in TYPES" :key="type">
            <template v-if="configs[type].length > 0">
              <div class="mm-sub-label">{{ TYPE_LABELS[type] }}</div>
              <div
                v-for="m in configs[type]"
                :key="m.id"
                class="mm-item"
                :class="{ 'is-active': selectedId === m.id }"
                @click="select(m)"
              >
                <span class="mm-item__name">{{ m.displayName }}</span>
                <span v-if="m.isActive" class="mm-item__badge">使用中</span>
              </div>
            </template>
          </template>
          <div v-if="allConfigs.length === 0" class="mm-side__empty">暂无配置，从下方添加入口开始</div>
        </div>

        <div class="mm-group">
          <div class="mm-group__label">添加配置</div>
          <div
            v-for="type in TYPES"
            :key="`add-${type}`"
            class="mm-item mm-item--add"
            @click="openAddForm(type)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span class="mm-item__name">{{ TYPE_LABELS[type] }}</span>
          </div>
        </div>
      </template>
    </aside>

    <!-- 右侧：配置详情 + 可用模型（仿 web_ui DetailPanel） -->
    <main class="mm-detail">
      <template v-if="selected">
        <header class="mm-detail__head">
          <div class="mm-detail__title">
            <span class="mm-detail__name">{{ selected.displayName }}</span>
            <span class="mm-detail__model">{{ selected.modelName }}</span>
            <span v-if="selected.isActive" class="mm-detail__badge">使用中</span>
          </div>
          <div class="mm-detail__actions">
            <el-button v-if="!selected.isActive" type="primary" size="small" @click="activateSelected">设为使用中</el-button>
            <el-button size="small" type="danger" plain @click="deleteSelected">删除</el-button>
          </div>
        </header>

        <div class="mm-fields">
          <div class="mm-field">
            <span class="mm-field__label">模型</span>
            <span class="mm-field__value">{{ selectedCard?.label ?? selected.modelName }}</span>
          </div>
          <div class="mm-field">
            <span class="mm-field__label">厂商</span>
            <span class="mm-field__value">{{ providerOf(selected.modelName) || '-' }}</span>
          </div>
          <div class="mm-field">
            <span class="mm-field__label">API URL</span>
            <span class="mm-field__value mm-field__value--mono">{{ selected.baseUrl }}</span>
          </div>
          <div class="mm-field">
            <span class="mm-field__label">API Key</span>
            <span class="mm-field__value mm-field__value--mono">
              {{ maskedKey }}
              <button v-if="selected.apiKey" class="mm-key-toggle" type="button" :title="keyVisible ? '隐藏' : '显示'" @click="keyVisible = !keyVisible">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <template v-if="keyVisible">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </template>
                  <template v-else>
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </template>
                </svg>
              </button>
            </span>
          </div>
          <div class="mm-field">
            <span class="mm-field__label">参数</span>
            <span class="mm-field__value mm-field__value--mono">{{ paramsText(selected.parameters) || '默认' }}</span>
          </div>
          <div class="mm-field">
            <span class="mm-field__label">创建时间</span>
            <span class="mm-field__value mm-field__value--mono">{{ formatTime(selected.createdAt) }}</span>
          </div>
          <div v-if="selected.isActive && selected.modelType === 'chat'" class="mm-field">
            <span class="mm-field__label">备用模型</span>
            <span class="mm-field__value">
              <template v-if="selectedFallback">
                {{ selectedFallback.displayName }}
                <span class="mm-model-raw">{{ selectedFallback.modelName }}</span>
              </template>
              <template v-else>
                <span class="mm-fallback-none">未设置（调用失败直接报错）</span>
              </template>
              <el-button link type="primary" size="small" @click="openFallbackDialog">设置</el-button>
            </span>
          </div>
        </div>

        <div class="mm-models">
          <div class="mm-models__head">
            <span class="mm-models__title">
              可用模型
              <span class="mm-count">{{ chatCards.length + embCards.length }}</span>
              <span class="mm-models__filter-hint">仅显示已配置 Key 的厂商</span>
            </span>
            <el-radio-group v-model="modelTab" size="small">
              <el-radio-button value="chat">聊天模型 {{ chatCards.length }}</el-radio-button>
              <el-radio-button value="embedding">嵌入模型 {{ embCards.length }}</el-radio-button>
            </el-radio-group>
          </div>

          <el-table v-if="modelTab === 'chat'" :data="chatCards" size="small" style="width: 100%">
            <el-table-column label="MODEL" min-width="200">
              <template #default="{ row }">
                <span class="mm-model-name">{{ row.label }}</span>
                <span class="mm-model-raw">{{ row.name }}</span>
                <span v-if="row.status !== 'active'" class="mm-model-tag">已停售</span>
              </template>
            </el-table-column>
            <el-table-column label="厂商" width="130">
              <template #default="{ row }">{{ providerLabel(row.provider) }}</template>
            </el-table-column>
            <el-table-column label="CONTEXT" width="110" align="right">
              <template #default="{ row }"><span class="mono">{{ formatNumber(row.contextSize) }}</span></template>
            </el-table-column>
            <el-table-column label="MAX OUTPUT" width="120" align="right">
              <template #default="{ row }"><span class="mono">{{ formatNumber(row.outputSize) }}</span></template>
            </el-table-column>
            <el-table-column label="描述" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">{{ row.description }}</template>
            </el-table-column>
          </el-table>

          <el-table v-else :data="embCards" size="small" style="width: 100%">
            <el-table-column label="MODEL" min-width="200">
              <template #default="{ row }">
                <span class="mm-model-name">{{ row.label }}</span>
                <span class="mm-model-raw">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="厂商" width="130">
              <template #default="{ row }">{{ providerLabel(row.provider) }}</template>
            </el-table-column>
            <el-table-column label="CONTEXT" width="110" align="right">
              <template #default="{ row }"><span class="mono">{{ formatNumber(row.contextSize) }}</span></template>
            </el-table-column>
            <el-table-column label="DIMENSIONS" width="130" align="right">
              <template #default="{ row }"><span class="mono">{{ row.dimensions?.join(' / ') ?? '—' }}</span></template>
            </el-table-column>
            <el-table-column label="批大小" width="90" align="right">
              <template #default="{ row }"><span class="mono">{{ row.batchLimit ?? '—' }}</span></template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <div v-else class="mm-detail__empty">
        <p class="mm-detail__empty-title">选择左侧配置查看详情</p>
        <p class="mm-detail__empty-desc">或从「添加配置」创建新的模型配置</p>
      </div>
    </main>

    <!-- 添加配置对话框（仿 web_ui CreateCredentialDialog） -->
    <el-dialog
      :model-value="addType !== null"
      :title="`添加${addType ? TYPE_LABELS[addType] : ''}`"
      width="580px"
      :close-on-click-modal="false"
      @update:model-value="(v: boolean) => { if (!v) cancelAdd() }"
    >
      <el-form label-width="110px" @submit.prevent>
        <el-form-item label="显示名称">
          <el-input v-model="addForm.displayName" placeholder="例如：生产环境 DeepSeek" />
        </el-form-item>

        <template v-if="addType === 'mineru'">
          <el-form-item label="Token">
            <el-input v-model="addForm.apiKey" type="password" placeholder="sk-...（mineru.net 免费创建）" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="addForm.modelName" placeholder="vlm / pipeline" />
          </el-form-item>
          <p class="mm-hint">模型说明：vlm（精度高，复杂版式/扫描件/公式）、pipeline（零幻觉，内容逐字准确）</p>
        </template>

        <template v-else-if="addType === 'reranker'">
          <el-form-item label="启用重排序">
            <el-switch v-model="addForm.parameters.rerank_enabled" />
            <span class="mm-hint">关闭后仅使用 RRF 融合检索，跳过 cross-encoder 重排序（节省延迟）</span>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="模型">
            <el-select v-model="pickValue" placeholder="选择模型（按厂商分组，或选自定义自由输入）" style="width: 100%" @change="onPickChange">
              <el-option-group v-for="g in providerGroups" :key="g.provider" :label="providerLabel(g.provider)">
                <el-option v-for="c in g.cards" :key="c.name" :label="`${c.label}（${c.name}）`" :value="c.name" />
              </el-option-group>
              <el-option-group label="自定义（自由输入模型名）">
                <el-option label="OpenAI 兼容模型" :value="CUSTOM_OPENAI" />
                <el-option label="Anthropic 兼容模型" :value="CUSTOM_ANTHROPIC" />
              </el-option-group>
            </el-select>
            <el-input
              v-if="customMode"
              v-model="addForm.modelName"
              :placeholder="customMode === 'openai' ? '输入模型名，例如 gpt-5-mini' : '输入模型名，例如 claude-sonnet-4-6'"
              style="margin-top: 8px"
            />
          </el-form-item>
          <el-form-item label="API URL">
            <el-input
              v-model="addForm.baseUrl"
              :placeholder="customMode === 'anthropic' ? '例如 https://api.anthropic.com/v1' : '选卡后自动填充厂商默认地址，自定义模型手动填写'"
            />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="addForm.apiKey" type="password" placeholder="sk-..." show-password />
          </el-form-item>
          <p v-if="pickedCard" class="mm-hint">
            {{ pickedCard.description }} · 上下文 {{ formatNumber(pickedCard.contextSize) }} · 输出上限 {{ formatNumber(pickedCard.outputSize) }}{{ pickedCard.dimensions?.length ? ` · 支持维度 ${pickedCard.dimensions.join(' / ')}` : '' }}{{ pickedCard.batchLimit ? ` · 批大小 ≤${pickedCard.batchLimit}` : '' }}
          </p>
          <el-form-item v-for="(prop, key) in addParamSchema" :key="key" :label="prop.title ?? key">
            <el-select v-if="prop.enum?.length" v-model="addForm.parameters[key]" style="width: 100%">
              <el-option v-for="opt in prop.enum" :key="String(opt)" :label="String(opt)" :value="(opt as string | number)" />
            </el-select>
            <el-input-number
              v-else-if="prop.type === 'number' || prop.type === 'integer'"
              v-model="addForm.parameters[key]"
              :min="prop.minimum"
              :max="prop.maximum"
              :step="prop.type === 'integer' ? 1 : 0.1"
              :placeholder="prop.default != null ? String(prop.default) : ''"
              style="width: 100%"
            />
            <el-switch v-else-if="prop.type === 'boolean'" v-model="addForm.parameters[key]" />
            <el-input v-else v-model="addForm.parameters[key]" :placeholder="prop.default != null ? String(prop.default) : ''" />
          </el-form-item>
        </template>
      </el-form>

      <p v-if="addError" class="form-error">{{ addError }}</p>
      <div v-if="testResult" class="test-msg" :class="{ ok: testResult.ok, fail: !testResult.ok }">{{ testResult.message }}</div>

      <template #footer>
        <el-button @click="cancelAdd">取消</el-button>
        <el-button :disabled="addLoading" @click="testConnection">测试连接</el-button>
        <el-button type="primary" :disabled="addLoading" @click="saveModel">{{ addLoading ? '保存中...' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- 设置备用模型（降级目标） -->
    <el-dialog v-model="fallbackDialogVisible" title="设置备用模型" width="480px">
      <p class="mm-hint" style="margin-left: 0;">
        主模型调用失败或 60 秒无响应时，自动切换到备用模型重试一次。
        备用模型只能是同类型的已配置模型（且限可用模型目录中注册的模型）。
      </p>
      <el-select v-model="fallbackPick" placeholder="选择备用模型（清除 = 不使用）" style="width: 100%" clearable>
        <el-option
          v-for="c in fallbackOptions"
          :key="c.id"
          :label="`${c.displayName} · ${c.modelName}`"
          :value="c.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="fallbackDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveFallback">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mm-page {
  display: flex;
  gap: 10px;
  height: calc(100vh - 80px);
  padding: 10px;
}

/* ── 左侧 ── */
.mm-side {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid var(--border-default);
  border-radius: 22px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.mm-side__head {
  padding: 20px 18px 14px;
}

.mm-side__head h2 {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: var(--text-primary);
}

.mm-side__head p {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-muted);
}

.mm-side__empty {
  padding: 20px 18px;
  font-size: 12px;
  color: var(--text-muted);
}

.mm-group {
  padding: 8px 10px 4px;
}

.mm-group__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.mm-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text-muted);
}

.mm-sub-label {
  padding: 10px 10px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.mm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 2px 0;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  transition: background 0.15s ease;
}

.mm-item:hover {
  background: var(--surface-muted);
}

.mm-item.is-active {
  background: rgba(74, 144, 217, 0.1);
  color: var(--brand-primary);
  font-weight: 600;
}

.mm-item--add {
  color: var(--text-secondary);
}

.mm-item--add:hover {
  color: var(--brand-primary);
}

.mm-item__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-item__badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  padding: 2px 8px;
  border-radius: 100px;
}

/* ── 右侧 ── */
.mm-detail {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid var(--border-default);
  border-radius: 22px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
  overflow-y: auto;
  padding: 18px;
}

.mm-detail__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-default);
}

.mm-detail__title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mm-detail__name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.mm-detail__model {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--text-muted);
}

.mm-detail__badge {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  padding: 3px 10px;
  border-radius: 100px;
}

.mm-detail__actions {
  flex-shrink: 0;
}

.mm-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 0;
}

.mm-field {
  display: grid;
  grid-template-columns: 104px 1fr;
  gap: 12px;
  align-items: baseline;
}

.mm-field__label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.mm-field__value {
  font-size: 13.5px;
  color: var(--text-primary);
  word-break: break-all;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mm-field__value--mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--text-secondary);
}

.mm-key-toggle {
  display: inline-flex;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
}

.mm-key-toggle:hover {
  color: var(--text-primary);
}

/* ── 可用模型表格 ── */
.mm-models {
  margin-top: 16px;
}

.mm-models__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.mm-models__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.mm-models__filter-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-muted);
}

.mm-model-name {
  font-weight: 600;
  color: var(--text-primary);
}

.mm-model-tag {
  margin-left: 8px;
  padding: 1px 7px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  background: var(--surface-muted);
  border-radius: 100px;
}

.mm-model-raw {
  margin-left: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--text-muted);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.mm-detail__empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.mm-detail__empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.mm-detail__empty-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.mm-hint {
  margin: 0 0 12px 110px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.mm-fallback-none {
  color: var(--text-muted);
}

.form-error {
  margin: 0 0 10px 110px;
  font-size: 12px;
  color: #dc2626;
}

.test-msg {
  margin: 0 0 10px 110px;
  font-size: 12px;
}

.test-msg.ok {
  color: #16a34a;
}

.test-msg.fail {
  color: #dc2626;
}
</style>
