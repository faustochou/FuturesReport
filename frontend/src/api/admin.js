import axios from 'axios'
import i18n from '../i18n'

const ADMIN_TOKEN_KEY = 'futures_admin_token'
const USER_TOKEN_KEY  = 'futures_auth_token'

const adminService = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/',
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
})

adminService.interceptors.request.use(config => {
  config.headers['Accept-Language'] = i18n.global.locale.value
  const token = getAdminAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

adminService.interceptors.response.use(
  response => {
    const res = response.data
    if (!res.success && res.success !== undefined) {
      return Promise.reject(new Error(res.error || res.message || 'Admin request failed'))
    }
    return res
  },
  error => Promise.reject(error)
)

export const getAdminToken       = () => localStorage.getItem(ADMIN_TOKEN_KEY) || ''
export const getAdminAccessToken = () => getAdminToken() || localStorage.getItem(USER_TOKEN_KEY) || ''
export const setAdminToken       = (token) => {
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token)
  else        localStorage.removeItem(ADMIN_TOKEN_KEY)
}

// Auth
export const adminLogin    = (data)   => adminService.post('/api/admin/login', data)
export const getAdminMe    = ()       => adminService.get('/api/admin/me')

// Dashboard
export const getDashboard  = ()       => adminService.get('/api/admin/dashboard')

// Users – existing
export const getAdminUsers    = ()              => adminService.get('/api/admin/users')
export const updateAdminUser  = (id, data)      => adminService.put(`/api/admin/users/${id}`, data)

// Users – new
export const changeUserRole   = (id, role)      => adminService.put(`/api/admin/users/${id}/role`,   { role })
export const toggleUserActive = (id, is_active) => adminService.put(`/api/admin/users/${id}/active`, { is_active })
export const deleteUser       = (id)            => adminService.delete(`/api/admin/users/${id}`)

// Version history
export const getVersionHistory = () => adminService.get('/api/admin/versions')

// Stripe settings (read-only)
export const getStripeSettings = () => adminService.get('/api/admin/stripe/settings')

// Subscription tier management
export const listAdminTiers    = ()               => adminService.get('/api/admin/subscription/tiers')
export const updateAdminTier   = (code, data)     => adminService.put(`/api/admin/subscription/tiers/${code}`, data)
