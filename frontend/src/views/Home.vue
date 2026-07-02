<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">
        <AppLogo variant="brand" />
      </div>
      <div class="nav-links"></div>
    </nav>

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

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> {{ $t('home.systemStatus') }}
          </div>

          <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
          <p class="section-desc">
            {{ $t('home.systemReadyDesc') }}
          </p>

          <!-- 数据指标卡片 -->
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

          <!-- 项目模拟步骤介绍 -->
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
        </div>

        <!-- 右栏：未來學研究方法論 -->
        <div class="right-panel">
          <div class="method-box">

            <!-- Dark header block -->
            <div class="method-header-block">
              <span class="method-badge">{{ $t('home.methodologyBadge') }}</span>
              <h2 class="method-title">{{ $t('home.methodologyTitle') }}</h2>
              <p class="method-desc">{{ $t('home.methodologyDesc') }}</p>
            </div>

            <!-- Light body -->
            <div class="method-body">

              <!-- Supported report types -->
              <div class="method-section-label">
                <span class="section-diamond">◇</span> {{ $t('home.reportTypesLabel') }}
              </div>
              <div class="report-types-grid">
                <div class="report-type-card">
                  <span class="report-type-num">01</span>
                  <span class="report-type-name">{{ $t('home.reportCorporate') }}</span>
                </div>
                <div class="report-type-card">
                  <span class="report-type-num">02</span>
                  <span class="report-type-name">{{ $t('home.reportGovernment') }}</span>
                </div>
                <div class="report-type-card">
                  <span class="report-type-num">03</span>
                  <span class="report-type-name">{{ $t('home.reportAcademic') }}</span>
                </div>
                <div class="report-type-card">
                  <span class="report-type-num">04</span>
                  <span class="report-type-name">{{ $t('home.reportInternational') }}</span>
                </div>
              </div>

              <!-- Research methodology tags -->
              <div class="method-section-label">
                <span class="section-diamond">◇</span> {{ $t('home.methodLabel') }}
              </div>
              <div class="method-tags">
                <span class="method-tag">STEEP</span>
                <span class="method-tag">CLA</span>
                <span class="method-tag">Futures Cone</span>
                <span class="method-tag">Scenario Planning</span>
              </div>

              <!-- CTA -->
              <div class="cta-area">
                <p class="cta-label">{{ $t('home.ctaTitle') }}</p>
                <button class="cta-btn" @click="goToLaunch">
                  <span>{{ hasActiveSubscription ? $t('home.ctaStart') : $t('home.ctaSubscribe') }}</span>
                  <span class="cta-arrow">→</span>
                </button>
                <p v-if="!hasActiveSubscription" class="cta-hint">{{ $t('home.ctaHint') }}</p>
              </div>

            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase />

      <footer class="site-footer">
        <small>© 2026 Nexora. All rights reserved. 未境 版权所有。 Based on MiroFish, licensed under AGPLv3</small>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import { authState } from '../store/auth'

const router = useRouter()

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

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
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

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 左侧面板 */
.left-panel {
  flex: 0.8;
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

/* 右侧：未來學研究方法論 */
.right-panel {
  flex: 1.2;
}

.method-box {
  border: 1px solid var(--black);
  overflow: hidden;
}

/* Dark header block */
.method-header-block {
  background: var(--black);
  padding: 36px 36px 32px;
}

.method-badge {
  display: inline-block;
  background: var(--orange);
  color: var(--white);
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 4px 10px;
  text-transform: uppercase;
  margin-bottom: 22px;
}

.method-title {
  font-size: 2.6rem;
  font-weight: 500;
  color: var(--white);
  margin: 0 0 18px;
  line-height: 1.2;
  letter-spacing: -1px;
}

.method-desc {
  font-size: 0.88rem;
  line-height: 1.85;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

/* Light body */
.method-body {
  padding: 30px 32px 32px;
  background: var(--white);
  display: flex;
  flex-direction: column;
  gap: 0;
}

.method-section-label {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  letter-spacing: 0.5px;
}

.section-diamond {
  color: var(--orange);
  font-size: 0.9rem;
  line-height: 1;
}

/* Report types grid */
.report-types-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: #E0E0E0;
  border: 1px solid #E0E0E0;
  margin-bottom: 28px;
}

.report-type-card {
  background: var(--white);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: background 0.2s;
  cursor: default;
}

.report-type-card:hover {
  background: #F5F5F5;
}

.report-type-num {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--orange);
  letter-spacing: 1px;
}

.report-type-name {
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--black);
}

/* Methodology tags */
.method-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 28px;
}

.method-tag {
  background: var(--black);
  color: var(--white);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 6px 14px;
  letter-spacing: 0.8px;
  transition: background 0.2s;
}

.method-tag:hover {
  background: #333;
}

/* CTA */
.cta-area {
  border-top: 1px solid var(--border);
  padding-top: 24px;
}

.cta-label {
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0 0 14px;
  color: var(--black);
  letter-spacing: 0.3px;
}

.cta-btn {
  width: 100%;
  background: var(--orange);
  color: var(--white);
  border: none;
  padding: 18px 24px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  letter-spacing: 1px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.25s ease, transform 0.2s ease;
}

.cta-btn:hover {
  background: #d93d00;
  transform: translateY(-2px);
}

.cta-btn:active {
  transform: translateY(0);
}

.cta-arrow {
  font-size: 1.1rem;
  transition: transform 0.2s;
}

.cta-btn:hover .cta-arrow {
  transform: translateX(4px);
}

.cta-hint {
  margin-top: 10px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: #AAA;
  text-align: center;
  letter-spacing: 0.3px;
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
  .report-types-grid {
    grid-template-columns: 1fr;
  }

  .method-box {
    padding: 24px;
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

html[lang="en"] .navbar .nav-links {
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
