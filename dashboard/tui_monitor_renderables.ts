import { BoxRenderable, TextRenderable } from "@opentui/core";

import type { DisplayMode } from "./tui_monitor_model.ts";
import { STAT_SPECS } from "./tui_monitor_stats.ts";
import { COLORS, PANEL_THEME } from "./tui_theme.ts";

type RenderContext = ConstructorParameters<typeof BoxRenderable>[0];

export type MonitorViewTab = { mode: DisplayMode; renderable: TextRenderable };

export function createMonitorViewTabs(renderer: RenderContext) {
  const box = new BoxRenderable(renderer, {
    id: "view-tabs",
    flexDirection: "row",
    gap: 1,
    backgroundColor: COLORS.headerBg,
    height: 1,
  });
  const tabs = ([
    ["view-tab-overview", "overview"],
    ["view-tab-detail", "detail"],
    ["view-tab-map", "map"],
    ["view-tab-config", "config"],
    ["view-tab-graphs", "graphs"],
  ] as const).map(([id, mode]) => ({
    mode,
    renderable: new TextRenderable(renderer, {
      id,
      content: "",
      fg: PANEL_THEME.textPrimary,
      bg: COLORS.headerBg,
      wrapMode: "none",
      truncate: true,
    }),
  }));
  for (const tab of tabs) box.add(tab.renderable);
  return { box, tabs };
}

export function createMonitorStatsRow(renderer: RenderContext) {
  const row = new BoxRenderable(renderer, {
    id: "stats-row",
    flexDirection: "row",
    gap: 1,
    backgroundColor: COLORS.headerBg,
    paddingLeft: 1,
    paddingRight: 1,
    justifyContent: "space-between",
  });
  const labels: TextRenderable[] = [];
  const values: TextRenderable[] = [];
  const cards: BoxRenderable[] = [];
  for (const spec of STAT_SPECS) {
    const card = new BoxRenderable(renderer, {
      id: `stat-${spec.key}`,
      flexGrow: spec.grow,
      border: true,
      borderColor: COLORS.border,
      backgroundColor: COLORS.headerBg,
      paddingLeft: 2,
      paddingRight: 2,
      paddingTop: 0,
      paddingBottom: 0,
      alignItems: "center",
      justifyContent: "center",
      gap: 0,
    });
    const label = new TextRenderable(renderer, {
      id: `stat-label-${spec.key}`,
      content: spec.label,
      fg: PANEL_THEME.textMuted,
      bg: COLORS.headerBg,
      wrapMode: "none",
      truncate: true,
      height: 1,
    });
    const value = new TextRenderable(renderer, {
      id: `stat-value-${spec.key}`,
      content: "",
      fg: PANEL_THEME.textPrimary,
      bg: COLORS.headerBg,
      wrapMode: "none",
      truncate: true,
      height: 1,
    });
    card.add(label);
    card.add(value);
    row.add(card);
    cards.push(card);
    labels.push(label);
    values.push(value);
  }
  const compactText = new TextRenderable(renderer, {
    id: "compact-stats",
    content: "",
    fg: PANEL_THEME.textPrimary,
    bg: COLORS.headerBg,
    wrapMode: "none",
    truncate: true,
    visible: false,
  });
  row.add(compactText);
  return { row, labels, values, cards, compactText };
}

export function createTextRows(args: {
  renderer: RenderContext;
  parent: BoxRenderable;
  count: number;
  prefix: string;
  fg: string;
  bg: string;
}) {
  const { renderer, parent, count, prefix, fg, bg } = args;
  const rows: TextRenderable[] = [];
  for (let index = 0; index < count; index += 1) {
    const row = new TextRenderable(renderer, {
      id: `${prefix}-${index}`,
      content: "",
      fg,
      bg,
      wrapMode: "none",
      truncate: true,
    });
    parent.add(row);
    rows.push(row);
  }
  return rows;
}
