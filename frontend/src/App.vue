<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, type Comment, type CommentPage, type Ordering } from '@/api/types'
import { formatCount, t } from '@/composables/i18n'
import { setHead } from '@/composables/head'
import { connectLive, onCommentPosted } from '@/composables/live'
import { route, takeInitial } from '@/composables/router'
import { openComposer, toasts } from '@/composables/ui'
import AppHeader from './components/AppHeader.vue'
import CommentNode from './components/CommentNode.vue'
import CommentsTable from './components/CommentsTable.vue'
import Composer from './components/Composer.vue'
import Lightbox from './components/Lightbox.vue'
import Pager from './components/Pager.vue'
import Shortcuts from './components/Shortcuts.vue'
import ThreadPage from './components/ThreadPage.vue'
import { useCountUp } from '@/composables/fx'

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
const search = reactive({ query: '', page: 1, data: null as CommentPage | null, loading: false, failed: false })
// Responses can arrive out of order (slow sort, quick re-sort): only the latest may render.
let listSeq = 0
let searchSeq = 0

const { value: threadsShown, to: countThreadsTo } = useCountUp()
watch(
  () => state.data?.total,
  (total) => total !== undefined && countThreadsTo(total),
)
const heroWords = computed(() => t.value.heroTitle.split(' '))

const showTop = ref(false)
function onScroll(): void {
  showTop.value = window.scrollY > 1200
}
function toTop(): void {
  window.scrollTo({ top: 0, behavior: 'smooth' })
  document.getElementById('search-input')?.focus({ preventScroll: true })
}

const isLiveView = computed(() => state.page === 1 && state.ordering === '-created_at')

function readUrl(): void {
  const params = new URLSearchParams(location.search)
  const page = Number(params.get('page'))
  const ordering = params.get('ordering') as Ordering | null
  state.page = Number.isInteger(page) && page > 0 ? page : 1
  state.ordering = ordering && VALID_ORDERINGS.includes(ordering) ? ordering : '-created_at'
}

function writeUrl(replace = false): void {
  const params = new URLSearchParams()
  if (state.page > 1) params.set('page', String(state.page))
  if (state.ordering !== '-created_at') params.set('ordering', state.ordering)
  const qs = params.toString()
  history[replace ? 'replaceState' : 'pushState'](null, '', qs ? `?${qs}` : location.pathname)
}

