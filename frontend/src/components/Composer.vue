<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, type Captcha } from '@/api/types'
import { t } from '@/composables/i18n'
import { announceLocally } from '@/composables/live'
import { checkMarkup, plainText, safeHtml, type MarkupIssue } from '@/composables/markup'
import { burst } from '@/composables/fx'
import { composer, enterModal, isMac, toast } from '@/composables/ui'

type Field = 'username' | 'email' | 'home_page' | 'text' | 'attachment' | 'captcha'

const PROFILE_KEY = 'threadline.profile'
const USERNAME_RE = /^[A-Za-z0-9]+$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const URL_RE = /^https?:\/\/[^\s<>"'`\\]+$/i
const CAPTCHA_RE = /^[A-Za-z0-9]+$/
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif']
const IMAGE_MAX_BYTES = 10 * 1024 * 1024

const form = reactive({ username: '', email: '', home_page: '', text: '', captcha: '' })
const errors = reactive<Partial<Record<Field | 'non_field', string>>>({})
const touched = reactive<Partial<Record<Field, boolean>>>({})
const file = ref<File | null>(null)
const filePreview = ref<string | null>(null)
const captcha = ref<Captcha | null>(null)
const tab = ref<'write' | 'preview'>('write')
const previewHtml = ref('')
const submitting = ref(false)
const dragging = ref(false)
const linkUrl = ref('')
const linkOpen = ref(false)
const linkError = ref('')
const linkInput = ref<HTMLInputElement>()
const textarea = ref<HTMLTextAreaElement>()
let leaveModal: (() => void) | null = null
let previewSeq = 0
const panel = ref<HTMLElement>()

restoreProfile()

const title = computed(() => (composer.parent ? t.value.composerReply(composer.parent.username) : t.value.composerNew))
const parentQuote = computed(() => (composer.parent ? plainText(composer.parent.html) : ''))

/* ---------- validation (mirrors the server, which stays authoritative) ---------- */
function markupMessage(issue: MarkupIssue): string {
  switch (issue.kind) {
    case 'tag':
      return t.value.errTag(issue.tag)
    case 'unclosed':
      return t.value.errUnclosed(issue.tag)
    case 'mismatch':
      return t.value.errMismatch(issue.expected, issue.got)
    case 'orphan':
      return t.value.errOrphan(issue.tag)
    case 'href':
      return t.value.errHref
  }
}

function validate(field: Field): string | undefined {
  const v = t.value
  switch (field) {
    case 'username':
      if (!form.username.trim()) return v.errRequired
      return USERNAME_RE.test(form.username.trim()) ? undefined : v.errUsername
    case 'email':
      if (!form.email.trim()) return v.errRequired
      return EMAIL_RE.test(form.email.trim()) ? undefined : v.errEmail
    case 'home_page':
      return !form.home_page.trim() || URL_RE.test(form.home_page.trim()) ? undefined : v.errUrl
    case 'text': {
      if (!form.text.trim()) return v.errRequired
      const issue = checkMarkup(form.text)
      return issue ? markupMessage(issue) : undefined
    }
    case 'captcha':
      if (!captcha.value) return v.captchaLoadError
      if (!form.captcha.trim()) return v.errRequired
      return CAPTCHA_RE.test(form.captcha.trim()) ? undefined : v.errCaptcha
    case 'attachment':
      return errors.attachment
  }
}

function blur(field: Field): void {
  // Don't scold a field the user merely tabbed through; empty fields are
  // reported on submit. Once a field has been typed in, it validates on blur.
  const value = field in form ? form[field as keyof typeof form] : ''
  if (!value && !touched[field]) return
  touched[field] = true
  errors[field] = validate(field)
}

watch(
  () => form.text,
  () => {
    if (touched.text || errors.text) errors.text = validate('text')
    schedulePreview()
  },
)

/* ---------- preview: rendered by the server, exactly as it will be saved ---------- */
let previewTimer: number | undefined
function schedulePreview(): void {
  window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(renderPreview, 300)
}
async function renderPreview(): Promise<void> {
  const seq = ++previewSeq
  if (!form.text.trim() || checkMarkup(form.text)) {
    previewHtml.value = ''
    return
  }
  try {
    const { html } = await api.preview(form.text)
    if (seq === previewSeq) previewHtml.value = html
  } catch (e) {
    if (seq !== previewSeq) return
    previewHtml.value = '' // never keep rendering an older text
    if (e instanceof ApiError && e.body.errors.text) errors.text = e.body.errors.text
  }
}

/* ---------- toolbar ---------- */
function wrap(open: string, close: string): void {
  const el = textarea.value
  if (!el) return
  const { selectionStart: s, selectionEnd: e, value } = el
  form.text = value.slice(0, s) + open + value.slice(s, e) + close + value.slice(e)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(s + open.length, e + open.length)
  })
}
function toggleLink(): void {
  linkOpen.value = !linkOpen.value
  linkError.value = ''
  if (linkOpen.value) nextTick(() => linkInput.value?.focus())
}
function closeLink(): void {
  linkOpen.value = false
  linkError.value = ''
  textarea.value?.focus()
}
function insertLink(): void {
  const url = linkUrl.value.trim()
  if (!/^(https?:\/\/|mailto:)\S+$/i.test(url)) {
    linkError.value = t.value.errLinkUrl
    return
  }
  linkUrl.value = ''
  linkOpen.value = false
  linkError.value = ''
  wrap(`<a href="${url.replace(/"/g, '%22')}">`, '</a>')
}

