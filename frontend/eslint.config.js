import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

import reactX from 'eslint-plugin-react-x';
import reactDom from 'eslint-plugin-react-dom';
import eslintConfigPrettier from 'eslint-config-prettier'; // Import eslint-config-prettier

export default tseslint.config(
  {
    ignores: ['dist/', 'node_modules/', '*.config.js'],
  },
  // Base config for non-type-checked files
  {
    files: ['*.config.ts', 'vite.config.ts'],
    extends: [...tseslint.configs.recommended],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    rules: {
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },
  // Main application files with full type checking
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    extends: [...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        project: ['./tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-refresh': reactRefresh,
      'react-hooks': reactHooks,
      // Add the react-x and react-dom plugins
      'react-x': reactX,
      'react-dom': reactDom,
    },
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Enable its recommended typescript rules
      ...reactX.configs['recommended-typescript'].rules,
      ...reactDom.configs.recommended.rules,
      // Disable React 19 warnings for now since we're not using React 19
      'react-x/no-use-context': 'off',
      'react-x/no-context-provider': 'off',
      // Phase 6 FE-01: strict typing rules flipped to error (Plan 06-01).
      // Per D-05, the test-file override block was removed so src/test/** also
      // runs strict rules. Plan 06-02 owns the violation fix sweep — between
      // these two plans landing, `npm run lint` will be red on main if they
      // do not co-merge (see 06-01 PLAN.md verification §Notes on Merge Ordering).
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unsafe-assignment': 'error',
      '@typescript-eslint/no-unsafe-call': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/no-unsafe-member-access': 'error',
      '@typescript-eslint/no-unsafe-argument': 'error',
      // M002/S12 R017 enforcement gate (redundant safety alongside the
      // src/__tests__/no-legacy-primitives.test.ts vitest guard). Blocks
      // any future PR from re-importing the retired legacy primitives at
      // lint time, before vitest runs.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/components/common/*', '**/components/buttons/*'],
              message:
                'Legacy primitives in components/common/ and components/buttons/ were retired in M002/S12. Use components/ui/* (S08 design system) or the relocated homes (forms/, cars/, images/, filters/, tables/, routes/, shell/) instead.',
            },
          ],
        },
      ],
    },
  },
  eslintConfigPrettier // Add this last
);