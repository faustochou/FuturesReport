<template>
  <main class="admin-page">
    <section class="admin-header">
      <button class="back-btn" type="button" @click="router.push('/')">←</button>
      <div>
        <p class="eyebrow">Admin Console</p>
        <h1>後台管理系統</h1>
      </div>
      <button v-if="admin" class="logout-btn" type="button" @click="logoutAdmin">登出</button>
    </section>

    <section v-if="!admin" class="login-panel">
      <h2>管理員登入</h2>
      <form class="form-grid" @submit.prevent="submitAdminLogin">
        <label>
          <span>管理員帳號</span>
          <input v-model.trim="loginForm.username" autocomplete="username" required />
        </label>
        <label>
          <span>管理員密碼</span>
          <input v-model="loginForm.password" autocomplete="current-password" type="password" required />
        </label>
        <button class="primary-btn" type="submit" :disabled="loading">
          {{ loading ? '登入中...' : '登入後台' }}
        </button>
      </form>
      <p class="hint">請使用第一個註冊的帳號登入後台；後續註冊者皆為一般用戶。</p>
      <p v-if="error" class="error-text">{{ error }}</p>
    </section>

    <section v-else class="admin-layout">
      <aside class="user-list">
        <div class="section-title">
          <div>
            <p class="eyebrow">Registered Users</p>
            <h2>註冊用戶列表</h2>
          </div>
          <button class="icon-btn" type="button" title="Refresh" @click="loadUsers">↻</button>
        </div>

        <label class="search-box">
          <span>搜尋</span>
          <input v-model.trim="query" placeholder="username / provider / model" />
        </label>

        <div class="users-table">
          <button
            v-for="user in filteredUsers"
            :key="user.user_id"
            class="user-row"
            :class="{ active: selectedUser?.user_id === user.user_id }"
            type="button"
            @click="selectUser(user)"
          >
            <span>
              <strong>{{ user.username }}</strong>
              <small>{{ user.user_id }}</small>
            </span>
            <span class="pill" :class="{ ready: user.llm_configured }">
              {{ user.llm_configured ? 'LLM 已設定' : '未設定' }}
            </span>
          </button>
        </div>
      </aside>

      <section class="editor-panel">
        <template v-if="selectedUser">
          <div class="section-title">
            <div>
              <p class="eyebrow">Edit User</p>
              <h2>編輯 {{ selectedUser.username }}</h2>
            </div>
            <span class="pill ready" v-if="selectedUser.llm_configured">API Key: {{ selectedUser.llm?.api_key_hint }}</span>
          </div>

          <form class="editor-form" @submit.prevent="saveUser">
            <label>
              <span>用戶名稱</span>
              <input v-model.trim="editForm.username" required minlength="3" />
            </label>

            <label>
              <span>重設密碼</span>
              <input v-model="editForm.password" type="password" minlength="8" placeholder="留空代表不更改" />
            </label>

            <div class="divider"></div>

            <label>
              <span>LLM 服務商</span>
              <select v-model="editForm.llm.provider" @change="syncProviderDefaults">
                <option value="">不修改 / 未設定</option>
                <option v-for="(provider, key) in providers" :key="key" :value="key">
                  {{ provider.label }}
                </option>
              </select>
            </label>

            <label>
              <span>模型</span>
              <select v-if="currentModels.length" v-model="editForm.llm.model">
                <option v-for="model in currentModels" :key="model" :value="model">{{ model }}</option>
              </select>
              <input v-else v-model.trim="editForm.llm.model" />
            </label>

            <label>
              <span>Base URL</span>
              <input v-model.trim="editForm.llm.base_url" />
            </label>

            <label>
              <span>API Key</span>
              <input v-model="editForm.llm.api_key" type="password" placeholder="留空代表沿用原本 Key" />
            </label>

            <label class="check-row">
              <input v-model="editForm.llm.clear" type="checkbox" />
              <span>清除這位用戶的 LLM 設定</span>
            </label>

            <button class="primary-btn" type="submit" :disabled="loading">
              {{ loading ? '儲存中...' : '儲存變更' }}
            </button>
          </form>
          <p v-if="message" class="success-text">{{ message }}</p>
          <p v-if="error" class="error-text">{{ error }}</p>
        </template>

        <div v-else class="empty-state">
          <h2>選擇一位用戶</h2>
          <p>從左側列表選取註冊用戶後，可以編輯帳號與 LLM API 設定。</p>
        </div>
      </section>
    </section>

    <section v-if="admin" class="version-panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">Version Management</p>
          <h2>版本更新紀錄</h2>
        </div>
        <button class="icon-btn" type="button" title="Refresh versions" @click="loadVersions">↻</button>
      </div>

      <div class="version-list">
        <article v-for="item in versions" :key="`${item.version}-${item.commit}`" class="version-card">
          <div class="version-card-header">
            <div>
              <strong>{{ item.version }}</strong>
              <span>{{ item.date }}</span>
            </div>
            <code>{{ item.commit }}</code>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.summary }}</p>
          <div class="change-columns">
            <div class="change-column">
              <h4>新增</h4>
              <ul>
                <li v-for="change in item.added" :key="change">{{ change }}</li>
                <li v-if="!item.added?.length" class="muted">無</li>
              </ul>
            </div>
            <div class="change-column">
              <h4>修改</h4>
              <ul>
                <li v-for="change in item.modified" :key="change">{{ change }}</li>
                <li v-if="!item.modified?.length" class="muted">無</li>
              </ul>
            </div>
            <div class="change-column">
              <h4>刪除</h4>
              <ul>
                <li v-for="change in item.deleted" :key="change">{{ change }}</li>
                <li v-if="!item.deleted?.length" class="muted">無</li>
              </ul>
            </div>
          </div>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  adminLogin,
  getAdminAccessToken,
  getAdminMe,
  getAdminUsers,
  getVersionHistory,
  setAdminToken,
  updateAdminUser
} from '../api/admin'

