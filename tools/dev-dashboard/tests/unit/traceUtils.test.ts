import { describe, it, expect } from 'vitest';
import { buildSpans, colorForFunction, getStackAtTime } from '../../src/lib/traceUtils';
import type { CallEvent } from '../../src/aspects/e2e-traces/types';

// ---------------------------------------------------------------------------
// buildSpans
// ---------------------------------------------------------------------------

describe('buildSpans', () => {
  it('empty events → empty spans', () => {
    expect(buildSpans([])).toEqual([]);
  });

  it('one call/return pair → one span with correct start/end/depth/file/function', () => {
    const events: CallEvent[] = [
      { event: 'call', file: 'routers/health.py', function: 'health_check', line: 10, depth: 0, timestamp_ns: 100 },
      { event: 'return', file: 'routers/health.py', function: 'health_check', line: 10, depth: 0, timestamp_ns: 500 },
    ];
    const spans = buildSpans(events);
    expect(spans).toHaveLength(1);
    expect(spans[0]!.start_ns).toBe(100);
    expect(spans[0]!.end_ns).toBe(500);
    expect(spans[0]!.depth).toBe(0);
    expect(spans[0]!.file).toBe('routers/health.py');
    expect(spans[0]!.function).toBe('health_check');
  });

  it('nested calls (depth 0→1→2) → 3 spans, inner spans contained within outer', () => {
    const events: CallEvent[] = [
      { event: 'call',   file: 'a.py', function: 'outer',  line: 1, depth: 0, timestamp_ns: 0   },
      { event: 'call',   file: 'b.py', function: 'middle', line: 2, depth: 1, timestamp_ns: 10  },
      { event: 'call',   file: 'c.py', function: 'inner',  line: 3, depth: 2, timestamp_ns: 20  },
      { event: 'return', file: 'c.py', function: 'inner',  line: 3, depth: 2, timestamp_ns: 30  },
      { event: 'return', file: 'b.py', function: 'middle', line: 2, depth: 1, timestamp_ns: 40  },
      { event: 'return', file: 'a.py', function: 'outer',  line: 1, depth: 0, timestamp_ns: 50  },
    ];
    const spans = buildSpans(events);
    expect(spans).toHaveLength(3);

    const outer  = spans.find((s) => s.function === 'outer')!;
    const middle = spans.find((s) => s.function === 'middle')!;
    const inner  = spans.find((s) => s.function === 'inner')!;

    // Inner spans are contained within outer
    expect(outer.start_ns).toBeLessThanOrEqual(middle.start_ns);
    expect(outer.end_ns).toBeGreaterThanOrEqual(middle.end_ns);
    expect(middle.start_ns).toBeLessThanOrEqual(inner.start_ns);
    expect(middle.end_ns).toBeGreaterThanOrEqual(inner.end_ns);
  });

  it('open call (no return) → span.end_ns equals last event timestamp', () => {
    const events: CallEvent[] = [
      { event: 'call',   file: 'a.py', function: 'outer',  line: 1, depth: 0, timestamp_ns: 0  },
      { event: 'call',   file: 'b.py', function: 'inner',  line: 2, depth: 1, timestamp_ns: 10 },
      { event: 'return', file: 'b.py', function: 'inner',  line: 2, depth: 1, timestamp_ns: 20 },
      // outer has no return — last event is at 20
    ];
    const spans = buildSpans(events);
    const outer = spans.find((s) => s.function === 'outer')!;
    expect(outer).toBeDefined();
    expect(outer.end_ns).toBe(20);
  });

  it('multiple sequential calls at same depth → two separate spans', () => {
    const events: CallEvent[] = [
      { event: 'call',   file: 'a.py', function: 'first',  line: 1, depth: 0, timestamp_ns: 0  },
      { event: 'return', file: 'a.py', function: 'first',  line: 1, depth: 0, timestamp_ns: 10 },
      { event: 'call',   file: 'b.py', function: 'second', line: 2, depth: 0, timestamp_ns: 20 },
      { event: 'return', file: 'b.py', function: 'second', line: 2, depth: 0, timestamp_ns: 30 },
    ];
    const spans = buildSpans(events);
    expect(spans).toHaveLength(2);
    const first  = spans.find((s) => s.function === 'first')!;
    const second = spans.find((s) => s.function === 'second')!;
    expect(first.start_ns).toBe(0);
    expect(first.end_ns).toBe(10);
    expect(second.start_ns).toBe(20);
    expect(second.end_ns).toBe(30);
  });
});

// ---------------------------------------------------------------------------
// getStackAtTime
// ---------------------------------------------------------------------------

describe('getStackAtTime', () => {
  const events: CallEvent[] = [
    { event: 'call',   file: 'a.py', function: 'outer',  line: 1, depth: 0, timestamp_ns: 0  },
    { event: 'call',   file: 'b.py', function: 'inner',  line: 2, depth: 1, timestamp_ns: 10 },
    { event: 'return', file: 'b.py', function: 'inner',  line: 2, depth: 1, timestamp_ns: 20 },
    { event: 'return', file: 'a.py', function: 'outer',  line: 1, depth: 0, timestamp_ns: 30 },
  ];
  const spans = buildSpans(events);

  it('time before all spans → []', () => {
    expect(getStackAtTime(spans, -1)).toEqual([]);
  });

  it('time inside outer span but before inner → [outer]', () => {
    const stack = getStackAtTime(spans, 5);
    expect(stack).toHaveLength(1);
    expect(stack[0]!.function).toBe('outer');
  });

  it('time inside both outer and inner → [outer, inner] sorted by depth', () => {
    const stack = getStackAtTime(spans, 15);
    expect(stack).toHaveLength(2);
    expect(stack[0]!.depth).toBeLessThan(stack[1]!.depth);
    expect(stack[0]!.function).toBe('outer');
    expect(stack[1]!.function).toBe('inner');
  });

  it('time after all spans → []', () => {
    expect(getStackAtTime(spans, 1000)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// colorForFunction
// ---------------------------------------------------------------------------

const PALETTE = [
  '#4e9af1','#e4854d','#a8cc52','#c44ec4','#6bc8a6',
  '#f1c94e','#e45d5d','#7b9af1','#f19a4e','#5dc8b4',
  '#c45d9a','#9af14e',
];

describe('colorForFunction', () => {
  it('same input always returns same color', () => {
    const c1 = colorForFunction('login');
    const c2 = colorForFunction('login');
    expect(c1).toBe(c2);
  });

  it('output is a hex string from PALETTE', () => {
    const color = colorForFunction('health_check');
    expect(PALETTE).toContain(color);
  });

  it('different inputs produce (mostly) different colors', () => {
    const names = [
      'login', 'logout', 'health_check', 'create_project',
      'delete_project', 'list_users', 'update_user',
    ];
    const colors = names.map(colorForFunction);
    // At least some should differ — not all identical
    const unique = new Set(colors);
    expect(unique.size).toBeGreaterThan(1);
  });
});
