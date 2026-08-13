<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { fetchGroups } from '@/api/group'
import {
  streamAskQuestion,
  fetchMyQaHistory,
  fetchMyQaHistoryDetail,
  deleteMyQaHistory,
  type CitationItem,
  type CitationMeta,
} from '@/api/qa'
import type { QaHistoryDetail, QaHistoryItem, QaHistoryMessage } from '@/api/admin'
import { extractApiError } from '@/api/http'
import ChunkPreviewModal from '@/components/ChunkPreviewModal.vue'
import QaSidebar from './components/QaSidebar.vue'
import QaTranscript from './components/QaTranscript.vue'
import QaComposer from './components/QaComposer.vue'
import QaEmptyHero from './components/QaEmptyHero.vue'
import { useQaSessions, type QaMessage } from './composables/useQaSessions'

const appStore = useAppStore()
const authStore = useAuthStore()
const {
  sessions,
  activeSession,
  activeSessionId,
  createSession,
  selectSession,
  deleteSession,
  appendMessage,
  updateMessage,
  uid,
} = useQaSessions()

// ── Group state ──
const groupsLoading = ref(false)
const groupsError = ref('')
const selectedGroupId = ref<number | null>(appStore.currentGroupId)

const selectedGroupName = computed(() => {
  const g = appStore.visibleGroups.find((x) => x.groupId === selectedGroupId.value)
  return g?.groupName ?? ''
})

const hasGroup = computed(() => selectedGroupId.value !== null)

async function loadGroups() {
  groupsLoading.value = true
  groupsError.value = ''
  try {
    const result = await fetchGroups()
    appStore.applyGroupQueryResult(result)
    if (selectedGroupId.value === null || !appStore.visibleGroups.some((g) => g.groupId === selectedGroupId.value)) {
      selectedGroupId.value = appStore.currentGroupId ?? appStore.visibleGroups[0]?.groupId ?? null
    }
  } catch (err) {
    groupsError.value = extractApiError(err, '加载群组失败')
  } finally {
    groupsLoading.value = false
  }
}

watch(selectedGroupId, (v) => {
  appStore.setCurrentGroupId(v)
  // If active session is bound to a different group, leave it intact — user may be reviewing history.
  // When the user asks a new question, we'll rebind if needed.
})

// ── Ask flow ──
const asking = ref(false)
let askAbort: AbortController | null = null

// ── Cloud history (read-only review of persisted QA sessions) ──
const historyItems = ref<QaHistoryItem[]>([])
const historyLoading = ref(false)
const historyOpen = ref(false)
const viewingHistory = ref(false)
const viewingHistoryId = ref<number | null>(null)
const historyMessages = ref<QaMessage[]>([])
const historyGroupId = ref<number | null>(null)

function toQaMessage(m: QaHistoryMessage): QaMessage {
  return {
    id: `h-${m.messageId}`,
    role: m.role === 'USER' ? 'user' : 'assistant',
    content: m.content,
    createdAt: m.createdAt ? new Date(m.createdAt).getTime() : Date.now(),
    answered: m.role === 'ASSISTANT' ? m.content.length > 0 : undefined,
    reasonCode: m.reasonCode,
    reasonMessage: m.reasonMessage,
    citations: m.citations ?? [],
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const result = await fetchMyQaHistory(1, 50)
    historyItems.value = result.items
  } catch (err) {
    console.error('Load QA history failed:', extractApiError(err, ''))
  } finally {
    historyLoading.value = false
  }
}

async function handleSelectHistory(sessionId: number) {
  try {
    const detail = await fetchMyQaHistoryDetail(sessionId)
    historyMessages.value = detail.messages.map(toQaMessage)
    historyGroupId.value = detail.groupId
    viewingHistoryId.value = sessionId
    viewingHistory.value = true
  } catch (err) {
    console.error('Load QA history detail failed:', extractApiError(err, ''))
  }
}

async function handleDeleteHistory(sessionId: number) {
  try {
    await deleteMyQaHistory(sessionId)
    historyItems.value = historyItems.value.filter((i) => i.sessionId !== sessionId)
    if (viewingHistoryId.value === sessionId) {
      exitHistory()
    }
  } catch (err) {
    console.error('Delete QA history failed:', extractApiError(err, ''))
  }
}

