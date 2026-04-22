import { cleanupTimelines, detachAnimationEngine } from "./tui_monitor_animations.ts";
import type { MonitorContext } from "./tui_monitor_boot.ts";

export function createShutdown(ctx: MonitorContext): () => void {
  return () => {
    if (ctx.closed) return;
    ctx.closed = true;
    if (ctx.timers.timer) {
      clearTimeout(ctx.timers.timer);
      ctx.timers.timer = null;
    }
    if (ctx.timers.orphanWatchTimer) {
      clearInterval(ctx.timers.orphanWatchTimer);
      ctx.timers.orphanWatchTimer = null;
    }
    if (ctx.timers.controlStatusTimer) {
      clearTimeout(ctx.timers.controlStatusTimer);
      ctx.timers.controlStatusTimer = null;
    }
    ctx.renderer.off("resize", ctx.handleResize);
    process.off("SIGTERM", ctx.shutdown);
    process.off("SIGINT", ctx.shutdown);
    cleanupTimelines(ctx.timelines);
    detachAnimationEngine();
    ctx.renderer.destroy();
  };
}
