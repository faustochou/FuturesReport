<template>
  <main class="admin-page">
    <section class="admin-header">
      <div>
        <p class="eyebrow">{{ $t('admin.consoleLabel') }}</p>
        <h1>{{ $t('admin.title') }}</h1>
      </div>
      <button v-if="admin" class="logout-btn" type="button" @click="logoutAdmin">{{ $t('admin.logout') }}</button>
    </section>

    <!-- ── Login ── -->
    <section v-if="!admin" class="login-panel">
      <h2>{{ $t('admin.loginTitle') }}</h2>
      <form class="form-grid" @submit.prevent="submitAdminLogin">
        <label>
          <span>{{ $t('admin.loginUsername') }}</span>
          <input v-model.trim="loginForm.username" autocomplete="username" required />
        </label>
        <label>
          <span>{{ $t('admin.loginPassword') }}</span>
          <input v-model="loginForm.password" autocomplete="current-password" type="password" required />
        </label>
        <button class="primary-btn" type="submit" :disabled="loading">
          {{ loading ? $t('admin.loggingIn') : $t('admin.loginBtn') }}
        </button>
      </form>
      <p class="hint">{{ $t('admin.loginHint') }}</p>
      <p v-if="error" class="error-text">{{ error }}</p>
    </section>

    <!-- ── Tabs (logged-in) ── -->
    <template v-else>
      <nav class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          type="button"
          @click="activeTab = tab.id"
        >{{ $t(`admin.${tab.labelKey}`) }}</button>
      </nav>

      <!-- ── Dashboard ── -->
      <section v-if="activeTab === 'dashboard'" class="dashboard-panel">
        <div class="stat-grid">
          <div class="stat-card">
            <p class="stat-value">{{ stats.total_users ?? '—' }}</p>
            <p class="stat-label">{{ $t('admin.statTotalUsers') }}</p>
          </div>
          <div class="stat-card">
            <p class="stat-value">{{ stats.active_users ?? '—' }}</p>
            <p class="stat-label">{{ $t('admin.statActiveUsers') }}</p>
          </div>
          <div class="stat-card">
            <p class="stat-value">{{ stats.admin_users ?? '—' }}</p>
            <p class="stat-label">{{ $t('admin.statAdmins') }}</p>
          </div>
          <div class="stat-card">
            <p class="stat-value">{{ stats.llm_configured ?? '—' }}</p>
            <p class="stat-label">{{ $t('admin.statLlm') }}</p>
          </div>
          <div v-if="system.memory_percent !== undefined" class="stat-card">
            <p class="stat-value">{{ system.memory_percent }}%</p>
            <p class="stat-label">{{ $t('admin.statMemory') }}</p>
          </div>
          <div v-if="system.cpu_percent !== undefined" class="stat-card">
            <p class="stat-value">{{ system.cpu_percent }}%</p>
            <p class="stat-label">{{ $t('admin.statCpu') }}</p>
          </div>
        </div>
        <button class="icon-btn refresh-btn" type="button" @click="loadDashboard">{{ $t('admin.refresh') }}</button>
      </section>

      <!-- ── User Management ── -->
      <section v-if="activeTab === 'users'" class="admin-layout">
        <aside class="user-list">
          <div class="section-title">
            <div>
              <p class="eyebrow">{{ $t('admin.registeredUsers') }}</p>
              <h2>{{ $t('admin.userListTitle') }}</h2>
            </div>
            <button class="icon-btn" type="button" title="Refresh" @click="loadUsers">↻</button>
          </div>

          <label class="search-box">
            <span>{{ $t('admin.search') }}</span>
            <input v-model.trim="query" placeholder="username / provider / model" />
          </label>

          <div class="users-table">
            <button
              v-for="user in filteredUsers"
              :key="user.user_id"
              class="user-row"
              :class="{ active: selectedUser?.user_id === user.user_id, inactive: !user.is_active }"
              type="button"
              @click="selectUser(user)"
            >
              <span>
                <strong>{{ user.username }}</strong>
                <small>{{ user.user_id }}</small>
              </span>
              <span class="badges">
                <span class="pill admin-pill" v-if="user.is_admin">Admin</span>
                <span class="pill inactive-pill" v-if="!user.is_active">{{ $t('admin.disabled') }}</span>
                <span class="pill" :class="{ ready: user.llm_configured }">
                  {{ user.llm_configured ? 'LLM ✓' : 'LLM —' }}
                </span>
                <span
                  class="pill"
                  :class="user.subscription?.status === 'active' ? 'sub-active-pill' : 'sub-none-pill'"
                >
                  {{ user.subscription ? user.subscription.tier_code : $t('admin.noSub') }}
                </span>
              </span>
            </button>
          </div>
        </aside>

        <section class="editor-panel">
          <template v-if="selectedUser">
            <div class="section-title">
              <div>
                <p class="eyebrow">{{ $t('admin.editUser') }}</p>
                <h2>{{ $t('admin.editUserTitle', { username: selectedUser.username }) }}</h2>
              </div>
              <div class="header-badges">
                <span class="pill admin-pill" v-if="selectedUser.is_admin">Admin</span>
                <span class="pill inactive-pill" v-if="!selectedUser.is_active">{{ $t('admin.alreadyDisabled') }}</span>
                <span class="pill ready" v-if="selectedUser.llm_configured">
                  API Key: {{ selectedUser.llm?.api_key_hint }}
                </span>
              </div>
            </div>

            <!-- Basic info form -->
            <form class="editor-form" @submit.prevent="saveUser">
              <label>
                <span>{{ $t('admin.usernameLabel') }}</span>
                <input v-model.trim="editForm.username" required minlength="3" />
              </label>
              <label>
                <span>{{ $t('admin.resetPassword') }}</span>
                <input v-model="editForm.password" type="password" minlength="8" :placeholder="$t('admin.passwordPlaceholder')" />
              </label>
              <div class="divider"></div>
              <label>
                <span>{{ $t('admin.llmProvider') }}</span>
                <select v-model="editForm.llm.provider" @change="syncProviderDefaults">
                  <option value="">{{ $t('admin.noModify') }}</option>
                  <option v-for="(provider, key) in providers" :key="key" :value="key">
                    {{ provider.label }}
                  </option>
                </select>
              </label>
              <label>
                <span>{{ $t('admin.model') }}</span>
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
                <span>{{ $t('admin.apiKey') }}</span>
                <input v-model="editForm.llm.api_key" type="password" :placeholder="$t('admin.apiKeyPlaceholder')" />
              </label>
              <label class="check-row">
                <input v-model="editForm.llm.clear" type="checkbox" />
                <span>{{ $t('admin.clearLlm') }}</span>
              </label>
              <button class="primary-btn" type="submit" :disabled="loading">
                {{ loading ? $t('admin.saving') : $t('admin.saveBtn') }}
              </button>
            </form>

            <!-- Role & active controls -->
            <div class="action-row">
              <button
                class="action-btn promote-btn"
                type="button"
                :disabled="loading || selectedUser.is_admin"
                @click="promoteUser"
              >{{ $t('admin.promoteBtn') }}</button>
              <button
                class="action-btn demote-btn"
                type="button"
                :disabled="loading || !selectedUser.is_admin"
                @click="demoteUser"
              >{{ $t('admin.demoteBtn') }}</button>
              <button
                class="action-btn"
                :class="selectedUser.is_active ? 'disable-btn' : 'enable-btn'"
                type="button"
                :disabled="loading"
                @click="toggleActive"
              >{{ selectedUser.is_active ? $t('admin.disableBtn') : $t('admin.enableBtn') }}</button>
              <button
                class="action-btn delete-btn"
                type="button"
                :disabled="loading"
                @click="confirmDelete"
              >{{ $t('admin.deleteBtn') }}</button>
            </div>

            <p v-if="message" class="success-text">{{ message }}</p>
            <p v-if="error" class="error-text">{{ error }}</p>

            <!-- Subscription override -->
            <div class="divider"></div>
            <div class="sub-mgmt">
              <p class="eyebrow">{{ $t('admin.subMgmt') }}</p>
              <p class="sub-current-line">
                {{ $t('admin.currentPlanLabel') }}：
                <span
                  class="pill"
                  :class="selectedUser.subscription?.status === 'active' ? 'sub-active-pill' : ''"
                >
                  {{ selectedUser.subscription ? selectedUser.subscription.tier_code : $t('admin.noSub2') }}
                </span>
                <span v-if="selectedUser.subscription?.stripe_subscription_id" class="sub-via">
                  {{ $t('admin.stripeSub') }}
                </span>
                <span v-else-if="selectedUser.subscription" class="sub-via">
                  {{ $t('admin.adminSub') }}
                </span>
              </p>
              <div class="inline-row sub-action-row">
                <select v-model="subForm.tierCode" class="sub-select">
                  <option value="">{{ $t('admin.revokeOption') }}</option>
                  <option v-for="tier in tiers" :key="tier.tier_code" :value="tier.tier_code">
                    {{ tier.display_name }}
                  </option>
                </select>
                <button
                  class="action-btn"
                  type="button"
                  :disabled="subLoading"
                  @click="setSubscription"
                >{{ subLoading ? $t('admin.applying') : $t('admin.applyBtn') }}</button>
              </div>
              <p class="sub-hint">{{ $t('admin.applyHint') }}</p>
              <p v-if="subMessage" class="success-text">{{ subMessage }}</p>
              <p v-if="subError" class="error-text">{{ subError }}</p>
            </div>
          </template>

          <div v-else class="empty-state">
            <h2>{{ $t('admin.selectUser') }}</h2>
            <p>{{ $t('admin.selectUserDesc') }}</p>
          </div>
        </section>
      </section>

      <!-- ── Version History ── -->
      <section v-if="activeTab === 'versions'" class="version-panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">{{ $t('admin.versionMgmt') }}</p>
            <h2>{{ $t('admin.versionTitle') }}</h2>
          </div>
          <button class="icon-btn" type="button" @click="loadVersions">↻</button>
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
                <h4>{{ $t('admin.added') }}</h4>
                <ul>
                  <li v-for="change in item.added" :key="change">{{ change }}</li>
                  <li v-if="!item.added?.length" class="muted">{{ $t('admin.none') }}</li>
                </ul>
              </div>
              <div class="change-column">
                <h4>{{ $t('admin.modified') }}</h4>
                <ul>
                  <li v-for="change in item.modified" :key="change">{{ change }}</li>
                  <li v-if="!item.modified?.length" class="muted">{{ $t('admin.none') }}</li>
                </ul>
              </div>
              <div class="change-column">
                <h4>{{ $t('admin.deleted') }}</h4>
                <ul>
                  <li v-for="change in item.deleted" :key="change">{{ change }}</li>
                  <li v-if="!item.deleted?.length" class="muted">{{ $t('admin.none') }}</li>
                </ul>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- ── Stripe Settings ── -->
      <section v-if="activeTab === 'stripe'" class="settings-panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">{{ $t('admin.paymentGateway') }}</p>
            <h2>{{ $t('admin.stripeTitle') }}</h2>
          </div>
          <button class="icon-btn" type="button" @click="loadStripeSettings">↻</button>
        </div>

        <div v-if="stripeSettings" class="settings-grid">
          <!-- Status row -->
          <div class="setting-card">
            <p class="setting-label">{{ $t('admin.stripeStatus') }}</p>
            <p class="setting-value">
              <span class="pill" :class="stripeSettings.is_configured ? 'ready' : ''">
                {{ stripeSettings.is_configured ? $t('admin.configured') : $t('admin.notConfigured') }}
              </span>
              <span v-if="stripeSettings.is_configured" class="pill mode-pill">
                {{ stripeSettings.is_test_mode ? $t('admin.testMode') : $t('admin.liveMode') }}
              </span>
            </p>
          </div>

          <!-- Secret key -->
          <div class="setting-card">
            <p class="setting-label">Secret Key</p>
            <p class="setting-value mono">
              {{ stripeSettings.secret_key_hint || $t('admin.notSet') }}
              <span class="hint-note">{{ $t('admin.keyHint') }}</span>
            </p>
          </div>

          <!-- Publishable key -->
          <div class="setting-card">
            <p class="setting-label">Publishable Key</p>
            <p class="setting-value mono">{{ stripeSettings.publishable_key_hint || $t('admin.notSet') }}</p>
          </div>

          <!-- Webhook -->
          <div class="setting-card webhook-card">
            <p class="setting-label">{{ $t('admin.webhookUrl') }}</p>
            <div class="webhook-row">
              <code class="webhook-url">{{ stripeSettings.webhook_url }}</code>
              <button class="icon-btn copy-btn" type="button" @click="copyWebhookUrl" title="Copy">⎘</button>
            </div>
            <p class="hint-note">{{ $t('admin.webhookPasteHint') }}</p>
            <p class="hint-note">{{ $t('admin.webhookEventsHint') }}</p>
            <p class="setting-value">
              <span class="pill" :class="stripeSettings.webhook_configured ? 'ready' : ''">
                {{ $t('admin.webhookSecret') }} {{ stripeSettings.webhook_configured ? $t('admin.configured') : $t('admin.notConfigured') }}
              </span>
            </p>
          </div>

          <!-- Env var instructions -->
          <div class="setting-card env-card">
            <p class="setting-label">{{ $t('admin.envVarsTitle') }}</p>
            <pre class="env-block">STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_LITE=price_...</pre>
            <p class="hint-note">{{ $t('admin.stripeKeyHint') }}</p>
          </div>
        </div>
        <p v-else class="muted">{{ $t('admin.loadingText') }}</p>
        <p v-if="stripeError" class="error-text">{{ stripeError }}</p>
      </section>

      <!-- ── Subscription Tiers ── -->
      <section v-if="activeTab === 'tiers'" class="tiers-panel">
        <div class="section-title">
          <div>
            <p class="eyebrow">{{ $t('admin.subPlansLabel') }}</p>
            <h2>{{ $t('admin.tierTitle') }}</h2>
          </div>
          <button class="icon-btn" type="button" @click="loadTiers">↻</button>
        </div>

        <div class="tier-list">
          <div v-for="tier in tiers" :key="tier.tier_code" class="tier-card">
            <div class="tier-card-header">
              <div>
                <strong class="tier-name">{{ tier.display_name }}</strong>
                <code class="tier-code">{{ tier.tier_code }}</code>
              </div>
              <span class="pill" :class="tier.is_available ? 'ready' : 'unavail-pill'">
                {{ tier.is_available ? $t('admin.available') : $t('admin.unavailable') }}
              </span>
            </div>

            <div class="tier-form">
              <!-- is_available toggle -->
              <label class="check-row">
                <input
                  type="checkbox"
                  :checked="tier.is_available"
                  @change="toggleTierAvailability(tier)"
                  :disabled="tierLoading === tier.tier_code"
                />
                <span>{{ $t('admin.enableTier') }}</span>
              </label>

              <!-- Stripe Price ID -->
              <label>
                <span>Stripe Price ID</span>
                <div class="inline-row">
                  <input
                    :value="tierEdits[tier.tier_code]?.price_id ?? tier.stripe_price_id ?? ''"
                    @input="setTierEdit(tier.tier_code, 'price_id', $event.target.value)"
                    placeholder="price_xxxxxxxxxxxx"
                    class="price-input"
                  />
                  <button
                    class="action-btn"
                    type="button"
                    :disabled="tierLoading === tier.tier_code"
                    @click="saveTierPriceId(tier)"
                  >{{ $t('admin.savePriceId') }}</button>
                </div>
              </label>

              <!-- Feature flags -->
              <label>
                <span>{{ $t('admin.flagsLabel') }}</span>
                <textarea
                  :value="tierEdits[tier.tier_code]?.flags ?? JSON.stringify(tier.feature_flags, null, 2)"
                  @input="setTierEdit(tier.tier_code, 'flags', $event.target.value)"
                  rows="5"
                  class="flags-textarea"
                  placeholder='{"max_agents": 100, "sim_runs_per_month": 10}'
                ></textarea>
                <button
                  class="action-btn"
                  type="button"
                  :disabled="tierLoading === tier.tier_code"
                  @click="saveTierFlags(tier)"
                >{{ $t('admin.saveFlagsBtn') }}</button>
              </label>

              <p v-if="tierMessages[tier.tier_code]" class="success-text">{{ tierMessages[tier.tier_code] }}</p>
              <p v-if="tierErrors[tier.tier_code]" class="error-text">{{ tierErrors[tier.tier_code] }}</p>
            </div>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  adminLogin,
  changeUserRole,
  deleteUser,
  getAdminAccessToken,
  getAdminMe,
  getAdminUsers,
  getDashboard,
  getStripeSettings,
  getVersionHistory,
  listAdminTiers,
  setAdminToken,
  setUserSubscription,
  toggleUserActive,
  updateAdminTier,
  updateAdminUser,
} from '../api/admin'
import DEFAULT_PROVIDERS from '../config/providers'

