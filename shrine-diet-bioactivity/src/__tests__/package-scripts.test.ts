import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

// Guards the class of defect fixed in the b73c3cf-restore: an npm script (or a
// Makefile target that calls one) that points at a `scripts/*.ts` file which was
// deleted — the "zombie target" trap where the pipeline LOOKS restored while a
// referenced script no longer exists. A source-text existence check, deliberately
// both-arm testable: it goes RED the moment any script references a missing file.

const pkgRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function tsxTargets(scripts: Record<string, string>): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  for (const [name, cmd] of Object.entries(scripts)) {
    for (const m of cmd.matchAll(/tsx\s+(scripts\/[^\s&|]+\.ts)/g)) {
      out.push([name, m[1]]);
    }
  }
  return out;
}

describe('package.json scripts reference real files', () => {
  const pkg = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'));
  const targets = tsxTargets(pkg.scripts ?? {});

  it('extracts at least the restored data-pipeline scripts', () => {
    // Sanity that the matcher works (else the it.each below would vacuously pass).
    expect(targets.length).toBeGreaterThanOrEqual(6);
  });

  it.each(targets)('script "%s" → %s exists on disk', (_name, relPath) => {
    expect(existsSync(join(pkgRoot, relPath))).toBe(true);
  });

  it('RED arm: the existence check fails for a deleted script path', () => {
    // Proves the guard discriminates — a zombie target (e.g. the removed
    // build-food-bridge.ts) would fail exactly here.
    expect(existsSync(join(pkgRoot, 'scripts/build-food-bridge.ts'))).toBe(false);
  });
});
