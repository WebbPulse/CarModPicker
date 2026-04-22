import { sentryVitePlugin } from '@sentry/vite-plugin';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

// D-34 + Landmine 13: CI-only sourcemap upload. Local builds (no CI env +
// no auth token) silently skip the plugin — no upload, no noise.
const isCIBuild = !!process.env.CI && !!process.env.SENTRY_AUTH_TOKEN;

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(isCIBuild
      ? [
          sentryVitePlugin({
            org: process.env.SENTRY_ORG,
            project: process.env.SENTRY_PROJECT,
            authToken: process.env.SENTRY_AUTH_TOKEN,
            release: { name: process.env.SENTRY_RELEASE },
          }),
        ]
      : []),
  ],
  server: {
    port: 4000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Optionally, rewrite the path if your backend expects no '/api' prefix:
        // rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  preview: {
    allowedHosts: ['www.carmodpicker.com', 'carmodpicker.com'],
  },
  build: {
    // Landmine 12: 'hidden' emits .map files so the vite-plugin has maps to
    // upload, BUT strips the `//# sourceMappingURL=...` comment from bundle
    // files so end users can't fetch them from the CDN.
    sourcemap: 'hidden',
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Single vendor chunk for all node_modules to avoid circular chunks
          // (e.g. vendor <-> vendor-react when other libs depend on React)
          if (id.includes('node_modules')) {
            return 'vendor';
          }
          // App code: no manual chunks; Rollup splits by lazy() routes in App.tsx
        },
      },
    },
    chunkSizeWarningLimit: 600, // Increase limit slightly to reduce warnings
  },
});
