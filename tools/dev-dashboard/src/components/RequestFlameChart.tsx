import { useState } from 'react';
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
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const spans = buildSpans(request.call_events);

  const minNs = spans.length > 0 ? Math.min(...spans.map((s) => s.start_ns)) : 0;
  const maxNs = spans.length > 0 ? Math.max(...spans.map((s) => s.end_ns)) : 0;
  const totalDuration = maxNs - minNs;

  const maxDepth = spans.length > 0 ? Math.max(...spans.map((s) => s.depth)) : 0;

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const fraction = (e.clientX - rect.left) / rect.width;
    setHoverTime(fraction * totalDuration);
  }

  function handleMouseLeave() {
    setHoverTime(null);
  }

  const currentStack =
    hoverTime !== null ? getStackAtTime(spans, hoverTime + minNs) : [];

  const hasSpans = spans.length > 0 && totalDuration > 0;

  return (
    <div className="flame-chart-wrap">
      <div className="flame-header">
        <span className="flame-method">{request.method}</span>
        <span>{request.path}</span>
        <span>&rarr;</span>
        <span className={statusClass(request.status_code)}>{request.status_code}</span>
        <span>({request.duration_ms}ms)</span>
      </div>

      {hasSpans ? (
        <div
          data-testid="flame-chart"
          className="flame-area"
          style={{ height: `${(maxDepth + 1) * ROW_HEIGHT}px` }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {spans.map((span, i) => {
            const left = ((span.start_ns - minNs) / totalDuration) * 100;
            const width = Math.max(
              0.2,
              ((span.end_ns - span.start_ns) / totalDuration) * 100,
            );
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
          {hoverTime !== null && (
            <div
              style={{
                position: 'absolute',
                left: `${(hoverTime / totalDuration) * 100}%`,
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
            {hoverTime !== null ? 'idle' : 'hover chart to explore stack'}
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
