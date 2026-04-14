/**
 * Left-rail collapse state. Persisted at
 * localStorage['dev-dashboard.railCollapsed'] as "1" / "0".
 */
export const RAIL_COLLAPSED_KEY = 'dev-dashboard.railCollapsed';

export function readStoredRailCollapsed(): boolean {
  try {
    return localStorage.getItem(RAIL_COLLAPSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function writeStoredRailCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(RAIL_COLLAPSED_KEY, collapsed ? '1' : '0');
  } catch {
    /* storage unavailable */
  }
}
