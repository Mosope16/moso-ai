import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true, // Permit any forwarded VS Code port or devtunnel hostname
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, res) => {
            console.error('[Vite Proxy Error]:', err.message);
            if (res && 'writeHead' in res && !res.headersSent) {
              res.writeHead(502, {
                'Content-Type': 'application/json',
              });
              res.end(
                JSON.stringify({
                  error: 'Backend proxy error: Could not reach FastAPI on http://127.0.0.1:8000. Ensure the backend server is running.',
                  code: 'PROXY_BACKEND_UNREACHABLE',
                })
              );
            }
          });
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            // For SSE streams, disable buffering and keep-alive
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              res.setHeader('Cache-Control', 'no-cache, no-transform');
              res.setHeader('Connection', 'keep-alive');
              res.setHeader('X-Accel-Buffering', 'no');
            }
          });
        },
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
