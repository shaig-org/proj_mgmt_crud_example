/**
 * Persisted video-playback-speed preference shared by the inline video player
 * and the video lightbox.
 *
 * Key: localStorage['dev-dashboard.videoSpeed'] — a number in VIDEO_SPEEDS.
 * Default: 0.25 (most scenario videos are easier to follow at quarter speed).
 */

export const VIDEO_SPEED_STORAGE_KEY = 'dev-dashboard.videoSpeed';
export const VIDEO_SPEEDS = [0.1, 0.15, 0.25, 0.5, 1, 1.5, 2] as const;
export type VideoSpeed = (typeof VIDEO_SPEEDS)[number];
export const VIDEO_SPEED_DEFAULT: VideoSpeed = 0.25;

export function isVideoSpeed(n: number): n is VideoSpeed {
  return (VIDEO_SPEEDS as readonly number[]).includes(n);
}

export function readVideoSpeed(): VideoSpeed {
  try {
    const raw = localStorage.getItem(VIDEO_SPEED_STORAGE_KEY);
    if (raw === null) return VIDEO_SPEED_DEFAULT;
    const n = Number.parseFloat(raw);
    if (Number.isFinite(n) && isVideoSpeed(n)) return n;
  } catch {
    /* storage unavailable */
  }
  return VIDEO_SPEED_DEFAULT;
}

export function writeVideoSpeed(n: number): void {
  try {
    if (isVideoSpeed(n)) {
      localStorage.setItem(VIDEO_SPEED_STORAGE_KEY, String(n));
    }
  } catch {
    /* storage unavailable */
  }
}
