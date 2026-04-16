import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createElement, act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { RequestFlameChart } from '../../src/components/RequestFlameChart';
import type { E2eRequestTrace } from '../../src/aspects/e2e-traces/types';

// Minimal request fixture with two spans (call/return pairs).
const REQUEST_WITH_EVENTS: E2eRequestTrace = {
  seq: 1,
  method: 'POST',
  path: '/auth/login',
  status_code: 200,
  duration_ms: 12,
  timestamp_ms: 1734567890000,
  call_events: [
    { event: 'call',   file: 'routers/auth_api.py',          function: 'login',                    line: 45, depth: 0, timestamp_ns: 0    },
    { event: 'call',   file: 'capabilities/__init__.py',      function: 'AuthCapability.authenticate', line: 88, depth: 1, timestamp_ns: 100  },
    { event: 'return', file: 'capabilities/__init__.py',      function: 'AuthCapability.authenticate', line: 88, depth: 1, timestamp_ns: 900  },
    { event: 'return', file: 'routers/auth_api.py',           function: 'login',                    line: 45, depth: 0, timestamp_ns: 1100 },
  ],
};

const REQUEST_NO_EVENTS: E2eRequestTrace = {
  seq: 2,
  method: 'GET',
  path: '/health',
  status_code: 200,
  duration_ms: 1,
  timestamp_ms: 1734567890000,
  call_events: [],
};

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(element: React.ReactElement) {
  act(() => {
    root.render(element);
  });
}

describe('RequestFlameChart', () => {
  it('renders flame-chart container', () => {
    render(createElement(RequestFlameChart, { request: REQUEST_WITH_EVENTS }));
    const chart = container.querySelector('[data-testid="flame-chart"]');
    expect(chart).not.toBeNull();
  });

  it('renders correct number of flame-span elements for a given request', () => {
    render(createElement(RequestFlameChart, { request: REQUEST_WITH_EVENTS }));
    const spans = container.querySelectorAll('[data-testid="flame-span"]');
    // 2 call/return pairs → 2 spans
    expect(spans.length).toBe(2);
  });

  it('flame-stack shows "hover chart to explore stack" initially', () => {
    render(createElement(RequestFlameChart, { request: REQUEST_WITH_EVENTS }));
    const stack = container.querySelector('[data-testid="flame-stack"]');
    expect(stack).not.toBeNull();
    expect(stack!.textContent).toContain('hover chart to explore stack');
  });

  it('shows "No call events" when request has no events', () => {
    render(createElement(RequestFlameChart, { request: REQUEST_NO_EVENTS }));
    const chart = container.querySelector('[data-testid="flame-chart"]');
    expect(chart).toBeNull();
    expect(container.textContent).toContain('No call events');
  });
});
