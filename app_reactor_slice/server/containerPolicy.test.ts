import assert from "node:assert/strict";
import test from "node:test";
import {
  containersToStop,
  protectedContainerNames,
  weightWindowWriteBelongsToPass,
} from "./containerPolicy.ts";

test("a seed weight-window file does not cover a later refine pass", () => {
  const seedWrite = Date.parse("2026-11-25T00:09:15Z");
  const passStart = Date.parse("2026-11-25T00:09:29Z");
  assert.equal(weightWindowWriteBelongsToPass(seedWrite, passStart), false);
});

test("a weight-window file written during the pass covers a teardown SIGKILL", () => {
  const passStart = Date.parse("2026-11-25T00:09:29Z");
  const written = passStart + 60_000;
  assert.equal(weightWindowWriteBelongsToPass(written, passStart), true);
  assert.equal(weightWindowWriteBelongsToPass(written, 0), false);
});

test("the sweep keeps the live container and the one still being created", () => {
  const protect = protectedContainerNames({
    live: "rimag-app-sim-live",
    pending: "rimag-app-sim-next",
    queuedRunning: "rimag-app-sim-live",
  });
  assert.deepEqual(
    containersToStop(
      ["rimag-app-sim-live", "rimag-app-sim-stray", "rimag-app-sim-next"],
      protect,
    ),
    ["rimag-app-sim-stray"],
  );
});
