import { describe, it, expect } from 'vitest';
import { pickFoldedFilename } from '../../src/aspects/traces/TracesAspect';

describe('traces folded filename detection', () => {
  it('user_ask_5_prefers_real_folded_compact_txt', () => {
    expect(
      pickFoldedFilename(
        new Set(['folded-compact.txt', 'mermaid.md', 'flame.html']),
      ),
    ).toBe('folded-compact.txt');
  });

  it('user_ask_5_falls_back_to_legacy_folded_txt', () => {
    expect(pickFoldedFilename(new Set(['folded.txt']))).toBe('folded.txt');
  });

  it('user_ask_5_prefers_compact_when_both_present', () => {
    expect(
      pickFoldedFilename(new Set(['folded.txt', 'folded-compact.txt'])),
    ).toBe('folded-compact.txt');
  });

  it('user_ask_5_returns_null_when_neither_present', () => {
    expect(pickFoldedFilename(new Set(['mermaid.md']))).toBeNull();
  });
});