const router = useRouter()
const { t }  = useI18n()
const admin  = ref(null)
const activeTab = ref('dashboard')

const tabs = [
  { id: 'dashboard', labelKey: 'tabDashboard' },
  { id: 'users',     labelKey: 'tabUsers' },
  { id: 'stripe',    labelKey: 'tabStripe' },
  { id: 'tiers',     labelKey: 'tabTiers' },
  { id: 'versions',  labelKey: 'tabVersions' },
]

// Dashboard
const stats  = ref({})
const system = ref({})

// Users
const users        = ref([])
const providers    = ref({ ...DEFAULT_PROVIDERS })
const versions     = ref([])
const selectedUser = ref(null)
const loading      = ref(false)
const error        = ref('')
const message      = ref('')
const query        = ref('')

const loginForm = reactive({ username: '', password: '' })

const editForm = reactive({
  username: '',
  password: '',
  llm: { provider: '', model: '', base_url: '', api_key: '', clear: false },
})

const currentProvider = computed(() => providers.value[editForm.llm.provider] || {})
const currentModels   = computed(() => currentProvider.value.models || [])
const filteredUsers   = computed(() => {
  const kw = query.value.toLowerCase()
  if (!kw) return users.value
  return users.value.filter(u => {
    const llm = u.llm || {}
    return [u.username, u.user_id, llm.provider, llm.model]
      .filter(Boolean)
      .some(v => String(v).toLowerCase().includes(kw))
  })
})

