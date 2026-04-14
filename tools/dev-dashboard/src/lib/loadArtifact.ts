export class ArtifactMissingError extends Error {
  constructor(public readonly path: string) {
    super(`Artifact not found: ${path}`);
    this.name = 'ArtifactMissingError';
  }
}

export class ArtifactMalformedError extends Error {
  constructor(
    public readonly path: string,
    public readonly cause: unknown,
  ) {
    super(`Artifact is not valid JSON: ${path}`);
    this.name = 'ArtifactMalformedError';
  }
}

export class ArtifactSchemaError extends Error {
  constructor(
    public readonly path: string,
    public readonly field: string,
  ) {
    super(`Artifact at ${path} is missing required field: ${field}`);
    this.name = 'ArtifactSchemaError';
  }
}

export interface LoadResult<T> {
  data: T;
  mtime: string | null;
}

/**
 * Fetch a JSON artifact. Returns parsed data + Last-Modified header.
 * Throws ArtifactMissingError on 404 and ArtifactMalformedError on parse
 * failure (both carry the requested path for better error surfaces).
 */
export async function loadArtifact<T>(
  url: string,
  fetcher: typeof fetch = fetch,
): Promise<LoadResult<T>> {
  const resp = await fetcher(url);
  if (resp.status === 404) {
    throw new ArtifactMissingError(url);
  }
  if (!resp.ok) {
    throw new Error(`Artifact fetch failed for ${url}: HTTP ${resp.status}`);
  }
  const text = await resp.text();
  let data: T;
  try {
    data = JSON.parse(text) as T;
  } catch (e) {
    throw new ArtifactMalformedError(url, e);
  }
  return { data, mtime: resp.headers.get('Last-Modified') };
}

export async function loadArtifactText(
  url: string,
  fetcher: typeof fetch = fetch,
): Promise<LoadResult<string>> {
  const resp = await fetcher(url);
  if (resp.status === 404) {
    throw new ArtifactMissingError(url);
  }
  if (!resp.ok) {
    throw new Error(`Artifact fetch failed for ${url}: HTTP ${resp.status}`);
  }
  const text = await resp.text();
  return { data: text, mtime: resp.headers.get('Last-Modified') };
}
