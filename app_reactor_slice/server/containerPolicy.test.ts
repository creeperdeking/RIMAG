import assert from "node:assert/strict";
import test from "node:test";
import {
  containersToStop,
  protectedContainerNames,
  trackedContainerAction,
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

test("a finished container with no log stream ends the pass", () => {
  assert.equal(
    trackedContainerAction({
      running: true,
      containerName: "rimag-app-sim-mwvxk5gn-1",
      pendingContainerName: "",
      listed: [],
      childAlive: false,
    }),
    "finish",
  );
});

test("a live container whose log stream died is followed again", () => {
  assert.equal(
    trackedContainerAction({
      running: true,
      containerName: "rimag-app-sim-mwvxk5gn-1",
      pendingContainerName: "",
      listed: ["rimag-app-sim-mwvxk5gn-1"],
      childAlive: false,
    }),
    "refollow",
  );
});

test("a container that is still starting, or still has a log stream, is left alone", () => {
  assert.equal(
    trackedContainerAction({
      running: true,
      containerName: "",
      pendingContainerName: "rimag-app-sim-next",
      listed: [],
      childAlive: false,
    }),
    "keep",
  );
  assert.equal(
    trackedContainerAction({
      running: true,
      containerName: "rimag-app-sim-live",
      pendingContainerName: "",
      listed: ["rimag-app-sim-live"],
      childAlive: true,
    }),
    "keep",
  );
  assert.equal(
    trackedContainerAction({
      running: false,
      containerName: "rimag-app-sim-live",
      pendingContainerName: "",
      listed: [],
      childAlive: false,
    }),
    "keep",
  );
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
