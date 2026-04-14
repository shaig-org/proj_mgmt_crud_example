import { describe, it, expect } from 'vitest';
import { injectFlameStyles } from '../../src/aspects/traces/TracesAspect';

/**
 * jsdom-based checks for the same-origin iframe style injector. The real
 * flame.html produced by pytest-tracer (Brendan Gregg's FlameGraph.pl) is a
 * single SVG with a fixed `width="1200"` attribute plus inline `#search` /
 * `#matched` text nodes. Our injector must (a) strip the fixed width so CSS
 * can stretch it to 100% and (b) hide the broken search controls.
 */
function buildIframeWithFlame(): HTMLIFrameElement {
  const iframe = document.createElement('iframe');
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument;
  if (!doc) throw new Error('no contentDocument');
  doc.open();
  doc.write(
    '<!doctype html><html><head></head><body>' +
      '<svg width="1200" height="142" viewBox="0 0 1200 142">' +
      '<text id="search">Search</text>' +
      '<text id="matched"></text>' +
      '</svg></body></html>',
  );
  doc.close();
  return iframe;
}

describe('iter4 flame iframe style injector', () => {
  it('iter4_flame_inject_strips_fixed_svg_width_attribute', () => {
    const iframe = buildIframeWithFlame();
    injectFlameStyles(iframe);
    const svg = iframe.contentDocument!.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.hasAttribute('width')).toBe(false);
    expect(svg!.hasAttribute('height')).toBe(false);
  });

  it('iter4_flame_inject_adds_override_style_once', () => {
    const iframe = buildIframeWithFlame();
    injectFlameStyles(iframe);
    injectFlameStyles(iframe);
    const styles =
      iframe.contentDocument!.querySelectorAll('#dd-flame-overrides');
    expect(styles.length).toBe(1);
  });

  it('iter4_flame_inject_css_targets_search_and_matched', () => {
    const iframe = buildIframeWithFlame();
    injectFlameStyles(iframe);
    const style = iframe.contentDocument!.getElementById('dd-flame-overrides');
    expect(style).not.toBeNull();
    const css = style!.textContent ?? '';
    expect(css).toMatch(/#search/);
    expect(css).toMatch(/#matched/);
    expect(css).toMatch(/display:\s*none/);
    expect(css).toMatch(/svg\s*\{[^}]*width:\s*100%/);
  });

  it('iter4_flame_inject_handles_missing_contentDocument_gracefully', () => {
    const iframe = document.createElement('iframe');
    // Not attached to DOM; some jsdom builds expose contentDocument anyway,
    // but the injector must not throw regardless.
    expect(() => injectFlameStyles(iframe)).not.toThrow();
  });
});
