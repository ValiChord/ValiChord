/**
 * Static file server + WebSocket proxy for the ValiChord demo page.
 * Serves files from the demo/ directory on http://localhost:8888.
 * Also proxies WebSocket connections to the local Holochain conductor:
 *   /app-ws   → ws://localhost:4500  (app interface)
 *   /admin-ws → ws://localhost:4444  (admin interface)
 * This lets the browser use a single port (8888) regardless of whether
 * it is connecting from localhost or via HTTPS Codespace port-forwarding.
 * No external dependencies — pure Node.js built-ins.
 */

import { createServer }   from 'node:http';
import { createConnection } from 'node:net';
import { readFile }        from 'node:fs/promises';
import { extname, join }   from 'node:path';
import { fileURLToPath }   from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const PORT       = parseInt(process.env.PORT || '8888', 10);  // Render sets PORT
const APP_PORT   = 4500;
const ADMIN_PORT = 4444;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.mjs':  'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
};

// ── Static file handler ───────────────────────────────────────────────────────

const server = createServer(async (req, res) => {
  const url = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  if (url.includes('..')) { res.writeHead(403); res.end(); return; }
  const filePath = join(__dirname, url);
  try {
    const data = await readFile(filePath);
    res.writeHead(200, {
      'Content-Type': MIME[extname(filePath)] || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found');
  }
});

// ── WebSocket proxy ───────────────────────────────────────────────────────────
// Tunnels browser WebSocket connections through to the local conductor ports.
// The browser only needs access to port 8888; the conductor ports stay local.

server.on('upgrade', (req, browserSocket, head) => {
  let backendPort;
  if      (req.url === '/app-ws')   backendPort = APP_PORT;
  else if (req.url === '/admin-ws') backendPort = ADMIN_PORT;
  else { browserSocket.end('HTTP/1.1 404 Not Found\r\n\r\n'); return; }

  const backend = createConnection(backendPort, '127.0.0.1');

  backend.on('error', err => {
    console.error(`[proxy] backend :${backendPort} error: ${err.message}`);
    browserSocket.end('HTTP/1.1 502 Bad Gateway\r\n\r\n');
  });

  backend.on('connect', () => {
    // Reconstruct the HTTP/1.1 upgrade request for the conductor.
    // Replace Origin/Host so the conductor's allowed_origins: '*' accepts it.
    let reqStr = 'GET / HTTP/1.1\r\n';
    for (const [k, v] of Object.entries(req.headers)) {
      if (k === 'host')   { reqStr += `host: localhost:${backendPort}\r\n`; continue; }
      if (k === 'origin') { reqStr += `origin: http://localhost\r\n`;       continue; }
      reqStr += `${k}: ${v}\r\n`;
    }
    reqStr += '\r\n';
    backend.write(reqStr);
    if (head && head.length) backend.write(head);

    // Bidirectional pipe: backend 101 + frames → browser, browser frames → backend.
    backend.pipe(browserSocket);
    browserSocket.pipe(backend);
  });

  browserSocket.on('error', () => backend.destroy());
  backend.on('end',   () => browserSocket.end());
  browserSocket.on('end', () => backend.end());
});

// ── Listen ────────────────────────────────────────────────────────────────────

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Demo page  → http://localhost:${PORT}`);
  console.log(`WS proxy   → /app-ws → :${APP_PORT}, /admin-ws → :${ADMIN_PORT}`);
  console.log('Press Ctrl+C to stop.');
});
