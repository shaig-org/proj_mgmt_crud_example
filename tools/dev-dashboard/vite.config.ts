import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

const thisFile = fileURLToPath(import.meta.url);
const dashboardDir = path.dirname(thisFile);

async function resolveRepoRoot(start: string): Promise<string> {
  // Env override for tests.
  if (process.env.DEV_DASHBOARD_REPO_ROOT) {
    return path.resolve(process.env.DEV_DASHBOARD_REPO_ROOT);
  }
  let dir = path.resolve(start);
  for (let i = 0; i < 10; i++) {
    try {
      await fs.stat(path.join(dir, '.git'));
      return dir;
    } catch {
      /* walk */
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(start, '..', '..');
}

const MIME: Record<string, string> = {
  '.json': 'application/json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
};

interface ArtifactsPluginOptions {
  repoRoot: string;
  mounts: Record<string, string>;
}

export function repoArtifactsPlugin(opts: ArtifactsPluginOptions): Plugin {
  return {
    name: 'dev-dashboard-artifacts',
    configureServer(server) {
      server.middlewares.use(
        '/artifacts',
        (req: IncomingMessage, res: ServerResponse, next: () => void) => {
          if (req.method !== 'GET' && req.method !== 'HEAD') {
            res.statusCode = 405;
            res.end();
            return;
          }
          void serveArtifact(req, res, next, opts);
        },
      );
    },
  };
}

async function serveArtifact(
  req: IncomingMessage,
  res: ServerResponse,
  next: () => void,
  opts: ArtifactsPluginOptions,
): Promise<void> {
  const reqUrl = req.url ?? '/';
  const [rawPath] = reqUrl.split('?');
  const decoded = decodeURIComponent(rawPath);

  let matched: { prefix: string; fsRoot: string } | null = null;
  for (const [prefix, fsRoot] of Object.entries(opts.mounts)) {
    if (decoded === prefix || decoded.startsWith(prefix + '/') || decoded === prefix.slice(0, -1)) {
      matched = { prefix, fsRoot };
      break;
    }
  }
  if (!matched) {
    next();
    return;
  }

  const rel = decoded.slice(matched.prefix.length).replace(/^\/+/, '');
  const absolutePath = path.resolve(matched.fsRoot, rel);

  // Path traversal guard.
  if (!absolutePath.startsWith(path.resolve(matched.fsRoot))) {
    res.statusCode = 403;
    res.end();
    return;
  }

  let stat;
  try {
    stat = await fs.stat(absolutePath);
  } catch {
    res.statusCode = 404;
    res.end();
    return;
  }

  if (stat.isDirectory()) {
    // Directory listing (JSON).
    const entries = await fs.readdir(absolutePath, { withFileTypes: true });
    const listing = entries.map((e) => ({
      name: e.name,
      type: e.isDirectory() ? 'dir' : 'file',
    }));
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Last-Modified', stat.mtime.toUTCString());
    res.end(JSON.stringify({ entries: listing }));
    return;
  }

  const ext = path.extname(absolutePath).toLowerCase();
  const type = MIME[ext] ?? 'application/octet-stream';
  res.statusCode = 200;
  res.setHeader('Content-Type', type);
  res.setHeader('Content-Length', String(stat.size));
  res.setHeader('Last-Modified', stat.mtime.toUTCString());
  if (req.method === 'HEAD') {
    res.end();
    return;
  }
  createReadStream(absolutePath).pipe(res);
}

// ---------------------------------------------------------------------------
// Run-diff plugin — POST /api/run-diff/capabilities
// ---------------------------------------------------------------------------

/** Git ref characters that are safe to pass as CLI arguments, plus the WORKING sentinel. */
const SAFE_REF_RE = /^[a-zA-Z0-9._\-/~^@{}:]+$/;
const WORKING_TREE_REF = 'WORKING';

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

function jsonResponse(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Length', Buffer.byteLength(payload));
  res.end(payload);
}

export function runDiffPlugin(repoRoot: string): Plugin {
  return {
    name: 'dev-dashboard-run-diff',
    configureServer(server) {
      server.middlewares.use(
        '/api/run-diff/capabilities',
        (req: IncomingMessage, res: ServerResponse, next: () => void) => {
          if (req.method !== 'POST') {
            next();
            return;
          }
          void handleRunDiff(req, res, repoRoot);
        },
      );
    },
  };
}

async function handleRunDiff(
  req: IncomingMessage,
  res: ServerResponse,
  repoRoot: string,
): Promise<void> {
  let body: { from?: unknown; to?: unknown };
  try {
    body = JSON.parse(await readBody(req)) as { from?: unknown; to?: unknown };
  } catch {
    jsonResponse(res, 400, { ok: false, error: 'Invalid JSON body' });
    return;
  }

  const fromRef = String(body.from ?? 'main');
  const toRef = String(body.to ?? 'HEAD');

  const isValidRef = (r: string) => r === WORKING_TREE_REF || SAFE_REF_RE.test(r);
  if (!isValidRef(fromRef) || !isValidRef(toRef)) {
    jsonResponse(res, 400, { ok: false, error: 'Invalid git ref — only alphanumeric, ., -, _, /, ~, ^, @ allowed (or "WORKING" for working tree)' });
    return;
  }

  const backendDir = path.resolve(repoRoot, 'backend');

  try {
    const { stdout, stderr } = await execFileAsync(
      'uv',
      [
        'run', 'python', '-m',
        'project_management_crud_example.tools.diff_capabilities',
        '--from', fromRef,
        '--to', toRef,
      ],
      { cwd: backendDir, timeout: 30_000 },
    );
    jsonResponse(res, 200, { ok: true, stdout: stdout.trim(), stderr: stderr.trim() });
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    jsonResponse(res, 500, {
      ok: false,
      error: e.stderr?.trim() || e.message || 'Unknown error',
      stdout: e.stdout?.trim() ?? '',
    });
  }
}

// Also expose /artifacts/staleness.json mapped to .staleness.json in this dir.
async function buildConfig() {
  const repoRoot = await resolveRepoRoot(dashboardDir);

  const mounts: Record<string, string> = {
    '/scenarios': path.resolve(repoRoot, 'frontend/walkthroughs'),
    '/capabilities': path.resolve(repoRoot, 'backend/evidence/capabilities'),
    '/traces': path.resolve(repoRoot, 'backend/.trace-artifacts'),
    '/e2e-traces': path.resolve(repoRoot, 'backend/e2e-traces'),
    '/staleness.json': path.resolve(dashboardDir, '.staleness.json'),
  };

  return defineConfig({
    root: dashboardDir,
    plugins: [react(), repoArtifactsPlugin({ repoRoot, mounts }), runDiffPlugin(repoRoot)],
    define: {
      'import.meta.env.VITE_REPO_ROOT': JSON.stringify(repoRoot),
    },
    server: {
      host: '127.0.0.1',
      port: 5179,
      strictPort: false,
      fs: {
        allow: [
          dashboardDir,
          path.resolve(repoRoot, 'frontend/walkthroughs'),
          path.resolve(repoRoot, 'backend/evidence/capabilities'),
          path.resolve(repoRoot, 'backend/.trace-artifacts'),
          path.resolve(repoRoot, 'backend/e2e-traces'),
        ],
      },
    },
  });
}

export default buildConfig();
