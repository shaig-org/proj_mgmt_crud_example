import { describe, it, expect, beforeEach } from 'vitest';
import {
  THEME_STORAGE_KEY,
  applyTheme,
  readStoredTheme,
  toggleTheme,
  writeStoredTheme,
} from '../../src/lib/theme';

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('user_ask_2_defaults_to_dark_when_nothing_stored', () => {
    expect(readStoredTheme()).toBe('dark');
  });

  it('user_ask_2_reads_stored_light_theme', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    expect(readStoredTheme()).toBe('light');
  });

  it('user_ask_2_ignores_garbage_stored_value_and_returns_dark', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'solarized-chartreuse');
    expect(readStoredTheme()).toBe('dark');
  });

  it('user_ask_2_writeStoredTheme_roundtrips', () => {
    writeStoredTheme('light');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    writeStoredTheme('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('user_ask_2_applyTheme_sets_data_theme_attribute', () => {
    applyTheme('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    applyTheme('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('user_ask_2_toggleTheme_flips_value', () => {
    expect(toggleTheme('dark')).toBe('light');
    expect(toggleTheme('light')).toBe('dark');
  });
});
