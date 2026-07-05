<template>
  <header class="app-header">
    <div class="header-inner">

      <!-- 左側：Logo + 品牌名稱，點擊返回首頁 -->
      <a class="header-brand" @click.prevent="router.push('/')">
        <AppLogo variant="brand" />
        <span class="brand-name">未來報告</span>
      </a>

      <!-- 右側功能區（桌機：始終可見） -->
      <div class="header-right">
        <LanguageSwitcher />
        <AuthPanel />
      </div>

      <!-- 漢堡選單按鈕（手機：桌機隱藏） -->
      <button
        class="hamburger"
        type="button"
        :class="{ 'is-active': mobileOpen }"
        :aria-label="mobileOpen ? '關閉選單' : '展開選單'"
        @click="mobileOpen = !mobileOpen"
      >
        <span class="bar"></span>
        <span class="bar"></span>
        <span class="bar"></span>
      </button>
    </div>

    <!-- 手機展開選單（獨立於 header-inner，避免 overflow 截裁子選單） -->
    <Transition name="menu-slide">
      <div v-if="mobileOpen" class="mobile-menu">
        <div class="mobile-menu-item">
          <LanguageSwitcher />
        </div>
        <div class="mobile-menu-item">
          <AuthPanel />
        </div>
      </div>
    </Transition>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLogo from './AppLogo.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'
import AuthPanel from './AuthPanel.vue'

const router = useRouter()

/* 手機展開狀態 */
const mobileOpen = ref(false)
</script>

<style scoped>
/* ── 外框：固定在頂部，捲動仍可見 ── */
.app-header {
  position: sticky;
  top: 0;
  z-index: 200;
  width: 100%;
  height: 64px;
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.05);
  /* 手機展開後會超過 64px，所以不能 overflow:hidden */
}

/* ── 內層：左右對齊，水平居中 ── */
.header-inner {
  max-width: 1400px;
  height: 64px;
  margin: 0 auto;
  padding: 0 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

/* ── 左側品牌區 ── */
.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  cursor: pointer;
  flex-shrink: 0;
}

.brand-name {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 13px;
  font-weight: 800;
  color: #111;
  letter-spacing: 0.5px;
  transition: color 0.2s;
}

.header-brand:hover .brand-name {
  color: #555;
}

/* ── 右側功能區（桌機） ── */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ── 漢堡按鈕（預設隱藏，手機才顯示） ── */
.hamburger {
  display: none;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid #111;
  background: #fff;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}

.hamburger:hover {
  background: #f5f5f5;
}

/* 三條橫線 */
.bar {
  display: block;
  width: 16px;
  height: 1.5px;
  background: #111;
  transition: transform 0.25s ease, opacity 0.2s ease;
  transform-origin: center;
}

/* 展開時變 X */
.hamburger.is-active .bar:nth-child(1) {
  transform: translateY(6.5px) rotate(45deg);
}
.hamburger.is-active .bar:nth-child(2) {
  opacity: 0;
  transform: scaleX(0);
}
.hamburger.is-active .bar:nth-child(3) {
  transform: translateY(-6.5px) rotate(-45deg);
}

/* ── 手機展開選單 ── */
.mobile-menu {
  position: absolute;
  left: 0;
  right: 0;
  /* top 與 app-header 一致（sticky 元件的 top + 高度） */
  top: 64px;
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  z-index: 199;
  /* 允許 LanguageSwitcher 的子選單溢出 */
  overflow: visible;
}

.mobile-menu-item {
  padding: 10px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.mobile-menu-item:last-child {
  border-bottom: none;
}

/* 讓 switcher-trigger 和 auth-trigger 在手機寬度撐滿 */
.mobile-menu-item :deep(.switcher-trigger),
.mobile-menu-item :deep(.auth-trigger) {
  width: 100%;
  min-height: 40px;
  justify-content: space-between;
}

/* ── Vue Transition：選單滑入 / 滑出 ── */
.menu-slide-enter-from,
.menu-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.menu-slide-enter-active,
.menu-slide-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

/* ── 響應式斷點 ── */
@media (max-width: 767px) {
  .header-inner {
    padding: 0 20px;
  }

  /* 桌機右側改為隱藏（改由手機選單控制） */
  .header-right {
    display: none;
  }

  /* 顯示漢堡按鈕 */
  .hamburger {
    display: flex;
  }
}
</style>
