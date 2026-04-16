import type { CallEvent } from '../aspects/e2e-traces/types';

export interface Span {
  start_ns: number;
  end_ns: number; // equals start_ns if no matching return (open span)
  depth: number;
  file: string;
  function: string;
  line: number;
}

/**
 * Match call/return event pairs into Span objects with explicit start/end times.
 * Open spans (no matching return) get end_ns = last event's timestamp_ns.
 */
export function buildSpans(events: CallEvent[]): Span[] {
  const spans: Span[] = [];
  // Stack per depth: Map<depth, CallEvent[]>
  const stacks = new Map<number, CallEvent[]>();
  const lastNs = events.at(-1)?.timestamp_ns ?? 0;

  for (const evt of events) {
    if (evt.event === 'call') {
      if (!stacks.has(evt.depth)) stacks.set(evt.depth, []);
      stacks.get(evt.depth)!.push(evt);
    } else {
      const depth_stack = stacks.get(evt.depth);
      if (depth_stack && depth_stack.length > 0) {
        const call = depth_stack.pop()!;
        spans.push({
          start_ns: call.timestamp_ns,
          end_ns: evt.timestamp_ns,
          depth: evt.depth,
          file: call.file,
          function: call.function,
          line: call.line,
        });
      }
    }
  }
  // Flush open spans (no matching return) — extend to last event time
  for (const [, stack] of stacks) {
    for (const call of stack) {
      spans.push({
        start_ns: call.timestamp_ns,
        end_ns: lastNs,
        depth: call.depth,
        file: call.file,
        function: call.function,
        line: call.line,
      });
    }
  }
  return spans;
}

/**
 * Return all spans active at the given time (start_ns <= t <= end_ns),
 * sorted by depth ascending (shallowest first).
 */
export function getStackAtTime(spans: Span[], t: number): Span[] {
  return spans
    .filter((s) => s.start_ns <= t && t <= s.end_ns)
    .sort((a, b) => a.depth - b.depth);
}

const PALETTE = [
  '#4e9af1',
  '#e4854d',
  '#a8cc52',
  '#c44ec4',
  '#6bc8a6',
  '#f1c94e',
  '#e45d5d',
  '#7b9af1',
  '#f19a4e',
  '#5dc8b4',
  '#c45d9a',
  '#9af14e',
];

/** Stable color for a function name (hash → 12-color palette). */
export function colorForFunction(name: string): string {
  let hash = 0;
  for (const c of name) hash = (hash * 31 + c.charCodeAt(0)) | 0;
  return PALETTE[Math.abs(hash) % PALETTE.length]!;
}
