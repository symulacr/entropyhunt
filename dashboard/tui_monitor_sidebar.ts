import { bold as withBold, fg as withFg, t, type TextRenderable } from "@opentui/core";

import type { FocusPanel, ViewState } from "./tui_monitor_model.ts";
import { buildDetailSummary } from "./tui_monitor_presenters.ts";
import { renderDroneRow, renderEventRow } from "./tui_sidebar.ts";
import { PANEL_THEME } from "./tui_theme.ts";

function fillRows<T>(
  rows: TextRenderable[],
  items: readonly T[],
  render: (item: T, index: number) => string | ReturnType<typeof t>,
) {
  for (let index = 0; index < rows.length; index += 1) {
    const item = items[index];
    rows[index]!.content = item ? render(item, index) : "";
  }
}

export function syncMonitorSidebar(args: {
  state: ViewState;
  focusedPanel: FocusPanel;
  cursorX: number;
  cursorY: number;
  selectedDrone: number;
  selectedEvent: number;
  eventRowCount: number;
  detailTitle: TextRenderable;
  detailLine1: TextRenderable;
  detailLine2: TextRenderable;
  droneRows: TextRenderable[];
  eventRows: TextRenderable[];
}) {
  const {
    state,
    focusedPanel,
    cursorX,
    cursorY,
    selectedDrone,
    selectedEvent,
    eventRowCount,
    detailTitle,
    detailLine1,
    detailLine2,
    droneRows,
    eventRows,
  } = args;

  const [detailA, detailB, detailC] = buildDetailSummary(state, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent);
  detailTitle.content = t`${withFg(PANEL_THEME.textPrimary)(withBold(detailA))}`;
  detailLine1.content = detailB;
  detailLine2.content = detailC;

  fillRows(droneRows, state.drones, (drone, index) =>
    renderDroneRow({
      drone,
      selected: focusedPanel === "roster" && selectedDrone === index,
      focusedPanel: focusedPanel === "roster",
    }),
  );
  fillRows(eventRows, state.events, (event, index) =>
    index < eventRowCount
      ? renderEventRow({
          event,
          selected: focusedPanel === "events" && selectedEvent === index,
          focusedPanel: focusedPanel === "events",
        })
      : "",
  );
}
