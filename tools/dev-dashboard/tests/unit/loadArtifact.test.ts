import { describe, it, expect } from 'vitest';
import {
  ArtifactMalformedError,
  ArtifactMissingError,
  loadArtifact,
} from '../../src/lib/loadArtifact';

function makeFetch(init: {
  status: number;
  body: string;
  headers?: Record<string, string>;
}): typeof fetch {
  const fakeFetch: typeof fetch = async () => {
    return new Response(init.body, {
      status: init.status,
      headers: init.headers,
    });
  };
  return fakeFetch;
}

describe('loadArtifact', () => {
  it('loadArtifact_returns_data_and_response_mtime', async () => {
    const f = makeFetch({
      status: 200,
      body: '{"x":1}',
      headers: { 'Last-Modified': 'Wed, 12 Apr 2026 08:00:00 GMT' },
    });
    const { data, mtime } = await loadArtifact<{ x: number }>('/a.json', f);
    expect(data).toEqual({ x: 1 });
    expect(mtime).toBe('Wed, 12 Apr 2026 08:00:00 GMT');
  });

  it('loadArtifact_throws_typed_error_on_404', async () => {
    const f = makeFetch({ status: 404, body: '' });
    await expect(loadArtifact('/missing.json', f)).rejects.toBeInstanceOf(
      ArtifactMissingError,
    );
  });

  it('loadArtifact_throws_typed_error_on_invalid_json', async () => {
    const f = makeFetch({ status: 200, body: 'not json' });
    await expect(loadArtifact('/bad.json', f)).rejects.toBeInstanceOf(
      ArtifactMalformedError,
    );
    const f2 = makeFetch({ status: 200, body: 'not json' });
    try {
      await loadArtifact('/bad.json', f2);
    } catch (e) {
      expect((e as ArtifactMalformedError).path).toBe('/bad.json');
    }
  });
});