/* ---------- file ---------- */
function pickFile(f: File | null | undefined): void {
  clearFile()
  if (!f) return
  const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
  const isImage = IMAGE_TYPES.includes(f.type) || ['jpg', 'jpeg', 'png', 'gif'].includes(ext)
  const isText = ext === 'txt'
  if (!isImage && !isText) {
    errors.attachment = t.value.errFileType
    return
  }
  if (isText && f.size > 100 * 1024) {
    errors.attachment = t.value.errFileTxt
    return
  }
  if (isImage && f.size > IMAGE_MAX_BYTES) {
    errors.attachment = t.value.errFileTooBig
    return
  }
  file.value = f
  if (isImage) filePreview.value = URL.createObjectURL(f)
}
function clearFile(): void {
  if (filePreview.value) URL.revokeObjectURL(filePreview.value)
  file.value = null
  filePreview.value = null
  errors.attachment = undefined
}
function onDrop(event: DragEvent): void {
  dragging.value = false
  pickFile(event.dataTransfer?.files[0])
}

/* ---------- captcha ---------- */
async function refreshCaptcha(): Promise<void> {
  form.captcha = ''
  try {
    captcha.value = await api.captcha()
    if (errors.captcha === t.value.captchaLoadError) errors.captcha = undefined
  } catch {
    captcha.value = null
    errors.captcha = t.value.captchaLoadError
  }
}

/* ---------- submit ---------- */
async function submit(): Promise<void> {
  if (submitting.value) return // Ctrl+Enter twice must not send twice
  const fields: Field[] = ['username', 'email', 'home_page', 'text', 'captcha']
  fields.forEach((f) => {
    touched[f] = true
    errors[f] = validate(f)
  })
  errors.non_field = undefined
  if (fields.some((f) => errors[f]) || errors.attachment || !captcha.value) {
    focusFirstError()
    return
  }

  const body = new FormData()
  body.set('username', form.username.trim())
  body.set('email', form.email.trim())
  body.set('home_page', form.home_page.trim())
  body.set('text', form.text)
  body.set('captcha_key', captcha.value.key)
  body.set('captcha', form.captcha.trim())
  if (composer.parent) body.set('parent_id', String(composer.parent.id))
  if (file.value) body.set('attachment', file.value)

  submitting.value = true
  try {
    const comment = await api.post(body)
    const button = panel.value?.querySelector<HTMLElement>('button[type="submit"]')?.getBoundingClientRect()
    if (button) burst(button.left + button.width / 2, button.top + button.height / 2)
    saveProfile()
    announceLocally(comment)
    toast(t.value.published)
    form.text = ''
    clearFile()
    close()
  } catch (e) {
    applyServerError(e)
    await refreshCaptcha() // captchas are single-use on the server
    focusFirstError()
  } finally {
    submitting.value = false
  }
}

