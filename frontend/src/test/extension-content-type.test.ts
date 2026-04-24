import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('QUAL-06: Chrome extension POST Content-Type compliance (FastAPI 0.132+ strict)', () => {
  it('every fetch POST sets application/json Content-Type or uses FormData', () => {
    const extDir = resolve(__dirname, '..', '..', '..', 'chrome-extension');
    const files = globSync('src/**/*.ts', { cwd: extDir, absolute: true });
    const postRegex = /fetch\([^)]+\{[^}]*method:\s*["']POST["'][^}]*\}/gs;
    const violations: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, 'utf8');
      const matches = src.match(postRegex) ?? [];
      for (const match of matches) {
        const hasJsonHeader =
          /["']Content-Type["']\s*:\s*["']application\/json["']/.test(match);
        const hasFormData = /body:\s*(formData|\w*FormData)/i.test(match);
        if (!hasJsonHeader && !hasFormData) {
          violations.push(`${file}: ${match.slice(0, 140)}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
