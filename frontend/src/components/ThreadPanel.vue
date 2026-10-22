<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'
import type { Comment } from '@/api/types'
import { t } from '@/composables/i18n'
import { onCommentPosted } from '@/composables/live'
import CommentNode, { type TreeNode } from './CommentNode.vue'

const props = defineProps<{ root: Comment }>()

const tree = reactive<TreeNode>({ comment: props.root, children: [] })
const index = new Map<number, TreeNode>([[props.root.id, tree]])
const cursor = ref<string | null>(null)
const loading = ref(true)
const failed = ref(false)

function attach(comment: Comment, fresh = false): void {
  if (index.has(comment.id)) return
  const parent = index.get(comment.parent_id ?? -1)
  if (!parent) return
  const node: TreeNode = reactive({ comment, children: [], fresh })
  parent.children.push(node)
  index.set(comment.id, node)
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const slice = await api.thread(props.root.id, cursor.value)
    // Items arrive depth-first, so every parent is attached before its children.
    slice.items.forEach((c) => attach(c))
    cursor.value = slice.next_cursor
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

let unsubscribe = (): void => {}
onMounted(() => {
  load()
  unsubscribe = onCommentPosted((c) => {
    if (c.root_id === props.root.id && c.parent_id !== null) attach(c, true)
  })
})
onBeforeUnmount(() => unsubscribe())
</script>

<template>
  <div class="thread">
    <CommentNode :node="tree" />
    <p v-if="loading" class="state">{{ t.loading }}</p>
    <p v-else-if="failed" class="state">
      {{ t.loadError }} <button type="button" class="btn btn-ghost" @click="load">{{ t.retry }}</button>
    </p>
    <p v-else-if="!tree.children.length" class="state">{{ t.noReplies }}</p>
    <button v-if="cursor && !loading" type="button" class="btn btn-ghost more" @click="load">{{ t.loadMoreReplies }}</button>
  </div>
</template>

<style scoped>
.thread {
  padding: 0.25rem 0 0.5rem;
}
.state {
  margin: 0.75rem 0 0 1.6rem;
  color: var(--muted);
  font-size: var(--step--1);
}
.more {
  margin: 0.75rem 0 0 1.6rem;
}
</style>