// Stripe settings
const stripeSettings = ref(null)
const stripeError    = ref('')

// Tier management
const tiers       = ref([])
const tierEdits   = reactive({})   // { [tier_code]: { price_id, flags } }
const tierLoading = ref('')        // tier_code currently saving
const tierMessages = reactive({})
const tierErrors   = reactive({})

// User subscription override (admin)
const subLoading = ref(false)
const subMessage = ref('')
const subError   = ref('')
const subForm    = reactive({ tierCode: '' })

// Auto-load tab data when switching
watch(activeTab, (tab) => {
  if (tab === 'dashboard') loadDashboard()
  if (tab === 'users')     { loadUsers(); loadTiers() }
  if (tab === 'stripe')    loadStripeSettings()
  if (tab === 'tiers')     loadTiers()
  if (tab === 'versions')  loadVersions()
})

// ── Login ────────────────────────────────────────────────────────────────────

const submitAdminLogin = async () => {
  loading.value = true
  error.value   = ''
  try {
    const res = await adminLogin(loginForm)
    setAdminToken(res.data?.token)
    admin.value = res.data?.admin
    loginForm.password = ''
    await loadDashboard()
  } catch (err) {
    error.value = err.message || t('admin.loginFailed')
  } finally {
    loading.value = false
  }
}

