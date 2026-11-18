import fs from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import type { Connect, Plugin } from "vite";
import { defineConfig } from "vite";

const SETUPS_FILE = path.resolve("save/setups.json");

function readSetups(): Record<string, unknown> {
  try {
    const parsed = JSON.parse(fs.readFileSync(SETUPS_FILE, "utf8")) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed as Record<string, unknown>;
  } catch {
    return {};
  }
}

function writeSetups(setups: Record<string, unknown>) {
  fs.mkdirSync(path.dirname(SETUPS_FILE), { recursive: true });
  const temporary = `${SETUPS_FILE}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(setups, null, 2)}\n`);
  fs.renameSync(temporary, SETUPS_FILE);
}

function setupStore(): Plugin {
  const handle: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (url !== "/api/setups") {
      next();
      return;
    }
    if (req.method === "GET") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(readSetups()));
      return;
    }
    if (req.method === "PUT") {
      const chunks: Buffer[] = [];
      req.on("data", (chunk: Buffer) => chunks.push(chunk));
      req.on("end", () => {
        try {
          const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            res.statusCode = 400;
            res.end("Expected a JSON object of setups");
            return;
          }
          writeSetups(parsed as Record<string, unknown>);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(readSetups()));
        } catch {
          res.statusCode = 400;
          res.end("Invalid JSON");
        }
      });
      return;
    }
    res.statusCode = 405;
    res.end();
  };
  return {
    name: "reactor-slice-setup-store",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [react(), setupStore()],
  server: {
    host: true,
    port: 3001,
    strictPort: true,
  },
  build: {
    outDir: "build",
  },
});