/**
 * Server messages are English; the UI shows its own UA/RU text per field and
 * per error code. The server's text is kept only for markup errors, where it
 * names the offending tag and the client check already speaks the language.
 */
function applyServerError(e: unknown): void {
  const v = t.value
  if (!(e instanceof ApiError)) {
    errors.non_field = v.errPublish
    return
  }
  if (e.status === 413) {
    errors.attachment = v.errFileTooBig
    return
  }
  if (e.status === 429) {
    errors.non_field = v.errRateLimit
    return
  }
  if (e.status >= 500) {
    errors.non_field = v.errServer
    return
  }
  const byField: Record<string, string> = {
    username: v.errUsername,
    email: v.errEmail,
    home_page: v.errUrl,
    captcha: v.errCaptcha,
    attachment: v.errAttachment,
    parent_id: v.errParent,
  }
  for (const [field, message] of Object.entries(e.body.errors)) {
    if (field === 'text') errors.text = message
    else if (field in byField) errors[field as Field] = byField[field]
    else errors.non_field = message
  }
  if (!Object.keys(e.body.errors).length) errors.non_field = v.errPublish
}

function focusFirstError(): void {
  nextTick(() => {
    const target =
      panel.value?.querySelector<HTMLElement>('[aria-invalid="true"]') ?? panel.value?.querySelector<HTMLElement>('.alert')
    target?.focus()
  })
}

/* ---------- open / close ---------- */
function close(): void {
  composer.open = false
}
function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    if (linkOpen.value) closeLink() // Esc closes the innermost layer only
    else close()
  }
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submit()
  if (event.key === 'Tab') trapFocus(event)
}
/** Keep Tab inside the drawer (the page behind is also inert). */
function trapFocus(event: KeyboardEvent): void {
  const items = panel.value?.querySelectorAll<HTMLElement>(
    'button:not([disabled]), input:not([disabled]):not(.sr-only), textarea, a[href], label.drop-pick',
  )
  if (!items?.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
watch(
  () => composer.open,
  (open) => {
    if (open) {
      Object.keys(errors).forEach((k) => delete errors[k as Field])
      Object.keys(touched).forEach((k) => delete touched[k as Field])
      tab.value = 'write'
      linkOpen.value = false
      linkError.value = ''
      refreshCaptcha()
      leaveModal = enterModal()
      document.addEventListener('keydown', onKey)
      nextTick(() => panel.value?.querySelector<HTMLElement>(form.username ? 'textarea' : 'input')?.focus())
    } else {
      document.removeEventListener('keydown', onKey)
      leaveModal?.()
      leaveModal = null
    }
  },
)
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  leaveModal?.()
})

