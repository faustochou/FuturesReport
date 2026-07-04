<template>
  <div class="launch-container">
    <!-- Navbar -->
    <nav class="navbar">
      <div class="nav-brand">
        <AppLogo variant="brand" />
      </div>
      <div class="nav-links">
        <button class="back-btn" @click="router.push('/')">← {{ $t('common.back') }}</button>
      </div>
    </nav>

    <div class="launch-content">

      <!-- Gate: not logged in -->
      <div v-if="!authState.token" class="gate-box">
        <div class="gate-icon">◻</div>
        <h2 class="gate-title">{{ $t('launch.loginRequired') }}</h2>
        <p class="gate-desc">{{ $t('launch.loginDesc') }}</p>
        <button class="gate-btn" @click="router.push('/')">{{ $t('launch.loginBtn') }}</button>
      </div>

      <!-- Gate: logged in but no active subscription -->
      <div v-else-if="!hasActiveSubscription" class="gate-box">
        <div class="gate-icon gate-icon--lock">◈</div>
        <h2 class="gate-title">{{ $t('launch.gateTitle') }}</h2>
        <p class="gate-desc">{{ $t('launch.gateDesc') }}</p>
        <button class="gate-btn gate-btn--primary" @click="router.push('/subscription')">{{ $t('launch.gateBtn') }}</button>
      </div>

      <!-- Main console (subscription active) -->
      <template v-else>
        <div class="launch-header">
          <div class="panel-label">
            <span class="status-dot">■</span> {{ $t('launch.title') }}
          </div>
          <p class="launch-subtitle">{{ $t('launch.subtitle') }}</p>
        </div>

        <div class="console-box">
          <!-- Upload zone -->
          <div class="console-section">
            <div class="console-header">
              <span class="console-label">{{ $t('home.realitySeed') }}</span>
              <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
            </div>

            <div
              class="upload-zone"
              :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
              @dragover.prevent="handleDragOver"
              @dragleave.prevent="handleDragLeave"
              @drop.prevent="handleDrop"
              @click="triggerFileInput"
            >
              <input
                ref="fileInput"
                type="file"
                multiple
                accept=".pdf,.md,.txt"
                @change="handleFileSelect"
                style="display: none"
                :disabled="loading"
              />

              <div v-if="files.length === 0" class="upload-placeholder">
                <div class="upload-icon">↑</div>
                <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
              </div>

              <div v-else class="file-list">
                <div v-for="(file, index) in files" :key="index" class="file-item">
                  <span class="file-icon">📄</span>
                  <span class="file-name">{{ file.name }}</span>
                  <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <div class="console-divider">
            <span>{{ $t('home.inputParams') }}</span>
          </div>

          <!-- Prompt -->
          <div class="console-section">
            <div class="console-header">
              <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
            </div>
            <div class="input-wrapper">
              <textarea
                v-model="formData.simulationRequirement"
                class="code-input"
                :placeholder="$t('home.promptPlaceholder')"
                rows="6"
                :disabled="loading"
              ></textarea>
              <select
                v-if="isConfigured && availableModels.length > 0"
                :value="currentModel"
                class="model-select"
                :disabled="changingModel"
                @change="onModelChange"
              >
                <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
              </select>
              <select v-else class="model-select model-select--disabled" disabled>
                <option>Nexora AI</option>
              </select>
            </div>
          </div>

          <!-- Start button -->
          <div class="console-section btn-section">
            <button
              class="start-engine-btn"
              @click="startSimulation"
              :disabled="!canSubmit || loading"
            >
              <span v-if="!loading">{{ $t('home.startEngine') }}</span>
              <span v-else>{{ $t('home.initializing') }}</span>
              <span class="btn-arrow">→</span>
            </button>
          </div>
        </div>

        <!-- 推演記錄 -->
        <HistoryDatabase />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { authState, saveLlmConfig } from '../store/auth'
import HistoryDatabase from '../components/HistoryDatabase.vue'

const router = useRouter()

