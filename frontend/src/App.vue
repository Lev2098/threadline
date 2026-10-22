<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'
import type { Comment, CommentPage, Ordering } from '@/api/types'
import { t } from '@/composables/i18n'
import { connectLive, onCommentPosted } from '@/composables/live'
import { openComposer, toasts } from '@/composables/ui'
import AppHeader from './components/AppHeader.vue'
import CommentNode from './components/CommentNode.vue'
import CommentsTable from './components/CommentsTable.vue'
import Composer from './components/Composer.vue'
import Lightbox from './components/Lightbox.vue'
import Pager from './components/Pager.vue'

const VALID_ORDERINGS: Ordering[] = ['-created_at', 'created_at', 'username', '-username', 'email', '-email']

const state = reactive({
  page: 1,
  ordering: '-created_at' as Ordering,
  data: null as CommentPage | null,
  loading: true,
  failed: false,
})
const fresh = ref(new Set<number>())
const pending = ref<Comment[]>([])
const search = reactive({ query: '', data: null as CommentPage | null, loading: false })

const isLiveView = computed(() => state.page === 1 && state.ordering === '-created_at')

function readUrl(): void {
  const params = new URLSearchParams(location.search)
  const page = Number(params.get('page'))
  const ordering = params.get('ordering') as Ordering | null
  state.page = Number.isInteger(page) && page > 0 ? page : 1
  state.ordering = ordering && VALID_ORDERINGS.includes(ordering) ? ordering : '-created_at'
}

function writeUrl(): void {
  const params = new URLSearchParams()
  if (state.page > 1) params.set('page', String(state.page))
  if (state.ordering !== '-created_at') params.set('ordering', state.ordering)
  const qs = params.toString()
  history.pushState(null, '', qs ? `?${qs}` : location.pathname)
}

async function load(): Promise<void> {
  state.loading = true
  state.failed = false
  try {
    state.data = await api.listComments(state.page, state.ordering)
    state.page = state.data.page
    pending.value = []
  } catch {
    state.failed = true
  } finally {
    state.loading = false
  }
}

function go(page: number): void {
  state.page = page
  writeUrl()
  load()
  document.getElementById('discussions')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function sort(ordering: Ordering): void {
  state.ordering = ordering
  state.page = 1
  writeUrl()
  load()
}

/** Live roots: slide straight into the default view, otherwise wait behind a pill. */
function onLive(comment: Comment): void {
  const data = state.data
  if (!data) return
  if (comment.parent_id === null) {
    if (data.items.some((c) => c.id === comment.id) || pending.value.some((c) => c.id === comment.id)) return
    if (isLiveView.value) {
      reveal([comment])
    } else {
      pending.value = [comment, ...pending.value]
    }
    return
  }
  const root = data.items.find((c) => c.id === comment.root_id)
  if (root) root.replies_count += 1
}

function reveal(comments: Comment[]): void {
  const data = state.data!
  data.items = [...comments, ...data.items].slice(0, data.page_size)
  data.total += comments.length
  data.pages = Math.max(1, Math.ceil(data.total / data.page_size))
  fresh.value = new Set([...fresh.value, ...comments.map((c) => c.id)])
}

function showPending(): void {
  if (isLiveView.value) {
    reveal(pending.value)
    pending.value = []
  } else {
    state.ordering = '-created_at'
    go(1)
  }
}

async function runSearch(query: string): Promise<void> {
  search.query = query
  if (!query) {
    search.data = null
    return
  }
  search.loading = true
  try {
    search.data = await api.search(query)
  } finally {
    search.loading = false
  }
}

onMounted(() => {
  readUrl()
  load()
  connectLive()
  onCommentPosted(onLive)
  window.addEventListener('popstate', () => {
    readUrl()
    load()
  })
})
</script>

<template>
  <AppHeader @search="runSearch" />

  <main class="page">
    <section class="hero" aria-labelledby="hero-title">
      <svg class="hero-thread" viewBox="0 0 120 220" aria-hidden="true">
        <path d="M20 0v80a28 28 0 0 0 28 28h44" />
        <path d="M48 108v56a28 28 0 0 0 28 28h24" />
        <circle cx="92" cy="108" r="7" />
        <circle cx="100" cy="192" r="7" class="live-dot" />
      </svg>
      <div class="hero-copy">
        <h1 id="hero-title">{{ t.heroTitle }}</h1>
        <p>{{ t.heroLead }}</p>
        <div class="hero-actions">
          <button type="button" class="btn btn-primary" @click="openComposer()">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
            {{ t.startDiscussion }}
          </button>
          <span v-if="state.data" class="stat"><b>{{ state.data.total.toLocaleString() }}</b> {{ t.statThreads }}</span>
        </div>
      </div>
    </section>

    <section v-if="search.query" class="search-results" aria-live="polite">
      <header class="results-head">
        <h2>
          {{ search.data && search.data.total ? t.searchResults(search.data.total, search.query) : search.loading ? t.loading : t.searchNothing(search.query) }}
        </h2>
        <button type="button" class="btn btn-ghost" @click="runSearch('')">{{ t.closeSearch }}</button>
      </header>
      <div class="results-list">
        <CommentNode v-for="c in search.data?.items ?? []" :key="c.id" :node="{ comment: c, children: [] }" />
      </div>
    </section>

    <section id="discussions" class="discussions" :aria-busy="state.loading">
      <Transition name="pill">
        <button v-if="pending.length" type="button" class="pill" @click="showPending">
          <i aria-hidden="true" />{{ t.newComments(pending.length) }}
        </button>
      </Transition>

      <div v-if="state.failed" class="empty">
        <p>{{ t.loadError }}</p>
        <button type="button" class="btn btn-primary" @click="load">{{ t.retry }}</button>
      </div>
      <div v-else-if="state.data && !state.data.items.length && !state.loading" class="empty">
        <p>{{ t.empty }}</p>
        <button type="button" class="btn btn-primary" @click="openComposer()">{{ t.startDiscussion }}</button>
      </div>
      <template v-else-if="state.data">
        <CommentsTable :items="state.data.items" :ordering="state.ordering" :fresh="fresh" :class="{ dim: state.loading }" @sort="sort" />
        <Pager :page="state.data.page" :pages="state.data.pages" @go="go" />
      </template>
      <div v-else class="skeleton" aria-hidden="true"><span v-for="i in 6" :key="i" /></div>
    </section>
  </main>

  <Composer />
  <Lightbox />

  <div class="toasts" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast" :class="toast.tone">{{ toast.text }}</div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 clamp(1rem, 4vw, 2.5rem) 4rem;
}

