import { createApp } from 'vue'
import App from './App.vue'
import { locale } from './composables/i18n'
import './styles/base.css'

document.documentElement.lang = locale.value
createApp(App).mount('#app')
