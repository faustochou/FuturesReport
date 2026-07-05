<template>
  <main class="sub-page">
    <section class="sub-hero">
      <p class="eyebrow">{{ $t('subscription.plans') }}</p>
      <h1>{{ $t('subscription.heroTitle') }}</h1>
      <p class="sub-desc">{{ $t('subscription.heroDesc') }}</p>
    </section>

    <!-- Checkout result banners -->
    <div v-if="checkoutResult === 'success'" class="banner success-banner">
      {{ $t('subscription.successBanner') }}
    </div>
    <div v-if="checkoutResult === 'cancel'" class="banner cancel-banner">
      {{ $t('subscription.cancelBanner') }}
    </div>

    <!-- Current subscription info (if logged in and subscribed) -->
    <section v-if="currentSub" class="current-sub-card">
      <div>
        <p class="eyebrow">{{ $t('subscription.currentPlan') }}</p>
        <p class="current-tier">{{ activeTier?.display_name ?? currentSub.tier_code }}</p>
        <p class="current-status">
          {{ $t('subscription.statusLabel') }}：<strong>{{ statusLabel(currentSub.status) }}</strong>
          <span v-if="currentSub.current_period_end">
            · {{ $t('subscription.expiryLabel') }} {{ formatDate(currentSub.current_period_end) }}
          </span>
        </p>
      </div>
      <button class="outline-btn" type="button" :disabled="portalLoading" @click="goPortal">
        {{ portalLoading ? $t('subscription.redirecting') : $t('subscription.manageBtn') }}
      </button>
    </section>

    <!-- Pricing cards -->
    <section class="pricing-grid">
      <!-- Lite -->
      <article class="pricing-card featured-card">
        <div class="plan-header">
          <p class="eyebrow">{{ $t('subscription.mostPopular') }}</p>
          <h2>Lite</h2>
          <p class="plan-price">$9 <span class="period">{{ $t('subscription.perMonth') }}</span></p>
        </div>
        <ul class="plan-features">
          <li>✓ {{ $t('subscription.liteF1') }}</li>
          <li>✓ {{ $t('subscription.liteF2') }}</li>
          <li>✓ {{ $t('subscription.liteF3') }}</li>
          <li>✓ {{ $t('subscription.liteF4') }}</li>
        </ul>
        <button
          class="primary-btn"
          type="button"
          :disabled="checkoutLoading || !isLoggedIn"
          @click="subscribe('lite')"
        >
          <span v-if="checkoutLoading === 'lite'">{{ $t('subscription.redirecting') }}</span>
          <span v-else-if="!isLoggedIn">{{ $t('subscription.loginFirst') }}</span>
          <span v-else>{{ $t('subscription.subscribeBtn') }}</span>
        </button>
        <p v-if="!isLoggedIn" class="login-hint">
          <button class="text-link" type="button" @click="router.push('/')">{{ $t('subscription.loginHint') }}</button>
          {{ $t('subscription.loginHintPost') }}
        </p>
        <p v-if="subError" class="error-text">{{ subError }}</p>
      </article>

      <!-- Premium (coming soon) -->
      <article class="pricing-card disabled-card">
        <div class="plan-header">
          <p class="eyebrow coming-soon-tag">{{ $t('subscription.comingSoon') }}</p>
          <h2>Premium</h2>
          <p class="plan-price plan-price--dim">$29 <span class="period">{{ $t('subscription.perMonth') }}</span></p>
        </div>
        <ul class="plan-features dim-features">
          <li>✓ {{ $t('subscription.premiumF1') }}</li>
          <li>✓ {{ $t('subscription.premiumF2') }}</li>
          <li>✓ {{ $t('subscription.premiumF3') }}</li>
          <li>✓ {{ $t('subscription.premiumF4') }}</li>
        </ul>
        <button class="disabled-btn" type="button" disabled>{{ $t('subscription.comingSoon') }}</button>
      </article>

      <!-- Pro (coming soon) -->
      <article class="pricing-card disabled-card">
        <div class="plan-header">
          <p class="eyebrow coming-soon-tag">{{ $t('subscription.comingSoon') }}</p>
          <h2>Pro</h2>
          <p class="plan-price plan-price--dim">{{ $t('subscription.proPrice') }}</p>
        </div>
        <ul class="plan-features dim-features">
          <li>✓ {{ $t('subscription.proF1') }}</li>
          <li>✓ {{ $t('subscription.proF2') }}</li>
          <li>✓ {{ $t('subscription.proF3') }}</li>
          <li>✓ {{ $t('subscription.proF4') }}</li>
          <li>✓ {{ $t('subscription.proF5') }}</li>
        </ul>
        <button class="disabled-btn" type="button" disabled>{{ $t('subscription.comingSoon') }}</button>
      </article>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { authState } from '../store/auth'
import {
  getSubscriptionStatus,
  createCheckoutSession,
  createPortalSession,
} from '../api/subscription'

const router = useRouter()
const route  = useRoute()
const { t, locale } = useI18n()

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
    subError.value = err.message || t('subscription.checkoutError')
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
    subError.value = err.message || t('subscription.portalError')
  } finally {
    portalLoading.value = false
  }
}

const statusLabel = (s) => ({
  active:              t('subscription.statusActive'),
  trialing:            t('subscription.statusTrialing'),
  canceled:            t('subscription.statusCanceled'),
  past_due:            t('subscription.statusPastDue'),
  incomplete:          t('subscription.statusIncomplete'),
  incomplete_expired:  t('subscription.statusExpired'),
  unpaid:              t('subscription.statusUnpaid'),
}[s] || s)

const formatDate = (iso) => {
  if (!iso) return ''
  const lang = locale.value === 'en' ? 'en-US' : locale.value === 'zh' ? 'zh-CN' : 'zh-TW'
  return new Date(iso).toLocaleDateString(lang, { year: 'numeric', month: 'long', day: 'numeric' })
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

.sub-hero {
  text-align: center;
  padding: 48px 32px 32px;
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
  .sub-hero    { padding: 32px 16px 24px; }
  .pricing-grid { padding: 0 16px; }
  .current-sub-card { flex-direction: column; align-items: flex-start; }
}
</style>
