<template>
  <!-- 公開頁面使用 AppHeader；五個 Step 工作流程頁面自帶 header，內嵌 HeaderTools，
       不需要浮動工具列；其餘頁面（如隱私權政策）沒有自己的 header，才保留浮動工具列 -->
  <AppHeader v-if="showAppHeader" />
  <div v-else-if="showFloatingTools" class="global-tools">
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
// 這五個路由對應的頁面（Process/Simulation/SimulationRun/Report/Interaction）都有
// 自己的 app-header，並在 header-right 內嵌了 <HeaderTools />，因此不需要（也不應該）
// 再疊加 App.vue 層級的浮動工具列，否則會蓋住頁面自己的 Step 資訊與狀態指示燈。
const WORKSPACE_ROUTE_NAMES = ['Process', 'Simulation', 'SimulationRun', 'Report', 'Interaction']

const showAppHeader = computed(() => PUBLIC_ROUTES.includes(route.path))
const showFloatingTools = computed(() => !showAppHeader.value && !WORKSPACE_ROUTE_NAMES.includes(route.name))
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
