import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    // Allow connections from Holochain Launcher iframe
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin',
    },
    proxy: {
      // WebSocket proxy: browser connects to /hc-ws, Vite forwards to conductor.
      // Required in Codespace: the forwarded https:// page can't open ws://localhost
      // directly — ws://localhost resolves to the user's machine, not the Codespace.
      '/hc-ws': {
        target: 'ws://localhost:8888',
        ws: true,
        rewrite: (path) => path.replace(/^\/hc-ws/, ''),
      },
    },
  },
  build: {
    target: 'esnext',
  },
})
