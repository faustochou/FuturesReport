import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import AppLogo from './components/AppLogo.vue'

const app = createApp(App)

app.use(router)
app.use(i18n)
app.component('AppLogo', AppLogo)

app.mount('#app')
