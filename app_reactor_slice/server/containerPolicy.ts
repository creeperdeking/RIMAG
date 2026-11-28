/**
 * A weight-window file belongs to this pass only when it was written after the
 * pass's container was spawned. A seed written earlier must not turn a SIGKILL
 * of the following refine into a successful pass.
 */
export function weightWindowWriteBelongsToPass(metaMtimeMs: number, passStartedAtMs: number): boolean {
  return passStartedAtMs > 0 && Number.isFinite(metaMtimeMs) && metaMtimeMs >= passStartedAtMs;
}

/** Names a sweep must leave running: the live container and the one compose is starting. */
export function protectedContainerNames(input: {
  live: string;
  pending: string;
  queuedRunning?: string | null;
}): string[] {
  const names = [input.live, input.pending, input.queuedRunning ?? ""];
  return [...new Set(names.map((name) => name.trim()).filter((name) => name.length > 0))];
}

export function containersToStop(running: string[], protect: readonly string[]): string[] {
  const keep = new Set(protect);
  return running.filter((name) => name.length > 0 && !keep.has(name));
}

export type TrackedContainerAction = "keep" | "refollow" | "finish";

/**
 * What to do with a run the queue still calls running.
 * A container that is still being created (pending name, not in `docker ps` yet)
 * must be left alone. A live log stream is left alone too: its close handler
 * finishes the pass. A stream that died while the container is up has to be
 * followed again, or the next autorefine pass never starts. A known container
 * that has left `docker ps` with nobody attached has already exited.
 */
export function trackedContainerAction(input: {
  running: boolean;
  containerName: string;
  pendingContainerName: string;
  listed: readonly string[];
  childAlive: boolean;
}): TrackedContainerAction {
  if (!input.running || !input.containerName || input.pendingContainerName) return "keep";
  if (input.childAlive) return "keep";
  return input.listed.includes(input.containerName) ? "refollow" : "finish";
}
