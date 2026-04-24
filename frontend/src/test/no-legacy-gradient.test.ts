import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('FE-05: no bg-gradient-to-* class names in source (Tailwind v3 legacy)', () => {
  it('no file contains bg-gradient-to-', () => {
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
        if (/bg-gradient-to-/.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
