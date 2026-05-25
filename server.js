const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const root = __dirname;
const port = Number(process.env.PORT || 3001);

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, headers);
  res.end(body);
}

function serveFile(res, filePath) {
  fs.readFile(filePath, (error, data) => {
    if (error) {
      send(res, 404, "Not found", { "Content-Type": "text/plain; charset=utf-8" });
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    send(res, 200, data, { "Content-Type": types[ext] || "application/octet-stream" });
  });
}

function runUpdater(res, args = []) {
  const child = spawn("python", ["scripts/update_data.py", ...args], {
    cwd: root,
    shell: false,
  });

  let output = "";
  let errorOutput = "";
  child.stdout.on("data", (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    errorOutput += chunk.toString();
  });
  child.on("close", (code) => {
    const payload = {
      ok: code === 0,
      code,
      output: output.trim(),
      error: errorOutput.trim(),
    };
    send(res, code === 0 ? 200 : 500, JSON.stringify(payload, null, 2), {
      "Content-Type": "application/json; charset=utf-8",
    });
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "POST" && url.pathname === "/api/update") {
    runUpdater(res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/stock") {
    const query = (url.searchParams.get("symbol") || "").trim();
    if (!query || query.length > 80 || !/^[A-Za-z0-9 .&()-]+$/.test(query)) {
      send(res, 400, JSON.stringify({ ok: false, error: "Enter a valid NSE symbol or company name." }), {
        "Content-Type": "application/json; charset=utf-8",
      });
      return;
    }

    runUpdater(res, ["--symbol", query]);
    return;
  }

  const requested = url.pathname === "/" ? "/index.html" : url.pathname;
  const safePath = path.normalize(decodeURIComponent(requested)).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(root, safePath);

  if (!filePath.startsWith(root)) {
    send(res, 403, "Forbidden", { "Content-Type": "text/plain; charset=utf-8" });
    return;
  }

  serveFile(res, filePath);
});

server.listen(port, () => {
  console.log(`Screener running at http://localhost:${port}`);
});
