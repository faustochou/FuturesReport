<template>
  <div class="home-container">
    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">{{ $t('home.tagline') }}</span>
            <span class="version-text">{{ $t('home.version') }}</span>
          </div>

          <h1 class="main-title">
            {{ $t('home.heroTitle1') }}<br>
            <span class="gradient-text">{{ $t('home.heroTitle2') }}</span>
          </h1>

          <div class="hero-desc">
            <p>
              <i18n-t keypath="home.heroDesc" tag="span">
                <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
                <template #agentScale><span class="highlight-orange">{{ $t('home.heroDescAgentScale') }}</span></template>
                <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
              </i18n-t>
            </p>
            <p class="slogan-text">
              {{ $t('home.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>

          <button class="hero-cta-btn" @click="goToLaunch">
            <span>{{ hasActiveSubscription ? $t('home.ctaStart') : $t('home.ctaSubscribe') }}</span>
            <span class="cta-arrow">→</span>
          </button>

          <div class="decoration-square"></div>
        </div>

        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <AppLogo variant="hero" class="hero-logo" />
          </div>

          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：三行独立布局 -->
      <section class="dashboard-section">
        <!-- Row 1: 系统状态 -->
        <div class="status-row">
          <div class="panel-header">
            <span class="status-dot">■</span> {{ $t('home.systemStatus') }}
          </div>
          <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
          <p class="section-desc">{{ $t('home.systemReadyDesc') }}</p>
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
              <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
              <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
            </div>
          </div>
        </div>

        <!-- Row 2: 工作流序列 -->
        <div class="steps-container">
          <div class="steps-header">
             <span class="diamond-icon">◇</span> {{ $t('home.workflowSequence') }}
          </div>
          <div class="workflow-list">
            <div class="workflow-item">
              <span class="step-num">01</span>
              <div class="step-info">
                <div class="step-title">{{ $t('home.step01Title') }}</div>
                <div class="step-desc">{{ $t('home.step01Desc') }}</div>
              </div>
            </div>
            <div class="workflow-item">
              <span class="step-num">02</span>
              <div class="step-info">
                <div class="step-title">{{ $t('home.step02Title') }}</div>
                <div class="step-desc">{{ $t('home.step02Desc') }}</div>
              </div>
            </div>
            <div class="workflow-item">
              <span class="step-num">03</span>
              <div class="step-info">
                <div class="step-title">{{ $t('home.step03Title') }}</div>
                <div class="step-desc">{{ $t('home.step03Desc') }}</div>
              </div>
            </div>
            <div class="workflow-item">
              <span class="step-num">04</span>
              <div class="step-info">
                <div class="step-title">{{ $t('home.step04Title') }}</div>
                <div class="step-desc">{{ $t('home.step04Desc') }}</div>
              </div>
            </div>
            <div class="workflow-item">
              <span class="step-num">05</span>
              <div class="step-info">
                <div class="step-title">{{ $t('home.step05Title') }}</div>
                <div class="step-desc">{{ $t('home.step05Desc') }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3: 未来前瞻分析引擎 (full-width) -->
        <div class="method-box">

            <!-- Header: title + description -->
            <div class="method-header">
              <div class="method-header-top">
                <span class="method-status-dot"></span>
              </div>
              <h2 class="method-title">{{ $t('home.methodologyTitle') }}</h2>
              <p class="method-desc">{{ $t('home.methodologyDesc') }}</p>
            </div>

            <div class="method-rule"></div>

            <!-- Report types: icon list -->
            <div class="report-list">
              <div class="report-item">
                <div class="report-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                    <rect x="9" y="3" width="6" height="4" rx="1.5"/>
                    <polyline points="7 13 10 16 17 11"/>
                  </svg>
                </div>
                <div class="report-text">
                  <span class="report-name">{{ $t('home.reportCorporate') }}</span>
                  <span class="report-sub">Annual &amp; Financial Reports</span>
                </div>
                <span class="report-num">01</span>
              </div>
              <div class="report-item">
                <div class="report-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 21h18M3 10h18M12 3 3 10h18L12 3z"/>
                    <path d="M9 21v-5h6v5"/>
                  </svg>
                </div>
                <div class="report-text">
                  <span class="report-name">{{ $t('home.reportGovernment') }}</span>
                  <span class="report-sub">Government &amp; Policy Reports</span>
                </div>
                <span class="report-num">02</span>
              </div>
              <div class="report-item">
                <div class="report-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 14 3 9l9-5 9 5-9 5z"/>
                    <path d="M3 9v6l9 5 9-5V9"/>
                    <line x1="12" y1="14" x2="12" y2="19"/>
                  </svg>
                </div>
                <div class="report-text">
                  <span class="report-name">{{ $t('home.reportAcademic') }}</span>
                  <span class="report-sub">Academic Research Papers</span>
                </div>
                <span class="report-num">03</span>
              </div>
              <div class="report-item">
                <div class="report-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="9"/>
                    <path d="M3.6 9h16.8M3.6 15h16.8"/>
                    <path d="M12 3c-2.4 3-3.6 5.8-3.6 9s1.2 6 3.6 9M12 3c2.4 3 3.6 5.8 3.6 9s-1.2 6-3.6 9"/>
                  </svg>
                </div>
                <div class="report-text">
                  <span class="report-name">{{ $t('home.reportInternational') }}</span>
                  <span class="report-sub">International Organizations</span>
                </div>
                <span class="report-num">04</span>
              </div>
            </div>

            <div class="method-rule"></div>

            <!-- CTA -->
            <div class="method-footer">
              <button class="cta-btn" @click="goToLaunch">
                <span>{{ hasActiveSubscription ? $t('home.ctaStart') : $t('home.ctaSubscribe') }}</span>
                <span class="cta-arrow">→</span>
              </button>
              <p v-if="!hasActiveSubscription" class="cta-hint">{{ $t('home.ctaHint') }}</p>
            </div>

          </div>
      </section>

      <footer class="site-footer">
        <div class="social-row" v-if="socialLinks">
          <a v-if="socialLinks.social_facebook" :href="socialLinks.social_facebook" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="Facebook">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
          </a>
          <a v-if="socialLinks.social_x" :href="socialLinks.social_x" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="X">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
          </a>
          <a v-if="socialLinks.social_instagram" :href="socialLinks.social_instagram" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="Instagram">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
          </a>
          <a v-if="socialLinks.social_threads" :href="socialLinks.social_threads" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="Threads">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.028-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.476l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 013.02.142c-.126-.742-.375-1.332-.74-1.663-.485-.444-1.218-.668-2.18-.668h-.042c-.895.005-2.57.137-3.528 1.547l-1.72-1.12c1.307-2.015 3.36-2.397 5.233-2.397h.052c1.69 0 3.071.454 3.905 1.277 1.005.989 1.325 2.437 1.418 3.762.272.128.53.276.77.44 1.399.947 2.223 2.217 2.57 3.883.451 2.189-.146 4.843-2.29 6.945-1.864 1.834-4.114 2.765-7.298 2.789z"/></svg>
          </a>
          <a v-if="socialLinks.social_github" :href="socialLinks.social_github" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="GitHub">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
          </a>
        </div>
        <small>© 2026 Nexora. All rights reserved. 未境 版权所有。 Based on MiroFish, licensed under AGPLv3</small>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authState } from '../store/auth'
import { getSocialLinks } from '../api/settings'

const router = useRouter()
const socialLinks = ref(null)

const hasActiveSubscription = computed(() => {
  const sub = authState.user?.subscription
  if (!sub) return false
  return sub.status === 'active' && ['lite', 'premium', 'pro'].includes(sub.tier_code)
})

const scrollToBottom = () => {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}

const goToLaunch = () => {
  router.push(hasActiveSubscription.value ? '/launch' : '/subscription')
}

onMounted(async () => {
  try {
    const res = await getSocialLinks()
    socialLinks.value = res.data
  } catch {
    // silent — social icons stay hidden
  }
})
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

.site-footer {
  margin-top: 56px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  text-align: center;
  color: #888;
}

.site-footer small {
  font-size: 0.72rem;
  line-height: 1.6;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-text {
  color: #999;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px;
  width: 100%;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 三行布局 */
.dashboard-section {
  display: flex;
  flex-direction: column;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
}

/* Row 1: 状态行 */
.status-row {
  display: block;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* Hero CTA 按钮 */
.hero-cta-btn {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  background: #000000;
  color: #FFFFFF;
  border: none;
  padding: 14px 22px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.88rem;
  cursor: pointer;
  letter-spacing: 1px;
  margin-bottom: 24px;
  transition: background 0.25s, color 0.25s, transform 0.18s;
}

.hero-cta-btn:hover {
  background: #16e77f;
  color: #000000;
  transform: translateY(-2px);
}

.hero-cta-btn:active {
  transform: translateY(0);
}

.hero-cta-btn:hover .cta-arrow {
  transform: translateX(5px);
}

/* 社群图标 */
.social-row {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 16px;
}

.social-link {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: #bbb;
  transition: color 0.2s, transform 0.18s;
  text-decoration: none;
}

.social-link:hover {
  color: var(--black);
  transform: translateY(-2px);
}

.social-link svg {
  width: 18px;
  height: 18px;
}

/* Row 3: 未来前瞻分析引擎 — 全黑暗主題 */
.method-box {
  width: 100%;
  background: #0A0A0A;
  border: 1px solid #1C1C1C;
  overflow: hidden;
}

/* ── Header ── */
.method-header {
  padding: 36px 36px 30px;
}

.method-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
}

.method-badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.35);
}

.method-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--orange);
  box-shadow: 0 0 8px rgba(255, 69, 0, 0.7);
  animation: dot-pulse 2.4s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(255,69,0,0.7); }
  50%       { opacity: 0.5; box-shadow: 0 0 2px rgba(255,69,0,0.3); }
}