const router = useRouter()
const admin = ref(null)
const users = ref([])
const providers = ref({})
const versions = ref([])
const selectedUser = ref(null)
const loading = ref(false)
const error = ref('')
const message = ref('')
const query = ref('')

const loginForm = reactive({
  username: '',
  password: ''
})

const editForm = reactive({
  username: '',
  password: '',
  llm: {
    provider: '',
    model: '',
    base_url: '',
    api_key: '',
    clear: false
  }
})

const currentProvider = computed(() => providers.value[editForm.llm.provider] || {})
const currentModels = computed(() => currentProvider.value.models || [])
const filteredUsers = computed(() => {
  const keyword = query.value.toLowerCase()
  if (!keyword) return users.value
  return users.value.filter(user => {
    const llm = user.llm || {}
    return [user.username, user.user_id, llm.provider, llm.model]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(keyword))
  })
})

const submitAdminLogin = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await adminLogin(loginForm)
    setAdminToken(res.data?.token)
    admin.value = res.data?.admin
    loginForm.password = ''
    await loadUsers()
    await loadVersions()
  } catch (err) {
    error.value = err.message || '後台登入失敗'
  } finally {
    loading.value = false
  }
}

const loadAdminSession = async () => {
  if (!getAdminAccessToken()) return
  try {
    const res = await getAdminMe()
    admin.value = res.data?.admin
    await loadUsers()
    await loadVersions()
  } catch {
    setAdminToken('')
    admin.value = null
  }
}

const loadUsers = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await getAdminUsers()
    users.value = res.data?.users || []
    providers.value = res.data?.providers || {}
    if (selectedUser.value) {
      const refreshed = users.value.find(user => user.user_id === selectedUser.value.user_id)
      if (refreshed) selectUser(refreshed)
    }
  } catch (err) {
    error.value = err.message || '讀取用戶列表失敗'
  } finally {
    loading.value = false
  }
}

const loadVersions = async () => {
  try {
    const res = await getVersionHistory()
    versions.value = res.data?.versions || []
  } catch (err) {
    error.value = err.message || '讀取版本紀錄失敗'
  }
}

const selectUser = (user) => {
  selectedUser.value = user
  editForm.username = user.username || ''
  editForm.password = ''
  editForm.llm.provider = user.llm?.provider || ''
  editForm.llm.model = user.llm?.model || ''
  editForm.llm.base_url = user.llm?.base_url || ''
  editForm.llm.api_key = ''
  editForm.llm.clear = false
}

const syncProviderDefaults = () => {
  const provider = currentProvider.value
  if (!provider) return
  editForm.llm.model = provider.default_model || provider.models?.[0] || editForm.llm.model
  editForm.llm.base_url = provider.base_url || editForm.llm.base_url
}

const saveUser = async () => {
  if (!selectedUser.value) return
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const payload = {
      username: editForm.username,
      password: editForm.password || undefined,
      llm: {
        provider: editForm.llm.provider,
        model: editForm.llm.model,
        base_url: editForm.llm.base_url,
        api_key: editForm.llm.api_key || undefined,
        clear: editForm.llm.clear
      }
    }
    const res = await updateAdminUser(selectedUser.value.user_id, payload)
    const updated = res.data?.user
    users.value = users.value.map(user => user.user_id === updated.user_id ? updated : user)
    selectUser(updated)
    message.value = '已儲存用戶設定'
  } catch (err) {
    error.value = err.message || '儲存失敗'
  } finally {
    loading.value = false
  }
}

