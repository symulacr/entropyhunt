import { normalizeSnapshot } from "./tui_monitor_model.ts";
import { fetchMonitorSnapshot } from "./tui_monitor_io.ts";
import { showActiveShell } from "./tui_monitor_runtime.ts";
import type { MonitorContext } from "./tui_monitor_boot.ts";

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export async function runTickCycle(ctx: MonitorContext): Promise<void> {
  if (ctx.closed) return;
  const startedAt = performance.now();
  try {
    const snapshot = await fetchMonitorSnapshot(ctx.args.source);
    const state = normalizeSnapshot(snapshot, ctx.args.source, false);
    ctx.lastTickLatencyMs = performance.now() - startedAt;
    ctx.lastSuccessfulSnapshotAt = Date.now();
    if (state.survivorFound && ctx.survivorStartedAt === 0) ctx.survivorStartedAt = Date.now();

    ctx.history.coverage.push(state.coverage);
    if (ctx.history.coverage.length > 24) ctx.history.coverage.shift();
    ctx.history.uncertainty.push(state.avgEntropy);
    if (ctx.history.uncertainty.length > 24) ctx.history.uncertainty.shift();
    ctx.history.auctions.push(state.auctions);
    if (ctx.history.auctions.length > 24) ctx.history.auctions.shift();
    ctx.history.dropouts.push(state.dropouts);
    if (ctx.history.dropouts.length > 24) ctx.history.dropouts.shift();
    ctx.history.latency.push(Math.max(0, Math.round(ctx.lastTickLatencyMs)));
    if (ctx.history.latency.length > 24) ctx.history.latency.shift();

    for (const drone of state.drones) {
      const existing = ctx.history.drones[drone.id] ?? { entropy: [], searched: [] };
      existing.entropy.push(drone.entropy);
      if (existing.entropy.length > 24) existing.entropy.shift();
      existing.searched.push(drone.searchedCells);
      if (existing.searched.length > 24) existing.searched.shift();
      ctx.history.drones[drone.id] = existing;
    }

    ctx.lastGood = state;
    ctx.setWaiting(false, ctx.args.source);
    ctx.updateView(state);
  } catch (e) {
    process.stderr.write(`[tui-controller] ${e}\n`);
    ctx.spinnerIndex = (ctx.spinnerIndex + 1) % SPINNER_FRAMES.length;
    if (ctx.lastGood) {
      ctx.updateView({ ...ctx.lastGood, staleData: true });
      showActiveShell({ shell: ctx.scene.shell, waitingShell: ctx.scene.waitingShell, requestRender: ctx.requestRender });
    } else {
      ctx.setWaiting(true, ctx.args.source);
    }
  }
}