function exitHistory() {
  viewingHistory.value = false
  viewingHistoryId.value = null
  historyMessages.value = []
  historyGroupId.value = null
}

function ensureSessionForAsk(): string {
  if (activeSession.value && activeSession.value.groupId === selectedGroupId.value) {
    return activeSession.value.id
  }
  // If active session is for a different group OR no active session, create a new one
  const s = createSession(selectedGroupId.value, selectedGroupName.value)
  return s.id
}

function appendTargetMessage(sid: string, msg: QaMessage) {
  if (viewingHistory.value) {
    historyMessages.value.push(msg)
  } else {
    appendMessage(sid, msg)
  }
}

function updateTargetMessage(sid: string, mid: string, patch: Partial<QaMessage>) {
  if (viewingHistory.value) {
    const m = historyMessages.value.find((x) => x.id === mid)
    if (m) Object.assign(m, patch)
  } else {
    updateMessage(sid, mid, patch)
  }
}

async function handleAsk(text: string) {
  if (!text.trim() || selectedGroupId.value === null || asking.value) return
  if (!authStore.accessToken) {
    console.warn('No access token; cannot stream.')
    return
  }

  // 云端历史续聊：消息追加到 historyMessages，后端追加到同一 qa_session
  const isHistory = viewingHistory.value
  const sessionId = isHistory ? String(viewingHistoryId.value) : ensureSessionForAsk()
  const now = Date.now()

  // Push user message
  const userMsg: QaMessage = {
    id: uid(),
    role: 'user',
    content: text,
    createdAt: now,
  }
  appendTargetMessage(sessionId, userMsg)

  // Push pending assistant message
  const assistantId = uid()
  appendTargetMessage(sessionId, {
    id: assistantId,
    role: 'assistant',
    content: '',
    createdAt: Date.now(),
    pending: true,
  })

  asking.value = true
  askAbort = new AbortController()
  let streamedContent = ''
  let answerReceived = false
  // 声明在 try 外：闭包内赋值 + try 内读取会触发 TS 控制流分析的 never 收窄
  let refused: CitationMeta | null = null
  try {
    await streamAskQuestion(
      {
        groupId: selectedGroupId.value,
        question: text,
        sessionId: isHistory ? viewingHistoryId.value : null,
      },
      authStore.accessToken!,
      {
        signal: askAbort.signal,
        onToken(token: string) {
          streamedContent += token
          updateTargetMessage(sessionId, assistantId, {
            content: streamedContent,
            pending: true,
          })
        },
        onAnswer(answer: string) {
          answerReceived = true
          streamedContent = answer
          updateTargetMessage(sessionId, assistantId, {
            content: answer,
            pending: true,
          })
        },
        onCitations(citations: CitationItem[], meta?: CitationMeta) {
          refused = meta?.reasonCode ? { reasonCode: meta.reasonCode, reasonMessage: meta.reasonMessage ?? null } : null
          updateTargetMessage(sessionId, assistantId, {
            content: streamedContent,
            pending: false,
            answered: citations.length > 0 || streamedContent.length > 0,
            reasonCode: refused?.reasonCode ?? null,
            reasonMessage: refused?.reasonMessage ?? null,
            citations,
          })
        },
        onError(message: string) {
          updateTargetMessage(sessionId, assistantId, {
            content: streamedContent,
            pending: false,
            answered: false,
            reasonCode: 'STREAM_ERROR',
            reasonMessage: message,
            citations: [],
          })
        },
      },
    )

    // 兜底：没有收到 answer 事件时（解析失败），显示原始内容
    if (!answerReceived) {
      updateTargetMessage(sessionId, assistantId, {
        content: streamedContent,
        pending: false,
        answered: refused ? false : streamedContent.length > 0,
        // refused 在回调闭包中赋值，TS 控制流分析会将其收窄为 never，
        // 用显式断言绕开（运行时值始终是 CitationMeta | null）
        reasonCode: (refused as CitationMeta | null)?.reasonCode ?? null,
        reasonMessage: (refused as CitationMeta | null)?.reasonMessage ?? null,
        citations: [],
      })
    }
  } catch (err) {
    const isAbort = (err as { name?: string })?.name === 'AbortError'
    updateTargetMessage(sessionId, assistantId, {
      content: streamedContent,
      pending: false,
      answered: isAbort ? streamedContent.length > 0 : false,
      reasonCode: isAbort ? 'INTERRUPTED' : 'REQUEST_FAILED',
      reasonMessage: isAbort ? '已停止生成' : extractApiError(err, '请求失败，请稍后再试'),
      citations: [],
    })
  } finally {
    asking.value = false
    askAbort = null
  }
}