async function load(): Promise<void> {
  const embedded = takeInitial<{ page: CommentPage; ordering: Ordering }>('home')
  if (embedded && embedded.ordering === state.ordering && embedded.page.page === state.page) {
    // Server-rendered first page: data is already in the HTML, no request needed.
    state.data = embedded.page
    state.loading = false
    return
  }
  const seq = ++listSeq
  state.loading = true
  state.failed = false
  try {
    const data = await api.listComments(state.page, state.ordering)
    if (seq !== listSeq) return
    state.data = data
    if (state.page !== data.page) {
      state.page = data.page // the server clamps pages past the end
      writeUrl(true)
    }
    pending.value = []
  } catch (e) {
    if (seq !== listSeq) return
    if (e instanceof ApiError && e.status === 400 && state.page !== 1) {
      // A page number the API refuses (e.g. hand-edited URL): start over at page 1.
      state.page = 1
      writeUrl(true)
      return load()
    }
    state.failed = true
  } finally {
    if (seq === listSeq) state.loading = false
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

// The author's own comment arrives twice: announced locally and echoed by the socket.
const seenLive = new Set<number>()

/** Live roots: slide straight into the default view, otherwise wait behind a pill. */
function onLive(comment: Comment): void {
  const data = state.data
  if (!data || seenLive.has(comment.id)) return
  seenLive.add(comment.id)
  if (comment.parent_id === null) {
    if (data.items.some((c) => c.id === comment.id)) return
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

async function runSearch(query: string, page = 1): Promise<void> {
  const seq = ++searchSeq
  if (query !== search.query) search.data = null // never show old results under a new query
  search.query = query
  search.page = page
  search.failed = false
  if (!query) {
    search.loading = false
    return
  }
  search.loading = true
  try {
    const data = await api.search(query, page)
    if (seq === searchSeq) search.data = data
  } catch {
    if (seq === searchSeq) search.failed = true
  } finally {
    if (seq === searchSeq) search.loading = false
  }
}

function closeSearch(): void {
  runSearch('')
  document.getElementById('search-input')?.focus()
}

const searchHeading = computed(() => {
  if (search.loading && !search.data) return t.value.loading
  if (search.failed) return t.value.searchFailed
  if (search.data?.total) return t.value.searchResults(search.data.total, search.query)
  return t.value.searchNothing(search.query)
})

function enterHome(): void {
  setHead(t.value.homeTitle, t.value.heroLead)
  readUrl()
  load()
  const q = new URLSearchParams(location.search).get('q')
  if (q) runSearch(q) // e.g. from Google's sitelinks search box
}

watch(
  () => route.value.name,
  (name) => {
    if (name === 'home') enterHome()
  },
)

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  if (route.value.name === 'home') enterHome()
  connectLive()
  onCommentPosted(onLive)
  window.addEventListener('popstate', () => {
    if (route.value.name !== 'home') return
    readUrl()
    load()
  })
})
</script>

<template>
  <AppHeader @search="runSearch" />

  <ThreadPage v-if="route.name === 'thread'" :id="route.id" />
  <main v-else class="page">
    <section class="hero" aria-labelledby="hero-title">
      <svg class="hero-thread" viewBox="0 0 120 220" aria-hidden="true">
        <path d="M20 0v80a28 28 0 0 0 28 28h44" />
        <path d="M48 108v56a28 28 0 0 0 28 28h24" />
        <circle cx="92" cy="108" r="7" />
        <circle cx="100" cy="192" r="7" class="live-dot" />
      </svg>
      <div class="hero-copy">
        <h1 id="hero-title" :aria-label="t.heroTitle">
          <span v-for="(word, i) in heroWords" :key="`${word}-${i}`" class="word" :style="{ '--i': i }" aria-hidden="true"
            >{{ word }}</span
          >
        </h1>
        <p>{{ t.heroLead }}</p>
        <div class="hero-actions">
          <button type="button" class="btn btn-primary" @click="openComposer()">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
            {{ t.startDiscussion }}
          </button>
          <span v-if="state.data" class="stat"><b class="count-up"
            ><span aria-hidden="true">{{ formatCount(threadsShown) }}</span
            ><span class="reserve">{{ formatCount(state.data.total) }}</span></b
          > {{ t.statThreads }}</span>
        </div>
      </div>
    </section>

    <section v-if="search.query" class="search-results" aria-live="polite" :aria-busy="search.loading">
      <header class="results-head">
        <h2>{{ searchHeading }}</h2>
        <div class="results-actions">
          <button v-if="search.failed" type="button" class="btn btn-primary" @click="runSearch(search.query, search.page)">
            {{ t.retry }}
          </button>
          <button type="button" class="btn btn-ghost" @click="closeSearch">{{ t.closeSearch }}</button>
        </div>
      </header>
      <div class="results-list" :class="{ dim: search.loading }">
        <CommentNode v-for="c in search.data?.items ?? []" :key="c.id" :node="{ comment: c, children: [] }" />
      </div>
      <Pager v-if="search.data" :page="search.data.page" :pages="search.data.pages" @go="(p) => runSearch(search.query, p)" />
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
  <Shortcuts />

  <Transition name="fade-up">
    <button v-if="showTop" type="button" class="to-top icon-btn" :aria-label="t.toTop" @click="toTop">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
    </button>
  </Transition>

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
.word {
  display: inline-block;
  /* trailing spaces collapse inside inline-blocks, so words are spaced by margin */
  margin-right: 0.26em;
  animation: word-in 0.7s var(--ease-out) both;
  animation-delay: calc(0.15s + var(--i) * 0.09s);
}
/* No opacity fade: the heading is the page's LCP element, and an invisible
   element isn't "painted" until the fade ends. Blur-to-sharp reads the same. */
@keyframes word-in {
  from {
    transform: translateY(0.35em) rotate(2deg);
    filter: blur(8px);
  }
}
.to-top {
  position: fixed;
  right: 1.25rem;
  bottom: 1.25rem;
  z-index: 30;
  box-shadow: var(--shadow-lift);
}
.to-top svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
}
.fade-up-enter-active,
.fade-up-leave-active {
  transition: opacity 0.25s, transform 0.3s var(--ease-out);
}
.fade-up-enter-from,
.fade-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
.word:last-child {
  margin-right: 0;
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
/* the animated number sits on top of the final one, which reserves the width */
.count-up {
  display: inline-grid;
}
.count-up > span {
  grid-area: 1 / 1;
  text-align: right;
}
.count-up .reserve {
  color: transparent; /* reserves width and is what screen readers read */
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
.results-actions {
  display: flex;
  gap: 0.5rem;
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
  color: var(--paper);
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
