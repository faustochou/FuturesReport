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
      <article
        v-for="plan in plans"
        :key="plan.code"
        class="pricing-card"
        :class="{
          'featured-card': isOpen(plan) && plan.featured,
          'disabled-card': !isOpen(plan),
          'current-card': isCurrent(plan),
        }"
      >
        <div class="plan-header">
          <p class="eyebrow" :class="{ 'coming-soon-tag': !isOpen(plan) }">
            <template v-if="!isOpen(plan)">{{ $t('subscription.comingSoon') }}</template>
            <template v-else-if="plan.eyebrowKey">{{ $t(plan.eyebrowKey) }}</template>
            <template v-else>&nbsp;</template>
          </p>
          <h2>{{ plan.name }}</h2>
          <p v-if="plan.price" class="plan-price" :class="{ 'plan-price--dim': !isOpen(plan) }">
            {{ plan.price }} <span class="period">{{ $t('subscription.perMonth') }}</span>
          </p>
          <p v-else class="plan-price plan-price--dim">{{ $t('subscription.proPrice') }}</p>
        </div>

        <ul class="plan-features" :class="{ 'dim-features': !isOpen(plan) }">
          <li v-for="key in plan.features" :key="key">✓ {{ $t(`subscription.${key}`) }}</li>
        </ul>

        <template v-if="isOpen(plan)">
          <button
            class="primary-btn"
            type="button"
            :disabled="!isLoggedIn || !!checkoutLoading || isCurrent(plan)"
            @click="choosePlan(plan)"
          >
            <span v-if="checkoutLoading === plan.code">{{ $t('subscription.redirecting') }}</span>
            <span v-else-if="!isLoggedIn">{{ $t('subscription.loginFirst') }}</span>
            <span v-else-if="isCurrent(plan)">{{ $t('subscription.currentPlanBtn') }}</span>
            <span v-else-if="viaPortal">{{ $t('subscription.switchPlanBtn') }}</span>
            <span v-else>{{ $t('subscription.subscribeBtn') }}</span>
          </button>
          <p v-if="!isLoggedIn" class="login-hint">
            <button class="text-link" type="button" @click="router.push('/')">{{ $t('subscription.loginHint') }}</button>
            {{ $t('subscription.loginHintPost') }}
          </p>
        </template>
        <button v-else class="disabled-btn" type="button" disabled>{{ $t('subscription.comingSoon') }}</button>
      </article>
    </section>
    <p v-if="subError" class="error-text plan-error">{{ subError }}</p>

    <!-- Models provided by this site (Premium / Pro / admin only) -->
    <section v-if="authState.user?.can_use_platform_models" class="platform-card">
      <p class="eyebrow">{{ $t('subscription.platformModelsTitle') }}</p>
      <p class="platform-desc">{{ $t('subscription.platformModelsDesc') }}</p>
      <ul v-if="authState.platformModels.length" class="platform-list">
        <li v-for="m in authState.platformModels" :key="m.id">
          <strong>{{ m.label }}</strong>
          <span class="platform-meta">{{ m.provider_label }} · {{ m.model }}</span>
          <span v-if="authState.user.platform_model?.id === m.id" class="platform-badge">
            {{ $t('subscription.platformModelInUse') }}
          </span>
        </li>
      </ul>
      <p v-else class="platform-desc">{{ $t('subscription.platformModelsEmpty') }}</p>
      <p v-if="authState.platformModels.length" class="platform-desc">{{ $t('subscription.platformModelsHow') }}</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { authState, loadPlatformModels } from '../store/auth'
import {
  getPublicTiers,
  getSubscriptionStatus,
  createCheckoutSession,
  createPortalSession,
} from '../api/subscription'

const router = useRouter()
const route  = useRoute()
const { t, locale } = useI18n()

// Plan cards. Lite/Premium are open for purchase only when the admin has enabled
// the tier AND set its Stripe price (GET /api/subscription/tiers); Pro is
// contact-only and always shown as coming soon.
const plans = [
  {
    code: 'lite', name: 'Lite', price: '$9', featured: true, eyebrowKey: 'subscription.mostPopular',
    features: ['liteF1', 'liteF2', 'liteF3', 'liteF4'],
  },
  {
    code: 'premium', name: 'Premium', price: '$29', eyebrowKey: 'subscription.premiumTag',
    features: ['premiumF1', 'premiumF2', 'premiumF3', 'premiumF4', 'premiumF5', 'premiumF6'],
  },
  {
    code: 'pro', name: 'Pro', price: '', contactOnly: true,
    features: ['proF1', 'proF2', 'proF3', 'proF4', 'proF5'],
  },
]

const openTiers = ref({ lite: true })
const isOpen = (plan) => !plan.contactOnly && !!openTiers.value[plan.code]

const isLoggedIn    = computed(() => !!authState.token)
const checkoutLoading = ref('')
const portalLoading   = ref(false)
const subError        = ref('')
const currentSub      = ref(null)
const activeTier      = ref(null)
const checkoutResult  = computed(() => route.query.checkout || '')

const hasLiveSub = computed(() =>
  !!currentSub.value && ['active', 'trialing'].includes(currentSub.value.status)
)
const isCurrent = (plan) => hasLiveSub.value && currentSub.value.tier_code === plan.code
// A Stripe-billed subscriber changes plan in the billing portal (a second checkout
// would bill them twice); admin-granted plans have no Stripe subscription.
const viaPortal = computed(() => hasLiveSub.value && !!currentSub.value.stripe_subscription_id)

const loadTiers = async () => {
  try {
    const res = await getPublicTiers()
    const map = {}
    for (const tier of res.data?.tiers || []) map[tier.tier_code] = !!tier.is_available
    openTiers.value = map
  } catch {
    // keep the default (Lite open) if the plan list cannot be fetched
  }
}

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

const choosePlan = (plan) => (viaPortal.value ? goPortal() : subscribe(plan.code))

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
  subError.value      = ''
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

onMounted(async () => {
  loadTiers()
  await loadStatus()
  loadPlatformModels()
})
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

.current-card { border-width: 2px; }

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
  align-content: start;
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

.plan-error { text-align: center; margin: 16px 32px 0; }

/* Models provided by this site */
.platform-card {
  display: grid;
  gap: 10px;
  width: calc(100% - 64px);
  max-width: 1020px;
  margin: 32px auto 0;
  padding: 20px 24px;
  border: 1px solid #111;
  background: #fff;
}

.platform-desc { margin: 0; font-size: 13px; color: #555; line-height: 1.6; }

.platform-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.platform-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 12px;
  border: 1px solid #ddd;
  font-size: 13px;
}

.platform-meta { color: #666; font-size: 12px; }

.platform-badge {
  margin-left: auto;
  padding: 2px 8px;
  border: 1px solid #1a936f;
  background: #f1faf6;
  color: #116249;
  font-size: 11px;
  font-weight: 800;
}

@media (max-width: 640px) {
  .sub-hero    { padding: 32px 16px 24px; }
  .pricing-grid { padding: 0 16px; }
  .platform-card { width: calc(100% - 32px); }
  .plan-error { margin: 16px 16px 0; }
  .current-sub-card { flex-direction: column; align-items: flex-start; }
}
</style>