const logoutAdmin = () => {
  setAdminToken('')
  admin.value = null
  users.value = []
  versions.value = []
  selectedUser.value = null
}

onMounted(loadAdminSession)
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 72px 32px 32px;
  background: #f6f6f1;
  color: #111;
  font-family: 'JetBrains Mono', 'Noto Sans TC', monospace;
}

.admin-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}

.admin-header h1,
.section-title h2,
.login-panel h2,
.empty-state h2 {
  margin: 0;
  letter-spacing: 0;
}

.eyebrow {
  margin: 0 0 4px;
  color: #666;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.back-btn,
.icon-btn,
.logout-btn,
.primary-btn {
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font-weight: 800;
  cursor: pointer;
}

.back-btn,
.icon-btn {
  width: 38px;
  height: 38px;
}

.logout-btn {
  min-height: 38px;
  padding: 0 14px;
}

.login-panel,
.user-list,
.editor-panel,
.version-panel {
  border: 1px solid #111;
  background: #fff;
  box-shadow: 6px 6px 0 #111;
}

.login-panel {
  max-width: 420px;
  padding: 20px;
}

.admin-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.user-list,
.editor-panel {
  padding: 18px;
}

.version-panel {
  margin-top: 18px;
  padding: 18px;
}

.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.form-grid,
.editor-form {
  display: grid;
  gap: 14px;
}

label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  font-weight: 800;
}

input,
select {
  width: 100%;
  min-height: 38px;
  border: 1px solid #111;
  border-radius: 0;
  padding: 8px 10px;
  background: #fff;
  color: #111;
  font: inherit;
  font-size: 13px;
}

.primary-btn {
  min-height: 40px;
  background: #111;
  color: #fff;
}

.primary-btn:disabled {
  opacity: 0.55;
  cursor: wait;
}

.hint,
.empty-state p {
  color: #666;
  font-size: 13px;
  line-height: 1.6;
}

.search-box {
  margin-bottom: 14px;
}

.users-table {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 260px);
  overflow: auto;
}

.user-row {
  min-height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px;
  border: 1px solid #ddd;
  background: #fff;
  color: #111;
  text-align: left;
  cursor: pointer;
}

.user-row.active {
  border-color: #111;
  box-shadow: 3px 3px 0 #111;
}

.user-row small {
  display: block;
  max-width: 180px;
  margin-top: 4px;
  color: #777;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pill {
  flex: none;
  padding: 5px 8px;
  border: 1px solid #d64545;
  color: #8c1f1f;
  background: #fff7f7;
  font-size: 11px;
  font-weight: 800;
}

.pill.ready {
  border-color: #1a936f;
  color: #116249;
  background: #f1faf6;
}

.divider {
  height: 1px;
  background: #111;
  opacity: 0.18;
}

.check-row {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.check-row input {
  width: 16px;
  min-height: 16px;
}

.error-text,
.success-text {
  margin-top: 12px;
  font-size: 13px;
  font-weight: 800;
}

.error-text {
  color: #d64545;
}

.success-text {
  color: #116249;
}

.empty-state {
  min-height: 360px;
  display: grid;
  align-content: center;
  justify-items: center;
  text-align: center;
}

.version-list {
  display: grid;
  gap: 12px;
}

.version-card {
  border: 1px solid #ddd;
  padding: 14px;
  background: #fff;
}

.version-card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.version-card-header div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-card-header span,
.version-card p,
.muted {
  color: #666;
}

.version-card code {
  padding: 3px 6px;
  border: 1px solid #ddd;
  background: #f6f6f1;
  font-size: 12px;
}

.version-card h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.version-card p {
  margin: 0 0 12px;
  line-height: 1.6;
}

.change-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.change-column {
  border-top: 1px solid #eee;
  padding-top: 10px;
}

.change-column h4 {
  margin: 0 0 8px;
  font-size: 12px;
}

.change-column ul {
  margin: 0;
  padding-left: 18px;
  color: #222;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 860px) {
  .admin-page {
    padding: 76px 14px 24px;
  }

  .admin-layout {
    grid-template-columns: 1fr;
  }

  .change-columns {
    grid-template-columns: 1fr;
  }
}
</style>