/* ---------- hero ---------- */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: clamp(1rem, 3vw, 2.5rem);
  align-items: start;
  padding: clamp(2rem, 6vw, 4.5rem) 0 clamp(1.5rem, 4vw, 2.75rem);
}
.hero-thread {
  width: 100%;
  height: auto;
  overflow: visible;
}
.hero-thread path {
  fill: none;
  stroke: var(--signal);
  stroke-width: 5;
  stroke-linecap: round;
  stroke-dasharray: 400;
  stroke-dashoffset: 400;
  animation: thread-draw 1.6s 0.15s var(--ease-out) forwards;
}
.hero-thread path + path {
  stroke: var(--signal-2);
  animation-delay: 0.7s;
}
.hero-thread circle {
  fill: var(--signal);
  transform-box: fill-box;
  transform-origin: center;
  transform: scale(0);
  animation: dot-in 0.5s 1.1s var(--ease-out) forwards;
}
.hero-thread .live-dot {
  fill: var(--mint);
  animation-delay: 1.7s;
}
@keyframes thread-draw {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes dot-in {
  to {
    transform: scale(1);
  }
}
.hero h1 {
  margin: 0 0 1rem;
  font-family: var(--font-display);
  font-size: var(--step-5);
  font-weight: 800;
  line-height: 1.02;
  letter-spacing: -0.035em;
  max-width: 14ch;
}
.hero p {
  margin: 0 0 1.75rem;
  max-width: 54ch;
  font-size: var(--step-1);
  line-height: 1.5;
  color: var(--ink-2);
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.25rem;
}
.hero-actions .btn {
  padding: 0.9rem 1.5rem;
}
.hero-actions svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
}
.stat {
  color: var(--muted);
}
.stat b {
  font-family: var(--font-display);
  font-weight: 700;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

/* ---------- list ---------- */
.discussions {
  position: relative;
  scroll-margin-top: 6rem;
}
.dim {
  opacity: 0.55;
  transition: opacity 0.2s;
}
.pill {
  position: sticky;
  top: 5rem;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 auto 0.9rem;
  padding: 0.55rem 1.1rem;
  border: 0;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-weight: 600;
  box-shadow: var(--shadow-lift);
}
.pill i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--mint);
}
.pill-enter-active,
.pill-leave-active {
  transition: transform 0.35s var(--ease-out), opacity 0.25s;
}
.pill-enter-from,
.pill-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
.empty {
  display: grid;
  justify-items: center;
  gap: 1rem;
  padding: 3.5rem 1rem;
  border: 1.5px dashed var(--line);
  border-radius: var(--radius-l);
  text-align: center;
  color: var(--ink-2);
}
.empty p {
  margin: 0;
  max-width: 44ch;
}
.skeleton {
  display: grid;
  gap: 1px;
  border-radius: var(--radius-l);
  overflow: hidden;
  border: 1px solid var(--line);
}
.skeleton span {
  height: 3.6rem;
  background: linear-gradient(90deg, var(--surface) 0%, var(--surface-2) 50%, var(--surface) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}

/* ---------- search ---------- */
.search-results {
  margin-bottom: 2.5rem;
}
.results-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}
.results-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--step-1);
  font-weight: 700;
  letter-spacing: -0.01em;
}
.results-list {
  display: grid;
  gap: 0.75rem;
}

/* ---------- toasts ---------- */
.toasts {
  position: fixed;
  left: 50%;
  bottom: 1.5rem;
  z-index: 70;
  display: grid;
  gap: 0.5rem;
  transform: translateX(-50%);
}
.toast {
  padding: 0.7rem 1.2rem;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-weight: 600;
  box-shadow: var(--shadow-lift);
}
.toast.ok::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 0.6rem;
  border-radius: 50%;
  background: var(--mint);
  vertical-align: middle;
}
.toast.error {
  background: var(--rose);
  color: #fff;
}
.toast-enter-active,
.toast-leave-active {
  transition: transform 0.35s var(--ease-out), opacity 0.3s;
}
.toast-enter-from,
.toast-leave-to {
  transform: translateY(12px);
  opacity: 0;
}

@media (max-width: 640px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .hero-thread {
    display: none;
  }
}
</style>
