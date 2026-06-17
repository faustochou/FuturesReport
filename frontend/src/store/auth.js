import { reactive } from 'vue'
import {
  getCurrentUser,
  getLlmProviders,
  loginAccount,
  logoutAccount,
  registerAccount,
  updateLlmConfig
} from '../api/auth'

const TOKEN_KEY = 'futures_auth_token'

export const authState = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: null,
  providers: {},
  loading: false,
  error: ''
})

export const hasLlmConfig = () => Boolean(authState.user?.llm_configured)

const setSession = (token, user) => {
  authState.token = token || ''
  authState.user = user || null

  if (authState.token) {
    localStorage.setItem(TOKEN_KEY, authState.token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export const loadProviders = async () => {
  const res = await getLlmProviders()
  authState.providers = res.data?.providers || {}
  return authState.providers
}

export const loadCurrentUser = async () => {
  if (!authState.token) return null

  authState.loading = true
  authState.error = ''
  try {
    const res = await getCurrentUser()
    authState.user = res.data?.user || null
    return authState.user
  } catch (error) {
    // Only clear the session for actual auth failures (401), not transient network issues
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
  authState.error = ''
  try {
    const res = await loginAccount({ username, password })
    setSession(res.data?.token, res.data?.user)
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
  authState.error = ''
  try {
    const res = await registerAccount({ username, password })
    setSession(res.data?.token, res.data?.user)
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
  authState.error = ''
  try {
    const res = await updateLlmConfig(payload)
    authState.user = res.data?.user || authState.user
    return authState.user
  } catch (error) {
    authState.error = error.message || 'Failed to save LLM settings.'
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
