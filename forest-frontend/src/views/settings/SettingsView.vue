<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { extractApiError } from '@/api/http'

const router = useRouter()
const authStore = useAuthStore()

const mustChange = computed(() => authStore.currentUser?.mustChangePassword ?? false)

// ── Password section ──
const passwordExpanded = ref(mustChange.value)

// ── Password form ──
const pwForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const pwLoading = ref(false)
const pwError = ref('')
const pwSuccess = ref('')

async function handleChangePassword() {
  pwError.value = ''; pwSuccess.value = ''
  if (!pwForm.currentPassword.trim() || !pwForm.newPassword.trim() || !pwForm.confirmPassword.trim()) { pwError.value = '请填写所有密码字段'; return }
  if (pwForm.newPassword.length < 6) { pwError.value = '新密码长度至少 6 个字符'; return }
  if (pwForm.newPassword !== pwForm.confirmPassword) { pwError.value = '两次输入的新密码不一致'; return }
  if (pwForm.currentPassword === pwForm.newPassword) { pwError.value = '新密码不能与当前密码相同'; return }
  pwLoading.value = true
  try {
    await authStore.changePassword({ currentPassword: pwForm.currentPassword, newPassword: pwForm.newPassword })
    pwForm.currentPassword = ''; pwForm.newPassword = ''; pwForm.confirmPassword = ''
    pwSuccess.value = '密码修改成功'
    if (mustChange.value) setTimeout(() => router.push(authStore.homePath), 1200)
  } catch (err) { pwError.value = extractApiError(err, '修改密码失败') }
  finally { pwLoading.value = false }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>系统设置</h1>
      <p>管理您的账号安全与偏好</p>
    </div>

    <!-- 强制修改密码提示 -->
    <div v-if="mustChange" class="must-change-banner">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/><path d="M12 8V12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="16" r="0.5" fill="currentColor" stroke="none"/></svg>
      <span>出于安全考虑，您需要先修改密码后才能继续使用系统</span>
    </div>

    <!-- ── 账号安全与密码管理 ── -->
    <div class="settings-section">
      <button class="section-trigger" :class="{ expanded: passwordExpanded }" @click="passwordExpanded = !passwordExpanded">
        <span class="section-trigger__icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg></span>
        <span class="section-trigger__text"><span class="section-trigger__title">账号安全与密码管理</span><span class="section-trigger__desc">修改登录密码，保护账号安全</span></span>
        <svg class="section-trigger__chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9" /></svg>
      </button>
      <div v-if="passwordExpanded" class="section-body">
        <form class="pw-form" @submit.prevent="handleChangePassword">
          <div class="input-group"><label>当前密码</label><input v-model="pwForm.currentPassword" type="password" placeholder="输入当前密码" autocomplete="current-password" /></div>
          <div class="input-group"><label>新密码</label><input v-model="pwForm.newPassword" type="password" placeholder="输入新密码（至少 6 位）" autocomplete="new-password" /></div>
          <div class="input-group"><label>确认新密码</label><input v-model="pwForm.confirmPassword" type="password" placeholder="再次输入新密码" autocomplete="new-password" /></div>
          <p v-if="pwError" class="form-error">{{ pwError }}</p>
          <p v-if="pwSuccess" class="form-success">{{ pwSuccess }}</p>
          <button type="submit" class="btn-submit" :disabled="pwLoading">{{ pwLoading ? '保存中...' : '保存修改' }}</button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 24px; font-weight: 800; color: var(--text-primary); margin-bottom: 4px; }
.page-header p { font-size: 14px; color: var(--text-secondary); margin: 0; }

.must-change-banner { display: flex; align-items: center; gap: 10px; padding: 14px 18px; background: linear-gradient(135deg, rgba(245,158,11,0.08), rgba(245,158,11,0.03)); border: 1px solid rgba(245,158,11,0.2); border-radius: var(--radius-sm); color: #b45309; font-size: 14px; font-weight: 500; margin-bottom: 24px; }
.must-change-banner svg { flex-shrink: 0; color: #f59e0b; }

.settings-section { max-width: 620px; }
.section-trigger { display: flex; align-items: center; gap: 14px; width: 100%; padding: 18px 20px; background: var(--surface-white); border: 1px solid var(--border-default); border-radius: var(--radius-md); cursor: pointer; font-family: inherit; text-align: left; transition: all .2s ease; box-shadow: 0 1px 3px rgba(0,0,0,.03); }
.section-trigger:hover { border-color: var(--brand-primary); box-shadow: 0 4px 12px rgba(74,144,217,.08); }
.section-trigger.expanded { border-radius: var(--radius-md) var(--radius-md) 0 0; border-bottom-color: transparent; }
.section-trigger__icon { display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: rgba(74,144,217,.08); color: var(--brand-primary); flex-shrink: 0; }
.section-trigger__text { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.section-trigger__title { font-size: .95rem; font-weight: 700; color: var(--text-primary); }
.section-trigger__desc { font-size: .78rem; color: var(--text-muted); }
.section-trigger__chevron { color: var(--text-muted); flex-shrink: 0; transition: transform .25s ease; }
.section-trigger.expanded .section-trigger__chevron { transform: rotate(180deg); }
.section-body { background: var(--surface-white); border: 1px solid var(--border-default); border-top: none; border-radius: 0 0 var(--radius-md) var(--radius-md); padding: 0 20px 24px; animation: section-in .25s ease; }
@keyframes section-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }

.pw-form { display: flex; flex-direction: column; gap: 16px; }
.input-group { display: flex; flex-direction: column; gap: 5px; }
.input-group label { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.input-group input { padding: 10px 13px; border: 1.5px solid var(--border-default); border-radius: var(--radius-sm); font-size: 14px; font-family: inherit; color: var(--text-primary); background: var(--surface-white); transition: border-color .2s ease, box-shadow .2s ease; outline: none; }
.input-group input::placeholder { color: #94a3b8; }
.input-group input:focus { border-color: var(--brand-primary); box-shadow: 0 0 0 3px rgba(74,144,217,.1); }
.form-error { font-size: 13px; color: var(--el-color-danger); margin: 0; }
.form-success { font-size: 13px; color: var(--el-color-success); margin: 0; }
.btn-submit { padding: 11px 24px; border-radius: var(--radius-sm); background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)); color: #fff; font-size: 14px; font-weight: 600; border: none; cursor: pointer; transition: all .2s ease; box-shadow: 0 4px 14px rgba(74,144,217,.25); margin-top: 4px; }
.btn-submit:hover:not(:disabled) { box-shadow: 0 6px 20px rgba(74,144,217,.35); transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
