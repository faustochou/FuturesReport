<template>
  <main class="sub-page">
    <!-- Header -->
    <nav class="sub-nav">
      <button class="back-btn" type="button" @click="router.push('/')">←</button>
      <AppLogo variant="brand" />
    </nav>

    <section class="sub-hero">
      <p class="eyebrow">Subscription Plans</p>
      <h1>選擇適合你的方案</h1>
      <p class="sub-desc">FuturesReport 訂閱制讓 AI 多智能體模擬引擎持續為你服務。</p>
    </section>

    <!-- Checkout result banners -->
    <div v-if="checkoutResult === 'success'" class="banner success-banner">
      ✓ 訂閱成功！你的帳號已啟用。
    </div>
    <div v-if="checkoutResult === 'cancel'" class="banner cancel-banner">
      訂閱已取消，隨時可以重新選擇方案。
    </div>

    <!-- Current subscription info (if logged in and subscribed) -->
    <section v-if="currentSub" class="current-sub-card">
      <div>
        <p class="eyebrow">Current Plan</p>
        <p class="current-tier">{{ activeTier?.display_name ?? currentSub.tier_code }}</p>
        <p class="current-status">
          狀態：<strong>{{ statusLabel(currentSub.status) }}</strong>
          <span v-if="currentSub.current_period_end">
            · 到期日 {{ formatDate(currentSub.current_period_end) }}
          </span>
        </p>
      </div>
      <button class="outline-btn" type="button" :disabled="portalLoading" @click="goPortal">
        {{ portalLoading ? '跳轉中...' : '管理訂閱' }}
      </button>
    </section>

    <!-- Pricing cards -->
    <section class="pricing-grid">
      <!-- Lite -->
      <article class="pricing-card featured-card">
        <div class="plan-header">
          <p class="eyebrow">Most Popular</p>
          <h2>Lite</h2>
          <p class="plan-price">$9 <span class="period">/ 月</span></p>
        </div>
        <ul class="plan-features">
          <li>✓ 最多 100 個 Agent</li>
          <li>✓ 每月 10 次模擬</li>
          <li>✓ 報告匯出</li>
          <li>✓ 7 種地區時間模型</li>
        </ul>
        <button
          class="primary-btn"
          type="button"
          :disabled="checkoutLoading || !isLoggedIn"
          @click="subscribe('lite')"
        >
          <span v-if="checkoutLoading === 'lite'">跳轉中...</span>
          <span v-else-if="!isLoggedIn">請先登入</span>
          <span v-else>立即訂閱</span>
        </button>
        <p v-if="!isLoggedIn" class="login-hint">
          <button class="text-link" type="button" @click="router.push('/')">登入 / 註冊</button>
          後即可訂閱
        </p>
        <p v-if="subError" class="error-text">{{ subError }}</p>
      </article>

      <!-- Premium (coming soon) -->
      <article class="pricing-card disabled-card">
        <div class="plan-header">
          <p class="eyebrow coming-soon-tag">即將推出</p>
          <h2>Premium</h2>
          <p class="plan-price plan-price--dim">$29 <span class="period">/ 月</span></p>
        </div>
        <ul class="plan-features dim-features">
          <li>✓ 最多 10,000 個 Agent</li>
          <li>✓ 每月 100 次模擬</li>
          <li>✓ 進階報告分析</li>
          <li>✓ 優先技術支援</li>
        </ul>
        <button class="disabled-btn" type="button" disabled>即將推出</button>
      </article>

      <!-- Pro (coming soon) -->
      <article class="pricing-card disabled-card">
        <div class="plan-header">
          <p class="eyebrow coming-soon-tag">即將推出</p>
          <h2>Pro</h2>
          <p class="plan-price plan-price--dim">聯繫報價</p>
        </div>
        <ul class="plan-features dim-features">
          <li>✓ 無限 Agent 規模</li>
          <li>✓ 無限次模擬</li>
          <li>✓ 客製化地區模型</li>
          <li>✓ 專屬帳號支援</li>
          <li>✓ SLA 保障</li>
        </ul>
        <button class="disabled-btn" type="button" disabled>即將推出</button>
      </article>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authState } from '../store/auth'
import {
  getSubscriptionStatus,
  createCheckoutSession,
  createPortalSession,
} from '../api/subscription'

const router = useRouter()
const route  = useRoute()

const isLoggedIn    = computed(() => !!authState.token)
const checkoutLoading = ref('')
const portalLoading   = ref(false)
const subError        = ref('')
const currentSub      = ref(null)
const activeTier      = ref(null)
const checkoutResult  = computed(() => route.query.checkout || '')

