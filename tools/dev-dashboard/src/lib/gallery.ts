/**
 * Gallery toolbar persistence: tile-size slider + view toggle.
 *
 * Keys:
 *   localStorage['dev-dashboard.tileSize']    — integer px, default 320, clamped.
 *   localStorage['dev-dashboard.galleryView'] — 'gif' | 'strip', default 'gif'.
 */

export const TILE_SIZE_STORAGE_KEY = 'dev-dashboard.tileSize';
export const GALLERY_VIEW_STORAGE_KEY = 'dev-dashboard.galleryView';

export const TILE_SIZE_MIN = 160;
export const TILE_SIZE_MAX = 1200;
export const TILE_SIZE_DEFAULT = 320;
export const TILE_SIZE_STOPS = [160, 240, 320, 480, 640, 800, 1000, 1200] as const;

export type GalleryView = 'gif' | 'strip';
export const GALLERY_VIEW_DEFAULT: GalleryView = 'gif';

export function clampTileSize(n: number): number {
  if (!Number.isFinite(n)) return TILE_SIZE_DEFAULT;
  const rounded = Math.round(n);
  if (rounded < TILE_SIZE_MIN) return TILE_SIZE_MIN;
  if (rounded > TILE_SIZE_MAX) return TILE_SIZE_MAX;
  return rounded;
}

export function readTileSize(): number {
  try {
    const raw = localStorage.getItem(TILE_SIZE_STORAGE_KEY);
    if (raw === null) return TILE_SIZE_DEFAULT;
    const n = Number.parseInt(raw, 10);
    if (!Number.isFinite(n)) return TILE_SIZE_DEFAULT;
    return clampTileSize(n);
  } catch {
    return TILE_SIZE_DEFAULT;
  }
}

export function writeTileSize(n: number): void {
  try {
    localStorage.setItem(TILE_SIZE_STORAGE_KEY, String(clampTileSize(n)));
  } catch {
    /* storage unavailable */
  }
}

export function readGalleryView(): GalleryView {
  try {
    const v = localStorage.getItem(GALLERY_VIEW_STORAGE_KEY);
    if (v === 'gif' || v === 'strip') return v;
  } catch {
    /* storage unavailable */
  }
  return GALLERY_VIEW_DEFAULT;
}

export function writeGalleryView(v: GalleryView): void {
  try {
    localStorage.setItem(GALLERY_VIEW_STORAGE_KEY, v);
  } catch {
    /* storage unavailable */
  }
}
