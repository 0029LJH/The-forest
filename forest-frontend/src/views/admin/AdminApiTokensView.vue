<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createAdminApiToken,
  fetchAdminApiTokens,
  revokeAdminApiToken,
  type ApiTokenItem,
  type ApiTokenScope,
  type CreatedApiToken,
} from '@/api/apiToken'
import { fetchAdminUsers, type AdminUserItem } from '@/api/admin-user'
import { fetchAdminGroups, type AdminGroupItem } from '@/api/admin'
import { extractApiError } from '@/api/http'

const SCOPE_LABELS: Record<ApiTokenScope, string> = {
  qa: '知识库问答',
  groups_read: '群组信息读取',
  documents_read: '文档读取',
}

const items = ref<ApiTokenItem[]>([])
const loading = ref(false)
const userFilter = ref<number | null>(null)

const users = ref<AdminUserItem[]>([])
const groups = ref<AdminGroupItem[]>([])

// ── 列表 ──

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function userNameOf(item: ApiTokenItem): string {
  return item.displayName || item.username || `#${item.userId}`
}

function groupText(item: ApiTokenItem): string {
  if (item.groupIds == null) return '全部群组'
  return `${item.groupIds.length} 个群组`
}

async function load() {
  loading.value = true
  try {
    items.value = await fetchAdminApiTokens(userFilter.value)
  } catch (err) {
    ElMessage.error(extractApiError(err, '加载令牌列表失败'))
    items.value = []
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    ;[users.value, groups.value] = await Promise.all([
      fetchAdminUsers(),
      fetchAdminGroups().then((gs) => gs.filter((g) => g.status === 'ACTIVE')),
    ])
  } catch (err) {
    ElMessage.error(extractApiError(err, '加载用户/群组列表失败'))
  }
}

