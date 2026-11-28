// Tiny static server for the Playwright run in CI: serves web/out under the Pages base path,
// like GitHub Pages (directory -> index.html). Usage: node scripts/serve-out.mjs [port]
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(path.dirname(fileURLToPath(import.meta.url))), "out");
const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "/roshni-site";
const port = Number(process.argv[2] ?? 4173);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".wasm": "application/wasm", ".txt": "text/plain" };

createServer(async (req, res) => {
  const url = decodeURIComponent(new URL(req.url ?? "/", "http://x").pathname);
  if (!url.startsWith(base)) return res.writeHead(404).end();
  let file = path.join(root, url.slice(base.length));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  try {
    if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream" });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404).end();
  }
}).listen(port, () => console.log(`serving ${root} at http://localhost:${port}${base}/`));