const formData = ref({ simulationRequirement: '' })
const files = ref([])
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)

const hasActiveSubscription = computed(() => {
  const sub = authState.user?.subscription
  if (!sub) return false
  return sub.status === 'active' && ['lite', 'premium', 'pro'].includes(sub.tier_code)
})

const canSubmit = computed(() =>
  formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
)

const changingModel = ref(false)
const isConfigured = computed(() => Boolean(authState.user?.llm_configured))
const availableModels = computed(() => {
  const provider = authState.user?.llm?.provider
  const current = authState.user?.llm?.model
  if (!provider) return []
  const list = authState.providers[provider]?.models || []
  if (list.length === 0 && current) return [current]
  return list
})
const currentModel = computed(() => authState.user?.llm?.model || '')

const onModelChange = async (event) => {
  const newModel = event.target.value
  const provider = authState.user?.llm?.provider
  if (!newModel || !provider) return
  changingModel.value = true
  try {
    await saveLlmConfig({ provider, model: newModel })
  } catch {
    // keep existing config on error
  } finally {
    changingModel.value = false
  }
}

const triggerFileInput = () => {
  if (!loading.value) fileInput.value?.click()
}

const handleFileSelect = (event) => {
  addFiles(Array.from(event.target.files))
}

const handleDragOver = () => {
  if (!loading.value) isDragOver.value = true
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer.files))
}

const addFiles = (newFiles) => {
  const valid = newFiles.filter(f => ['pdf', 'md', 'txt'].includes(f.name.split('.').pop().toLowerCase()))
  files.value.push(...valid)
}

const removeFile = (index) => {
  files.value.splice(index, 1)
}

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    router.push({ name: 'Process', params: { projectId: 'new' } })
  })
}
</script>

<style scoped>
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.launch-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

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

.back-btn {
  background: none;
  border: 1px solid rgba(255,255,255,0.3);
  color: var(--white);
  padding: 6px 16px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: border-color 0.2s;
}

.back-btn:hover {
  border-color: var(--white);
}

.launch-content {
  max-width: 860px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Gate screens */
.gate-box {
  border: 1px solid var(--border);
  padding: 60px 40px;
  text-align: center;
  margin-top: 40px;
}

.gate-icon {
  font-size: 2.5rem;
  margin-bottom: 24px;
  opacity: 0.3;
}

.gate-icon--lock {
  color: var(--orange);
  opacity: 0.7;
}

.gate-title {
  font-size: 1.8rem;
  font-weight: 520;
  margin: 0 0 16px;
}

.gate-desc {
  color: var(--gray-text);
  line-height: 1.7;
  max-width: 480px;
  margin: 0 auto 32px;
}

.gate-btn {
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 14px 36px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 1px;
  transition: background 0.2s;
}

.gate-btn:hover {
  background: #222;
}

.gate-btn--primary {
  background: var(--orange);
}

.gate-btn--primary:hover {
  background: #e03d00;
}

/* Launch header */
.launch-header {
  margin-bottom: 32px;
}

.panel-label {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.launch-subtitle {
  font-size: 1.6rem;
  font-weight: 520;
  margin: 0;
  color: var(--black);
}

/* Console box (same design as home) */
.console-box {
  border: 1px solid #CCC;
  padding: 8px;
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.drag-over {
  border-color: var(--orange);
  background: #FFF5F0;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
  box-sizing: border-box;
}

.model-select {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #666;
  background: transparent;
  border: none;
  outline: none;
  cursor: pointer;
  max-width: 200px;
}

.model-select:hover:not(:disabled) {
  color: #222;
}

.model-select--disabled,
.model-select:disabled {
  color: #AAA;
  cursor: default;
  -webkit-appearance: none;
  appearance: none;
  pointer-events: none;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  overflow: hidden;
}

.start-engine-btn:not(:disabled) {
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  border: 1px solid #E5E5E5;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

@media (max-width: 768px) {
  .launch-content {
    padding: 40px 20px;
  }

  .gate-box {
    padding: 40px 24px;
  }
}
</style>
