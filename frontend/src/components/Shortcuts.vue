<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '@/composables/i18n'
import { composer, enterModal, lightbox, openComposer, toggleTheme } from '@/composables/ui'

const open = ref(false)
const closeBtn = ref<HTMLButtonElement>()
let leave: (() => void) | null = null

function typing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))
}

/** Single-key shortcuts, ignored while typing or while another dialog is open. */
function onKey(event: KeyboardEvent): void {
  if (event.metaKey || event.ctrlKey || event.altKey) return
  if (open.value) {
    if (event.key === 'Escape' || event.key === '?') open.value = false
    return
  }
  if (typing(event.target) || composer.open || lightbox.attachment) return
  if (event.key === '/') {
    event.preventDefault()
    document.getElementById('search-input')?.focus()
  } else if (event.key === 'n') {
    event.preventDefault()
    openComposer()
  } else if (event.key === 't') {
    toggleTheme()
  } else if (event.key === '?') {
    open.value = true
  }
}

watch(open, (value) => {
  if (value) {
    leave = enterModal()
    nextTick(() => closeBtn.value?.focus())
  } else {
    leave?.()
    leave = null
  }
})
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

defineExpose({ show: () => (open.value = true) })
</script>

<template>
  <Teleport to="body">
    <Transition name="pop">
      <div v-if="open" class="overlay" @click.self="open = false">
        <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title">
          <h2 id="shortcuts-title">{{ t.shortcutsTitle }}</h2>
          <dl>
            <div><dt><kbd>/</kbd></dt><dd>{{ t.shortcutSearch }}</dd></div>
            <div><dt><kbd>n</kbd></dt><dd>{{ t.shortcutNew }}</dd></div>
            <div><dt><kbd>t</kbd></dt><dd>{{ t.shortcutTheme }}</dd></div>
            <div><dt><kbd>?</kbd></dt><dd>{{ t.shortcutHelp }}</dd></div>
            <div><dt><kbd>Esc</kbd></dt><dd>{{ t.shortcutClose }}</dd></div>
          </dl>
          <button ref="closeBtn" type="button" class="btn btn-primary" @click="open = false">{{ t.close }}</button>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 55;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgb(16 15 38 / 40%);
  backdrop-filter: blur(4px);
}
.dialog {
  width: min(380px, 100%);
  padding: 1.5rem;
  border-radius: var(--radius-l);
  background: var(--surface);
  box-shadow: var(--shadow-lift);
}
h2 {
  margin: 0 0 1rem;
  font-family: var(--font-display);
  font-size: var(--step-1);
}
dl {
  display: grid;
  gap: 0.6rem;
  margin: 0 0 1.25rem;
}
dl div {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
dt {
  min-width: 3rem;
}
dd {
  margin: 0;
  color: var(--ink-2);
}
kbd {
  display: inline-block;
  min-width: 1.9rem;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--line);
  border-bottom-width: 3px;
  border-radius: 8px;
  background: var(--surface-2);
  font-family: var(--font-code);
  font-size: 0.85rem;
  text-align: center;
}
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.2s;
}
.pop-enter-active .dialog,
.pop-leave-active .dialog {
  transition: transform 0.3s var(--ease-out);
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
}
.pop-enter-from .dialog,
.pop-leave-to .dialog {
  transform: scale(0.94) translateY(8px);
}
</style>
