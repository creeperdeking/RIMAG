import fs from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import type { Connect, Plugin } from "vite";
import { defineConfig } from "vite";
import { BlenderClipboardError, copyColumnsToBlender } from "./server/blenderClipboard";
import {
  GeometryPlotError,
  geometryStatus,
  plotGeometrySlice,
} from "./server/geometryPlot";
import {
  appendSimulation,
  clearWeightWindows,
  adoptRunningSimulation,
  getSimulationQueue,
  isQueuePaused,
  isSimulationRunning,
  readQueueItem,
  removeQueuedSimulation,
  reorderQueuedSimulations,
  RimagRunnerError,
  setQueuePaused,
  startSimulation,
  stopSimulation,
  subscribe,
  subscribeQueue,
  updateQueuedSimulation,
  weightWindowsStatus,
} from "./server/rimagRunner";
import { liveSnapshot, startLive, stopLive, subscribeLive, updateLiveControl } from "./server/rimaelLive";
import { RimaelBusyError, RimaelRunnerError, runRimaelFuelTemperature, type RimaelRunOptions } from "./server/rimaelRunner";

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
      void adoptRunningSimulation().then(() => {
        if (!res.writableEnded) {
          res.end(
            JSON.stringify({
              running: isSimulationRunning(),
              queuePaused: isQueuePaused(),
              queue: getSimulationQueue(),
            }),
          );
        }
      });
      return;
    }

    if (url === "/api/simulation/queue" && req.method === "GET") {
      res.setHeader("Content-Type", "application/json");
      void adoptRunningSimulation().then(() => {
        if (!res.writableEnded) res.end(JSON.stringify(getSimulationQueue()));
      });
      return;
    }

    if (url === "/api/simulation/queue/reorder" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          const ids = (body as { ids?: unknown }).ids;
          if (!Array.isArray(ids) || !ids.every((id) => typeof id === "string")) {
            throw new RimagRunnerError("Body must be { ids: string[] }.");
          }
          const queue = reorderQueuedSimulations(ids);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(queue));
        })
        .catch((error: unknown) => {
          const message =
            error instanceof RimagRunnerError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not reorder the queue.";
          res.statusCode = error instanceof RimagRunnerError ? 409 : 400;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        });
      return;
    }

    if (url === "/api/simulation/queue/pause" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          const paused = Boolean((body as { paused?: unknown }).paused);
          const result = setQueuePaused(paused);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ ...result, queue: getSimulationQueue() }));
        })
        .catch((error: unknown) => {
          const message = error instanceof Error ? error.message : "Could not update queue pause.";
          res.statusCode = 400;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        });
      return;
    }

    const queueItemMatch = url?.match(/^\/api\/simulation\/queue\/([^/]+)$/);
    if (queueItemMatch) {
      const id = decodeURIComponent(queueItemMatch[1]);
      if (req.method === "GET") {
        const item = readQueueItem(id);
        res.setHeader("Content-Type", "application/json");
        if (!item) {
          res.statusCode = 404;
          res.end(JSON.stringify({ error: "Queue item not found." }));
          return;
        }
        res.end(JSON.stringify(item));
        return;
      }
      if (req.method === "DELETE") {
        try {
          const queue = removeQueuedSimulation(id);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(queue));
        } catch (error: unknown) {
          const message =
            error instanceof RimagRunnerError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not remove the queued run.";
          res.statusCode = error instanceof RimagRunnerError ? 409 : 400;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        }
        return;
      }
      if (req.method === "PUT") {
        void readJsonBody(req)
          .then((body) => {
            const item = updateQueuedSimulation(id, body);
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true, item, queue: getSimulationQueue() }));
          })
          .catch((error: unknown) => {
            const message =
              error instanceof RimagRunnerError
                ? error.message
                : error instanceof Error
                  ? error.message
                  : "Could not update the queued run.";
            res.statusCode = error instanceof RimagRunnerError ? 409 : 400;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: message }));
          });
        return;
      }
    }

    if (url === "/api/simulation/stop" && req.method === "POST") {
      const stopped = stopSimulation();
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ stopped, queuePaused: isQueuePaused() }));
      return;
    }

    if (url === "/api/simulation/stream" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        Connection: "keep-alive",
      });
      void adoptRunningSimulation().then(() => {
        if (res.writableEnded) return;
        res.write(
          `data: ${JSON.stringify({
            type: "ready",
            running: isSimulationRunning(),
            queuePaused: isQueuePaused(),
            queue: getSimulationQueue(),
          })}\n\n`,
        );
        const unsubscribeLog = subscribe(({ at, line }) => {
          res.write(`data: ${JSON.stringify({ type: "log", line, at })}\n\n`);
          if (line.startsWith("[runner] done exit=")) {
            const code = Number(line.slice("[runner] done exit=".length));
            res.write(
              `data: ${JSON.stringify({
                type: "done",
                code: Number.isFinite(code) ? code : 1,
                queue: getSimulationQueue(),
              })}\n\n`,
            );
          }
        });
        const unsubscribeQueue = subscribeQueue((queue) => {
          res.write(`data: ${JSON.stringify({ type: "queue", queue })}\n\n`);
        });
        req.on("close", () => {
          unsubscribeLog();
          unsubscribeQueue();
        });
      });
      return;
    }

    if (url === "/api/simulation/start" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          startSimulation(body);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ ok: true, running: true, queue: getSimulationQueue() }));
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

    if (url === "/api/simulation/append" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          const item = appendSimulation(body);
          res.setHeader("Content-Type", "application/json");
          res.end(
            JSON.stringify({
              ok: true,
              item,
              running: isSimulationRunning(),
              queue: getSimulationQueue(),
            }),
          );
        })
        .catch((error: unknown) => {
          const message =
            error instanceof RimagRunnerError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not append the simulation.";
          res.statusCode = error instanceof RimagRunnerError ? 409 : 400;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        });
      return;
    }

    if (url === "/api/simulation/weight-windows" && req.method === "GET") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(weightWindowsStatus()));
      return;
    }

    if (url === "/api/simulation/weight-windows" && req.method === "DELETE") {
      try {
        const removed = clearWeightWindows();
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ ok: true, removed, ...weightWindowsStatus() }));
      } catch (error: unknown) {
        const message =
          error instanceof RimagRunnerError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Could not clear weight windows.";
        res.statusCode = error instanceof RimagRunnerError ? 409 : 500;
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ error: message }));
      }
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

