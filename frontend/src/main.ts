import { createApp } from 'vue'
import App from './App.vue'
import { locale, setLocale } from './composables/i18n'
import './styles/base.css'

// ?lang=uk|ru (used in hreflang links) wins over the stored preference.
const langParam = new URLSearchParams(location.search).get('lang')
if (langParam === 'uk' || langParam === 'ru') setLocale(langParam)
document.documentElement.lang = locale.value
createApp(App).mount('#app')
