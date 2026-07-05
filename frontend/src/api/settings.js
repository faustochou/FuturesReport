import service from './index'

// Public settings – no auth required
export const getSocialLinks = () => service.get('/api/settings/social')
