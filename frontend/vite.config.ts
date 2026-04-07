import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