const loadAdminSession = async () => {
  if (!getAdminAccessToken()) return
  try {
    const res = await getAdminMe()
    admin.value = res.data?.admin
    await loadDashboard()
  } catch {
    setAdminToken('')
    admin.value = null
  }
}

const logoutAdmin = () => {
  setAdminToken('')
  admin.value    = null
  activeTab.value = 'dashboard'
  users.value    = []
  versions.value = []
  stats.value    = {}
  system.value   = {}
  selectedUser.value = null
}

// ── Dashboard ────────────────────────────────────────────────────────────────

const loadDashboard = async () => {
  try {
    const res    = await getDashboard()
    stats.value  = res.data?.stats  || {}
    system.value = res.data?.system || {}
  } catch (err) {
    error.value = err.message || t('admin.loadDashboardFailed')
  }
}

// ── Users ────────────────────────────────────────────────────────────────────

const loadUsers = async () => {
  loading.value = true
  error.value   = ''
  try {
    const res       = await getAdminUsers()
    users.value = res.data?.users || []
    // Always use hardcoded providers to avoid stale data from old deployments.
    if (selectedUser.value) {
      const refreshed = users.value.find(u => u.user_id === selectedUser.value.user_id)
      if (refreshed) selectUser(refreshed)
    }
  } catch (err) {
    error.value = err.message || t('admin.loadUsersFailed')
  } finally {
    loading.value = false
  }
}