.method-title {
  font-size: 2.5rem;
  font-weight: 500;
  color: #FFFFFF;
  margin: 0 0 16px;
  line-height: 1.2;
  letter-spacing: -1.2px;
}

.method-desc {
  font-size: 0.84rem;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.42);
  margin: 0;
}

/* ── Divider ── */
.method-rule {
  height: 1px;
  background: rgba(255, 255, 255, 0.07);
  margin: 0 36px;
}

/* ── Report list ── */
.report-list {
  padding: 6px 36px;
}

.report-item {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 17px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: background 0.2s;
  cursor: default;
}

.report-item:last-child {
  border-bottom: none;
}

.report-item:hover .report-icon {
  color: #16e77f;
}

.report-item:hover .report-name {
  color: #FFFFFF;
}

.report-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.3);
  transition: color 0.25s;
}

.report-icon svg {
  width: 100%;
  height: 100%;
}

.report-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.report-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.3;
  transition: color 0.25s;
}

.report-sub {
  font-family: var(--font-mono);
  font-size: 0.62rem;
  color: rgba(255, 255, 255, 0.22);
  letter-spacing: 0.5px;
}

.report-num {
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.15);
  letter-spacing: 1px;
  flex-shrink: 0;
}

/* ── Footer: methodology strip + CTA ── */
.method-footer {
  padding: 20px 36px 32px;
  background: rgba(255, 255, 255, 0.02);
}

