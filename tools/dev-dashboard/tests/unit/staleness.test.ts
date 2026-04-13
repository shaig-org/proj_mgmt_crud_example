import { describe, it, expect } from 'vitest';
import { classifyStaleness } from '../../src/lib/staleness';

describe('staleness classifier', () => {
  it('staleness_marks_aspect_stale_when_source_newer_than_artifact', () => {
    const out = classifyStaleness({
      primaryArtifactExists: true,
      primaryArtifactMtimeMs: 1000,
      newestSourceMtimeMs: 2000,
      newestSourceFile: 'a.ts',
    });
    expect(out.stale).toBe(true);
  });

  it('staleness_marks_fresh_when_artifact_newer_than_sources', () => {
    const out = classifyStaleness({
      primaryArtifactExists: true,
      primaryArtifactMtimeMs: 5000,
      newestSourceMtimeMs: 2000,
      newestSourceFile: 'a.ts',
    });
    expect(out.stale).toBe(false);
    expect(out.primaryArtifactExists).toBe(true);
  });

  it('staleness_marks_missing_when_artifact_does_not_exist', () => {
    const out = classifyStaleness({
      primaryArtifactExists: false,
      primaryArtifactMtimeMs: null,
      newestSourceMtimeMs: 2000,
      newestSourceFile: 'a.ts',
    });
    expect(out.primaryArtifactExists).toBe(false);
    expect(out.stale).toBe(false);
  });

  it('staleness_handles_aspect_with_zero_source_files', () => {
    const out = classifyStaleness({
      primaryArtifactExists: true,
      primaryArtifactMtimeMs: 1000,
      newestSourceMtimeMs: null,
      newestSourceFile: null,
    });
    expect(out.stale).toBe(false);
  });
});
