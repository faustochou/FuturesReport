<template>
  <!-- 首頁由 AppHeader 自帶語言/帳號功能；其他頁面保留浮動工具列 -->
  <div v-if="route.path !== '/'" class="global-tools">
    <LanguageSwitcher />
    <AuthPanel />
  </div>
  <router-view />
</template>

<script setup>
import { useRoute } from 'vue-router'
import AuthPanel from './components/AuthPanel.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

const route = useRoute()
</script>

<style>
/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* 全局按钮样式 */
button {
  font-family: inherit;
}

.global-tools {
  position: fixed;
  top: 14px;
  right: 16px;
  z-index: 2000;
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 720px) {
  .global-tools {
    top: 10px;
    right: 10px;
  }
}
</style>
