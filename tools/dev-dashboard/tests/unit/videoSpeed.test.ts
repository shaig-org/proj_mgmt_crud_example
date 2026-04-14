import { describe, it, expect, beforeEach } from 'vitest';
import {
  VIDEO_SPEED_DEFAULT,
  VIDEO_SPEED_STORAGE_KEY,
  isVideoSpeed,
  readVideoSpeed,
  writeVideoSpeed,
} from '../../src/lib/videoSpeed';

describe('videoSpeed', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('video_speed_default_is_0_25', () => {
    expect(VIDEO_SPEED_DEFAULT).toBe(0.25);
    expect(readVideoSpeed()).toBe(0.25);
  });

  it('video_speed_write_then_read_roundtrip', () => {
    writeVideoSpeed(0.5);
    expect(readVideoSpeed()).toBe(0.5);
    expect(localStorage.getItem(VIDEO_SPEED_STORAGE_KEY)).toBe('0.5');
  });

  it('video_speed_rejects_non_canonical_values', () => {
    expect(isVideoSpeed(0.25)).toBe(true);
    expect(isVideoSpeed(0.33)).toBe(false);
    writeVideoSpeed(0.33);
    expect(localStorage.getItem(VIDEO_SPEED_STORAGE_KEY)).toBeNull();
  });

  it('video_speed_falls_back_to_default_when_storage_value_is_invalid', () => {
    localStorage.setItem(VIDEO_SPEED_STORAGE_KEY, 'not-a-number');
    expect(readVideoSpeed()).toBe(VIDEO_SPEED_DEFAULT);
  });
});
