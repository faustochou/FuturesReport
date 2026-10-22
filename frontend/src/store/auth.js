import { reactive } from 'vue'
import {
  getCurrentUser,
  getLlmProviders,
  loginAccount,
  getPlatformModels,
  logoutAccount,
  registerAccount,
  selectPlatformModelApi,
  updateLlmConfig
} from '../api/auth'
import DEFAULT_PROVIDERS from '../config/providers'

const TOKEN_KEY = 'futures_auth_token'
const USER_KEY  = 'futures_auth_user'

function loadCachedUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveUserCache(user) {
  if (user) {
    try { localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch {}
  } else {
    localStorage.removeItem(USER_KEY)
  }
}

export const authState = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: loadCachedUser(),
  providers: { ...DEFAULT_PROVIDERS },
  // Site-provided models (Premium/Pro/admin only); filled by loadPlatformModels()
  platformModels: [],
  loading: false,
  error: ''
})

export const hasLlmConfig = () => Boolean(authState.user?.llm_configured)

const setSession = (token, user) => {
  authState.token = token || ''
  authState.user  = user  || null

  if (authState.token) {
    localStorage.setItem(TOKEN_KEY, authState.token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }

  saveUserCache(authState.user)
  if (!authState.token) authState.platformModels = []
}

export const loadPlatformModels = async () => {
  if (!authState.token || !authState.user?.can_use_platform_models) {
    authState.platformModels = []
    return authState.platformModels
  }
  try {
    const res = await getPlatformModels()
    authState.platformModels = res.data?.models || []
  } catch {
    authState.platformModels = []
  }
  return authState.platformModels
}

export const loadProviders = async () => {
  authState.providers = { ...DEFAULT_PROVIDERS }
  return authState.providers
}

export const loadCurrentUser = async () => {
  if (!authState.token) return null

  authState.loading = true
  authState.error   = ''
  try {
    const res = await getCurrentUser()
    authState.user = res.data?.user || null
    saveUserCache(authState.user)
    await loadPlatformModels()
    return authState.user
  } catch (error) {
    // Network error: backend is not reachable — keep cached session intact.
    if (error.isNetworkError) return null

    // Only clear the session for actual auth failures (401).
    const status = error.status || error.response?.status
    if (status === 401) {
      setSession('', null)
      authState.error = 'Session expired.'
    }
    return null
  } finally {
    authState.loading = false
  }
}

export const login = async ({ username, password }) => {
  authState.loading = true
  authState.error   = ''
  try {
    const res = await loginAccount({ username, password })
    setSession(res.data?.token, res.data?.user)
    await loadPlatformModels()
    return authState.user
  } catch (error) {
    authState.error = error.message || 'Login failed.'
    throw error
  } finally {
    authState.loading = false
  }
}

export const register = async ({ username, password }) => {
  authState.loading = true
  authState.error   = ''
  try {
    const res = await registerAccount({ username, password })
    setSession(res.data?.token, res.data?.user)
    await loadPlatformModels()
    return authState.user
  } catch (error) {
    authState.error = error.message || 'Registration failed.'
    throw error
  } finally {
    authState.loading = false
  }
}

export const saveLlmConfig = async (payload) => {
  authState.loading = true
  authState.error   = ''
  try {
    const res = await updateLlmConfig(payload)
    authState.user = res.data?.user || authState.user
    saveUserCache(authState.user)
    return authState.user
  } catch (error) {
    authState.error = error.message || 'Failed to save LLM settings.'
    throw error
  } finally {
    authState.loading = false
  }
}

// Pick a site-provided model (id) or null to go back to the user's own API key.
export const selectPlatformModel = async (platformModelId) => {
  authState.loading = true
  authState.error   = ''
  try {
    const res = await selectPlatformModelApi(platformModelId)
    authState.user = res.data?.user || authState.user
    saveUserCache(authState.user)
    return authState.user
  } catch (error) {
    authState.error = error.message || 'Failed to switch model.'
    throw error
  } finally {
    authState.loading = false
  }
}

export const logout = async () => {
  try {
    await logoutAccount()
  } catch {
    // Server-side logout is stateless; local cleanup is enough.
  }
  setSession('', null)
}
