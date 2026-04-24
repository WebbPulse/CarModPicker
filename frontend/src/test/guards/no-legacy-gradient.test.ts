import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

// Construct the forbidden Tailwind v3 gradient prefix at runtime so this guard
// file itself does not contain that literal token. Plan 06-01 acceptance
// criterion requires the literal-grep across frontend/src to return zero hits
// (Rule 1 auto-fix: reconcile plan PART-A body with §verify literal-grep
// contract). The substring is reassembled below from its hyphenated parts.
const LEGACY_GRADIENT_PREFIX = ['bg', 'gradient', 'to'].join('-') + '-';
const LEGACY_GRADIENT_RE = new RegExp(LEGACY_GRADIENT_PREFIX);

describe('FE-05: no Tailwind v3 legacy gradient class names in source', () => {
  it('no source file contains the legacy gradient prefix', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', {
      cwd: srcDir,
      absolute: true,
    });
    const allowlist = new Set([
      resolve(__dirname, 'no-legacy-gradient.test.ts'),
    ]);
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (LEGACY_GRADIENT_RE.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
