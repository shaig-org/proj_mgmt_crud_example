import type { AnyAspect } from '../aspects/types';

export class DuplicateAspectIdError extends Error {
  constructor(public readonly id: string) {
    super(`Duplicate aspect id registered: ${id}`);
    this.name = 'DuplicateAspectIdError';
  }
}

export function buildRegistry(aspects: AnyAspect[]): ReadonlyArray<AnyAspect> {
  const seen = new Set<string>();
  for (const a of aspects) {
    if (seen.has(a.id)) {
      throw new DuplicateAspectIdError(a.id);
    }
    seen.add(a.id);
  }
  return aspects;
}

export function getAspect(
  aspects: ReadonlyArray<AnyAspect>,
  id: string,
): AnyAspect | undefined {
  return aspects.find((a) => a.id === id);
}

export function resolveAspectFromHash(
  aspects: ReadonlyArray<AnyAspect>,
  hash: string,
): AnyAspect {
  // hash looks like `#/scenarios`, `#/scenarios?group=org`, `#/scenarios/<slug>`, or empty.
  const stripped = hash.replace(/^#\/?/, '');
  // The aspect id is the first path segment, before any `?` or `/`.
  const firstSegment = stripped.split('?')[0]!.split('/')[0]!;
  const match = aspects.find((a) => a.id === firstSegment);
  return match ?? aspects[0];
}
