<script setup lang="ts">
import type {
  AssistantCitationItem,
} from '@/types/assistant'

defineProps<{
  citations: AssistantCitationItem[]
}>()

const emit = defineEmits<{
  inspect: [citation: AssistantCitationItem]
}>()

function formatScore(score: number): string {
  if (!Number.isFinite(score)) return '--'
  return (score * 100).toFixed(1) + '%'
}

function fileTag(fileName: string): string {
  const ext = (fileName ?? '').toLowerCase().split('.').pop() ?? ''
  if (ext === 'pdf') return 'PDF'
  if (ext === 'md') return 'MD'
  if (ext === 'docx' || ext === 'doc') return 'DOC'
  if (ext === 'txt') return 'TXT'
  return ext.toUpperCase() || 'DOC'
}

function tagClass(fileName: string): string {
  const ext = (fileName ?? '').toLowerCase().split('.').pop() ?? ''
  if (ext === 'pdf') return 'citebar__type--pdf'
  if (ext === 'md') return 'citebar__type--md'
  if (ext === 'docx' || ext === 'doc') return 'citebar__type--doc'
  return 'citebar__type--txt'
}
</script>

<template>
  <div class="citebar">
    <header class="citebar__head">
      <span class="citebar__eyebrow">Evidence Chain</span>
      <span class="citebar__title">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
        <strong>引用证据</strong>
        <span class="citebar__count">{{ citations.length }}</span>
      </span>
    </header>

    <div class="citebar__scroll">
      <button
        v-for="(c, idx) in citations"
        :key="`${c.documentId ?? 'x'}-${c.chunkId ?? idx}`"
        class="citebar__card"
        type="button"
        :disabled="c.documentId == null"
        @click="c.documentId != null && emit('inspect', c)"
      >
        <div class="citebar__card-head">
          <span class="citebar__index">{{ String(idx + 1).padStart(2, '0') }}</span>
          <span class="citebar__type" :class="tagClass(c.fileName)">{{ fileTag(c.fileName) }}</span>
          <span class="citebar__score">{{ formatScore(c.score) }}</span>
        </div>
        <h4 class="citebar__filename" :title="c.fileName">
          {{ c.fileName ?? '未知文件' }}
        </h4>
        <div class="citebar__card-foot">
          <span v-if="c.chunkIndex != null" class="citebar__chunk">片段 #{{ c.chunkIndex }}</span>
          <div class="citebar__meter">
            <span class="citebar__meter-fill" :style="{ width: `${Math.min(100, (c.score || 0) * 100)}%` }" />
          </div>
          <span class="citebar__score">{{ formatScore(c.score) }}</span>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.citebar {
  margin-top: 14px;
  padding: 14px 0 4px;
  border-top: 1px dashed rgba(15, 23, 42, 0.1);
}

.citebar__head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 10px;
  padding-left: 2px;
}

.citebar__eyebrow {
  font-family: 'Poppins', sans-serif;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brand-primary);
}

.citebar__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.citebar__title svg {
  color: var(--brand-primary);
}

.citebar__title strong {
  font-weight: 600;
  color: var(--text-primary);
}

.citebar__count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  background: rgba(148, 163, 184, 0.14);
  padding: 1px 7px;
  border-radius: 100px;
}

.citebar__scroll {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 4px 2px 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--border-default) transparent;
}

.citebar__scroll::-webkit-scrollbar {
  height: 6px;
}

.citebar__scroll::-webkit-scrollbar-thumb {
  background: var(--border-default);
  border-radius: 3px;
}

.citebar__card {
  flex-shrink: 0;
  width: 260px;
  padding: 12px 14px 12px;
  background: #fff;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
  position: relative;
  overflow: hidden;
}

.citebar__card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 2px;
  height: 100%;
  background: linear-gradient(to bottom, var(--brand-primary), var(--brand-accent));
  opacity: 0;
  transition: opacity 0.2s ease;
}

.citebar__card:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: var(--brand-primary);
  box-shadow: 0 8px 20px rgba(74, 144, 217, 0.12);
}

.citebar__card:hover:not(:disabled)::before {
  opacity: 1;
}

.citebar__card:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.citebar__card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.citebar__index {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.citebar__type {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 7px;
  border-radius: 4px;
}

.citebar__type--pdf {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.citebar__type--md {
  background: rgba(74, 144, 217, 0.1);
  color: var(--brand-primary);
}

.citebar__type--doc {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.citebar__type--txt {
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
}

.citebar__score {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--brand-accent-dark);
}

.citebar__filename {
  margin: 0 0 6px;
  font-family: 'Poppins', 'Noto Sans SC', sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.citebar__card-foot {
  display: flex;
  align-items: center;
  gap: 10px;
}

.citebar__chunk {
  flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.66rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--surface-subtle);
  padding: 1px 6px;
  border-radius: 4px;
}

.citebar__meter {
  flex: 1;
  height: 3px;
  background: var(--surface-muted);
  border-radius: 2px;
  overflow: hidden;
}

.citebar__meter-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
  border-radius: 2px;
  transition: width 0.3s ease;
}
</style>