function stopAsking() {
  askAbort?.abort()
}

function handleNewChat() {
  exitHistory()
  createSession(selectedGroupId.value, selectedGroupName.value)
}

const composerRef = ref<InstanceType<typeof QaComposer> | null>(null)

function handleStarterPick(prompt: string) {
  composerRef.value?.setText(prompt)
}

// ── Citation preview bridge（复用助手侧分块预览：定位并高亮被引用片段）──
const chunkPreviewVisible = ref(false)
const chunkPreviewDoc = ref<{
  documentId: number
  fileName: string
  chunkId: number | null
  chunkIndex: number | null
} | null>(null)

function openCitation(c: CitationItem) {
  if (c.documentId == null) return
  chunkPreviewDoc.value = {
    documentId: c.documentId,
    fileName: c.fileName,
    chunkId: c.chunkId,
    chunkIndex: c.chunkIndex,
  }
  chunkPreviewVisible.value = true
}

// ── Lifecycle ──
onMounted(() => {
  if (appStore.visibleGroups.length === 0) {
    loadGroups()
  } else if (selectedGroupId.value === null) {
    selectedGroupId.value = appStore.visibleGroups[0]?.groupId ?? null
  }
  loadHistory()
})
</script>

<template>
  <div class="qa-page">
    <QaSidebar
      v-model:selected-group-id="selectedGroupId"
      :groups="appStore.visibleGroups"
      :groups-loading="groupsLoading"
      :sessions="sessions"
      :active-session-id="activeSessionId"
      :history-items="historyItems"
      :history-loading="historyLoading"
      :viewing-history-id="viewingHistoryId"
      @new-chat="handleNewChat"
      @select-session="selectSession"
      @delete-session="deleteSession"
      @view-history="handleSelectHistory"
      @delete-history="handleDeleteHistory"
    />

    <main class="qa-page__main">
      <template v-if="viewingHistory && historyMessages.length > 0">
        <QaTranscript
          :messages="historyMessages"
          session-id="history"
          :group-name="'历史记录'"
          @inspect-citation="openCitation"
        />
      </template>
      <template v-else-if="activeSession && activeSession.messages.length > 0">
        <QaTranscript
          :messages="activeSession.messages"
          :session-id="activeSession.id"
          :group-name="activeSession.groupName"
          @inspect-citation="openCitation"
        />
      </template>
      <template v-else>
        <QaEmptyHero
          :group-name="selectedGroupName"
          :has-group="hasGroup"
          @pick="handleStarterPick"
        />
      </template>

      <QaComposer
        ref="composerRef"
        :disabled="!hasGroup"
        :loading="asking"
        :group-name="selectedGroupName"
        @submit="handleAsk"
        @stop="stopAsking"
      />
    </main>

    <ChunkPreviewModal
      :visible="chunkPreviewVisible"
      :document-id="chunkPreviewDoc?.documentId ?? null"
      :file-name="chunkPreviewDoc?.fileName ?? ''"
      :chunk-id="chunkPreviewDoc?.chunkId ?? null"
      :chunk-index="chunkPreviewDoc?.chunkIndex ?? null"
      @update:visible="(v: boolean) => (chunkPreviewVisible = v)"
    />
  </div>
</template>

<style scoped>
.qa-page {
  display: flex;
  height: calc(100vh - 80px);
  min-height: 560px;
  background: #fff;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
}

.qa-page__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
}

.qa-page__main > :first-child {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.qa-page__main > :last-child {
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .qa-page {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
    border-radius: 0;
  }
}
</style>
