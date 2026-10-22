import { createApp } from 'vue'
import App from './App.vue'
import { locale, setLocale } from './composables/i18n'
// Self-hosted fonts (no third-party request, no render-blocking stylesheet).
// Each file declares every subset with unicode-range; browsers fetch only what a page uses.
import '@fontsource/golos-text/400.css'
import '@fontsource/golos-text/500.css'
import '@fontsource/golos-text/600.css'
import '@fontsource/golos-text/700.css'
import '@fontsource/unbounded/700.css'
import '@fontsource/unbounded/800.css'
import '@fontsource/jetbrains-mono/400.css'
import './styles/base.css'

// ?lang=uk|ru (used in hreflang links) wins over the stored preference.
const langParam = new URLSearchParams(location.search).get('lang')
if (langParam === 'uk' || langParam === 'ru') setLocale(langParam)
document.documentElement.lang = locale.value
createApp(App).mount('#app')
document.documentElement.setAttribute('data-app', 'ready')
