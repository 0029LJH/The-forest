<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { fetchDocumentChunks, type DocumentChunk } from '@/api/document'
import { markdownToHtml } from '@/utils/markdown'
import { extractApiError } from '@/api/http'

const props = defineProps<{
  visible: boolean
  documentId: number | null
  fileName: string
  chunkId: number | null
  chunkIndex: number | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const loading = ref(false)
const error = ref('')
const chunks = ref<DocumentChunk[]>([])
const targetIdx = ref(0)

function close() {
  emit('update:visible', false)
}

watch(
  () => [props.visible, props.documentId] as const,
  async ([visible, documentId]) => {
    if (!visible || documentId == null) return
    loading.value = true
    error.value = ''
    chunks.value = []
    targetIdx.value = 0
    try {
      const list = await fetchDocumentChunks(documentId)
      chunks.value = list
      // 优先按 chunkId（行 id）定位，回退按 chunkIndex 定位
      let idx = list.findIndex((c) => c.chunkId === props.chunkId)
      if (idx < 0 && props.chunkIndex != null) {
        idx = list.findIndex((c) => c.chunkIndex === props.chunkIndex)
      }
      targetIdx.value = idx >= 0 ? idx : 0
      await nextTick()
      scrollToTarget()
    } catch (err) {
      error.value = extractApiError(err, '加载分块失败')
    } finally {
      loading.value = false
    }
  },
)

const listRef = ref<HTMLElement | null>(null)

function scrollToTarget() {
  const el = listRef.value
  if (!el) return
  const target = el.querySelector('.chunk-preview__block--target')
  if (target) {
    target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}

function renderChunk(text: string): string {
  return markdownToHtml(text || '')
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    width="760px"
    top="6vh"
    :close-on-click-modal="true"
    @update:model-value="(val: boolean) => { if (!val) close() }"
  >
    <template #header>
      <div class="cp-head">
        <h2 class="cp-title" :title="fileName">{{ fileName || '文档分块' }}</h2>
        <span class="cp-badge">分块列表</span>
        <span v-if="chunkIndex != null" class="cp-badge cp-badge--target">引用片段 #{{ chunkIndex }}</span>
      </div>
    </template>

    <div class="cp-body">
      <div v-if="loading" class="cp-state">
        <div class="cp-spinner" />
        <p>加载分块中...</p>
      </div>

      <div v-else-if="error" class="cp-state cp-error">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8V12M12 16H12.01" stroke-linecap="round" />
        </svg>
        <p>{{ error }}</p>
      </div>

      <div v-else-if="chunks.length === 0" class="cp-state">
        <p>该文档暂无分块</p>
      </div>

      <div v-else ref="listRef" class="cp-list">
        <article
          v-for="(chunk, i) in chunks"
          :key="chunk.chunkId"
          class="cp-block"
          :class="{ 'chunk-preview__block--target': i === targetIdx }"
        >
          <header class="cp-block__head">
            <span class="cp-block__no">#{{ chunk.chunkIndex }}</span>
            <span v-if="i === targetIdx" class="cp-block__tag">引用来源</span>
          </header>
          <div class="cp-block__text" v-html="renderChunk(chunk.chunkText)" />
        </article>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.cp-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.cp-title {
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cp-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--surface-muted);
  padding: 2px 9px;
  border-radius: 100px;
}

.cp-badge--target {
  color: var(--brand-primary);
  background: rgba(30, 78, 124, 0.1);
}

.cp-body {
  min-height: 300px;
  max-height: 74vh;
  overflow-y: auto;
}

.cp-state {
  text-align: center;
  padding: 64px 24px;
  color: var(--text-muted);
}

.cp-state p {
  margin-top: 14px;
  font-size: 14px;
}

.cp-error {
  color: var(--el-color-danger);
}

.cp-error p {
  color: var(--el-color-danger);
}

.cp-spinner {
  width: 32px;
  height: 32px;
  margin: 0 auto;
  border: 3px solid var(--surface-muted);
  border-top-color: var(--brand-primary);
  border-radius: 50%;
  animation: cp-spin 0.7s linear infinite;
}

@keyframes cp-spin {
  to { transform: rotate(360deg); }
}

.cp-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px 4px 12px;
}

.cp-block {
  border: 1px solid var(--border-default);
  border-radius: 10px;
  background: #fff;
  padding: 12px 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.cp-block.chunk-preview__block--target {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 2px rgba(30, 78, 124, 0.15);
  background: rgba(30, 78, 124, 0.03);
}

.cp-block__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.cp-block__no {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.cp-block__tag {
  font-size: 0.66rem;
  font-weight: 700;
  color: var(--brand-primary);
  background: rgba(30, 78, 124, 0.1);
  padding: 1px 8px;
  border-radius: 100px;
  letter-spacing: 0.04em;
}

.cp-block__text {
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--text-primary);
  word-break: break-word;
}
</style>

<!-- 非 scoped：分块文本是 markdown（含 LaTeX），用与消息一致的样式渲染 -->
<style>
.cp-block__text p {
  margin: 6px 0;
}

.cp-block__text h1,
.cp-block__text h2,
.cp-block__text h3,
.cp-block__text h4 {
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  font-weight: 700;
  color: var(--text-primary);
  margin: 10px 0 6px;
}

.cp-block__text h1 { font-size: 1.15rem; }
.cp-block__text h2 { font-size: 1.05rem; }
.cp-block__text h3 { font-size: 0.98rem; }
.cp-block__text h4 { font-size: 0.92rem; }

.cp-block__text code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.84em;
  padding: 1px 6px;
  background: rgba(27, 43, 36, 0.06);
  border-radius: 4px;
  color: var(--brand-primary-dark);
}

.cp-block__text pre {
  margin: 8px 0;
  padding: 12px 14px;
  background: #0F1A14;
  border-radius: 8px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  color: #C8D8E8;
}

.cp-block__text pre code {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: inherit;
}

.cp-block__text ul,
.cp-block__text ol {
  margin: 6px 0;
  padding-left: 22px;
}

.cp-block__text ul { list-style: disc; }
.cp-block__text ol { list-style: decimal; }

.cp-block__text table {
  width: 100%;
  margin: 8px 0;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.cp-block__text th,
.cp-block__text td {
  padding: 6px 10px;
  border: 1px solid var(--border-default);
  text-align: left;
}

.cp-block__text img {
  max-width: 100%;
  border-radius: 6px;
}
</style>
