import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import tailwindcss from '@tailwindcss/vite';

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
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Group node_modules dependencies
          if (id.includes('node_modules')) {
            // Separate React and React DOM into their own chunk
            if (id.includes('react') || id.includes('react-dom')) {
              return 'vendor-react';
            }
            // Separate React Router into its own chunk
            if (id.includes('react-router')) {
              return 'vendor-router';
            }
            // Group other large dependencies
            if (id.includes('axios')) {
              return 'vendor-axios';
            }
            // All other node_modules go into vendor chunk
            return 'vendor';
          }

          // Group admin pages together
          if (id.includes('/pages/admin/')) {
            return 'admin';
          }

          // Group authentication pages together
          if (id.includes('/pages/authentication/')) {
            return 'auth';
          }

          // Group builder pages together
          if (id.includes('/pages/builder/')) {
            return 'builder';
          }

          // Group global parts pages together
          if (id.includes('/pages/globalParts/')) {
            return 'global-parts';
          }

          // Group build lists pages together
          if (id.includes('/pages/buildLists/')) {
            return 'build-lists';
          }
        },
      },
    },
    chunkSizeWarningLimit: 600, // Increase limit slightly to reduce warnings
  },
});
