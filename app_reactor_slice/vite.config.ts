import fs from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import type { Connect, Plugin } from "vite";
import { defineConfig } from "vite";
import { BlenderClipboardError, copyColumnsToBlender } from "./server/blenderClipboard";
import {
  isSimulationRunning,
  RimagRunnerError,
  startSimulation,
  stopSimulation,
  subscribe,
} from "./server/rimagRunner";

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

function readJsonBody(req: Connect.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown);
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function blenderClipboard(): Plugin {
  const handle: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (url !== "/api/blender-clipboard") {
      next();
      return;
    }
    if (req.method !== "POST") {
      res.statusCode = 405;
      res.end();
      return;
    }
    void readJsonBody(req)
      .then(async (body) => {
        const record = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
        const radius = Number(record.radius);
        const height = Number(record.height);
        const centers = Array.isArray(record.centers)
          ? record.centers.map((point) => {
              const pair = point as [unknown, unknown];
              return [Number(pair[0]), Number(pair[1])] as [number, number];
            })
          : [];
        const written = await copyColumnsToBlender(radius, height, centers);
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ path: written }));
      })
      .catch((error: unknown) => {
        const message = error instanceof BlenderClipboardError ? error.message : "Could not copy the 3D model.";
        res.statusCode = 400;
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ error: message }));
      });
  };
  return {
    name: "reactor-slice-blender-clipboard",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
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

function simulationApi(): Plugin {
  const handle: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (!url?.startsWith("/api/simulation")) {
      next();
      return;
    }

    if (url === "/api/simulation/status" && req.method === "GET") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ running: isSimulationRunning() }));
      return;
    }

    if (url === "/api/simulation/stop" && req.method === "POST") {
      const stopped = stopSimulation();
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ stopped }));
      return;
    }

    if (url === "/api/simulation/stream" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      });
      res.write(`data: ${JSON.stringify({ type: "ready", running: isSimulationRunning() })}\n\n`);
      const unsubscribe = subscribe((line) => {
        res.write(`data: ${JSON.stringify({ type: "log", line })}\n\n`);
        if (line.startsWith("[runner] done exit=")) {
          const code = Number(line.slice("[runner] done exit=".length));
          res.write(`data: ${JSON.stringify({ type: "done", code: Number.isFinite(code) ? code : 1 })}\n\n`);
        }
      });
      req.on("close", () => unsubscribe());
      return;
    }

    if (url === "/api/simulation/start" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          startSimulation(body);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ ok: true, running: true }));
        })
        .catch((error: unknown) => {
          const message =
            error instanceof RimagRunnerError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not start the simulation.";
          res.statusCode = error instanceof RimagRunnerError ? 409 : 400;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        });
      return;
    }

    res.statusCode = 405;
    res.end();
  };

  return {
    name: "reactor-slice-simulation",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [react(), setupStore(), blenderClipboard(), simulationApi()],
  server: {
    host: true,
    port: 3001,
    strictPort: true,
  },
  build: {
    outDir: "build",
  },
});
