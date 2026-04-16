import { describe, it, expect } from 'vitest';
import { normalizeUrl } from '../../src/aspects/screens/normalizeUrl';

describe('normalizeUrl', () => {
  it('normalizeUrl_returns_null_for_empty_string', () => {
    expect(normalizeUrl('')).toBeNull();
  });

  it('normalizeUrl_returns_null_for_non_url_string', () => {
    // Bare word with no leading slash is not parseable as a pathname
    expect(normalizeUrl('not-a-url')).toBeNull();
  });

  it('normalizeUrl_strips_origin_and_returns_static_route', () => {
    expect(normalizeUrl('http://localhost:5173/login')).toBe('/login');
  });

  it('normalizeUrl_strips_origin_and_returns_static_route_projects', () => {
    expect(normalizeUrl('http://localhost:5173/projects')).toBe('/projects');
  });

  it('normalizeUrl_strips_origin_and_returns_static_route_users', () => {
    expect(normalizeUrl('http://localhost:5173/users')).toBe('/users');
  });

  it('normalizeUrl_strips_origin_and_returns_static_route_organizations', () => {
    expect(normalizeUrl('http://localhost:5173/organizations')).toBe('/organizations');
  });

  it('normalizeUrl_normalizes_uuid_project_id_to_pattern', () => {
    expect(normalizeUrl('http://localhost:5173/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890')).toBe('/projects/:projectId');
  });

  it('normalizeUrl_normalizes_uuid_ticket_id_to_pattern', () => {
    expect(normalizeUrl('http://localhost:5173/tickets/00000000-0000-0000-0000-000000000001')).toBe('/tickets/:ticketId');
  });

  it('normalizeUrl_normalizes_uuid_epic_id_to_pattern', () => {
    expect(normalizeUrl('http://localhost:5173/epics/12345678-1234-1234-1234-123456789abc')).toBe('/epics/:epicId');
  });

  it('normalizeUrl_normalizes_numeric_id_to_pattern', () => {
    expect(normalizeUrl('http://localhost:5173/projects/42')).toBe('/projects/:projectId');
  });

  it('normalizeUrl_strips_trailing_slash_before_matching', () => {
    expect(normalizeUrl('http://localhost:5173/projects/')).toBe('/projects');
  });

  it('normalizeUrl_strips_query_string_before_matching', () => {
    expect(normalizeUrl('http://localhost:5173/projects?foo=bar')).toBe('/projects');
  });

  it('normalizeUrl_strips_hash_fragment_before_matching', () => {
    expect(normalizeUrl('http://localhost:5173/projects#section')).toBe('/projects');
  });

  it('normalizeUrl_returns_raw_pathname_for_unknown_route', () => {
    const result = normalizeUrl('http://localhost:5173/unknown/path/here');
    expect(result).toBe('/unknown/path/here');
    expect(result).not.toBeNull();
  });

  it('normalizeUrl_handles_root_path', () => {
    const result = normalizeUrl('http://localhost:5173/');
    expect(result).toBe('/');
    expect(result).not.toBeNull();
  });
});