function geometryApi(): Plugin {
  const handle: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (!url?.startsWith("/api/geometry")) {
      next();
      return;
    }

    if (url === "/api/geometry/status" && req.method === "GET") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(geometryStatus()));
      return;
    }

    if (url === "/api/geometry/plot" && req.method === "POST") {
      void readJsonBody(req)
        .then(async (body) => {
          const pngPath = await plotGeometrySlice(body);
          const data = fs.readFileSync(pngPath);
          res.statusCode = 200;
          res.setHeader("Content-Type", "image/png");
          res.setHeader("Cache-Control", "no-store");
          res.end(data);
        })
        .catch((error: unknown) => {
          const message =
            error instanceof GeometryPlotError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not plot geometry.";
          const status = error instanceof GeometryPlotError ? error.status : 400;
          res.statusCode = status;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: message }));
        });
      return;
    }

    res.statusCode = 405;
    res.end();
  };

  return {
    name: "reactor-slice-geometry-plot",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

function rimaelOptions(body: unknown): { options: RimaelRunOptions; record: Record<string, unknown> } {
  const record =
    body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
  const num = (key: string): number | undefined => {
    const raw = record[key];
    const value = typeof raw === "number" ? raw : Number(raw);
    return Number.isFinite(value) ? value : undefined;
  };
  return {
    record,
    options: {
      fuelTempC: num("fuel_temp_c"),
      fuelEmissivity: num("fuel_emissivity"),
      diskEmissivity: num("disk_emissivity"),
      diskThicknessCm: num("disk_thickness_cm"),
      diskAreaM2: num("disk_area_m2"),
      fuelThicknessCm: num("fuel_thickness_cm"),
      fuelAreaM2: num("fuel_area_m2"),
      fuelArcFrac: num("fuel_arc_frac"),
      tpvArcFrac: num("tpv_arc_frac"),
      shield1ArcFrac: num("shield1_arc_frac"),
      shield2ArcFrac: num("shield2_arc_frac"),
      fuelHeatingPowerW: num("fuel_heating_power_w"),
      shellEmissivity: num("shell_emissivity"),
      fuelGapCm: num("fuel_gap_cm"),
      tpvGapCm: num("tpv_gap_cm"),
      tpvAreaM2: num("tpv_area_m2"),
      tpvCellIndex: num("tpv_cell_index"),
      reflectorAreaM2: num("reflector_area_m2"),
      moderatorAreaM2: num("moderator_area_m2"),
      absorberAreaM2: num("absorber_area_m2"),
      reflectorThicknessCm: num("reflector_thickness_cm"),
      moderatorThicknessCm: num("moderator_thickness_cm"),
      absorberThicknessCm: num("absorber_thickness_cm"),
      runTimeMin: num("run_time_min"),
      diskRps: num("disk_rps"),
    },
  };
}

function rimaelError(error: unknown, fallback: string): { status: number; message: string } {
  const message =
    error instanceof RimaelRunnerError
      ? error.message
      : error instanceof Error
        ? error.message
        : fallback;
  return { status: error instanceof RimaelBusyError ? 409 : 500, message };
}

function rimaelApi(): Plugin {
  const handle: Connect.NextHandleFunction = (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (!url?.startsWith("/api/rimael")) {
      next();
      return;
    }

    if (url === "/api/rimael/live/stream" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        // Caddy compresses responses when the browser sends Accept-Encoding: gzip.
        // The encoder holds this stream until a gzip block fills, so EventSource
        // never fires and the disk stays still. identity makes Caddy leave it alone.
        "Content-Encoding": "identity",
        "X-Accel-Buffering": "no",
        Connection: "keep-alive",
      });
      const snap = liveSnapshot();
      const send = (event: unknown) => {
        if (!res.writableEnded) res.write(`data: ${JSON.stringify(event)}\n\n`);
      };
      send({ type: "ready", running: snap.running, message: snap.message, history: snap.history });
      const unsubscribe = subscribeLive((event) => send(event));
      req.on("close", () => unsubscribe());
      return;
    }

    if (url === "/api/rimael/live/control" && req.method === "POST") {
      void readJsonBody(req)
        .then((body) => {
          const { record } = rimaelOptions(body);
          const num = (key: string): number | undefined => {
            const value = Number(record[key]);
            return Number.isFinite(value) ? value : undefined;
          };
          updateLiveControl({ powerW: num("power_w"), rps: num("disk_rps"), scale: num("time_scale") });
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ ok: true, ...liveSnapshot(), history: undefined }));
        })
        .catch((error: unknown) => {
          const parsed = rimaelError(error, "Could not update the live control.");
          res.statusCode = parsed.status;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: parsed.message }));
        });
      return;
    }

    if (url === "/api/rimael/live/stop" && req.method === "POST") {
      stopLive();
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ ok: true, running: false }));
      return;
    }

    if (url === "/api/rimael/live/start" && req.method === "POST") {
      void readJsonBody(req)
        .then(async (body) => {
          const { options, record } = rimaelOptions(body);
          const powerW = Number(record.power_w);
          const rps = Number(record.disk_rps);
          const scale = Number(record.time_scale);
          const running = await startLive(options, {
            powerW: Number.isFinite(powerW) ? powerW : options.fuelHeatingPowerW ?? 0,
            rps: Number.isFinite(rps) ? rps : 0.2,
            scale: Number.isFinite(scale) ? scale : 1,
          });
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ ok: running, running }));
        })
        .catch((error: unknown) => {
          const parsed = rimaelError(error, "Could not start the live Modelica session.");
          res.statusCode = parsed.status;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: parsed.message }));
        });
      return;
    }

    if (url === "/api/rimael/run" && req.method === "POST") {
      void readJsonBody(req)
        .then(async (body) => {
          const { options } = rimaelOptions(body);
          const trace = await runRimaelFuelTemperature(options);
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(trace));
        })
        .catch((error: unknown) => {
          const parsed = rimaelError(error, "Could not run the RIMAEL Modelica simulation.");
          res.statusCode = parsed.status;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ error: parsed.message }));
        });
      return;
    }

    res.statusCode = 405;
    res.end();
  };

  return {
    name: "reactor-slice-rimael",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [react(), setupStore(), blenderClipboard(), simulationApi(), geometryApi(), rimaelApi()],
  server: {
    // Bound locally; Caddy terminates HTTPS on theca.fr and proxies here.
    host: "127.0.0.1",
    port: 8080,
    strictPort: true,
    allowedHosts: ["theca.fr"],
    hmr: {
      protocol: "wss",
      host: "theca.fr",
      clientPort: 443,
    },
  },
  build: {
    outDir: "build",
  },
});
