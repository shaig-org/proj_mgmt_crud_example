export const KNOWN_ROUTES: string[] = [
  '/login',
  '/projects',
  '/projects/:projectId',
  '/tickets/:ticketId',
  '/epics/:epicId',
  '/users',
  '/organizations',
];

/**
 * Normalize a URL to a route pattern string.
 *
 * Returns null only for empty string or truly unparseable input.
 * Returns the raw pathname for unknown routes (surfaces them in the index).
 */
export function normalizeUrl(url: string): string | null {
  if (!url) return null;

  let pathname: string;
  try {
    pathname = new URL(url).pathname;
  } catch {
    // Not an absolute URL — only treat as a pathname if it starts with '/'
    if (!url.startsWith('/')) {
      return null;
    }
    try {
      pathname = new URL(url, 'http://localhost').pathname;
    } catch {
      return null;
    }
  }

  // Strip trailing slash (unless pathname is exactly '/')
  if (pathname.length > 1 && pathname.endsWith('/')) {
    pathname = pathname.slice(0, -1);
  }

  // Try to match against known routes
  const actualSegments = pathname.split('/');

  for (const route of KNOWN_ROUTES) {
    const routeSegments = route.split('/');
    if (routeSegments.length !== actualSegments.length) continue;

    let matches = true;
    for (let i = 0; i < routeSegments.length; i++) {
      const routeSeg = routeSegments[i]!;
      const actualSeg = actualSegments[i]!;
      if (routeSeg.startsWith(':')) {
        // Any non-empty segment can fill a param slot
        if (actualSeg === '') {
          matches = false;
          break;
        }
      } else {
        // Literal segment — must match exactly
        if (routeSeg !== actualSeg) {
          matches = false;
          break;
        }
      }
    }

    if (matches) return route;
  }

  // No known route matched — return raw pathname (not null)
  return pathname;
}
