import { useEffect, useRef, useState } from 'react';
import type { E2eRequestTrace } from '../aspects/e2e-traces/types';
import { buildSpans, colorForFunction, getStackAtTime } from '../lib/traceUtils';

const ROW_HEIGHT = 22;

interface RequestFlameChartProps {
  request: E2eRequestTrace;
}

function statusClass(code: number): string {
  if (code >= 500) return 'flame-status-5xx';
  if (code >= 400) return 'flame-status-4xx';
  if (code >= 300) return 'flame-status-3xx';
  return 'flame-status-2xx';
}

export function RequestFlameChart({ request }: RequestFlameChartProps) {
  const [hoverNs, setHoverNs] = useState<number | null>(null);
  const [view, setView] = useState<{ start: number; end: number } | null>(null);
  const flameRef = useRef<HTMLDivElement>(null);

  const spans = buildSpans(request.call_events);

  const minNs = spans.length > 0 ? Math.min(...spans.map((s) => s.start_ns)) : 0;
  const maxNs = spans.length > 0 ? Math.max(...spans.map((s) => s.end_ns)) : 0;
  const totalDuration = maxNs - minNs;

  const effectiveStart = view?.start ?? 0;
  const effectiveEnd = view?.end ?? totalDuration;
  const viewDuration = effectiveEnd - effectiveStart;

  const maxDepth = spans.length > 0 ? Math.max(...spans.map((s) => s.depth)) : 0;

  // Use a ref to hold latest view values to avoid stale closures in the wheel handler
  const viewRef = useRef({ effectiveStart, viewDuration, totalDuration });
  viewRef.current = { effectiveStart, viewDuration, totalDuration };

  useEffect(() => {
    const el = flameRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const { effectiveStart: es, viewDuration: vd, totalDuration: td } = viewRef.current;
      const rect = el.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left) / rect.width;
      const focalNs = es + mouseX * vd;
      const factor = e.deltaY > 0 ? 1.35 : 0.74;
      const newDuration = Math.max(td * 0.01, Math.min(td, vd * factor));
      const newStart = Math.max(0, Math.min(td - newDuration, focalNs - mouseX * newDuration));
      setView({ start: newStart, end: newStart + newDuration });
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []); // empty deps — uses ref for current values

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const fraction = (e.clientX - rect.left) / rect.width;
    setHoverNs(effectiveStart + fraction * viewDuration);
  }

  function handleMouseLeave() {
    setHoverNs(null);
  }

  const currentStack =
    hoverNs !== null ? getStackAtTime(spans, hoverNs + minNs) : [];

  const hasSpans = spans.length > 0 && totalDuration > 0;

  return (
    <div className="flame-chart-wrap">
      <div className="flame-header">
        <span className="flame-method">{request.method}</span>
        <span>{request.path}</span>
        <span>&rarr;</span>
        <span className={statusClass(request.status_code)}>{request.status_code}</span>
        <span>({request.duration_ms}ms)</span>
        {view !== null && (
          <button
            className="flame-reset-zoom"
            onClick={() => setView(null)}
            data-testid="flame-reset-zoom"
            type="button"
          >
            reset zoom
          </button>
        )}
      </div>

      {hasSpans ? (
        <div
          ref={flameRef}
          data-testid="flame-chart"
          className="flame-area"
          style={{ height: `${(maxDepth + 1) * ROW_HEIGHT}px` }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {spans.map((span, i) => {
            // Skip spans entirely outside the view
            const spanStartRel = span.start_ns - minNs;
            const spanEndRel = span.end_ns - minNs;
            if (spanEndRel <= effectiveStart || spanStartRel >= effectiveEnd) return null;

            // Clip to view bounds
            const clippedStart = Math.max(spanStartRel, effectiveStart);
            const clippedEnd = Math.min(spanEndRel, effectiveEnd);

            const left = (clippedStart - effectiveStart) / viewDuration * 100;
            const width = Math.max(0.2, (clippedEnd - clippedStart) / viewDuration * 100);
            const top = span.depth * ROW_HEIGHT;
            return (
              <div
                key={i}
                data-testid="flame-span"
                title={`${span.file}:${span.function} (line ${span.line})\n${span.end_ns - span.start_ns}ns`}
                style={{
                  position: 'absolute',
                  left: `${left}%`,
                  width: `${width}%`,
                  top,
                  height: ROW_HEIGHT - 2,
                  background: colorForFunction(span.function),
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  fontSize: 11,
                  padding: '0 3px',
                  lineHeight: `${ROW_HEIGHT - 2}px`,
                  borderRadius: 2,
                  cursor: 'default',
                  color: '#000',
                  opacity: 0.9,
                  boxSizing: 'border-box',
                }}
              >
                {span.function}
              </div>
            );
          })}
          {hoverNs !== null && (
            <div
              style={{
                position: 'absolute',
                left: `${(hoverNs - effectiveStart) / viewDuration * 100}%`,
                top: 0,
                bottom: 0,
                width: 1,
                background: 'rgba(255,255,255,0.7)',
                pointerEvents: 'none',
              }}
            />
          )}
        </div>
      ) : (
        <div className="flame-empty">No call events</div>
      )}

      <div className="flame-stack" data-testid="flame-stack">
        {currentStack.length === 0 ? (
          <span className="flame-stack-empty">
            {hoverNs !== null ? 'idle' : 'hover chart to explore stack'}
          </span>
        ) : (
          currentStack.map((frame, i) => (
            <div key={i} className="flame-stack-frame" data-testid="flame-stack-frame">
              <span className="flame-stack-depth">{frame.depth}</span>
              <span
                className="flame-stack-fn"
                style={{ color: colorForFunction(frame.function) }}
              >
                {frame.function}
              </span>
              <span className="flame-stack-loc">
                {frame.file}:{frame.line}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
