import { ref } from 'vue'
import { ensureToken, resetToken } from '@/api/client'
import type { Comment } from '@/api/types'

type Listener = (comment: Comment) => void

export const connected = ref(false)
const listeners = new Set<Listener>()
let socket: WebSocket | null = null
let attempts = 0
let heartbeat: number | undefined

export function onCommentPosted(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Live feed with exponential back-off reconnects (1s → 30s, jittered). */
export async function connectLive(): Promise<void> {
  let token: string
  try {
    token = await ensureToken()
  } catch {
    scheduleReconnect()
    return
  }
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${scheme}://${location.host}/ws/comments/?token=${encodeURIComponent(token)}`)

  socket.onopen = () => {
    connected.value = true
    attempts = 0
    heartbeat = window.setInterval(() => socket?.send(JSON.stringify({ type: 'ping' })), 25_000)
  }
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data as string) as { type: string; comment?: Comment }
    if (data.type === 'comment.posted' && data.comment) listeners.forEach((fn) => fn(data.comment!))
  }
  socket.onclose = (event) => {
    connected.value = false
    window.clearInterval(heartbeat)
    if (event.code === 4401) resetToken() // expired token: reconnect with a fresh one
    scheduleReconnect()
  }
}

function scheduleReconnect(): void {
  const delay = Math.min(30_000, 1000 * 2 ** attempts) * (0.75 + Math.random() * 0.5)
  attempts += 1
  window.setTimeout(connectLive, delay)
}

/** Show the author's own comment immediately, even if the socket is down. Duplicates are ignored by id. */
export function announceLocally(comment: Comment): void {
  listeners.forEach((fn) => fn(comment))
}