const loadVersions = async () => {
  try {
    const res    = await getVersionHistory()
    versions.value = res.data?.versions || []
  } catch (err) {
    error.value = err.message || t('admin.loadVersionsFailed')
  }
}

const selectUser = (user) => {
  selectedUser.value         = user
  editForm.username          = user.username || ''
  editForm.password          = ''
  editForm.llm.provider      = user.llm?.provider  || ''
  editForm.llm.model         = user.llm?.model      || ''
  editForm.llm.base_url      = user.llm?.base_url   || ''
  editForm.llm.api_key       = ''
  editForm.llm.clear         = false
  message.value              = ''
  error.value                = ''
  subForm.tierCode           = user.subscription?.tier_code || ''
  subMessage.value           = ''
  subError.value             = ''
}

const setSubscription = async () => {
  if (!selectedUser.value) return
  subLoading.value = true
  subMessage.value = ''
  subError.value   = ''
  try {
    const res = await setUserSubscription(selectedUser.value.user_id, subForm.tierCode || null)
    _refreshUser(res.data)
    subMessage.value = subForm.tierCode
      ? t('admin.setTierTo', { tier: subForm.tierCode })
      : t('admin.revokedSub')
  } catch (err) {
    subError.value = err.message || t('admin.operationFailed')
  } finally {
    subLoading.value = false
  }
}

const syncProviderDefaults = () => {
  const p = currentProvider.value
  if (!p) return
  editForm.llm.model    = p.default_model || p.models?.[0] || editForm.llm.model
  editForm.llm.base_url = p.base_url      || editForm.llm.base_url
}

