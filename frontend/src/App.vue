<template>
  <!-- 公開頁面使用 AppHeader；工作區頁面保留浮動工具列 -->
  <AppHeader v-if="showAppHeader" />
  <div v-else class="global-tools">
    <LanguageSwitcher />
    <AuthPanel />
  </div>
  <router-view />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import AuthPanel from './components/AuthPanel.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

const route = useRoute()

const PUBLIC_ROUTES = ['/', '/launch', '/subscription', '/admin']
const showAppHeader = computed(() => PUBLIC_ROUTES.includes(route.path))
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
