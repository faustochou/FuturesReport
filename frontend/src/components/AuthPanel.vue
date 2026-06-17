<template>
  <div class="auth-shell">
    <button class="auth-trigger" type="button" @click="togglePanel">
      <span class="status-dot" :class="{ ready: authState.user && authState.user.llm_configured }"></span>
      <span>{{ triggerLabel }}</span>
    </button>

    <Teleport to="body">
      <div v-if="open" class="auth-overlay" @click.self="open = false">
        <section class="auth-modal" role="dialog" aria-modal="true">
          <div class="modal-header">
            <div>
              <div class="eyebrow">{{ authState.user ? t('auth.accountSettings') : t('auth.accountAccess') }}</div>
              <h2>{{ authState.user ? t('auth.llmSettings') : mode === 'login' ? t('auth.login') : t('auth.register') }}</h2>
            </div>
            <button class="close-btn" type="button" :aria-label="t('common.close')" @click="open = false">×</button>
          </div>

          <template v-if="!authState.user">
            <div class="tabs">
              <button :class="{ active: mode === 'login' }" type="button" @click="mode = 'login'">{{ t('auth.login') }}</button>
              <button :class="{ active: mode === 'register' }" type="button" @click="mode = 'register'">{{ t('auth.register') }}</button>
            </div>

            <form class="form-stack" @submit.prevent="submitAccount">
              <label>
                <span>{{ t('auth.username') }}</span>
                <input v-model.trim="accountForm.username" autocomplete="username" required minlength="3" />
              </label>
              <label>
                <span>{{ t('auth.password') }}</span>
                <input
                  v-model="accountForm.password"
                  :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
                  type="password"
                  required
                  minlength="8"
                />
              </label>
              <button class="primary-btn" type="submit" :disabled="authState.loading">
                {{ authState.loading ? t('auth.working') : mode === 'login' ? t('auth.login') : t('auth.createAccount') }}
              </button>
            </form>
          </template>

          <template v-else>
            <div class="account-row">
              <div>
                <div class="eyebrow">{{ t('auth.signedIn') }}</div>
                <strong>{{ authState.user.username }}</strong>
              </div>
              <div class="account-actions">
                <button v-if="authState.user.is_admin" class="text-btn" type="button" @click="goAdmin">{{ t('auth.adminConsole') }}</button>
                <button class="text-btn" type="button" @click="logout">{{ t('auth.logout') }}</button>
              </div>
            </div>

            <form class="form-stack" @submit.prevent="submitLlmConfig">
              <label>
                <span>{{ t('auth.provider') }}</span>
                <select v-model="llmForm.provider" @change="syncProviderDefaults">
                  <option v-for="(provider, key) in authState.providers" :key="key" :value="key">
                    {{ provider.label }}
                  </option>
                </select>
              </label>

              <label>
                <span>{{ t('auth.model') }}</span>
                <select v-model="llmForm.model">
                  <option v-for="model in currentModels" :key="model" :value="model">{{ model }}</option>
                </select>
              </label>

              <label>
                <span>{{ t('auth.baseUrl') }}</span>
                <input v-model.trim="llmForm.base_url" />
              </label>

              <label>
                <span>{{ t('auth.apiKey') }}</span>
                <input
                  v-model="llmForm.api_key"
                  autocomplete="off"
                  type="password"
                  :placeholder="keyPlaceholder"
                />
              </label>

              <div class="llm-status" :class="{ ready: authState.user.llm_configured }">
                {{ authState.user.llm_configured ? t('auth.savedModel', { provider: authState.user.llm?.provider, model: authState.user.llm?.model }) : t('auth.apiKeyRequired') }}
              </div>

              <button class="primary-btn" type="submit" :disabled="authState.loading">
                {{ authState.loading ? t('auth.saving') : t('auth.saveLlmSettings') }}
              </button>
            </form>
          </template>

          <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  authState,
  loadCurrentUser,
  loadProviders,
  login,
  logout,
  register,
  saveLlmConfig
} from '../store/auth'

const open = ref(false)
const mode = ref('login')
const localError = ref('')
const { t } = useI18n()
const router = useRouter()

const accountForm = reactive({
  username: '',
  password: ''
})

const llmForm = reactive({
  provider: 'openai',
  model: 'gpt-4o-mini',
  base_url: 'https://api.openai.com/v1',
  api_key: ''
})

const triggerLabel = computed(() => {
  if (!authState.user) return t('auth.login')
  if (!authState.user.llm_configured) return t('auth.setApiKey')
  return authState.user.llm?.model || t('auth.llmReady')
})