const _refreshUser = (updated) => {
  const pub = updated?.user || updated
  users.value = users.value.map(u => u.user_id === pub.user_id ? pub : u)
  if (selectedUser.value?.user_id === pub.user_id) selectUser(pub)
}

const saveUser = async () => {
  if (!selectedUser.value) return
  loading.value = true
  error.value   = ''
  message.value = ''
  try {
    const payload = {
      username: editForm.username,
      password: editForm.password || undefined,
      llm: {
        provider: editForm.llm.provider,
        model:    editForm.llm.model,
        base_url: editForm.llm.base_url,
        api_key:  editForm.llm.api_key || undefined,
        clear:    editForm.llm.clear,
      },
    }
    const res = await updateAdminUser(selectedUser.value.user_id, payload)
    _refreshUser(res.data)
    message.value = t('admin.saved')
  } catch (err) {
    error.value = err.message || t('admin.saveFailed')
  } finally {
    loading.value = false
  }
}

const promoteUser = async () => {
  if (!selectedUser.value) return
  loading.value = true
  error.value   = ''
  message.value = ''
  try {
    const res = await changeUserRole(selectedUser.value.user_id, 'admin')
    _refreshUser(res.data)
    message.value = t('admin.promoted')
  } catch (err) {
    error.value = err.message || t('admin.operationFailed')
  } finally {
    loading.value = false
  }
}

const demoteUser = async () => {
  if (!selectedUser.value) return
  if (!confirm(t('admin.confirmDemote', { username: selectedUser.value.username }))) return
  loading.value = true
  error.value   = ''
  message.value = ''
  try {
    const res = await changeUserRole(selectedUser.value.user_id, 'user')
    _refreshUser(res.data)
    message.value = t('admin.demoted')
  } catch (err) {
    error.value = err.message || t('admin.operationFailed')
  } finally {
    loading.value = false
  }
}

const toggleActive = async () => {
  if (!selectedUser.value) return
  const newState = !selectedUser.value.is_active
  loading.value  = true
  error.value    = ''
  message.value  = ''
  try {
    const res = await toggleUserActive(selectedUser.value.user_id, newState)
    _refreshUser(res.data)
    message.value = newState ? t('admin.accountEnabled') : t('admin.accountDisabled')
  } catch (err) {
    error.value = err.message || t('admin.operationFailed')
  } finally {
    loading.value = false
  }
}

const confirmDelete = async () => {
  if (!selectedUser.value) return
  if (!confirm(t('admin.confirmDelete', { username: selectedUser.value.username }))) return
  loading.value = true
  error.value   = ''
  message.value = ''
  try {
    await deleteUser(selectedUser.value.user_id)
    users.value       = users.value.filter(u => u.user_id !== selectedUser.value.user_id)
    selectedUser.value = null
    message.value     = t('admin.userDeleted')
  } catch (err) {
    error.value = err.message || t('admin.saveFailed')
  } finally {
    loading.value = false
  }
}

// ── Stripe Settings ──────────────────────────────────────────────────────────

const loadStripeSettings = async () => {
  stripeError.value = ''
  try {
    const res = await getStripeSettings()
    stripeSettings.value = res.data?.stripe || null
  } catch (err) {
    stripeError.value = err.message || t('admin.loadStripeFailed')
  }
}

const copyWebhookUrl = () => {
  const url = stripeSettings.value?.webhook_url
  if (!url) return
  navigator.clipboard.writeText(url).catch(() => {})
}

// ── Subscription Tiers ───────────────────────────────────────────────────────

const loadTiers = async () => {
  try {
    const res = await listAdminTiers()
    tiers.value = res.data?.tiers || []
  } catch (err) {
    error.value = err.message || t('admin.loadTiersFailed')
  }
}

const setTierEdit = (code, field, value) => {
  if (!tierEdits[code]) tierEdits[code] = {}
  tierEdits[code][field] = value
}

const _saveTier = async (tier, payload) => {
  tierLoading.value = tier.tier_code
  tierMessages[tier.tier_code] = ''
  tierErrors[tier.tier_code]   = ''
  try {
    const res = await updateAdminTier(tier.tier_code, payload)
    const updated = res.data?.tier
    tiers.value = tiers.value.map(t =>
      t.tier_code === tier.tier_code ? updated : t
    )
    tierMessages[tier.tier_code] = t('admin.savedConfirm')
  } catch (err) {
    tierErrors[tier.tier_code] = err.message || t('admin.saveFailed')
  } finally {
    tierLoading.value = ''
  }
}

const toggleTierAvailability = (tier) => {
  _saveTier(tier, { is_available: !tier.is_available })
}

