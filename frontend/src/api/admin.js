import axios from 'axios'
import i18n from '../i18n'

const ADMIN_TOKEN_KEY = 'futures_admin_token'
const USER_TOKEN_KEY = 'futures_auth_token'

const adminService = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

adminService.interceptors.request.use(config => {
  config.headers['Accept-Language'] = i18n.global.locale.value
  const token = getAdminAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
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

export const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_KEY) || ''
export const getAdminAccessToken = () => getAdminToken() || localStorage.getItem(USER_TOKEN_KEY) || ''

export const setAdminToken = (token) => {
  if (token) {
    localStorage.setItem(ADMIN_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(ADMIN_TOKEN_KEY)
  }
}

export const adminLogin = (data) => {
  return adminService.post('/api/admin/login', data)
}

export const getAdminMe = () => {
  return adminService.get('/api/admin/me')
}

export const getAdminUsers = () => {
  return adminService.get('/api/admin/users')
}

export const getVersionHistory = () => {
  return adminService.get('/api/admin/versions')
}

export const updateAdminUser = (userId, data) => {
  return adminService.put(`/api/admin/users/${userId}`, data)
}
