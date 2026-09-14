import { createReadStream, existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import http from "node:http";
import { extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = fileURLToPath(new URL(".", import.meta.url));
const distRoot = resolve(scriptDirectory, "..", "dist");
const host = process.env.FRONTEND_HOST || "0.0.0.0";
const port = Number(process.env.FRONTEND_PORT || "8081");
const apiOrigin = process.env.API_ORIGIN || "http://127.0.0.1:8000";

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`invalid FRONTEND_PORT: ${process.env.FRONTEND_PORT}`);
}

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".gif", "image/gif"],
  [".svg", "image/svg+xml"],
  [".ico", "image/x-icon"],
  [".webp", "image/webp"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
  [".txt", "text/plain; charset=utf-8"],
]);

function resolveStaticPath(urlPath) {
  let pathname;
  try {
    pathname = decodeURIComponent(urlPath.split("?")[0]);
  } catch {
    return null;
  }
  const candidate = pathname === "/" ? "index.html" : `.${pathname}`;
  const filePath = resolve(distRoot, candidate);
  if (filePath !== distRoot && !filePath.startsWith(`${distRoot}${sep}`)) {
    return null;
  }
  if (existsSync(filePath) && statSync(filePath).isFile()) {
    return filePath;
  }
  return join(distRoot, "index.html");
}

function proxyRequest(req, res) {
  const upstream = new URL(req.url, apiOrigin);
  const headers = { ...req.headers, host: upstream.host };

  const proxy = http.request(
    upstream,
    { method: req.method, headers },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
      upstreamRes.pipe(res);
    }
  );

  proxy.on("error", (error) => {
    const body = JSON.stringify({
      success: false,
      requestId: "static-proxy",
      error: {
        code: "BAD_GATEWAY",
        message: `upstream request failed: ${error.message}`,
      },
    });
    res.writeHead(502, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": Buffer.byteLength(body),
    });
    res.end(body);
  });

  req.pipe(proxy);
}

async function serveStatic(req, res) {
  const filePath = resolveStaticPath(req.url || "/");
  if (!filePath) {
    res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("forbidden");
    return;
  }

  try {
    const extension = extname(filePath).toLowerCase();
    const contentType = mimeTypes.get(extension) || "application/octet-stream";
    const fileInfo = statSync(filePath);
    res.writeHead(200, {
      "Content-Type": contentType,
      "Content-Length": fileInfo.size,
      "Cache-Control": filePath.endsWith("index.html") ? "no-cache" : "public, max-age=3600",
    });
    createReadStream(filePath).pipe(res);
  } catch {
    const fallback = join(distRoot, "index.html");
    const html = await readFile(fallback);
    res.writeHead(200, {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Length": html.length,
      "Cache-Control": "no-cache",
    });
    res.end(html);
  }
}

const server = http.createServer((req, res) => {
  if (!req.url) {
    res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("bad request");
    return;
  }

  if (req.url === "/__health") {
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ ok: true, apiOrigin, distRoot, port }));
    return;
  }

  if (req.url.startsWith("/api/")) {
    proxyRequest(req, res);
    return;
  }

  void serveStatic(req, res);
});

server.listen(port, host, () => {
  console.log(`Frontend listening on http://${host}:${port}`);
  console.log(`Proxying /api to ${apiOrigin}`);
});