const saveTierPriceId = (tier) => {
  const price_id = (tierEdits[tier.tier_code]?.price_id ?? tier.stripe_price_id ?? '').trim()
  _saveTier(tier, { stripe_price_id: price_id })
}

const saveTierFlags = (tier) => {
  const raw = tierEdits[tier.tier_code]?.flags ?? JSON.stringify(tier.feature_flags)
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    tierErrors[tier.tier_code] = t('admin.flagsJsonError')
    return
  }
  _saveTier(tier, { feature_flags: parsed })
}

onMounted(loadAdminSession)
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 24px 32px 32px;
  background: #f6f6f1;
  color: #111;
  font-family: 'JetBrains Mono', 'Noto Sans TC', monospace;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 20px;
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

.icon-btn, .logout-btn, .primary-btn {
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font-weight: 800;
  cursor: pointer;
  font-family: inherit;
}

.icon-btn { width: 38px; height: 38px; }
.logout-btn  { min-height: 38px; padding: 0 14px; }

/* ── Tabs ── */
.tab-bar {
  display: flex;
  gap: 0;
  border: 1px solid #111;
  background: #fff;
  margin-bottom: 18px;
  width: fit-content;
}

.tab-btn {
  padding: 10px 22px;
  border: none;
  border-right: 1px solid #111;
  background: transparent;
  color: #111;
  font-family: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.12s;
}

