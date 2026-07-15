<template>
  <div class="header-tools">
    <LanguageSwitcher />
    <AuthPanel />
  </div>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'
import AuthPanel from './AuthPanel.vue'
</script>

<style scoped>
/*
  工作流程頁（圖谱构建/环境搭建/双世界并行模拟/报告生成/深度互动）header-right 中的
  語言切換器 + 帳號/模型徽章。刻意保持在文檔流內（非 fixed/absolute），
  避免蓋住同一 header 中的 Step 資訊與狀態指示燈。
*/
.header-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
</style>