const loadStatus = async () => {
  if (!isLoggedIn.value) return
  try {
    const res = await getSubscriptionStatus()
    currentSub.value  = res.data?.subscription  || null
    activeTier.value  = res.data?.active_tier    || null
  } catch {
    // Not subscribed yet — that's fine
  }
}

const subscribe = async (tierCode) => {
  if (!isLoggedIn.value) return
  subError.value        = ''
  checkoutLoading.value = tierCode
  try {
    const res = await createCheckoutSession(tierCode)
    const url = res.data?.checkout_url
    if (url) window.location.href = url
  } catch (err) {
    subError.value = err.message || '建立結帳工作階段失敗'
  } finally {
    checkoutLoading.value = ''
  }
}

const goPortal = async () => {
  portalLoading.value = true
  try {
    const res = await createPortalSession()
    const url = res.data?.portal_url
    if (url) window.location.href = url
  } catch (err) {
    subError.value = err.message || '建立客戶入口失敗'
  } finally {
    portalLoading.value = false
  }
}

const statusLabel = (s) => ({
  active:              '使用中',
  trialing:            '試用中',
  canceled:            '已取消',
  past_due:            '付款逾期',
  incomplete:          '未完成',
  incomplete_expired:  '已過期',
  unpaid:              '未付款',
}[s] || s)

const formatDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric' })
}

onMounted(loadStatus)
</script>

<style scoped>
.sub-page {
  min-height: 100vh;
  padding: 0 0 60px;
  background: #f6f6f1;
  color: #111;
  font-family: 'JetBrains Mono', 'Noto Sans TC', monospace;
}

.sub-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 32px;
  border-bottom: 1px solid #111;
  background: #fff;
}

.back-btn {
  width: 38px;
  height: 38px;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font-weight: 800;
  cursor: pointer;
  font-family: inherit;
}

.sub-hero {
  text-align: center;
  padding: 56px 32px 32px;
}

.sub-hero h1 {
  margin: 8px 0 12px;
  font-size: clamp(28px, 5vw, 48px);
  font-weight: 800;
  letter-spacing: -0.02em;
}

.sub-desc {
  margin: 0;
  color: #555;
  font-size: 15px;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  color: #666;
  letter-spacing: 0.08em;
}

/* Banners */
.banner {
  max-width: 680px;
  margin: 0 auto 24px;
  padding: 14px 20px;
  border: 1px solid #111;
  font-weight: 800;
  font-size: 14px;
}

.success-banner { background: #f1faf6; border-color: #1a936f; color: #116249; }
.cancel-banner  { background: #fdf6ec; border-color: #c97c2e; color: #7a4a10; }

/* Current subscription */
.current-sub-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  max-width: 680px;
  margin: 0 auto 32px;
  padding: 18px 20px;
  border: 1px solid #111;
  background: #fff;
  box-shadow: 4px 4px 0 #111;
}

.current-tier {
  margin: 4px 0 6px;
  font-size: 22px;
  font-weight: 800;
}

.current-status {
  margin: 0;
  font-size: 13px;
  color: #555;
}

/* Pricing grid */
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 18px;
  max-width: 1020px;
  margin: 0 auto;
  padding: 0 32px;
}

.pricing-card {
  border: 1px solid #111;
  background: #fff;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.featured-card {
  box-shadow: 6px 6px 0 #111;
  border-width: 2px;
}

.disabled-card {
  opacity: 0.65;
}

.plan-header { display: grid; gap: 6px; }

.plan-header h2 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
}

.plan-price {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
}

.plan-price--dim { color: #888; }

.period {
  font-size: 14px;
  font-weight: 400;
  color: #666;
}

.plan-features {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
  font-size: 13px;
  flex: 1;
}

.dim-features { color: #888; }

.primary-btn {
  min-height: 44px;
  border: 2px solid #111;
  background: #111;
  color: #fff;
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.outline-btn {
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid #111;
  background: #fff;
  color: #111;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  flex: none;
}

.outline-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.disabled-btn {
  min-height: 44px;
  border: 1px solid #bbb;
  background: #eee;
  color: #999;
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: not-allowed;
}

.coming-soon-tag { color: #c97c2e; }

.login-hint {
  margin: 0;
  font-size: 12px;
  color: #666;
  text-align: center;
}

.text-link {
  background: none;
  border: none;
  color: #111;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}

.error-text { color: #d64545; font-size: 13px; font-weight: 800; margin: 0; }

@media (max-width: 640px) {
  .sub-nav     { padding: 12px 16px; }
  .sub-hero    { padding: 40px 16px 24px; }
  .pricing-grid { padding: 0 16px; }
  .current-sub-card { flex-direction: column; align-items: flex-start; }
}
</style>