.method-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.method-strip-item {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.28);
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.method-strip-sep {
  color: rgba(255, 255, 255, 0.12);
  font-size: 0.75rem;
  line-height: 1;
}

.cta-btn {
  width: 100%;
  background: #FFFFFF;
  color: #000000;
  border: none;
  padding: 17px 22px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.88rem;
  cursor: pointer;
  letter-spacing: 1px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.25s, color 0.25s, transform 0.18s;
}

.cta-btn:hover {
  background: #16e77f;
  color: #000000;
  transform: translateY(-2px);
}

.cta-btn:active {
  transform: translateY(0);
}

.cta-arrow {
  font-size: 1rem;
  transition: transform 0.2s;
}

.cta-btn:hover .cta-arrow {
  transform: translateX(5px);
}

.cta-hint {
  margin-top: 11px;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  color: rgba(255, 255, 255, 0.2);
  text-align: center;
  letter-spacing: 0.5px;
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }

  .hero-section {
    flex-direction: column;
  }

  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }

  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }

  .site-footer {
    margin-top: 40px;
  }
}

@media (max-width: 600px) {
  .method-header,
  .report-list,
  .method-rule,
  .method-footer {
    padding-left: 24px;
    padding-right: 24px;
  }
}
</style>

<style>
/* English locale adjustments (unscoped to target html[lang]) */
html[lang="en"] .main-title {
  font-size: 3.5rem;
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: -1px;
}

html[lang="en"] .hero-desc {
  text-align: left;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .slogan-text {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .tag-row {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}


/* Left pane: system status + workflow */
html[lang="en"] .status-section {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .status-section .status-ready {
  font-size: 1.6rem;
}

html[lang="en"] .status-section .metric-value {
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 1.4rem;
}

html[lang="en"] .workflow-list .step-title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .workflow-list .step-desc {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  font-size: 0.72rem !important;
  line-height: 1.4 !important;
}

html[lang="en"] .workflow-list {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
