import { describe, it, expect } from 'vitest';
import { extractMermaidSource } from '../../src/aspects/traces/TracesAspect';

describe('extractMermaidSource', () => {
  it('user_ask_5_strips_markdown_fence_from_real_mermaid_md', () => {
    const text = [
      '# title::of::scenario',
      '',
      '```mermaid',
      'sequenceDiagram',
      '    participant a as A',
      '    a ->> a: noop',
      '```',
      '',
    ].join('\n');
    expect(extractMermaidSource(text)).toBe(
      'sequenceDiagram\n    participant a as A\n    a ->> a: noop',
    );
  });

  it('user_ask_5_returns_raw_source_when_no_fence_present', () => {
    const raw = 'sequenceDiagram\n    a ->> b: msg';
    expect(extractMermaidSource(raw)).toBe(raw);
  });

  it('user_ask_5_trims_trailing_whitespace', () => {
    expect(extractMermaidSource('graph TD\n  A --> B\n\n\n')).toBe(
      'graph TD\n  A --> B',
    );
  });
});
