import { describe, it, expect, beforeEach } from 'vitest';
import {
  RAIL_COLLAPSED_KEY,
  readStoredRailCollapsed,
  writeStoredRailCollapsed,
} from '../../src/lib/rail';

describe('rail collapsed persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('user_ask_4_defaults_to_expanded_when_nothing_stored', () => {
    expect(readStoredRailCollapsed()).toBe(false);
  });

  it('user_ask_4_reads_stored_collapsed_value', () => {
    localStorage.setItem(RAIL_COLLAPSED_KEY, '1');
    expect(readStoredRailCollapsed()).toBe(true);
  });

  it('user_ask_4_write_then_read_roundtrips', () => {
    writeStoredRailCollapsed(true);
    expect(localStorage.getItem(RAIL_COLLAPSED_KEY)).toBe('1');
    expect(readStoredRailCollapsed()).toBe(true);
    writeStoredRailCollapsed(false);
    expect(localStorage.getItem(RAIL_COLLAPSED_KEY)).toBe('0');
    expect(readStoredRailCollapsed()).toBe(false);
  });
});
