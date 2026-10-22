import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig, type Plugin } from 'vite'

/**
 * Preloads the fonts that paint above the fold, so they arrive before first
 * render instead of swapping in later and shifting the layout (CLS).
 * Asset names are hashed, so the links are added after bundling.
 */
function preloadCriticalFonts(patterns: RegExp[]): Plugin {
  return {
    name: 'preload-critical-fonts',
    enforce: 'post',
    transformIndexHtml: {
      order: 'post',
      handler(_html, ctx) {
        if (!ctx.bundle) return []
        return Object.keys(ctx.bundle)
          .filter((file) => patterns.some((pattern) => pattern.test(file)))
          .map((file) => ({
            tag: 'link',
            attrs: { rel: 'preload', href: `/${file}`, as: 'font', type: 'font/woff2', crossorigin: '' },
            injectTo: 'head' as const,
          }))
      },
    },
  }
}

const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [
    vue(),
    // Cyrillic for the copy, Latin for digits, punctuation and user names.
    preloadCriticalFonts([/(unbounded-(cyrillic|latin)-800|golos-text-(cyrillic|latin)-(400|600))-normal-[\w-]+\.woff2$/]),
  ],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/graphql': backend,
      '/media': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: {
    target: 'es2022',
    cssCodeSplit: true,
    sourcemap: false,
    // Fonts stay separate, immutable-cached files: inlined data: URLs would be
    // blocked by the CSP (font-src 'self') and re-downloaded with every CSS change.
    assetsInlineLimit: (file: string) => (/\.(woff2?|ttf)$/.test(file) ? false : undefined),
  },
})
