import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/coverage/**',
        'dist/',
        'build/',
        // D-13 (Phase 8): app bootstrap; executes once on mount, not
        // meaningfully testable as a unit.
        'src/main.tsx',
        // D-13 (Phase 8): pure TypeScript types; no executable runtime code.
        'src/types/Api.ts',
      ],
      // Deferred to plan 01-09 (SAFE-03 threshold enforcement).
      // D-06 targets: lines: 60, functions: 50, branches: 50, statements: 60.
      // Frontend baseline as of 2026-04-22: lines 0.43% / functions 10.52% / branches 18.43% / statements 0.43%.
      // Un-comment these values only after plan 01-09 lifts coverage to >=60/50/50/60.
      // thresholds: {
      //   lines: 60,
      //   functions: 50,
      //   branches: 50,
      //   statements: 60,
      // },
    },
  },
});