async function onRevoke(row: ApiTokenItem) {
  try {
    await ElMessageBox.confirm(
      `确定吊销令牌「${row.name}」（${row.tokenPrefix}）？吊销后使用该令牌的调用将立即失效。`,
      '吊销令牌',
      { type: 'warning', confirmButtonText: '吊销', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await revokeAdminApiToken(row.tokenId)
    ElMessage.success('令牌已吊销')
    load()
  } catch (err) {
    ElMessage.error(extractApiError(err, '吊销失败'))
  }
}

// ── 创建 ──

const createVisible = ref(false)
const creating = ref(false)
const form = ref({
  userId: null as number | null,
  name: '',
  scopes: [] as ApiTokenScope[],
  groupIds: [] as number[],
  expiresInDays: 0, // 0 = 永久
})

const expiryOptions = [
  { value: 0, label: '永久有效' },
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天' },
  { value: 365, label: '365 天' },
]

function openCreate() {
  form.value = { userId: null, name: '', scopes: [], groupIds: [], expiresInDays: 0 }
  createVisible.value = true
}

async function onCreate() {
  if (form.value.userId == null) {
    ElMessage.warning('请选择令牌归属的用户')
    return
  }
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入令牌名称')
    return
  }
  if (form.value.scopes.length === 0) {
    ElMessage.warning('请至少选择一个权限范围')
    return
  }
  creating.value = true
  try {
    const result = await createAdminApiToken({
      userId: form.value.userId,
      name: form.value.name.trim(),
      scopes: form.value.scopes,
      groupIds: form.value.groupIds.length > 0 ? form.value.groupIds : null,
      expiresInDays: form.value.expiresInDays > 0 ? form.value.expiresInDays : null,
    })
    createVisible.value = false
    showToken(result)
    load()
  } catch (err) {
    ElMessage.error(extractApiError(err, '创建失败'))
  } finally {
    creating.value = false
  }
}

// ── 一次性展示完整 token ──

const tokenVisible = ref(false)
const created = ref<CreatedApiToken | null>(null)
const copied = ref(false)

function showToken(result: CreatedApiToken) {
  created.value = result
  copied.value = false
  tokenVisible.value = true
}

async function copyToken() {
  if (!created.value) return
  try {
    await navigator.clipboard.writeText(created.value.token)
    copied.value = true
    setTimeout(() => (copied.value = false), 2500)
  } catch {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

function closeToken() {
  tokenVisible.value = false
  created.value = null
}

const createDialogTitle = computed(() => '创建 API 令牌')

onMounted(() => {
  load()
  loadOptions()
})
</script>

<template>
  <div class="apitoken-page">
    <div class="page-header">
      <h1>API 令牌</h1>
      <p>为外部系统签发知识库访问令牌（细粒度权限 + 可选群组白名单），管理员代管</p>
      <el-button type="primary" @click="openCreate">创建令牌</el-button>
    </div>

    <div class="filter-bar">
      <el-select
        v-model="userFilter"
        style="width: 220px"
        clearable
        filterable
        placeholder="全部用户"
        @change="load"
      >
        <el-option
          v-for="u in users"
          :key="u.userId"
          :label="`${u.displayName || u.username} (${u.username})`"
          :value="u.userId"
        />
      </el-select>
    </div>

    <div class="table-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="tokenPrefix" label="令牌" width="140">
          <template #default="{ row }">
            <code class="token-prefix">{{ row.tokenPrefix }}</code>
          </template>
        </el-table-column>
        <el-table-column label="归属用户" width="140">
          <template #default="{ row }">
            {{ userNameOf(row) }}
          </template>
        </el-table-column>
        <el-table-column label="权限" min-width="220">
          <template #default="{ row }">
            <span v-for="s in row.scopes" :key="s" class="scope-tag">{{ SCOPE_LABELS[s as keyof typeof SCOPE_LABELS] ?? s }}</span>
          </template>
        </el-table-column>
        <el-table-column label="群组范围" width="110">
          <template #default="{ row }">
            <span class="group-tag" :class="{ 'group-tag--all': row.groupIds == null }">
              {{ groupText(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-tag" :class="row.status === 'ACTIVE' ? 'status-tag--active' : 'status-tag--revoked'">
              {{ row.status === 'ACTIVE' ? '有效' : '已吊销' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="有效期至" width="140">
          <template #default="{ row }">{{ row.expiresAt ? formatTime(row.expiresAt) : '永久' }}</template>
        </el-table-column>
        <el-table-column label="最近使用" width="140">
          <template #default="{ row }">{{ row.lastUsedAt ? formatTime(row.lastUsedAt) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'ACTIVE'"
              link
              type="danger"
              @click="onRevoke(row)"
            >
              吊销
            </el-button>
            <span v-else class="revoked-text">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建对话框 -->
    <el-dialog v-model="createVisible" :title="createDialogTitle" width="520px">
      <el-form label-width="90px" @submit.prevent>
        <el-form-item label="归属用户" required>
          <el-select v-model="form.userId" filterable placeholder="选择令牌代表的用户" style="width: 100%">
            <el-option
              v-for="u in users"
              :key="u.userId"
              :label="`${u.displayName || u.username} (${u.username})`"
              :value="u.userId"
              :disabled="u.status !== 'ACTIVE'"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="64" placeholder="例如：CI 流水线 / 数据同步脚本" />
        </el-form-item>
        <el-form-item label="权限范围" required>
          <el-checkbox-group v-model="form.scopes">
            <el-checkbox value="qa">知识库问答（/api/open/qa/ask）</el-checkbox>
            <el-checkbox value="groups_read">群组信息读取</el-checkbox>
            <el-checkbox value="documents_read">文档读取（列表/下载）</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="群组范围">
          <el-select
            v-model="form.groupIds"
            multiple
            filterable
            collapse-tags
            placeholder="不选择 = 该用户可访问的全部群组"
            style="width: 100%"
          >
            <el-option
              v-for="g in groups"
              :key="g.groupId"
              :label="g.groupName"
              :value="g.groupId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="form.expiresInDays" style="width: 100%">
            <el-option v-for="opt in expiryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 完整 token 一次性展示 -->
    <el-dialog
      v-model="tokenVisible"
      title="令牌创建成功"
      width="560px"
      :close-on-click-modal="false"
      @closed="closeToken"
    >
      <div v-if="created" class="token-once">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>完整 token 仅显示这一次，关闭后无法再次查看，请立即复制保存</template>
        </el-alert>
        <div class="token-once__box">
          <code class="token-once__code">{{ created.token }}</code>
          <el-button :type="copied ? 'success' : 'primary'" size="small" @click="copyToken">
            {{ copied ? '已复制' : '复制' }}
          </el-button>
        </div>
        <div class="token-once__meta">
          <span>名称：{{ created.name }}</span>
          <span>权限：{{ created.scopes.map((s) => SCOPE_LABELS[s as keyof typeof SCOPE_LABELS] ?? s).join('、') }}</span>
          <span>群组：{{ created.groupIds == null ? '全部群组' : `${created.groupIds.length} 个群组` }}</span>
          <span>有效期至：{{ created.expiresAt ? formatTime(created.expiresAt) : '永久' }}</span>
        </div>
        <div class="token-once__hint">
          调用示例：<code>curl -H "Authorization: Bearer {{ created.token }}" http://localhost:10001/api/open/me</code>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="tokenVisible = false">我已保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.apitoken-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h1 {
  font-size: 20px;
  margin: 0;
}

.page-header p {
  flex: 1;
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
}

.filter-bar {
  margin-bottom: 12px;
}

.table-card {
  background: #fff;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 12px;
}

.token-prefix {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.scope-tag {
  display: inline-block;
  margin: 2px 4px 2px 0;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--brand-primary);
  background: rgba(74, 144, 217, 0.1);
  border-radius: 100px;
}

.group-tag {
  font-size: 12px;
  color: var(--text-secondary);
}

.group-tag--all {
  color: var(--text-muted);
}

.status-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 100px;
}

.status-tag--active {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.status-tag--revoked {
  color: var(--text-muted);
  background: var(--surface-muted);
}

.revoked-text {
  color: var(--text-muted);
  font-size: 12px;
}

.token-once__box {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0;
  padding: 12px 14px;
  background: var(--surface-muted);
  border: 1px dashed var(--border-default);
  border-radius: 8px;
}

.token-once__code {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  word-break: break-all;
  user-select: all;
}

.token-once__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.token-once__hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.token-once__hint code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  background: var(--surface-muted);
  padding: 1px 6px;
  border-radius: 4px;
  word-break: break-all;
}
</style>
