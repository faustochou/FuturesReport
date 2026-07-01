import service from './index'

export const getSubscriptionStatus = () =>
  service.get('/api/subscription/status')

export const createCheckoutSession = (tier_code) =>
  service.post('/api/subscription/create-checkout-session', { tier_code })

export const createPortalSession = () =>
  service.post('/api/subscription/create-portal-session')
