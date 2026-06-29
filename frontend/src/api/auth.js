import service from './index'

export const getLlmProviders = () => {
  return service.get('/api/auth/providers')
}

export const registerAccount = (data) => {
  return service.post('/api/auth/register', data)
}

export const loginAccount = (data) => {
  return service.post('/api/auth/login', data)
}

export const getCurrentUser = () => {
  return service.get('/api/auth/me')
}

export const updateLlmConfig = (data) => {
  return service.put('/api/auth/llm-config', data)
}

export const logoutAccount = () => {
  return service.post('/api/auth/logout')
}
