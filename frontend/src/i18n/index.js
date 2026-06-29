import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const availableLocales = []

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    availableLocales.push({ key, label: languages[key].label })
  }
}

function detectLocale() {
  const saved = localStorage.getItem('locale')
  if (saved && messages[saved]) return saved

  const lang = (navigator.languages?.[0] || navigator.language || 'en').toLowerCase()

  if (lang.startsWith('zh-tw') || lang.startsWith('zh-hk') || lang.startsWith('zh-mo')) return 'zh-TW'
  if (lang.startsWith('zh')) return 'zh'
  if (lang.startsWith('en')) return 'en'

  return 'en'
}

const detectedLocale = detectLocale()

const i18n = createI18n({
  legacy: false,
  locale: detectedLocale,
  fallbackLocale: 'en',
  messages
})

export { availableLocales }
export default i18n
