import { createCliRenderer } from "@opentui/core";

import { FOCUS_THEME } from "./tui_theme.ts";
import {
  type DisplayMode,
  type FocusPanel,
  type ViewState,
  computeLayoutMetrics,
  normalizeSnapshot,
} from "./tui_monitor_model.ts";
import { handleMonitorKeyDown } from "./tui_monitor_input.ts";
import { hasLostControllingParent, hasLostSource, hasLostWatchedParent, showActiveShell, syncWaitingShell } from "./tui_monitor_runtime.ts";
import { bindMonitorMouseInteractions } from "./tui_monitor_interactions.ts";
import { createMonitorScene } from "./tui_monitor_scene.ts";
import { fetchMonitorSnapshot, postMonitorControl, type MonitorArgs } from "./tui_monitor_io.ts";
import { syncMonitorFrame } from "./tui_monitor_sync.ts";
import { type MonitorPanelBinding } from "./tui_monitor_focus.ts";
import type { MonitorHistory } from "./tui_monitor_aux.ts";
import {
  attachAnimationEngine,
  detachAnimationEngine,
  createTargetPulseTimeline,
  createFooterHeartbeatTimeline,
  cleanupTimelines,
} from "./tui_monitor_animations.ts";
import type { Timeline } from "@opentui/core";

import { bootMonitor } from "./tui_monitor_boot.ts";
import { runTickCycle } from "./tui_monitor_tick.ts";
import { createShutdown } from "./tui_monitor_shutdown.ts";

export async function runMonitorController(args: MonitorArgs) {
  const ctx = await bootMonitor(args);

  await runTickCycle(ctx);

  ctx.timers.orphanWatchTimer = setInterval(() => {
    if (ctx.closed) return;
    if (hasLostWatchedParent(Number.isFinite(ctx.watchedParentPid) ? ctx.watchedParentPid : null, ctx.isPidAlive)
      || hasLostControllingParent(ctx.initialParentPid, process.ppid)
      || hasLostSource(ctx.lastSuccessfulSnapshotAt, Date.now(), ctx.sourceLossExitMs)) {
      ctx.shutdown();
    }
  }, 1000);

  process.on("SIGTERM", ctx.shutdown);
  process.on("SIGINT", ctx.shutdown);

  const scheduleTick = () => {
    ctx.timers.timer = setTimeout(async () => {
      if (ctx.closed) return;
      try {
        await runTickCycle(ctx);
      } catch (e) {
        process.stderr.write(`[tui-controller] ${e}\n`);
      }
      if (!ctx.closed) {
        scheduleTick();
      }
    }, args.intervalMs);
  };

  scheduleTick();
}
