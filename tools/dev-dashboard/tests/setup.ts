// Set the React act() environment flag so that React 19's internal scheduler
// works correctly with Vitest's jsdom environment.
// See: https://react.dev/warnings/react-dom-test-utils
(globalThis as unknown as Record<string, unknown>)['IS_REACT_ACT_ENVIRONMENT'] = true;
