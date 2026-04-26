import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

/**
 * R017 / M002-S12 enforcement gate.
 *
 * The S12 ripple sweep retired `frontend/src/components/common/` and
 * `frontend/src/components/buttons/` in favor of the S08 design system
 * (`frontend/src/components/ui/*`) plus relocated non-primitive homes
 * (`forms/`, `cars/`, `images/`, `filters/`, `tables/`, `routes/`, `shell/`).
 *
 * This guard fails CI if any future commit re-introduces a relative import
 * from those legacy directories. R017's enforcement clause ("via lint rule
 * or grep check") is satisfied by THIS test plus the optional
 * `no-restricted-imports` rule in `eslint.config.js`.
 *
 * Pattern matched: `from '..(/..)*\/(common|buttons)/...'` — i.e. any
 * relative import path where the segment immediately before the trailing
 * specifier is `common` or `buttons`. Absolute aliases (`@/...`) are not
 * scanned because the project does not use them; if they are ever
 * introduced, extend the regex.
 *
 * The guard file itself is excluded from the scan via the `allowlist` set
 * (its source contains the literal token in JSDoc and string form).
 */
const LEGACY_PRIMITIVE_RE = /from\s+['"](?:\.\.\/)+(?:common|buttons)\//;

describe('R017 / M002-S12: no legacy components/common or components/buttons imports', () => {
  it('no source file imports from components/common/ or components/buttons/', () => {
    const srcDir = resolve(__dirname, '..');
    const files = globSync('**/*.{ts,tsx}', {
      cwd: srcDir,
      absolute: true,
      ignore: [
        '**/node_modules/**',
        '**/dist/**',
        '**/coverage/**',
        '__tests__/**',
        'components/common/**',
        'components/buttons/**',
      ],
    });

    const allowlist = new Set<string>([
      resolve(__dirname, 'no-legacy-primitives.test.ts'),
    ]);

    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (LEGACY_PRIMITIVE_RE.test(line)) {
          violations.push({
            file,
            line: i + 1,
            match: line.trim(),
          });
        }
      });
    }

    expect(violations).toEqual([]);
  });
});