function restoreProfile(): void {
  try {
    const saved = JSON.parse(localStorage.getItem(PROFILE_KEY) ?? '{}') as Partial<typeof form>
    form.username = saved.username ?? ''
    form.email = saved.email ?? ''
    form.home_page = saved.home_page ?? ''
  } catch {
    /* ignore */
  }
}
function saveProfile(): void {
  try {
    const { username, email, home_page } = form
    localStorage.setItem(PROFILE_KEY, JSON.stringify({ username, email, home_page }))
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="composer.open" class="overlay" @click.self="close">
        <section ref="panel" class="drawer" role="dialog" aria-modal="true" aria-labelledby="composer-title">
          <header class="head">
            <h2 id="composer-title">{{ title }}</h2>
            <button type="button" class="icon-btn" :aria-label="t.close" @click="close">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
            </button>
          </header>

          <blockquote v-if="parentQuote" class="parent-quote"><span>{{ parentQuote }}</span></blockquote>

          <form class="form" novalidate @submit.prevent="submit">
            <div class="row two">
              <label class="field" :class="{ bad: errors.username }">
                <span class="label">{{ t.fieldUsername }}</span>
                <input
                  v-model="form.username"
                  autocomplete="nickname"
                  maxlength="64"
                  :aria-invalid="!!errors.username"
                  @blur="blur('username')"
                />
                <span class="hint">{{ errors.username || t.fieldUsernameHint }}</span>
              </label>
              <label class="field" :class="{ bad: errors.email }">
                <span class="label">{{ t.fieldEmail }}</span>
                <input
                  v-model="form.email"
                  type="email"
                  autocomplete="email"
                  maxlength="254"
                  :aria-invalid="!!errors.email"
                  @blur="blur('email')"
                />
                <span v-if="errors.email" class="hint">{{ errors.email }}</span>
              </label>
            </div>

            <label class="field" :class="{ bad: errors.home_page }">
              <span class="label">{{ t.fieldHomepage }} <em>{{ t.optional }}</em></span>
              <input
                v-model="form.home_page"
                type="url"
                inputmode="url"
                placeholder="https://"
                maxlength="2048"
                :aria-invalid="!!errors.home_page"
                @blur="blur('home_page')"
              />
              <span v-if="errors.home_page" class="hint">{{ errors.home_page }}</span>
            </label>

            <div class="field editor" :class="{ bad: errors.text }">
              <div class="editor-bar">
                <span class="label" id="text-label">{{ t.fieldText }}</span>
                <div class="tabs" role="tablist">
                  <button type="button" role="tab" :aria-selected="tab === 'write'" @click="tab = 'write'">{{ t.write }}</button>
                  <button type="button" role="tab" :aria-selected="tab === 'preview'" @click="(tab = 'preview'), renderPreview()">
                    {{ t.preview }}
                  </button>
                </div>
              </div>

              <div v-show="tab === 'write'">
                <div class="toolbar" role="toolbar" :aria-label="t.formatting">
                  <button type="button" title="<i>" @click="wrap('<i>', '</i>')"><i>i</i></button>
                  <button type="button" title="<strong>" @click="wrap('<strong>', '</strong>')"><strong>strong</strong></button>
                  <button type="button" title="<code>" @click="wrap('<code>', '</code>')"><code>code</code></button>
                  <button type="button" title="<a>" :aria-expanded="linkOpen" @click="toggleLink">a</button>
                  <div v-if="linkOpen" class="link-pop">
                    <input
                      ref="linkInput"
                      v-model="linkUrl"
                      type="url"
                      :placeholder="t.linkPrompt"
                      :aria-label="t.linkPrompt"
                      :aria-invalid="!!linkError"
                      @keydown.enter.prevent="insertLink"
                    />
                    <button type="button" class="btn btn-primary" @click="insertLink">{{ t.insertLink }}</button>
                    <span v-if="linkError" class="hint link-error" role="alert">{{ linkError }}</span>
                  </div>
                </div>
                <textarea
                  ref="textarea"
                  v-model="form.text"
                  rows="6"
                  maxlength="5000"
                  aria-labelledby="text-label"
                  :aria-invalid="!!errors.text"
                  @blur="blur('text')"
                />
              </div>
              <div v-show="tab === 'preview'" class="preview" role="tabpanel">
                <div v-if="previewHtml" class="prose" v-html="safeHtml(previewHtml)" />
                <p v-else class="placeholder">{{ t.previewEmpty }}</p>
              </div>
              <span class="hint">{{ errors.text || t.fieldTextHint }}</span>
            </div>

            <div
              class="drop"
              :class="{ dragging, bad: errors.attachment, has: file }"
              @dragover.prevent="dragging = true"
              @dragleave="dragging = false"
              @drop.prevent="onDrop"
            >
              <template v-if="file">
                <img v-if="filePreview" :src="filePreview" alt="" class="drop-img" />
                <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
                </svg>
                <span class="drop-name">{{ file.name }}</span>
                <button type="button" class="btn btn-ghost" @click="clearFile">{{ t.removeFile }}</button>
              </template>
              <label v-else class="drop-pick">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></svg>
                <span>
                  <strong>{{ t.attach }}</strong>
                  <small>{{ t.attachHint }}</small>
                </span>
                <input
                  type="file"
                  class="sr-only"
                  accept=".jpg,.jpeg,.png,.gif,.txt,image/jpeg,image/png,image/gif,text/plain"
                  @change="pickFile(($event.target as HTMLInputElement).files?.[0])"
                />
              </label>
              <span v-if="errors.attachment" class="hint">{{ errors.attachment }}</span>
            </div>

            <div class="field captcha" :class="{ bad: errors.captcha }">
              <span class="label" id="captcha-label">{{ t.captcha }}</span>
              <div class="captcha-row">
                <img v-if="captcha" :src="captcha.image" :alt="t.captchaAlt" width="200" height="64" />
                <span v-else class="captcha-skeleton" />
                <button type="button" class="icon-btn" :aria-label="t.captchaRefresh" :title="t.captchaRefresh" @click="refreshCaptcha">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" /></svg>
                </button>
                <input
                  v-model="form.captcha"
                  autocomplete="off"
                  autocapitalize="off"
                  spellcheck="false"
                  maxlength="16"
                  aria-labelledby="captcha-label"
                  :aria-invalid="!!errors.captcha"
                  @blur="blur('captcha')"
                />
              </div>
              <span v-if="errors.captcha" class="hint">{{ errors.captcha }}</span>
            </div>

            <p v-if="errors.non_field" class="alert" role="alert" tabindex="-1">{{ errors.non_field }}</p>

            <footer class="actions">
              <button type="button" class="btn btn-ghost" @click="close">{{ t.cancel }}</button>
              <button type="submit" class="btn btn-primary" :disabled="submitting">
                {{ submitting ? t.submitting : t.submit }}
                <kbd aria-hidden="true">{{ isMac ? '⌘↵' : 'Ctrl+↵' }}</kbd>
              </button>
            </footer>
          </form>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  justify-content: flex-end;
  background: rgb(16 15 38 / 38%);
  backdrop-filter: blur(3px);
}
.drawer {
  width: min(620px, 100%);
  height: 100%;
  overflow-y: auto;
  padding: 1.5rem clamp(1rem, 4vw, 2rem) 2rem;
  background: var(--surface);
  box-shadow: -24px 0 60px -20px rgb(30 27 75 / 35%);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}
.head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--step-2);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
.head svg,
.captcha svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}
.parent-quote {
  margin: 0 0 1.25rem;
  padding: 0.6rem 0.9rem;
  border-left: 3px solid var(--signal);
  border-radius: 0 var(--radius-s) var(--radius-s) 0;
  background: var(--signal-soft);
  color: var(--ink-2);
  font-size: 0.92rem;
}
.parent-quote span {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.form {
  display: grid;
  gap: 1.1rem;
}
.row.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.field {
  display: grid;
  gap: 0.35rem;
  align-content: start;
}
.label {
  font-weight: 600;
  font-size: 0.92rem;
}
.label em {
  font-style: normal;
  font-weight: 400;
  color: var(--muted);
}
input:not([type='file']),
textarea {
  width: 100%;
  padding: 0.7rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: var(--surface-2);
  transition: border-color 0.2s, box-shadow 0.2s, background-color 0.2s;
}
input:focus,
textarea:focus {
  outline: none;
  border-color: var(--signal);
  background: var(--surface);
  box-shadow: 0 0 0 4px var(--signal-soft);
}
textarea {
  resize: vertical;
  min-height: 9rem;
  line-height: 1.55;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}
.hint {
  font-size: var(--step--1);
  color: var(--muted);
}
.bad .hint {
  color: var(--rose);
}
.bad input,
.bad textarea {
  border-color: var(--rose);
}
.bad input:focus,
.bad textarea:focus {
  box-shadow: 0 0 0 4px var(--rose-soft);
}
.editor-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tabs {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--line);
}
.tabs button {
  border: 0;
  background: none;
  border-radius: 999px;
  padding: 0.25rem 0.8rem;
  font-size: var(--step--1);
  font-weight: 600;
  color: var(--muted);
}
.tabs button[aria-selected='true'] {
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 1px 4px rgb(30 27 75 / 12%);
}
.toolbar {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.35rem;
  border: 1px solid var(--line);
  border-bottom: 0;
  border-radius: var(--radius-s) var(--radius-s) 0 0;
  background: var(--surface-2);
}
.toolbar > button {
  min-width: 2.2rem;
  padding: 0.3rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  color: var(--ink-2);
  font-size: 0.88rem;
}
.toolbar > button:hover,
.toolbar > button[aria-expanded='true'] {
  background: var(--surface);
  border-color: var(--line);
  color: var(--signal);
}
.toolbar code {
  font-family: var(--font-code);
  font-size: 0.82rem;
}
.link-pop {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  flex: 1 1 260px;
}
.link-pop input {
  flex: 1 1 180px;
}
.link-error {
  width: 100%;
  color: var(--rose);
}
.link-pop input {
  padding: 0.35rem 0.6rem;
}
.link-pop .btn {
  padding: 0.4rem 0.9rem;
}
.preview {
  min-height: 11.6rem;
  padding: 0.9rem;
  border: 1px dashed var(--signal-2);
  border-radius: var(--radius-s);
  background: var(--surface);
}
.placeholder {
  margin: 0;
  color: var(--muted);
}
.drop {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border: 1.5px dashed var(--line);
  border-radius: var(--radius-m);
  transition: border-color 0.2s, background-color 0.2s;
}
.drop.dragging {
  border-color: var(--signal);
  background: var(--signal-soft);
}
.drop.bad {
  border-color: var(--rose);
}
.drop svg {
  flex: none;
  width: 24px;
  height: 24px;
  fill: none;
  stroke: var(--signal);
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.drop-pick {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  width: 100%;
}
.drop-pick span {
  display: grid;
}
.drop-pick small {
  color: var(--muted);
}
.drop-pick:focus-within {
  outline: 2px solid var(--signal);
  outline-offset: 6px;
  border-radius: 6px;
}
.drop-img {
  width: 64px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
}
.drop-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.drop .hint {
  width: 100%;
}
.captcha-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.captcha-row img,
.captcha-skeleton {
  flex: none;
  width: 200px;
  height: 64px;
  border-radius: var(--radius-s);
  background: repeating-linear-gradient(135deg, var(--surface-2) 0 8px, var(--signal-soft) 8px 16px);
  border: 1px solid var(--line);
}
.captcha-row input {
  max-width: 10rem;
  font-family: var(--font-code);
  letter-spacing: 0.15em;
}
.alert {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-radius: var(--radius-s);
  background: var(--rose-soft);
  color: var(--rose);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding-top: 0.25rem;
}
kbd {
  font-family: var(--font-body);
  font-size: 0.72rem;
  opacity: 0.7;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s;
}
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.45s var(--ease-out);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
}

@media (max-width: 640px) {
  .overlay {
    align-items: flex-end;
  }
  .drawer {
    height: 94dvh;
    border-radius: var(--radius-l) var(--radius-l) 0 0;
  }
  .drawer-enter-from .drawer,
  .drawer-leave-to .drawer {
    transform: translateY(100%);
  }
  .row.two {
    grid-template-columns: 1fr;
  }
  .captcha-row {
    flex-wrap: wrap;
  }
  .captcha-row input {
    max-width: none;
    flex: 1;
  }
  kbd {
    display: none;
  }
}
</style>
