import React, { useState } from 'react';
import {
  TILE_SIZE_DEFAULT,
  TILE_SIZE_MAX,
  TILE_SIZE_MIN,
  TILE_SIZE_STOPS,
  clampTileSize,
} from '../../lib/gallery';
import type { ScreenIndex } from './screenIndex';

const SCREENS_TILE_KEY = 'dev-dashboard.screensTileSize';

function readScreensTileSize(): number {
  try {
    const raw = localStorage.getItem(SCREENS_TILE_KEY);
    if (raw === null) return TILE_SIZE_DEFAULT;
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? clampTileSize(n) : TILE_SIZE_DEFAULT;
  } catch {
    return TILE_SIZE_DEFAULT;
  }
}

function writeScreensTileSize(n: number): void {
  try {
    localStorage.setItem(SCREENS_TILE_KEY, String(clampTileSize(n)));
  } catch {
    /* storage unavailable */
  }
}

function slugifyRoute(route: string): string {
  return route.replace(/\//g, '-').replace(/^-/, '').replace(/:/g, '') || 'root';
}

interface ScreensIndexViewProps {
  screenIndex: ScreenIndex;
  uncovered: string[];
}

export function ScreensIndexView({ screenIndex, uncovered }: ScreensIndexViewProps): React.ReactElement {
  const [tileSize, setTileSize] = useState<number>(() =>
    typeof window === 'undefined' ? TILE_SIZE_DEFAULT : readScreensTileSize(),
  );

  function onTileSizeChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const n = clampTileSize(Number(e.currentTarget.value));
    setTileSize(n);
    writeScreensTileSize(n);
  }

  const covered = Array.from(screenIndex.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  function openDetail(route: string): void {
    window.location.hash = `#/screens/${encodeURIComponent(route)}`;
  }

  return (
    <div data-testid="screens-index">
      {/* Toolbar */}
      <div className="scen-toolbar">
        <label className="scen-toolbar__size">
          card size{' '}
          <input
            type="range"
            min={TILE_SIZE_MIN}
            max={TILE_SIZE_MAX}
            step={10}
            list="screens-tile-size-stops"
            value={tileSize}
            onChange={onTileSizeChange}
            data-testid="screens-tile-size-slider"
          />
          <datalist id="screens-tile-size-stops">
            {TILE_SIZE_STOPS.map((s) => (
              <option key={s} value={String(s)} />
            ))}
          </datalist>
          <span className="scen-toolbar__readout" data-testid="screens-tile-size-readout">
            {tileSize}px
          </span>
        </label>
        <span className="screens-toolbar__summary">
          {covered.length} covered · {uncovered.length} uncovered
        </span>
      </div>

      {/* Covered screens */}
      <h3 className="screens-section-title">Covered screens</h3>
      {covered.length === 0 ? (
        <p className="screens-empty">No screens visited yet — run scenarios to capture URL data.</p>
      ) : (
        <div
          className="screens-grid"
          data-testid="screens-grid"
          style={{ ['--tile-size' as string]: `${tileSize}px` }}
        >
          {covered.map(([route, visits]) => {
            const firstThumb = visits.find((v) => v.screenshot)?.screenshot;
            const slug = slugifyRoute(route);
            return (
              <button
                key={route}
                type="button"
                className="screen-card"
                data-testid={`screen-card-${slug}`}
                onClick={() => openDetail(route)}
              >
                <div className="screen-card__media">
                  {firstThumb ? (
                    <img
                      src={firstThumb}
                      alt={route}
                      className="screen-card__thumb"
                      loading="lazy"
                      decoding="async"
                    />
                  ) : (
                    <div className="screen-card__thumb screen-card__thumb--empty" aria-hidden="true" />
                  )}
                </div>
                <div className="screen-card__footer">
                  <span className="screen-card__route" title={route}>
                    {route}
                  </span>
                  <span className="screen-card__count">
                    {visits.length} {visits.length === 1 ? 'visit' : 'visits'}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Uncovered screens */}
      {uncovered.length > 0 && (
        <div className="screens-uncovered" data-testid="uncovered-screens">
          <h3 className="screens-section-title screens-section-title--warn">
            ⚠ Uncovered screens
          </h3>
          <p className="screens-uncovered__subtitle">
            These routes have no scenario step visiting them yet.
          </p>
          <div className="screens-uncovered__chips">
            {uncovered.map((route) => (
              <span key={route} className="screens-uncovered__chip">
                {route}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