const currentProvider = computed(() => authState.providers[llmForm.provider] || {})
const currentModels = computed(() => currentProvider.value.models || [])
const keyPlaceholder = computed(() => authState.user?.llm?.api_key_hint || t('auth.apiKeyPlaceholder'))
const errorMap = {
  'Invalid username or password.': 'auth.invalidCredentials',
  'Username must be at least 3 characters.': 'auth.usernameTooShort',
  'Password must be at least 8 characters.': 'auth.passwordTooShort',
  'Username already exists.': 'auth.usernameExists',
  'API key is required.': 'auth.apiKeyRequiredError',
  'Unsupported LLM provider.': 'auth.unsupportedProvider',
  'Session expired.': 'auth.sessionExpired',
  'Login failed.': 'auth.loginFailed',
  'Registration failed.': 'auth.registrationFailed',
  'Failed to save LLM settings.': 'auth.saveLlmFailed'
}
const errorMessage = computed(() => {
  const message = localError.value || authState.error
  if (!message) return ''
  const key = errorMap[message]
  return key ? t(key) : message
})

const togglePanel = () => {
  open.value = !open.value
  if (open.value) {
    localError.value = ''
    authState.error = ''
  }
}

const hydrateLlmForm = () => {
  const llm = authState.user?.llm
  if (llm?.provider) llmForm.provider = llm.provider
  if (llm?.model) llmForm.model = llm.model
  if (llm?.base_url) llmForm.base_url = llm.base_url
  syncProviderDefaults(false)
}

const syncProviderDefaults = (forceModel = true) => {
  const provider = currentProvider.value
  if (!provider) return
  llmForm.base_url = llmForm.base_url || provider.base_url || ''
  if (forceModel || !llmForm.model) {
    llmForm.model = provider.default_model || provider.models?.[0] || ''
  }
  if (forceModel) {
    llmForm.base_url = provider.base_url || llmForm.base_url
  }
}

const submitAccount = async () => {
  localError.value = ''
  try {
    if (mode.value === 'login') {
      await login(accountForm)
    } else {
      await register(accountForm)
    }
    accountForm.password = ''
    hydrateLlmForm()
  } catch (error) {
    localError.value = error.message || t('auth.accountRequestFailed')
  }
}

const submitLlmConfig = async () => {
  localError.value = ''
  try {
    await saveLlmConfig({
      provider: llmForm.provider,
      model: llmForm.model,
      base_url: llmForm.base_url,
      api_key: llmForm.api_key || undefined
    })
    llmForm.api_key = ''
  } catch (error) {
    localError.value = error.message || t('auth.saveLlmFailed')
  }
}

const goAdmin = () => {
  open.value = false
  router.push('/admin')
}

onMounted(async () => {
  await loadProviders()
  await loadCurrentUser()
  hydrateLlmForm()
})

watch(() => authState.user, hydrateLlmForm)
</script>

<style scoped>
.auth-shell {
  position: relative;
  font-family: 'Space Grotesk', 'Noto Sans TC', system-ui, sans-serif;
}

.auth-trigger {
  height: 36px;
  min-width: 92px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d64545;
}

.status-dot.ready {
  background: #1a936f;
}

.auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: start center;
  padding: 84px 16px 24px;
  background: rgba(0, 0, 0, 0.35);
}

.auth-modal {
  width: min(360px, calc(100vw - 32px));
  padding: 16px;
  border: 1px solid #111;
  background: #fff;
  box-shadow: 6px 6px 0 #111;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.modal-header h2 {
  margin: 3px 0 0;
  color: #111;
  font-size: 20px;
  line-height: 1.15;
}

.close-btn {
  width: 34px;
  height: 34px;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1px solid #111;
  margin-bottom: 14px;
}

.tabs button,
.text-btn {
  border: 0;
  background: #fff;
  color: #111;
  font-weight: 700;
  cursor: pointer;
}

.tabs button {
  height: 34px;
  border-right: 1px solid #111;
}

.tabs button:last-child {
  border-right: 0;
}

.tabs button.active {
  background: #111;
  color: #fff;
}

.form-stack {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 5px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

input,
select {
  width: 100%;
  min-height: 36px;
  border: 1px solid #111;
  border-radius: 0;
  padding: 8px 10px;
  background: #fff;
  color: #111;
  font: inherit;
  font-size: 13px;
}

.primary-btn {
  min-height: 38px;
  border: 1px solid #111;
  background: #111;
  color: #fff;
  font-weight: 800;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.55;
  cursor: wait;
}

.account-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.account-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.eyebrow {
  color: #666;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.llm-status {
  padding: 9px 10px;
  border: 1px solid #d64545;
  color: #8c1f1f;
  background: #fff7f7;
  font-size: 12px;
  font-weight: 700;
}

.llm-status.ready {
  border-color: #1a936f;
  color: #116249;
  background: #f1faf6;
}

.error-text {
  margin-top: 12px;
  color: #d64545;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 720px) {
  .auth-trigger {
    max-width: 132px;
  }
}
</style>
