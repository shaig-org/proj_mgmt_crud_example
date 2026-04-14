import { describe, it, expect, beforeEach } from 'vitest';
import {
  GALLERY_VIEW_STORAGE_KEY,
  TILE_SIZE_DEFAULT,
  TILE_SIZE_MAX,
  TILE_SIZE_MIN,
  TILE_SIZE_STORAGE_KEY,
  clampTileSize,
  readGalleryView,
  readTileSize,
  writeGalleryView,
  writeTileSize,
} from '../../src/lib/gallery';

describe('gallery toolbar persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('old_feature_03_tile_size_roundtrips_localStorage', () => {
    expect(readTileSize()).toBe(TILE_SIZE_DEFAULT);
    writeTileSize(480);
    expect(localStorage.getItem(TILE_SIZE_STORAGE_KEY)).toBe('480');
    expect(readTileSize()).toBe(480);
    writeTileSize(800);
    expect(readTileSize()).toBe(800);
  });

  it('old_feature_03_tile_size_clamps_to_valid_range', () => {
    expect(clampTileSize(10)).toBe(TILE_SIZE_MIN);
    expect(clampTileSize(99999)).toBe(TILE_SIZE_MAX);
    expect(clampTileSize(Number.NaN)).toBe(TILE_SIZE_DEFAULT);

    writeTileSize(50);
    expect(readTileSize()).toBe(TILE_SIZE_MIN);
    writeTileSize(5000);
    expect(readTileSize()).toBe(TILE_SIZE_MAX);

    localStorage.setItem(TILE_SIZE_STORAGE_KEY, 'not-a-number');
    expect(readTileSize()).toBe(TILE_SIZE_DEFAULT);
  });

  it('old_feature_02_gallery_view_defaults_to_gif', () => {
    expect(readGalleryView()).toBe('gif');
    localStorage.setItem(GALLERY_VIEW_STORAGE_KEY, 'garbage');
    expect(readGalleryView()).toBe('gif');
  });

  it('old_feature_02_gallery_view_roundtrips_localStorage', () => {
    writeGalleryView('strip');
    expect(localStorage.getItem(GALLERY_VIEW_STORAGE_KEY)).toBe('strip');
    expect(readGalleryView()).toBe('strip');
    writeGalleryView('gif');
    expect(readGalleryView()).toBe('gif');
  });
});
