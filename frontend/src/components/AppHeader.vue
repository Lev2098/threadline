<script setup lang="ts">
import { ref } from 'vue'
import { connected } from '@/composables/live'
import { locale, setLocale, t } from '@/composables/i18n'
import { theme, toggleTheme } from '@/composables/ui'

const emit = defineEmits<{ search: [query: string] }>()
const query = ref('')

function submit(): void {
  emit('search', query.value.trim())
}
</script>

<template>
  <header class="header">
    <a class="brand" href="/" aria-label="Threadline">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" />
        <path d="M10 7v10a5 5 0 0 0 5 5h7" />
        <circle cx="23" cy="22" r="3" />
      </svg>
      <span>{{ t.appName }}</span>
    </a>

    <form class="search" role="search" @submit.prevent="submit">
      <label class="sr-only" for="search-input">{{ t.search }}</label>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input
        id="search-input"
        v-model="query"
        type="search"
        maxlength="200"
        :placeholder="t.searchPlaceholder"
        @search="submit"
      />
    </form>

    <div class="tools">
      <span class="live" :class="{ on: connected }" aria-live="polite">
        <i aria-hidden="true" />{{ connected ? t.live : t.offline }}
      </span>
      <div class="lang" role="group" :aria-label="t.language">
        <button type="button" :aria-pressed="locale === 'uk'" @click="setLocale('uk')">UA</button>
        <button type="button" :aria-pressed="locale === 'ru'" @click="setLocale('ru')">RU</button>
      </div>
      <button type="button" class="icon-btn" :aria-label="t.theme" @click="toggleTheme">
        <svg v-if="theme === 'dark'" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4.5" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.25rem;
  padding: 0.85rem clamp(1rem, 4vw, 2.5rem);
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: blur(14px) saturate(1.4);
  border-bottom: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--ink);
  text-decoration: none;
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.brand svg {
  width: 30px;
  height: 30px;
}
.brand rect {
  fill: var(--signal);
}
.brand path {
  fill: none;
  stroke: #fff;
  stroke-width: 3;
  stroke-linecap: round;
}
.brand circle {
  fill: var(--mint);
}
.search {
  position: relative;
  max-width: 420px;
  justify-self: center;
  width: 100%;
}
.search svg {
  position: absolute;
  left: 0.9rem;
  top: 50%;
  width: 18px;
  height: 18px;
  transform: translateY(-50%);
  fill: none;
  stroke: var(--muted);
  stroke-width: 2;
  stroke-linecap: round;
}
.search input {
  width: 100%;
  padding: 0.6rem 1rem 0.6rem 2.6rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.search input:focus {
  outline: none;
  border-color: var(--signal);
  box-shadow: 0 0 0 4px var(--signal-soft);
}
.tools {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.tools svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}
.live {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: var(--step--1);
  color: var(--muted);
}
.live i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
}
.live.on {
  color: var(--mint);
}
.live.on i {
  background: var(--mint);
  box-shadow: 0 0 0 0 var(--mint);
  animation: pulse 2.4s infinite;
}
@keyframes pulse {
  70% {
    box-shadow: 0 0 0 7px transparent;
  }
}
.lang {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
}
.lang button {
  border: 0;
  background: none;
  padding: 0.3rem 0.6rem;
  border-radius: 999px;
  font-size: var(--step--1);
  font-weight: 600;
  color: var(--muted);
}
.lang button[aria-pressed='true'] {
  background: var(--signal);
  color: #fff;
}
@media (max-width: 760px) {
  .header {
    grid-template-columns: auto auto;
    row-gap: 0.7rem;
  }
  .search {
    grid-column: 1 / -1;
    grid-row: 2;
    max-width: none;
  }
  .tools {
    justify-self: end;
  }
  .live {
    display: none;
  }
}
</style>