.tab-btn:last-child { border-right: none; }
.tab-btn.active { background: #111; color: #fff; }
.tab-btn:hover:not(.active) { background: #f0f0eb; }

/* ── Dashboard ── */
.dashboard-panel { padding: 4px 0; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid #111;
  background: #fff;
  box-shadow: 4px 4px 0 #111;
  padding: 18px 16px;
  text-align: center;
}

.stat-value {
  margin: 0 0 6px;
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: #03bf65;
}

.stat-label {
  margin: 0;
  font-size: 12px;
  font-weight: 800;
  color: #555;
  text-transform: uppercase;
}

.refresh-btn {
  width: auto;
  padding: 0 16px;
  min-height: 38px;
}

/* ── Login ── */
.login-panel {
  max-width: 420px;
  padding: 20px;
  border: 1px solid #111;
  background: #fff;
  box-shadow: 6px 6px 0 #111;
}

/* ── User layout ── */
.admin-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.user-list, .editor-panel, .version-panel {
  border: 1px solid #111;
  background: #fff;
  box-shadow: 6px 6px 0 #111;
}

.user-list, .editor-panel { padding: 18px; }
.version-panel { padding: 18px; }

.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.header-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.form-grid, .editor-form { display: grid; gap: 14px; }

label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  font-weight: 800;
}

input, select {
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

.primary-btn:disabled { opacity: 0.55; cursor: wait; }

/* ── Action buttons ── */
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.action-btn {
  flex: 1 1 auto;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.promote-btn  { border-color: #1a936f; color: #116249; }
.promote-btn:hover:not(:disabled) { background: #f1faf6; }

.demote-btn   { border-color: #888; color: #555; }
.demote-btn:hover:not(:disabled) { background: #f8f8f8; }

.disable-btn  { border-color: #c97c2e; color: #7a4a10; }
.disable-btn:hover:not(:disabled) { background: #fdf6ec; }

.enable-btn   { border-color: #1a936f; color: #116249; }
.enable-btn:hover:not(:disabled)  { background: #f1faf6; }

.delete-btn   { border-color: #d64545; color: #8c1f1f; }
.delete-btn:hover:not(:disabled)  { background: #fff7f7; }

/* ── User list ── */
.hint, .empty-state p { color: #666; font-size: 13px; line-height: 1.6; }
.search-box { margin-bottom: 14px; }

.users-table {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 280px);
  overflow: auto;
}

.user-row {
  min-height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  border: 1px solid #ddd;
  background: #fff;
  color: #111;
  text-align: left;
  cursor: pointer;
  font-family: inherit;
}

.user-row.active   { border-color: #111; box-shadow: 3px 3px 0 #111; }
.user-row.inactive { opacity: 0.55; }

.user-row small {
  display: block;
  max-width: 180px;
  margin-top: 4px;
  color: #777;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.badges { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }

/* ── Pills ── */
.pill {
  flex: none;
  padding: 3px 7px;
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

.admin-pill {
  border-color: #2563eb;
  color: #1e40af;
  background: #eff6ff;
}

.inactive-pill {
  border-color: #c97c2e;
  color: #7a4a10;
  background: #fdf6ec;
}

/* ── Misc ── */
.divider { height: 1px; background: #111; opacity: 0.18; }
.check-row { grid-template-columns: auto 1fr; align-items: center; }
.check-row input { width: 16px; min-height: 16px; }

.error-text, .success-text { margin-top: 12px; font-size: 13px; font-weight: 800; }
.error-text   { color: #d64545; }
.success-text { color: #116249; }

.empty-state {
  min-height: 360px;
  display: grid;
  align-content: center;
  justify-items: center;
  text-align: center;
}

/* ── Version history ── */
.version-list { display: grid; gap: 12px; }

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

.version-card-header div { display: flex; align-items: center; gap: 10px; }
.version-card-header span, .version-card p, .muted { color: #666; }

.version-card code {
  padding: 3px 6px;
  border: 1px solid #ddd;
  background: #f6f6f1;
  font-size: 12px;
}

.version-card h3 { margin: 0 0 8px; font-size: 18px; }
.version-card p  { margin: 0 0 12px; line-height: 1.6; }

.change-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.change-column { border-top: 1px solid #eee; padding-top: 10px; }
.change-column h4 { margin: 0 0 8px; font-size: 12px; }
.change-column ul { margin: 0; padding-left: 18px; color: #222; font-size: 13px; line-height: 1.5; }

/* ── Stripe Settings ── */
.settings-panel, .tiers-panel {
  border: 1px solid #111;
  background: #fff;
  box-shadow: 6px 6px 0 #111;
  padding: 18px;
}

.settings-grid {
  display: grid;
  gap: 12px;
}

.setting-card {
  border: 1px solid #ddd;
  padding: 14px;
  background: #f6f6f1;
}

.setting-label {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  color: #666;
}

.setting-value {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.mono { font-family: 'JetBrains Mono', monospace; }

.webhook-card { grid-column: 1 / -1; }

.webhook-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.webhook-url {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #111;
  background: #fff;
  font-size: 12px;
  overflow-x: auto;
  white-space: nowrap;
}

.copy-btn { flex: none; }

.env-card { grid-column: 1 / -1; }

.env-block {
  margin: 8px 0;
  padding: 12px;
  border: 1px solid #ddd;
  background: #111;
  color: #03bf65;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1.7;
  overflow-x: auto;
}

.hint-note {
  margin: 4px 0 0;
  font-size: 11px;
  color: #888;
  font-weight: 400;
}

.mode-pill {
  border-color: #2563eb;
  color: #1e40af;
  background: #eff6ff;
}

/* ── Tier Management ── */
.tier-list {
  display: grid;
  gap: 14px;
}

.tier-card {
  border: 1px solid #ddd;
  background: #f6f6f1;
  padding: 16px;
}

.tier-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.tier-name {
  font-size: 18px;
  font-weight: 800;
}

.tier-code {
  margin-left: 8px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  background: #fff;
  font-size: 12px;
  color: #666;
}

.tier-form {
  display: grid;
  gap: 14px;
}

.inline-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.price-input {
  flex: 1;
}

.flags-textarea {
  width: 100%;
  border: 1px solid #111;
  padding: 8px 10px;
  font: inherit;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  background: #fff;
  color: #111;
  resize: vertical;
  display: block;
  margin-bottom: 8px;
}

.unavail-pill {
  border-color: #c97c2e;
  color: #7a4a10;
  background: #fdf6ec;
}

/* ── Subscription pills (user list) ── */
.sub-active-pill {
  border-color: #1a936f;
  color: #116249;
  background: #f1faf6;
  text-transform: uppercase;
  font-size: 10px;
}

.sub-none-pill {
  border-color: #ccc;
  color: #888;
  background: #f5f5f5;
  font-size: 10px;
}

/* ── Subscription override (editor) ── */
.sub-mgmt {
  display: grid;
  gap: 10px;
  padding-top: 4px;
}

.sub-current-line {
  margin: 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sub-via {
  font-size: 11px;
  color: #888;
}

.sub-action-row {
  align-items: stretch;
}

.sub-select {
  flex: 1;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  padding: 0 8px;
  font: inherit;
  font-size: 13px;
  height: 38px;
}

.sub-hint {
  margin: 0;
  font-size: 11px;
  color: #888;
}

@media (max-width: 860px) {
  .admin-page    { padding: 76px 14px 24px; }
  .admin-layout  { grid-template-columns: 1fr; }
  .change-columns { grid-template-columns: 1fr; }
  .stat-grid     { grid-template-columns: repeat(2, 1fr); }
  .tab-bar       { width: 100%; overflow-x: auto; }
  .tab-btn       { flex: none; white-space: nowrap; }
}
</style>
